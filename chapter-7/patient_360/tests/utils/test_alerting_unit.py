"""Unit tests for patient_360.utils.alerting (DAG-ALERT-001 failure callback)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from patient_360.utils import alerting


def _context(
    tmp_path: Path,
    exc: Exception | None = RuntimeError("spark-submit exited 1"),
    log_text: str | None = None,
):
    ti = SimpleNamespace(
        dag_id="patient360_hourly_v1",
        run_id="scheduled__2026-10-15T14:00:00+00:00",
        task_id="reconciliation_bronze",
        try_number=3,
        map_index=-1,
    )
    if log_text is not None:
        p = alerting.task_log_path(ti.dag_id, ti.run_id, ti.task_id, ti.try_number)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(log_text)
    return {"task_instance": ti, "ds": "2026-10-15", "run_id": ti.run_id, "exception": exc}


@pytest.fixture(autouse=True)
def _log_root(tmp_path, monkeypatch):
    monkeypatch.setenv("AIRFLOW__LOGGING__BASE_LOG_FOLDER", str(tmp_path / "logs"))
    monkeypatch.setenv("PATIENT360_ENV", "DEV")
    monkeypatch.delenv("ALERT_SINK", raising=False)
    monkeypatch.delenv("KEEP_API_URL", raising=False)


class _FakeResp:
    def __init__(self, body):
        self._body = json.dumps(body).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _capture_urlopen(responses):
    """Return (urlopen mock, calls list). ``responses`` maps (METHOD, url-suffix) -> body."""
    calls = []

    def fake(req, timeout=None):
        body = json.loads(req.data) if req.data else None
        calls.append((req.get_method(), req.full_url, body, dict(req.header_items())))
        for (m, suffix), resp in responses.items():
            if req.get_method() == m and req.full_url.endswith(suffix):
                return _FakeResp(resp)
        return _FakeResp({})

    return mock.patch.object(alerting.urllib.request, "urlopen", side_effect=fake), calls


# --- alert construction -----------------------------------------------------
def test_build_alert_minimal_contract(tmp_path):
    a = alerting.build_alert(_context(tmp_path))
    assert a["source"] == "airflow" and a["env"] == "DEV"
    assert a["dag_id"] == "patient360_hourly_v1" and a["task_id"] == "reconciliation_bronze"
    assert (
        a["run_id"].startswith("scheduled__") and a["ds"] == "2026-10-15" and a["try_number"] == 3
    )
    assert a["alert_id"].startswith("ALERT-") and a["alert_id"].endswith("Z-reconciliation_bronze")
    assert a["message"].startswith("RuntimeError: spark-submit exited 1")
    assert a["markers"] == []
    assert alerting.dedup_key(a) == "patient360_hourly_v1/scheduled__2026-10-15T14:00:00+00:00"


def test_build_alert_surfaces_log_markers(tmp_path):
    log_text = (
        "INFO spark stuff\n"
        "ERROR SE_RUN_MISSING_FOR_DS=2026-10-15 layer=bronze env=DEV\n"
        "Traceback...\n"
    )
    a = alerting.build_alert(_context(tmp_path, log_text=log_text))
    assert a["markers"] == ["SE_RUN_MISSING_FOR_DS=2026-10-15 layer=bronze env=DEV"]
    assert "SE_RUN_MISSING_FOR_DS=2026-10-15" in a["message"]
    assert alerting.summary(a) == (
        "patient360_hourly_v1/reconciliation_bronze failed for ds=2026-10-15: "
        "SE_RUN_MISSING_FOR_DS=2026-10-15 layer=bronze env=DEV"
    )


def test_build_alert_without_exception_or_log(tmp_path):
    a = alerting.build_alert(_context(tmp_path, exc=None))
    assert a["message"] == "task failed (no exception in context)"
    assert alerting.summary(a).endswith("task failed (no exception in context)")


def test_ds_derived_from_run_id_when_absent(tmp_path):
    ctx = _context(tmp_path)
    ctx.pop("ds")
    assert alerting.build_alert(ctx)["ds"] == "2026-10-15"


def test_extract_markers_keeps_last_three_distinct():
    text = "\n".join(
        [
            "Connection refused (a)",
            "Connection refused (a)",
            "Error code is: -9",
            "GOLD_RECON_FAILED_FOR_DS=2026-10-15 DQ_REC_001",
            "SE_RUN_MISSING_FOR_DS=2026-10-15",
        ]
    )
    assert alerting.extract_markers(text) == [
        "Error code is: -9",
        "GOLD_RECON_FAILED_FOR_DS=2026-10-15 DQ_REC_001",
        "SE_RUN_MISSING_FOR_DS=2026-10-15",
    ]


def test_task_log_path_matches_airflow3_template(tmp_path):
    p = alerting.task_log_path("d", "r", "t", 2)
    assert str(p).endswith("logs/dag_id=d/run_id=r/task_id=t/attempt=2.log")
    assert "map_index=0" in str(alerting.task_log_path("d", "r", "t", 2, map_index=0))


# --- sinks --------------------------------------------------------------------
def test_file_sink_writes_alert(tmp_path):
    a = alerting.build_alert(_context(tmp_path))
    ref = alerting.FileSink(tmp_path / "alerts").open(a)
    written = json.loads(Path(ref["incident_url"]).read_text())
    assert written["alert_id"] == a["alert_id"] and ref["dedup_key"] == alerting.dedup_key(a)


def test_keep_sink_creates_incident_and_links_alert(tmp_path):
    a = alerting.build_alert(_context(tmp_path, log_text="SE_RUN_MISSING_FOR_DS=2026-10-15\n"))
    patcher, calls = _capture_urlopen(
        {("GET", "/incidents?limit=50"): {"items": []}, ("POST", "/incidents"): {"id": "inc-1"}}
    )
    with patcher:
        ref = alerting.KeepSink("http://keep:8080", "k", ui_url="http://localhost:3010").open(a)
    methods = [(m, u.split("8080")[1]) for m, u, _, _ in calls]
    assert methods == [
        ("POST", "/alerts/event"),
        ("GET", "/incidents?limit=50"),
        ("POST", "/incidents"),
        ("POST", "/incidents/inc-1/alerts"),
    ]
    alert_dto = calls[0][2]
    assert alert_dto["fingerprint"] == alerting.dedup_key(a) and alert_dto["status"] == "firing"
    assert (
        alert_dto["labels"]["task_id"] == "reconciliation_bronze"
        and alert_dto["labels"]["ds"] == "2026-10-15"
    )
    assert calls[0][3]["X-api-key"] == "k"
    assert calls[2][2]["user_generated_name"].startswith(
        "patient360_hourly_v1/reconciliation_bronze failed"
    )
    assert calls[3][2] == [alerting.dedup_key(a)]
    assert ref == {
        "provider": "keep",
        "incident_id": "inc-1",
        "incident_url": "http://localhost:3010/incidents/inc-1",
        "dedup_key": alerting.dedup_key(a),
        "created": True,
    }


def test_keep_sink_reuses_open_incident_for_same_run(tmp_path):
    a = alerting.build_alert(_context(tmp_path))
    dag = "patient360_hourly_v1"
    incidents = {
        "items": [
            {"id": "inc-resolved", "status": "resolved", "services": [dag]},
            {"id": "inc-other", "status": "firing", "services": ["other_dag"]},
            {"id": "inc-old", "status": "IncidentStatus.FIRING", "services": [dag]},
        ]
    }
    linked = {"items": [{"fingerprint": alerting.dedup_key(a)}]}
    patcher, calls = _capture_urlopen(
        {("GET", "/incidents?limit=50"): incidents, ("GET", "/incidents/inc-old/alerts"): linked}
    )
    with patcher:
        ref = alerting.KeepSink("http://keep:8080").open(a)
    assert ref["incident_id"] == "inc-old" and ref["created"] is False
    assert not any(u.endswith("/incidents") and m == "POST" for m, u, _, _ in calls)


def test_pagerduty_sink_trigger_event(tmp_path):
    a = alerting.build_alert(_context(tmp_path))
    patcher, calls = _capture_urlopen(
        {("POST", "/v2/enqueue"): {"status": "success", "dedup_key": "pd-key"}}
    )
    with patcher:
        ref = alerting.PagerDutySink("rk123", airflow_base_url="http://af:8081").open(a)
    ((m, url, body, _),) = calls
    assert url == alerting.PagerDutySink.EVENTS_URL and m == "POST"
    assert body["routing_key"] == "rk123" and body["event_action"] == "trigger"
    assert body["dedup_key"] == alerting.dedup_key(a)
    assert (
        body["payload"]["severity"] == "critical"
        and body["payload"]["custom_details"]["task_id"] == "reconciliation_bronze"
    )
    assert body["links"][0]["href"].startswith("http://af:8081/dags/patient360_hourly_v1/")
    assert (
        ref["provider"] == "pagerduty"
        and ref["dedup_key"] == "pd-key"
        and ref["incident_id"] is None
    )


# --- selection ------------------------------------------------------------------
def test_sink_from_env_overrides_config(monkeypatch):
    monkeypatch.setenv("ALERT_SINK", "file")
    assert isinstance(alerting.sink_from_config("DEV"), alerting.FileSink)
    monkeypatch.setenv("ALERT_SINK", "keep")
    monkeypatch.setenv("KEEP_API_URL", "http://keep-backend:8080")
    s = alerting.sink_from_config("DEV")
    assert isinstance(s, alerting.KeepSink) and s.api_url == "http://keep-backend:8080"
    monkeypatch.setenv("ALERT_SINK", "pagerduty")
    assert isinstance(
        alerting.sink_from_config("PROD"), alerting.NoopSink
    )  # no routing key -> dropped
    monkeypatch.setenv("PAGERDUTY_ROUTING_KEY", "rk")
    assert isinstance(alerting.sink_from_config("PROD"), alerting.PagerDutySink)


def test_sink_from_config_reads_env_yaml(monkeypatch):
    assert isinstance(alerting.sink_from_config("DEV"), alerting.KeepSink)  # DEV.yaml: keep
    assert isinstance(alerting.sink_from_config("STAGING"), alerting.KeepSink)  # STAGING.yaml: keep
    assert isinstance(
        alerting.sink_from_config("PROD"), alerting.NoopSink
    )  # PROD.yaml: pagerduty, no key


# --- the callback never raises -----------------------------------------------------
def test_on_task_failure_swallows_sink_errors(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("ALERT_SINK", "keep")
    monkeypatch.setenv("KEEP_API_URL", "http://keep:8080")
    with mock.patch.object(
        alerting.urllib.request, "urlopen", side_effect=OSError("connection refused")
    ):
        assert alerting.on_task_failure(_context(tmp_path)) is None
    assert any("sink keep failed" in r.getMessage() for r in caplog.records)


def test_on_task_failure_swallows_bad_context():
    # A context with nothing usable still must not raise (sink resolves to none/keep and is caught).
    assert alerting.on_task_failure({}) is None
    assert alerting.on_task_failure({"task_instance": None, "exception": object()}) is None


def test_on_task_failure_file_sink_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("ALERT_SINK", "file")
    monkeypatch.setenv("ALERT_FILE_SINK_DIR", str(tmp_path / "alerts"))
    ref = alerting.on_task_failure(_context(tmp_path))
    assert ref["provider"] == "file" and Path(ref["incident_url"]).is_file()


def test_extract_markers_strips_json_log_tail():
    line = (
        'Traceback: SparkExpectationsMiscException(f\\"error occurred while saving '
        'the data into the stats table {e}\\")",'
        '"logger":"airflow.task.hooks.airflow.providers.apache.spark","level":"error"}'
    )
    expected = (
        'SparkExpectationsMiscException(f"error occurred while saving the data into '
        'the stats table {e}")'
    )
    assert alerting.extract_markers(line) == [expected]


def test_extract_markers_carries_uc_outage_signals():
    """The incident summary must name the UC outage, not just the SE wrapper exception."""
    text = "\n".join(
        [
            "SparkExpectationsMiscException: error occurred while saving the data",
            "Caused by: java.net.ConnectException: Connection refused",
            "io.unitycatalog.client.ApiException: NoSuchCatalogException: Catalog not found",
        ]
    )
    found = alerting.extract_markers(text)
    assert any(m.startswith("java.net.ConnectException") for m in found)
    assert any("NoSuchCatalogException" in m for m in found)
