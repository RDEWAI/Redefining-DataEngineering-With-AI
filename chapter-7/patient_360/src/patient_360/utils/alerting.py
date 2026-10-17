"""Failure alerting: Airflow task failure -> incident (LLD §8.5, §8.7).

``on_task_failure`` is the ``default_args["on_failure_callback"]`` of every
pipeline DAG (airflow-dag-pattern.md "Failure alerting", rule DAG-ALERT-001).
Airflow calls it once per task after the last retry. It builds a minimal
alert (the contract in ``inputs/alerts/v1/README.md``), opens an incident
through the configured :class:`IncidentSink`, and never raises: an alerting
failure must not mask the task failure.

The callback does NOT classify the failure. ``sre-plugin`` classifies from the
full task log on the runner side; here we only forward the exception and any
known failure markers found in the tail of the task's own log file, so the
incident title is specific when the marker is available.

Sinks (selected by ``ALERT_SINK`` env, else ``monitoring.alerting_sink`` in
``_infra/cd/config/<ENV>.yaml``):

* ``keep``       — Keep (open source) running in the DEV compose stack.
* ``pagerduty``  — PagerDuty Events API v2 (PROD).
* ``file``       — write ``ALERT-<id>.json`` to ``ALERT_FILE_SINK_DIR`` (tests, offline).
* ``none``       — no-op.

Only the standard library is used: the Airflow image ships neither
``requests`` nor ``httpx``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

log = logging.getLogger(__name__)

HTTP_TIMEOUT = 10
MESSAGE_LIMIT = 1024
LOG_TAIL_BYTES = 64 * 1024

# LLD §8.5 markers worth surfacing in the incident title/body. Mirrors the
# ordered rule table in sre-plugin/skills/rca/scripts/rca_common.py; the RCA
# skill does the authoritative classification from the full log.
FAILURE_MARKERS: tuple[re.Pattern[str], ...] = (
    re.compile(r"SE_RUN_MISSING_FOR_DS=\S+.*"),
    re.compile(r"GOLD_RECON_FAILED_FOR_DS=\S+.*"),
    re.compile(r"Error code is: -9"),
    re.compile(r"java\.lang\.OutOfMemoryError.*"),
    re.compile(r"ImportError: .*spark_expectations.*"),
    re.compile(r"SparkExpectationsMiscException.*"),
    re.compile(r"java\.net\.ConnectException.*"),  # before the bare "Connection refused"
    re.compile(r"NoSuchCatalogException.*"),
    re.compile(r"Connection refused.*"),
    re.compile(r"action_if_failed\s*[:=]\s*fail.*"),
)

IncidentRef = dict[str, Any]


# ---------------------------------------------------------------------------
# Alert construction
# ---------------------------------------------------------------------------
def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_alert_id(task_id: str, fired_at: str) -> str:
    """``ALERT-<YYYYMMDDTHHMMSS>Z-<task_id>`` — same shape as sre-plugin's make_alert_id."""
    ts = re.sub(r"[^0-9T]", "", fired_at.split(".")[0].split("+")[0])[:15]
    return f"ALERT-{ts}Z-{task_id}"


def dedup_key(alert: dict[str, Any]) -> str:
    """One incident per DAG run: a second failed task in the same run attaches to it."""
    return f"{alert['dag_id']}/{alert['run_id']}"


def task_log_path(
    dag_id: str, run_id: str, task_id: str, try_number: int, map_index: int = -1
) -> Path:
    """Airflow 3 default ``log_filename_template`` under ``base_log_folder``."""
    base = Path(os.environ.get("AIRFLOW__LOGGING__BASE_LOG_FOLDER", "/opt/airflow/logs"))
    parts = [f"dag_id={dag_id}", f"run_id={run_id}", f"task_id={task_id}"]
    if map_index is not None and map_index >= 0:
        parts.append(f"map_index={map_index}")
    return base.joinpath(*parts, f"attempt={try_number}.log")


_JSON_TAIL = re.compile(r'\\?",\s*\\?"[a-zA-Z_]+\\?":.*$')


