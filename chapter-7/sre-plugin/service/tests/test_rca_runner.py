"""Unit tests for sre-plugin/service/rca_runner.py (no network, no claude)."""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import pytest

SERVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE))

import rca_runner as rr  # noqa: E402

FIX = SERVICE / "fixtures"


def _fixture(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.fixture
def cfg(tmp_path: Path) -> rr.RunnerConfig:
    (tmp_path / "sre-plugin").mkdir()
    return rr.RunnerConfig(
        workspace_root=tmp_path,
        dry_run=True,
        webhook_token="tok",
        pagerduty_webhook_secret="pdsecret",
        pagerduty_api_key="pdkey",
        pagerduty_from_email="oncall@example.com",
        keep_api_url="http://keep:8080",
        keep_api_key="k",
        keep_ui_url="http://localhost:3010",
        env="DEV",
    )


class _StubClient:
    name = "stub"

    def __init__(self, alerts):
        self.alerts = alerts
        self.notes: list[tuple[str, str]] = []
        self.calls = 0

    def incident_alerts(self, incident_id):
        self.calls += 1
        return self.alerts

    def incident_url(self, incident_id):
        return f"http://ui/incidents/{incident_id}"

    def add_note(self, incident_id, text):
        self.notes.append((incident_id, text))


# --- normalisers -----------------------------------------------------------------
def test_normalise_keep_polls_for_linked_alert_and_reads_labels():
    client = _StubClient(_fixture("keep_incident_alerts.json")["items"])
    inc = rr.normalise_keep(_fixture("keep_incident_created.json"), client, retries=3, delay_s=0)
    assert inc.provider == "keep" and inc.incident_id == "1fab5929-947b-40e9-bca7-a6c0227d2786"
    assert inc.incident_url == "http://ui/incidents/1fab5929-947b-40e9-bca7-a6c0227d2786"
    assert (
        inc.alert["dag_id"] == "patient360_hourly_v1"
        and inc.alert["task_id"] == "reconciliation_bronze"
    )
    assert (
        inc.alert["run_id"] == "scheduled__2026-10-15T14:00:00+00:00"
        and inc.alert["try_number"] == 3
    )
    assert inc.alert["ds"] == "2026-10-15" and "SE_RUN_MISSING_FOR_DS" in inc.alert["message"]
    assert inc.dedup_key == "patient360_hourly_v1/scheduled__2026-10-15T14:00:00+00:00"


def test_normalise_keep_retries_then_fails_without_alert():
    client = _StubClient([])
    with pytest.raises(ValueError, match="no linked alert"):
        rr.normalise_keep(_fixture("keep_incident_created.json"), client, retries=3, delay_s=0)
    assert client.calls == 3


def test_normalise_pagerduty_reads_custom_details():
    client = _StubClient(_fixture("pagerduty_incident_alerts.json")["alerts"])
    inc = rr.normalise_pagerduty(_fixture("pagerduty_incident_triggered.json"), client)
    assert inc.provider == "pagerduty" and inc.incident_id == "PGR0VU2"
    assert inc.incident_url == "https://acme.pagerduty.com/incidents/PGR0VU2"
    assert inc.alert["task_id"] == "reconciliation_bronze" and inc.alert["env"] == "PROD"
    assert inc.dedup_key == "patient360_hourly_v1/scheduled__2026-10-15T14:00:00+00:00"


def test_normalise_pagerduty_ignores_other_events():
    payload = _fixture("pagerduty_incident_triggered.json")
    payload["event"]["event_type"] = "incident.acknowledged"
    assert rr.normalise_pagerduty(payload, _StubClient([])) is None


def test_normalise_generic_minimal():
    inc = rr.normalise_generic(
        {
            "dag_id": "d",
            "task_id": "t",
            "run_id": "manual__2026-10-15T01:00:00+00:00",
            "message": "boom",
            "incident_id": "x",
            "incident_provider": "keep",
        }
    )
    assert inc.provider == "keep" and inc.incident_id == "x" and inc.alert["message"] == "boom"
    with pytest.raises(ValueError):
        rr.normalise_generic({"message": "no ids"})


# --- verification ----------------------------------------------------------------
def test_pagerduty_signature():
    body = b'{"event":{}}'
    sig = hmac.new(b"pdsecret", body, hashlib.sha256).hexdigest()
    assert rr.verify_pagerduty_signature(body, f"v1={sig}", "pdsecret")
    assert rr.verify_pagerduty_signature(body, f"v1=deadbeef,v1={sig}", "pdsecret")
    assert not rr.verify_pagerduty_signature(body, "v1=deadbeef", "pdsecret")
    assert not rr.verify_pagerduty_signature(body, None, "pdsecret")
    assert not rr.verify_pagerduty_signature(body, f"v1={sig}", "")


def test_token_verification():
    assert (
        rr.verify_token("tok", "tok")
        and not rr.verify_token("nope", "tok")
        and not rr.verify_token("x", "")
    )


# --- result parsing + note -----------------------------------------------------------
SKILL_OUTPUT = """```
RESOLVED TARGET: ALERT-1-reconciliation_bronze (source: conversational → file)
Root cause: CONFIRMED — SE never ran because dq_enabled=false
Blast radius: 17 tasks upstream_failed
Owner: /developer-plugin:update-ingestion "enforce no-opt-out"
Report: outputs/rca/v1/ALERT-1-reconciliation_bronze/RCA-2026-10-15-ALERT-1-reconciliation_bronze.md
Self-check: CRITICAL: 0 issue(s) · WARNING: 0 · Result: PASS
Not observed: marquez_runs
```
**Key findings** ...
"""


def test_parse_skill_result():
    p = rr.parse_skill_result(SKILL_OUTPUT)
    assert p["root_cause"].startswith("CONFIRMED") and p["owner"].startswith(
        "/developer-plugin:update-ingestion"
    )
    assert (
        p["report"].endswith(".md")
        and p["self-check"].endswith("PASS")
        and p["resolved_target"].startswith("ALERT-1")
    )


def test_note_text_ok_and_failed():
    ok = rr.note_text(
        {
            "status": "ok",
            "alert_id": "A",
            "parsed": rr.parse_skill_result(SKILL_OUTPUT),
            "cost_usd": 3.09,
            "duration_s": 328,
            "session_id": "s",
        }
    )
    assert "[sre-plugin:rca] OK — A" in ok and "Root cause: CONFIRMED" in ok and "$3.09" in ok
    bad = rr.note_text(
        {
            "status": "failed",
            "alert_id": "A",
            "error": "claude timed out",
            "alert_path": "inputs/alerts/v1/A.json",
        }
    )
    assert (
        "RCA did not complete: claude timed out" in bad
        and "/sre-plugin:rca inputs/alerts/v1/A.json" in bad
    )


# --- runner behaviour -----------------------------------------------------------------
def test_handle_dry_run_writes_alert_journal_and_note(cfg):
    runner = rr.RcaRunner(cfg)
    stub = _StubClient([])
    runner.keep = stub
    inc = rr.normalise_keep(
        _fixture("keep_incident_created.json"),
        _StubClient(_fixture("keep_incident_alerts.json")["items"]),
        retries=1,
        delay_s=0,
    )
    run = runner.handle(inc)
    assert run["status"] == "ok" and run["note_posted"] is True
    alert_file = cfg.workspace_root / run["alert_path"]
    alert = json.loads(alert_file.read_text())
    assert (
        alert_file.parent == cfg.alerts_dir
        and alert["alert_id"] == "ALERT-20261015T140000Z-reconciliation_bronze"
    )
    assert alert["incident_id"] == inc.incident_id and alert["incident_provider"] == "keep"
    assert (
        alert["dedup_key"] == inc.dedup_key
        and alert["source"] == "airflow"
        and alert["env"] == "DEV"
    )
    assert stub.notes[0][0] == inc.incident_id and "[sre-plugin:rca] OK" in stub.notes[0][1]
    journal = runner.runs()
    assert len(journal) == 1 and journal[0]["dedup_key"] == inc.dedup_key


def test_submit_dedups_in_flight_and_journaled(cfg):
    runner = rr.RcaRunner(cfg)
    inc = rr.normalise_generic({"dag_id": "d", "task_id": "t", "run_id": "r1", "message": "m"})
    assert runner.submit(inc)["status"] == "queued"
    assert runner.submit(inc)["status"] == "duplicate"  # in flight
    runner.in_flight.clear()
    runner._journal({"dedup_key": inc.dedup_key, "status": "ok"})
    assert runner.submit(inc)["status"] == "duplicate"  # journaled
    assert runner.submit(inc, force=True)["status"] == "queued"  # explicit re-run


def test_claude_command_shape(cfg):
    cfg.dry_run = False
    runner = rr.RcaRunner(cfg)
    cmd = runner.claude_command(cfg.alerts_dir / "ALERT-x.json")
    assert cmd[:3] == [cfg.claude_bin, "-p", "/sre-plugin:rca inputs/alerts/v1/ALERT-x.json"]
    assert "--plugin-dir" in cmd and str(cfg.plugin_dir) in cmd
    assert "--bare" not in cmd  # subscription login on the host; the plugin hook must load
    assert cmd[cmd.index("--allowedTools") + 1] == rr.ALLOWED_TOOLS
    assert cmd[cmd.index("--permission-prompts") + 1] == "none" and "--output-format" in cmd


def test_run_claude_parses_json_and_failure_paths(cfg, monkeypatch):
    cfg.dry_run = False
    runner = rr.RcaRunner(cfg)
    good = {
        "subtype": "success",
        "result": SKILL_OUTPUT,
        "total_cost_usd": 1.5,
        "session_id": "sid",
        "permission_denials": [{"tool_input": {"command": "docker compose restart airflow"}}],
    }
    fake = mock.Mock(returncode=0, stdout=json.dumps(good), stderr="")
    with mock.patch.object(rr.subprocess, "run", return_value=fake) as sp:
        res = runner.run_claude(cfg.alerts_dir / "A.json")
    assert (
        res["ok"]
        and res["cost_usd"] == 1.5
        and res["permission_denials"] == ["docker compose restart airflow"]
    )
    assert sp.call_args.kwargs["cwd"] == cfg.workspace_root
    bad = mock.Mock(returncode=1, stdout="not json", stderr="boom")
    with mock.patch.object(rr.subprocess, "run", return_value=bad):
        res = runner.run_claude(cfg.alerts_dir / "A.json")
    assert not res["ok"] and "non-JSON" in res["error"]
    with mock.patch.object(
        rr.subprocess, "run", side_effect=rr.subprocess.TimeoutExpired("claude", 1)
    ):
        res = runner.run_claude(cfg.alerts_dir / "A.json")
    assert not res["ok"] and "timed out" in res["error"]


def test_failed_run_still_posts_note(cfg, monkeypatch):
    cfg.dry_run = False
    runner = rr.RcaRunner(cfg)
    stub = _StubClient([])
    runner.keep = stub
    inc = rr.normalise_generic(
        {
            "dag_id": "d",
            "task_id": "t",
            "run_id": "r",
            "message": "m",
            "incident_id": "i1",
            "incident_provider": "keep",
        }
    )
    with mock.patch.object(rr.subprocess, "run", side_effect=FileNotFoundError):
        run = runner.handle(inc)
    assert run["status"] == "failed" and "binary not found" in run["error"]
    assert stub.notes and "RCA did not complete" in stub.notes[0][1]


# --- HTTP layer ---------------------------------------------------------------------------
@pytest.fixture
def server(cfg):
    runner = rr.RcaRunner(cfg)
    runner.keep = _StubClient(_fixture("keep_incident_alerts.json")["items"])
    runner.pagerduty = _StubClient(_fixture("pagerduty_incident_alerts.json")["alerts"])
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), rr.make_handler(runner))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", runner
    httpd.shutdown()


