#!/usr/bin/env python3
"""rca-runner: incident webhook -> headless ``/sre-plugin:rca`` -> note on the incident.

The front half of the loop lives in the pipeline (``utils/alerting.py`` opens an
incident when a task fails). This service is the back half:

    POST /webhook/pagerduty   PagerDuty v3 webhook (``incident.triggered``), HMAC-verified
    POST /webhook/keep        Keep workflow ``rca-on-incident`` (incident created), token-verified
    POST /webhook/generic     a raw alert JSON (curl demos, smoke tests), token-verified
    GET  /healthz             liveness
    GET  /runs                journal of runs (``outputs/rca/v1/runs.jsonl``)

For every accepted incident it:

1. normalises the payload into one alert (dag_id, run_id, task_id, try_number,
   ds, env, message + incident_id/url/provider/dedup_key);
2. de-duplicates on ``dag_id/run_id`` (in flight or already journaled -> 202 duplicate);
3. writes ``inputs/alerts/v1/ALERT-<id>.json``;
4. runs ``claude -p "/sre-plugin:rca inputs/alerts/v1/ALERT-<id>.json"`` headless
   with the plugin loaded from ``--plugin-dir`` (its read-only hook applies);
5. parses the skill's fixed-prefix lines (``Root cause:``, ``Owner:``, ``Report:``,
   ``Self-check:``) from the JSON ``result``;
6. posts a note on the incident (PagerDuty notes API / Keep comment). It never
   acknowledges or resolves the incident, and it posts a note even when the RCA
   run failed, so the on-call engineer always learns what happened.

Standard library only, like the rest of sre-plugin. Verified against Keep
0.54.3 and Claude Code 2.1.286 (2026-10-15); see service/README.md.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import logging
import os
import queue
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

log = logging.getLogger("rca-runner")

ALLOWED_TOOLS = "Bash,Read,Write,Edit,Grep,Glob,Skill"
RESULT_LINE_PREFIXES = (
    "RESOLVED TARGET:",
    "Root cause:",
    "Blast radius:",
    "Owner:",
    "Report:",
    "Self-check:",
    "Not observed:",
)


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
@dataclass
class RunnerConfig:
    workspace_root: Path
    port: int = int(os.environ.get("RCA_RUNNER_PORT", "8090"))
    plugin_dir: Path | None = None
    claude_bin: str = os.environ.get("CLAUDE_BIN", "claude")
    max_budget_usd: float = float(os.environ.get("RCA_MAX_BUDGET_USD", "5"))
    max_turns: int = int(os.environ.get("RCA_MAX_TURNS", "60"))
    timeout_s: int = int(os.environ.get("RCA_TIMEOUT_S", "1800"))
    extra_claude_args: list[str] = field(
        default_factory=lambda: os.environ.get("RCA_CLAUDE_EXTRA_ARGS", "").split()
    )
    webhook_token: str = os.environ.get("RCA_WEBHOOK_TOKEN", "")
    pagerduty_webhook_secret: str = os.environ.get("PAGERDUTY_WEBHOOK_SECRET", "")
    pagerduty_api_key: str = os.environ.get("PAGERDUTY_API_KEY", "")
    pagerduty_from_email: str = os.environ.get("PAGERDUTY_FROM_EMAIL", "")
    pagerduty_api_url: str = os.environ.get("PAGERDUTY_API_URL", "https://api.pagerduty.com")
    keep_api_url: str = os.environ.get("KEEP_API_URL", "http://localhost:8085")
    keep_api_key: str = os.environ.get("KEEP_API_KEY", "keep-dev-key")
    keep_ui_url: str = os.environ.get("KEEP_UI_URL", "http://localhost:3010")
    env: str = os.environ.get("PATIENT360_ENV", "DEV").upper()
    dry_run: bool = False
    alerts_dir: Path | None = None
    journal: Path | None = None

    def __post_init__(self) -> None:
        self.workspace_root = Path(self.workspace_root).resolve()
        self.plugin_dir = Path(self.plugin_dir or self.workspace_root / "sre-plugin")
        self.alerts_dir = Path(self.alerts_dir or self.workspace_root / "inputs" / "alerts" / "v1")
        self.journal = Path(
            self.journal or self.workspace_root / "outputs" / "rca" / "v1" / "runs.jsonl"
        )


# ---------------------------------------------------------------------------
# HTTP helpers + incident clients
# ---------------------------------------------------------------------------
def request_json(
    method: str,
    url: str,
    body: Any = None,
    headers: dict[str, str] | None = None,
    timeout: int = 15,
) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Content-Type": "application/json", "Accept": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        raw = resp.read()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw.decode(errors="replace")}


class KeepIncidentClient:
    name = "keep"

    def __init__(self, api_url: str, api_key: str, ui_url: str):
        self.api_url = api_url.rstrip("/")
        self.ui_url = ui_url.rstrip("/")
        self.headers = {"X-API-KEY": api_key} if api_key else {}

    def incident_alerts(self, incident_id: str) -> list[dict[str, Any]]:
        d = request_json(
            "GET", f"{self.api_url}/incidents/{incident_id}/alerts", headers=self.headers
        )
        return d.get("items", d) if isinstance(d, dict) else d

    def incident_url(self, incident_id: str) -> str:
        return f"{self.ui_url}/incidents/{incident_id}"

    def add_note(self, incident_id: str, text: str) -> None:
        # Verified on keep-api 0.54.3: the comment endpoint needs the current status too.
        request_json(
            "POST",
            f"{self.api_url}/incidents/{incident_id}/comment",
            {"comment": text, "status": "firing"},
            self.headers,
        )


class PagerDutyIncidentClient:
    name = "pagerduty"

    def __init__(self, api_url: str, api_key: str, from_email: str):
        self.api_url = api_url.rstrip("/")
        self.headers = {
            "Authorization": f"Token token={api_key}",
            "From": from_email,
            "Content-Type": "application/json",
            "Accept": "application/vnd.pagerduty+json;version=2",
        }

    def incident_alerts(self, incident_id: str) -> list[dict[str, Any]]:
        d = request_json(
            "GET", f"{self.api_url}/incidents/{incident_id}/alerts", headers=self.headers
        )
        return d.get("alerts", []) if isinstance(d, dict) else []

    def add_note(self, incident_id: str, text: str) -> None:
        request_json(
            "POST",
            f"{self.api_url}/incidents/{incident_id}/notes",
            {"note": {"content": text}},
            self.headers,
        )


class NullIncidentClient:
    name = "none"

    def incident_alerts(self, incident_id: str) -> list[dict[str, Any]]:
        return []

    def add_note(self, incident_id: str, text: str) -> None:
        log.info("note (no incident client): %s", text.replace("\n", " | ")[:300])


# ---------------------------------------------------------------------------
# Incoming incident normalisation
# ---------------------------------------------------------------------------
@dataclass
class IncomingIncident:
    provider: str
    incident_id: str | None
    incident_url: str | None
    title: str
    alert: dict[str, Any]

    @property
    def dedup_key(self) -> str:
        return (
            self.alert.get("dedup_key") or f"{self.alert.get('dag_id')}/{self.alert.get('run_id')}"
        )


ALERT_KEYS = (
    "dag_id",
    "run_id",
    "task_id",
    "try_number",
    "ds",
    "env",
    "message",
    "markers",
    "alert_id",
    "fired_at",
    "source",
)


def _alert_from_details(details: dict[str, Any]) -> dict[str, Any]:
    alert = {k: details[k] for k in ALERT_KEYS if k in details and details[k] not in (None, "")}
    if "try_number" in alert:
        try:
            alert["try_number"] = int(alert["try_number"])
        except (TypeError, ValueError):
            alert.pop("try_number")
    return alert


def normalise_generic(payload: dict[str, Any]) -> IncomingIncident:
    """``payload`` is an alert (dag_id, run_id, task_id, message, ...) + optional incident_*."""
    alert = _alert_from_details(payload)
    if not alert.get("dag_id") or not alert.get("task_id"):
        raise ValueError("generic payload needs dag_id and task_id")
    alert.setdefault("run_id", f"manual__{utc_now_iso()}")
    alert.setdefault("message", payload.get("title") or "task failed")
    if payload.get("dedup_key"):
        alert["dedup_key"] = payload["dedup_key"]
    return IncomingIncident(
        payload.get("incident_provider") or "generic",
        payload.get("incident_id"),
        payload.get("incident_url"),
        payload.get("title") or f"{alert['dag_id']}/{alert['task_id']}",
        alert,
    )


def normalise_keep(
    payload: dict[str, Any],
    client: KeepIncidentClient | NullIncidentClient,
    retries: int = 10,
    delay_s: float = 1.0,
) -> IncomingIncident:
    """Keep posts the incident at creation time, BEFORE the alert is linked; poll for the alert."""
    inc = payload.get("incident")
    if isinstance(inc, str):
        try:
            inc = json.loads(inc)
        except json.JSONDecodeError:
            inc = {}
    inc = inc or {}
    incident_id = payload.get("incident_id") or inc.get("id")
    if not incident_id:
        raise ValueError("keep payload has no incident id")
    title = (
        payload.get("incident_name")
        or inc.get("user_generated_name")
        or f"keep incident {incident_id}"
    )
    alerts: list[dict[str, Any]] = []
    for _ in range(max(1, retries)):
        alerts = client.incident_alerts(incident_id)
        if alerts:
            break
        time.sleep(delay_s)
    if not alerts:
        raise ValueError(f"keep incident {incident_id} has no linked alert after {retries} tries")
    a = alerts[0]
    details = dict(a.get("labels") or {})
    details.setdefault("message", a.get("description") or a.get("name") or title)
    details.setdefault("alert_id", a.get("id"))
    details.setdefault("fired_at", a.get("lastReceived"))
    alert = _alert_from_details(details)
    alert["dedup_key"] = a.get("fingerprint") or f"{alert.get('dag_id')}/{alert.get('run_id')}"
    if not alert.get("dag_id") or not alert.get("task_id"):
        raise ValueError(f"keep alert {a.get('id')} lacks dag_id/task_id labels")
    url = getattr(client, "incident_url", lambda i: None)(incident_id)
    return IncomingIncident("keep", str(incident_id), url, title, alert)


def normalise_pagerduty(
    payload: dict[str, Any], client: PagerDutyIncidentClient | NullIncidentClient
) -> IncomingIncident | None:
    """v3 webhook envelope; only ``incident.triggered`` is acted on (None for other events)."""
    event = payload.get("event") or {}
    if event.get("event_type") != "incident.triggered":
        return None
    data = event.get("data") or {}
    incident_id = data.get("id")
    if not incident_id:
        raise ValueError("pagerduty payload has no incident id")
    alerts = client.incident_alerts(incident_id)
    details: dict[str, Any] = {}
    for a in alerts:
        body = a.get("body") or {}
        if isinstance(body.get("details"), dict) and body["details"].get("dag_id"):
            details = body["details"]
            break
    if not details:
        raise ValueError(
            f"pagerduty incident {incident_id} carries no alert with custom_details.dag_id"
        )
    alert = _alert_from_details(details)
    alert["dedup_key"] = (
        alerts[0].get("alert_key") if alerts else None
    ) or f"{alert.get('dag_id')}/{alert.get('run_id')}"
    return IncomingIncident(
        "pagerduty",
        str(incident_id),
        data.get("html_url"),
        data.get("title") or alert["dag_id"],
        alert,
    )


# ---------------------------------------------------------------------------
# Signature / token verification
# ---------------------------------------------------------------------------
def verify_pagerduty_signature(raw_body: bytes, header: str | None, secret: str) -> bool:
    if not secret or not header:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    for part in header.split(","):
        part = part.strip()
        if part.startswith("v1=") and hmac.compare_digest(part[3:], expected):
            return True
    return False


def verify_token(header: str | None, token: str) -> bool:
    return bool(token) and header is not None and hmac.compare_digest(header, token)


# ---------------------------------------------------------------------------
# Result parsing
# ---------------------------------------------------------------------------
def parse_skill_result(text: str) -> dict[str, str]:
    """Pick the fixed-prefix lines the skill prints (SKILL.md 'Output Format')."""
    out: dict[str, str] = {}
    for line in (text or "").splitlines():
        line = line.strip().strip("`").strip()
        for prefix in RESULT_LINE_PREFIXES:
            if line.startswith(prefix):
                key = prefix.rstrip(":").lower().replace(" ", "_")
                out.setdefault(key, line[len(prefix) :].strip())
    return out


def note_text(run: dict[str, Any]) -> str:
    """The note posted on the incident."""
    lines = [f"[sre-plugin:rca] {run['status'].upper()} — {run.get('alert_id', '')}"]
    parsed = run.get("parsed") or {}
    if run["status"] == "ok":
        lines += [
            f"Root cause: {parsed.get('root_cause', 'n/a')}",
            f"Owner: {parsed.get('owner', 'n/a')}",
            f"Blast radius: {parsed.get('blast_radius', 'n/a')}",
            f"Self-check: {parsed.get('self-check', parsed.get('self_check', 'n/a'))}",
            f"Report: {parsed.get('report', 'n/a')}",
        ]
    else:
        lines += [
            f"RCA did not complete: {run.get('error', 'unknown error')}",
            "Run it manually: /sre-plugin:rca " + str(run.get("alert_path", "latest")),
        ]
    lines.append(
        f"Cost: ${run.get('cost_usd', 0):.2f} · {run.get('duration_s', 0)}s"
        f" · session {run.get('session_id', '-')}"
    )
    lines.append(
        "This note was written by the automated RCA runner; nothing on the stack was changed."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------
class RcaRunner:
    def __init__(self, cfg: RunnerConfig):
        self.cfg = cfg
        self.queue: queue.Queue[IncomingIncident] = queue.Queue()
        self.in_flight: set[str] = set()
        self.lock = threading.Lock()
        self.keep = KeepIncidentClient(cfg.keep_api_url, cfg.keep_api_key, cfg.keep_ui_url)
        self.pagerduty = (
            PagerDutyIncidentClient(
                cfg.pagerduty_api_url, cfg.pagerduty_api_key, cfg.pagerduty_from_email
            )
            if cfg.pagerduty_api_key
            else NullIncidentClient()
        )
        self.worker = threading.Thread(target=self._worker, name="rca-worker", daemon=True)

    # --- journal ------------------------------------------------------------
    def journaled_keys(self) -> set[str]:
        keys: set[str] = set()
        if self.cfg.journal.is_file():
            for line in self.cfg.journal.read_text().splitlines():
                try:
                    keys.add(json.loads(line).get("dedup_key", ""))
                except json.JSONDecodeError:
                    continue
        return keys

    def runs(self) -> list[dict[str, Any]]:
        if not self.cfg.journal.is_file():
            return []
        out = []
        for line in self.cfg.journal.read_text().splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def _journal(self, run: dict[str, Any]) -> None:
        self.cfg.journal.parent.mkdir(parents=True, exist_ok=True)
        with self.cfg.journal.open("a") as fh:
            fh.write(json.dumps(run, default=str) + "\n")

    # --- intake ---------------------------------------------------------------
    def submit(self, incident: IncomingIncident, force: bool = False) -> dict[str, Any]:
        key = incident.dedup_key
        with self.lock:
            if not force and (key in self.in_flight or key in self.journaled_keys()):
                return {"status": "duplicate", "dedup_key": key}
            self.in_flight.add(key)
        self.queue.put(incident)
        return {"status": "queued", "dedup_key": key, "incident_id": incident.incident_id}

    def client_for(self, provider: str):
        return {"keep": self.keep, "pagerduty": self.pagerduty}.get(provider, NullIncidentClient())

    # --- processing -----------------------------------------------------------
    def write_alert_file(self, incident: IncomingIncident) -> Path:
        alert = dict(incident.alert)
        alert.setdefault("env", self.cfg.env)
        alert.setdefault("source", "airflow")
        alert.setdefault("fired_at", utc_now_iso())
        if not alert.get("alert_id"):
            ts = re.sub(r"[^0-9T]", "", alert["fired_at"].split(".")[0].split("+")[0])[:15]
            alert["alert_id"] = f"ALERT-{ts}Z-{alert['task_id']}"
        alert.update(
            {
                "incident_id": incident.incident_id,
                "incident_url": incident.incident_url,
                "incident_provider": incident.provider,
                "dedup_key": incident.dedup_key,
            }
        )
        alert = {k: v for k, v in alert.items() if v is not None}
        self.cfg.alerts_dir.mkdir(parents=True, exist_ok=True)
        path = self.cfg.alerts_dir / f"{alert['alert_id']}.json"
        path.write_text(json.dumps(alert, indent=2) + "\n")
        return path

    def claude_command(self, alert_path: Path) -> list[str]:
        rel = (
            alert_path.relative_to(self.cfg.workspace_root)
            if alert_path.is_relative_to(self.cfg.workspace_root)
            else alert_path
        )
        return [
            self.cfg.claude_bin,
            "-p",
            f"/sre-plugin:rca {rel}",
            "--plugin-dir",
            str(self.cfg.plugin_dir),
            "--allowedTools",
            ALLOWED_TOOLS,
            "--permission-prompts",
            "none",
            "--output-format",
            "json",
            "--max-budget-usd",
            str(self.cfg.max_budget_usd),
            "--max-turns",
            str(self.cfg.max_turns),
            *self.cfg.extra_claude_args,
        ]

    def run_claude(self, alert_path: Path) -> dict[str, Any]:
        """Run the skill headless.

        Returns {ok, parsed, result, cost_usd, session_id, error, duration_s}.
        """
        started = time.time()
        if self.cfg.dry_run:
            fake = (
                "RESOLVED TARGET: dry-run (source: conversational → file)\n"
                "Root cause: INDETERMINATE — dry run, the skill was not invoked\n"
                "Owner: No code change required\nReport: (dry run)\n"
                "Self-check: CRITICAL: 0 issue(s) · WARNING: 0 · Result: PASS"
            )
            return {
                "ok": True,
                "parsed": parse_skill_result(fake),
                "result": fake,
                "cost_usd": 0.0,
                "session_id": "dry-run",
                "duration_s": 0,
            }
        cmd = self.claude_command(alert_path)
        log.info("running: %s", " ".join(cmd))
        try:
            proc = subprocess.run(
                cmd,
                cwd=self.cfg.workspace_root,
                capture_output=True,
                text=True,
                timeout=self.cfg.timeout_s,
                stdin=subprocess.DEVNULL,
                env=os.environ.copy(),
            )
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "error": f"claude timed out after {self.cfg.timeout_s}s",
                "duration_s": round(time.time() - started),
            }
        except FileNotFoundError:
            return {
                "ok": False,
                "error": f"claude binary not found: {self.cfg.claude_bin}",
                "duration_s": 0,
            }
        duration = round(time.time() - started)
        try:
            data = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError:
            return {
                "ok": False,
                "error": (
                    f"claude exit {proc.returncode}, non-JSON output: "
                    f"{(proc.stdout or proc.stderr)[:300]}"
                ),
                "duration_s": duration,
            }
        result = data.get("result") or ""
        parsed = parse_skill_result(result)
        out = {
            "ok": proc.returncode == 0 and data.get("subtype") == "success" and "report" in parsed,
            "parsed": parsed,
            "result": result,
            "cost_usd": float(data.get("total_cost_usd") or 0),
            "session_id": data.get("session_id"),
            "duration_s": duration,
            "permission_denials": [
                d.get("tool_input", {}).get("command") for d in data.get("permission_denials") or []
            ],
        }
        if not out["ok"]:
            out["error"] = (
                f"claude exit {proc.returncode}, subtype={data.get('subtype')}; "
                f"result tail: {result[-300:]}"
                if result
                else f"claude exit {proc.returncode}: {proc.stderr[-300:]}"
            )
        return out

    def handle(self, incident: IncomingIncident) -> dict[str, Any]:
        run: dict[str, Any] = {
            "ts": utc_now_iso(),
            "provider": incident.provider,
            "incident_id": incident.incident_id,
            "incident_url": incident.incident_url,
            "dedup_key": incident.dedup_key,
            "title": incident.title,
        }
        try:
            alert_path = self.write_alert_file(incident)
            run["alert_path"] = (
                str(alert_path.relative_to(self.cfg.workspace_root))
                if alert_path.is_relative_to(self.cfg.workspace_root)
                else str(alert_path)
            )
            run["alert_id"] = alert_path.stem
            res = self.run_claude(alert_path)
            run.update({k: v for k, v in res.items() if k != "result"})
            run["status"] = "ok" if res.get("ok") else "failed"
        except Exception as exc:  # noqa: BLE001 - always journal and notify
            log.exception("rca run failed")
            run.update({"status": "failed", "error": str(exc)})
        note = note_text(run)
        run["note_posted"] = False
        if incident.incident_id:
            try:
                self.client_for(incident.provider).add_note(incident.incident_id, note)
                run["note_posted"] = True
            except Exception as exc:  # noqa: BLE001
                log.error(
                    "could not post note on %s %s: %s", incident.provider, incident.incident_id, exc
                )
                run["note_error"] = str(exc)
        self._journal(run)
        log.info(
            "run %s: %s (%s)",
            run.get("alert_id"),
            run["status"],
            run.get("parsed", {}).get("root_cause", run.get("error", ""))[:160],
        )
        return run

    def _worker(self) -> None:
        while True:
            incident = self.queue.get()
            try:
                self.handle(incident)
            finally:
                with self.lock:
                    self.in_flight.discard(incident.dedup_key)
                self.queue.task_done()

    def start(self) -> None:
        self.worker.start()


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------
def make_handler(runner: RcaRunner):
    cfg = runner.cfg

    class Handler(BaseHTTPRequestHandler):
        server_version = "rca-runner/1.0"

        def _send(self, code: int, body: dict[str, Any]) -> None:
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt, *args):  # noqa: D401 - quieter than the default
            log.debug("http: " + fmt, *args)

        def do_GET(self):
            if self.path == "/healthz":
                return self._send(
                    200,
                    {"status": "ok", "in_flight": sorted(runner.in_flight), "dry_run": cfg.dry_run},
                )
            if self.path.startswith("/runs"):
                return self._send(200, {"runs": runner.runs()[-50:]})
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b""
            try:
                payload = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                return self._send(400, {"error": "invalid JSON"})
            try:
                if self.path == "/webhook/pagerduty":
                    if not verify_pagerduty_signature(
                        raw, self.headers.get("X-PagerDuty-Signature"), cfg.pagerduty_webhook_secret
                    ):
                        return self._send(401, {"error": "bad signature"})
                    incident = normalise_pagerduty(payload, runner.pagerduty)
                    if incident is None:
                        return self._send(
                            202, {"status": "ignored", "reason": "not incident.triggered"}
                        )
                elif self.path == "/webhook/keep":
                    if not verify_token(self.headers.get("X-RCA-Token"), cfg.webhook_token):
                        return self._send(401, {"error": "bad token"})
                    incident = normalise_keep(payload, runner.keep)
                elif self.path == "/webhook/generic":
                    if not verify_token(self.headers.get("X-RCA-Token"), cfg.webhook_token):
                        return self._send(401, {"error": "bad token"})
                    incident = normalise_generic(payload)
                else:
                    return self._send(404, {"error": "not found"})
            except ValueError as exc:
                return self._send(422, {"error": str(exc)})
            except (urllib.error.URLError, OSError) as exc:
                return self._send(502, {"error": f"incident system unreachable: {exc}"})
            return self._send(202, runner.submit(incident, force=bool(payload.get("force"))))

    return Handler


def serve(cfg: RunnerConfig) -> None:
    runner = RcaRunner(cfg)
    runner.start()
    httpd = ThreadingHTTPServer(("0.0.0.0", cfg.port), make_handler(runner))
    log.info(
        "rca-runner listening on :%s (workspace=%s, plugin=%s, dry_run=%s)",
        cfg.port,
        cfg.workspace_root,
        cfg.plugin_dir,
        cfg.dry_run,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=Path.cwd(),
        help="chapter workspace (has sre-plugin/, inputs/, outputs/)",
    )
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--plugin-dir", type=Path, default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="do not invoke claude; post a canned note (smoke tests)",
    )
    parser.add_argument(
        "--once",
        type=Path,
        default=None,
        help="process one generic alert JSON file synchronously and exit",
    )
    parser.add_argument(
        "--alerts-dir",
        type=Path,
        default=None,
        help="where ALERT-*.json files are written (default inputs/alerts/v1)",
    )
    parser.add_argument(
        "--journal",
        type=Path,
        default=None,
        help="runs journal path (default outputs/rca/v1/runs.jsonl)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    kwargs: dict[str, Any] = {"workspace_root": args.workspace_root, "dry_run": args.dry_run}
    if args.port:
        kwargs["port"] = args.port
    if args.plugin_dir:
        kwargs["plugin_dir"] = args.plugin_dir
    if args.alerts_dir:
        kwargs["alerts_dir"] = args.alerts_dir
    if args.journal:
        kwargs["journal"] = args.journal
    cfg = RunnerConfig(**kwargs)
    if args.once:
        runner = RcaRunner(cfg)
        incident = normalise_generic(json.loads(args.once.read_text()))
        run = runner.handle(incident)
        print(json.dumps(run, indent=2, default=str))
        return 0 if run["status"] == "ok" else 1
    serve(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