def _clean_marker(raw: str) -> str:
    """Trim a marker to its message: drop a JSON-log tail and escaped quotes, cap the length."""
    text = _JSON_TAIL.sub("", raw).replace('\\"', '"').strip().strip('"').strip()
    return text[:160]


def extract_markers(text: str, limit: int = 3) -> list[str]:
    """Return the last ``limit`` distinct LLD §8.5 marker lines found in ``text``."""
    found: list[str] = []
    for line in text.splitlines():
        for pat in FAILURE_MARKERS:
            m = pat.search(line)
            if m:
                snippet = _clean_marker(m.group(0))
                if snippet and snippet not in found:
                    found.append(snippet)
                break
    return found[-limit:]


def read_log_tail(path: Path, max_bytes: int = LOG_TAIL_BYTES) -> str:
    """Best-effort tail of the task's own log file; '' when unreadable."""
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > max_bytes:
                fh.seek(size - max_bytes)
            return fh.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def build_alert(context: dict[str, Any]) -> dict[str, Any]:
    """Normalise an Airflow task-failure callback context into the alert contract."""
    ti = context.get("task_instance") or context.get("ti")
    dag_id = getattr(ti, "dag_id", None) or getattr(context.get("dag"), "dag_id", "unknown_dag")
    task_id = getattr(ti, "task_id", None) or getattr(
        context.get("task"), "task_id", "unknown_task"
    )
    run_id = getattr(ti, "run_id", None) or context.get("run_id") or "manual__unknown"
    try_number = int(getattr(ti, "try_number", 0) or 0)
    map_index = getattr(ti, "map_index", -1)
    ds = context.get("ds") or (run_id.split("__", 1)[-1][:10] if "__" in run_id else None)
    exc = context.get("exception")
    exc_text = (
        f"{type(exc).__name__}: {exc}"
        if exc is not None
        else "task failed (no exception in context)"
    )
    markers = extract_markers(
        read_log_tail(task_log_path(dag_id, run_id, task_id, try_number, map_index))
    )
    message = "\n".join([exc_text[:MESSAGE_LIMIT], *markers])
    fired_at = utc_now_iso()
    return {
        "alert_id": make_alert_id(task_id, fired_at),
        "fired_at": fired_at,
        "env": os.environ.get("PATIENT360_ENV", "DEV").upper(),
        "source": "airflow",
        "dag_id": dag_id,
        "run_id": run_id,
        "task_id": task_id,
        "try_number": try_number,
        "ds": ds,
        "message": message,
        "markers": markers,
    }


def summary(alert: dict[str, Any]) -> str:
    """One-line incident title: ``<dag>/<task> failed for ds=<ds>: <marker or exception>``."""
    head = alert["markers"][0] if alert.get("markers") else alert["message"].splitlines()[0]
    return f"{alert['dag_id']}/{alert['task_id']} failed for ds={alert.get('ds')}: {head}"[:240]


# ---------------------------------------------------------------------------
# HTTP (stdlib only)
# ---------------------------------------------------------------------------
def _request_json(
    method: str,
    url: str,
    body: dict[str, Any] | list[Any] | None,
    headers: dict[str, str] | None = None,
    timeout: int = HTTP_TIMEOUT,
) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Content-Type": "application/json", "Accept": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed scheme from config
        raw = resp.read()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw.decode(errors="replace")}


# ---------------------------------------------------------------------------
# Sinks
# ---------------------------------------------------------------------------
class IncidentSink(Protocol):
    name: str

    def open(self, alert: dict[str, Any]) -> IncidentRef | None: ...


class NoopSink:
    name = "none"

    def open(self, alert: dict[str, Any]) -> IncidentRef | None:
        return None


class FileSink:
    """Write the alert where ``/sre-plugin:rca <file>`` can pick it up."""

    name = "file"

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def open(self, alert: dict[str, Any]) -> IncidentRef:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{alert['alert_id']}.json"
        path.write_text(json.dumps(alert, indent=2) + "\n")
        return {
            "provider": self.name,
            "incident_id": None,
            "incident_url": str(path),
            "dedup_key": dedup_key(alert),
        }