def _post(url, body: bytes, headers: dict[str, str]):
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json", **headers}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_http_routes(server):
    base, runner = server
    with urllib.request.urlopen(f"{base}/healthz", timeout=5) as r:
        assert json.loads(r.read())["status"] == "ok"
    keep_body = json.dumps(_fixture("keep_incident_created.json")).encode()
    assert _post(f"{base}/webhook/keep", keep_body, {})[0] == 401
    code, body = _post(f"{base}/webhook/keep", keep_body, {"X-RCA-Token": "tok"})
    assert code == 202 and body["status"] == "queued"
    code, body = _post(f"{base}/webhook/keep", keep_body, {"X-RCA-Token": "tok"})
    assert code == 202 and body["status"] == "duplicate"
    pd_body = json.dumps(_fixture("pagerduty_incident_triggered.json")).encode()
    assert (
        _post(f"{base}/webhook/pagerduty", pd_body, {"X-PagerDuty-Signature": "v1=bad"})[0] == 401
    )
    sig = hmac.new(b"pdsecret", pd_body, hashlib.sha256).hexdigest()
    code, body = _post(f"{base}/webhook/pagerduty", pd_body, {"X-PagerDuty-Signature": f"v1={sig}"})
    assert code == 202 and body["status"] in (
        "queued",
        "duplicate",
    )  # same dedup key as the Keep fixture
    code, body = _post(f"{base}/webhook/generic", b'{"message":"no ids"}', {"X-RCA-Token": "tok"})
    assert code == 422
    assert _post(f"{base}/webhook/generic", b"{bad json", {"X-RCA-Token": "tok"})[0] == 400
    assert _post(f"{base}/webhook/nope", b"{}", {})[0] == 404