class KeepSink:
    """Keep (keephq.dev): alert -> incident -> link, deduplicated by fingerprint.

    Verified against keep-api 0.54.3 (2026-10-15): ``POST /alerts/event`` 202,
    ``POST /incidents`` 202 -> ``id``, ``POST /incidents/{id}/alerts`` 202.
    """

    name = "keep"

    def __init__(self, api_url: str, api_key: str = "", ui_url: str | None = None):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.ui_url = (ui_url or api_url).rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {"X-API-KEY": self.api_key} if self.api_key else {}

    def _existing_incident(self, fingerprint: str, dag_id: str) -> str | None:
        """Reuse the open incident already linked to this fingerprint, if any.

        Keep 0.54 does not expose the incident on ``GET /alerts`` (``incident`` is
        null there even after linking), so walk the recent firing incidents of
        this DAG and check their linked alerts' fingerprints.
        """
        try:
            incs = _request_json("GET", f"{self.api_url}/incidents?limit=50", None, self._headers())
        except (urllib.error.URLError, OSError, ValueError):
            return None
        items = incs.get("items", incs) if isinstance(incs, dict) else incs
        for inc in items if isinstance(items, list) else []:
            status = str(inc.get("status", "")).lower()
            if "firing" not in status and "acknowledged" not in status:
                continue
            if dag_id not in (inc.get("services") or []):
                continue
            try:
                linked = _request_json(
                    "GET", f"{self.api_url}/incidents/{inc['id']}/alerts", None, self._headers()
                )
            except (urllib.error.URLError, OSError, ValueError):
                continue
            linked = linked.get("items", linked) if isinstance(linked, dict) else linked
            if any(a.get("fingerprint") == fingerprint for a in linked or []):
                return str(inc["id"])
        return None

    def open(self, alert: dict[str, Any]) -> IncidentRef:
        fp = dedup_key(alert)
        title = summary(alert)
        alert_dto = {
            "id": alert["alert_id"],
            "name": title,
            "status": "firing",
            "severity": "critical",
            "source": ["airflow"],
            "fingerprint": fp,
            "lastReceived": alert["fired_at"],
            "environment": alert["env"],
            "service": alert["dag_id"],
            "description": alert["message"],
            "labels": {
                "dag_id": alert["dag_id"],
                "run_id": alert["run_id"],
                "task_id": alert["task_id"],
                "ds": alert.get("ds") or "",
                "try_number": str(alert.get("try_number", "")),
                "env": alert["env"],
                "alert_id": alert["alert_id"],
            },
        }
        _request_json("POST", f"{self.api_url}/alerts/event", alert_dto, self._headers())
        incident_id = self._existing_incident(fp, alert["dag_id"])
        created = False
        if not incident_id:
            inc = _request_json(
                "POST",
                f"{self.api_url}/incidents",
                {
                    "user_generated_name": title,
                    "user_summary": alert["message"],
                    "severity": "critical",
                },
                self._headers(),
            )
            incident_id = str(inc.get("id"))
            created = True
        _request_json(
            "POST", f"{self.api_url}/incidents/{incident_id}/alerts", [fp], self._headers()
        )
        return {
            "provider": self.name,
            "incident_id": incident_id,
            "incident_url": f"{self.ui_url}/incidents/{incident_id}",
            "dedup_key": fp,
            "created": created,
        }


class PagerDutySink:
    """PagerDuty Events API v2 ``trigger``; PagerDuty opens/dedups the incident."""

    name = "pagerduty"
    EVENTS_URL = "https://events.pagerduty.com/v2/enqueue"

    def __init__(
        self, routing_key: str, events_url: str | None = None, airflow_base_url: str | None = None
    ):
        self.routing_key = routing_key
        self.events_url = events_url or self.EVENTS_URL
        self.airflow_base_url = (airflow_base_url or "http://localhost:8081").rstrip("/")

    def open(self, alert: dict[str, Any]) -> IncidentRef:
        fp = dedup_key(alert)
        event = {
            "routing_key": self.routing_key,
            "event_action": "trigger",
            "dedup_key": fp,
            "payload": {
                "summary": summary(alert),
                "source": f"airflow/{alert['dag_id']}",
                "severity": "critical",
                "timestamp": alert["fired_at"],
                "component": alert["task_id"],
                "group": alert["dag_id"],
                "class": "pipeline-task-failure",
                "custom_details": {k: v for k, v in alert.items() if k != "markers"},
            },
            "links": [
                {
                    "href": (
                        f"{self.airflow_base_url}/dags/{alert['dag_id']}/runs/"
                        f"{alert['run_id']}/tasks/{alert['task_id']}"
                    ),
                    "text": "Airflow task instance",
                }
            ],
        }
        resp = _request_json("POST", self.events_url, event)
        return {
            "provider": self.name,
            # assigned by PagerDuty; delivered in the incident.triggered webhook
            "incident_id": None,
            "incident_url": None,
            "dedup_key": resp.get("dedup_key", fp) if isinstance(resp, dict) else fp,
        }


def sink_from_config(env: str | None = None) -> IncidentSink:
    """``ALERT_SINK`` env wins; else ``monitoring.alerting_sink`` from env config; else ``none``."""
    env = (env or os.environ.get("PATIENT360_ENV", "DEV")).upper()
    kind = os.environ.get("ALERT_SINK")
    keep_url = os.environ.get("KEEP_API_URL")
    keep_ui = os.environ.get("KEEP_UI_URL")
    if not kind or not keep_url or not keep_ui:
        try:
            from patient_360.utils.pipeline_config import load_config

            cfg = load_config(env)
            kind = kind or cfg.get("monitoring.alerting_sink", "none")
            keep_url = keep_url or cfg.get("monitoring.alerting_keep_api_url")
            keep_ui = keep_ui or cfg.get("monitoring.alerting_keep_ui_url")
        except Exception as exc:  # noqa: BLE001 - config is optional for the callback
            log.warning("alerting: env config unavailable (%s); ALERT_SINK=%s", exc, kind)
    kind = (kind or "none").lower()
    if kind == "keep":
        return KeepSink(
            keep_url or "http://keep-backend:8080", os.environ.get("KEEP_API_KEY", ""), keep_ui
        )
    if kind == "pagerduty":
        key = os.environ.get("PAGERDUTY_ROUTING_KEY", "")
        if not key:
            log.error(
                "alerting: ALERT_SINK=pagerduty but PAGERDUTY_ROUTING_KEY is empty; alert dropped"
            )
            return NoopSink()
        return PagerDutySink(
            key, os.environ.get("PAGERDUTY_EVENTS_URL"), os.environ.get("AIRFLOW_BASE_URL")
        )
    if kind == "file":
        return FileSink(os.environ.get("ALERT_FILE_SINK_DIR", "/tmp/alerts"))
    return NoopSink()


# ---------------------------------------------------------------------------
# The callback
# ---------------------------------------------------------------------------
def on_task_failure(context: dict[str, Any]) -> IncidentRef | None:
    """Airflow ``on_failure_callback``: build the alert, open the incident, never raise."""
    try:
        alert = build_alert(context)
    except Exception:  # noqa: BLE001
        log.exception("alerting: could not build alert from context")
        return None
    sink = sink_from_config(alert["env"])
    try:
        ref = sink.open(alert)
        log.info(
            "alerting: %s -> %s %s",
            alert["alert_id"],
            sink.name,
            json.dumps(ref or {}),
            extra={
                "task_id": alert["task_id"],
                "ds": alert.get("ds"),
                "pipeline_run_id": alert["run_id"],
            },
        )
        return ref
    except Exception as exc:  # noqa: BLE001 - never mask the task failure
        log.error(
            "alerting: sink %s failed for %s: %s",
            sink.name,
            alert["alert_id"],
            exc,
            extra={
                "task_id": alert["task_id"],
                "ds": alert.get("ds"),
                "pipeline_run_id": alert["run_id"],
            },
        )
        return None
