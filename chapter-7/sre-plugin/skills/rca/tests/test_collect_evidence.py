"""Unit tests for collect_evidence.py: offline mode, table resolution, and failure isolation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import collect_evidence as ce  # noqa: E402
import rca_common  # noqa: E402

CHAPTER_ROOT = Path(__file__).resolve().parents[4]
SHIPPED_PROJECT = CHAPTER_ROOT / "patient_360"


@pytest.fixture
def workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Minimal workspace: outputs/stories + a project with configs, dq_rules, dags, src."""
    ws = tmp_path / "ws"
    (ws / "outputs" / "stories").mkdir(parents=True)
    proj = ws / "proj"
    (proj / "src" / "proj" / "silver").mkdir(parents=True)
    (proj / "src" / "proj" / "gold").mkdir(parents=True)
    (proj / "airflow" / "configs").mkdir(parents=True)
    (proj / "airflow" / "dags").mkdir(parents=True)
    (proj / "dq_rules").mkdir()
    (proj / "_infra" / "cd" / "config").mkdir(parents=True)
    (proj / "pyproject.toml").write_text("[project]\nname='proj'\n")
    (proj / "airflow" / "configs" / "patients.yml").write_text(
        "table: patients\noutput_table: unity.bronze.synthea_patients\n"
    )
    (proj / "airflow" / "configs" / "claims.yml").write_text(
        "table: claims\noutput_table: unity.bronze.synthea_claims\n"
    )
    (proj / "dq_rules" / "clinical_patients.yml").write_text("rules: []\n")
    (proj / "airflow" / "dags" / "hourly.py").write_text("dag_id='patient360_hourly_v1'\n")
    (proj / "_infra" / "cd" / "config" / "DEV.yaml").write_text("env: DEV\n")
    (proj / "src" / "proj" / "silver" / "patients.py").write_text(
        'T = "unity.silver.clinical_patients"\nS = "unity.silver.clinical_patients_stats"\n'
    )
    (proj / "src" / "proj" / "gold" / "summary.py").write_text('T = "unity.gold.patient_summary"\n')
    return ws, proj


def _alert(**over):
    base = {
        "alert_id": "ALERT-1-reconciliation_bronze",
        "fired_at": "2026-10-14T15:30:12+00:00",
        "env": "DEV",
        "condition": "Pipeline task failure after all retries",
        "severity": "CRITICAL",
        "source": "airflow",
        "dag_id": "patient360_hourly_v1",
        "run_id": "scheduled__2026-10-14T15:00:00+00:00",
        "task_id": "reconciliation_bronze",
        "try_number": 3,
        "ds": "2026-10-14",
        "message": "SE_RUN_MISSING_FOR_DS=2026-10-14",
    }
    base.update(over)
    return base


# --------------------------------------------------------------------------
# Table resolution
# --------------------------------------------------------------------------
def test_resolve_tables_from_fixture_project(workspace):
    _ws, proj = workspace
    assert ce.resolve_tables("ingest_patients", proj, "proj") == ["unity.bronze.synthea_patients"]
    assert ce.resolve_tables("bronze_ingestion.ingest_claims", proj, "proj") == [
        "unity.bronze.synthea_claims"
    ]
    assert ce.resolve_tables("transform_patients_silver", proj, "proj") == [
        "unity.silver.clinical_patients",
        "unity.bronze.synthea_patients",
    ]
    assert ce.resolve_tables("build_patient_summary_gold", proj, "proj") == [
        "unity.gold.patient_summary"
    ]
    assert ce.resolve_tables("reconciliation_bronze", proj, "proj") == [
        "unity.bronze.synthea_claims",
        "unity.bronze.synthea_patients",
    ]
    assert ce.resolve_tables("emit_metrics", proj, "proj") == []
    assert ce.resolve_tables(None, proj, "proj") == []


def test_stats_and_error_suffixes_are_not_treated_as_tables(workspace):
    _ws, proj = workspace
    assert "unity.silver.clinical_patients_stats" not in ce.layer_tables_from_source(
        proj, "proj", "silver"
    )


@pytest.mark.skipif(
    not (SHIPPED_PROJECT / "airflow" / "dags").is_dir(), reason="shipped project not present"
)
def test_resolve_tables_against_shipped_project():
    tables = ce.resolve_tables("reconciliation_bronze", SHIPPED_PROJECT, "patient_360")
    assert len(tables) >= 10 and all(t.startswith("unity.bronze.") for t in tables)
    gold = ce.resolve_tables("reconciliation_gold", SHIPPED_PROJECT, "patient_360")
    assert "unity.gold.patient_summary" in gold


# --------------------------------------------------------------------------
# Offline collection
# --------------------------------------------------------------------------
def test_offline_writes_manifest_and_config_snapshot(workspace, tmp_path: Path):
    ws, _proj = workspace
    alert_dir = ws / "outputs" / "rca" / "v1" / "ALERT-1-reconciliation_bronze"
    alert_dir.mkdir(parents=True)
    (alert_dir / "alert.json").write_text(json.dumps(_alert()))
    rc = ce.main(
        ["--alert", str(alert_dir / "alert.json"), "--offline", "--workspace-root", str(ws)]
    )
    assert rc == 0
    manifest = json.loads((alert_dir / "evidence" / "manifest.json").read_text())
    assert manifest["offline"] is True
    assert manifest["surfaces"]["config_snapshot"]["status"] == "ok"
    assert manifest["surfaces"]["airflow_task_log"]["status"] == "skipped"
    assert manifest["surfaces"]["se_stats"]["status"] == "skipped"
    snap = alert_dir / "evidence" / "config_snapshot"
    assert (snap / "configs__patients.yml").is_file()
    assert (snap / "dag__hourly.py").is_file()
    assert (snap / "env__DEV.yaml").is_file()
    assert sorted(manifest["tables"]) == [
        "unity.bronze.synthea_claims",
        "unity.bronze.synthea_patients",
    ]


# --------------------------------------------------------------------------
# Failure isolation: a dead stack yields `unavailable`, never an exception
# --------------------------------------------------------------------------
def test_unreachable_airflow_lands_in_manifest(workspace, monkeypatch, tmp_path: Path):
    ws, _proj = workspace
    out = tmp_path / "ev"

    class Dead:
        def __init__(self, *a, **k): ...

        def dag_run(self, *a):
            raise rca_common.HttpError(None, "http://x", "connection refused")

        def task_instances(self, *a, **k):
            raise rca_common.HttpError(None, "http://x", "connection refused")

        def task_log(self, *a):
            raise rca_common.HttpError(404, "http://x", "not found")

    monkeypatch.setattr(ce, "AirflowClient", Dead)
    m = ce.Manifest(_alert(), offline=False)
    ce.collect_airflow(_alert(), out, m)
    assert m.data["surfaces"]["airflow_dagrun"]["status"] == "unavailable"
    assert "connection refused" in m.data["surfaces"]["airflow_dagrun"]["reason"]
    assert m.data["surfaces"]["airflow_task_log"]["status"] == "unavailable"
    assert "404" in m.data["surfaces"]["airflow_task_log"]["reason"]


def test_docker_failure_is_isolated_per_service(workspace, monkeypatch, tmp_path: Path):
    _ws, proj = workspace
    out = tmp_path / "ev"
    out.mkdir()

    def fake_run(argv, timeout=60, cwd=None):
        if "ps" in argv:
            return 0, '{"Service":"airflow","State":"running"}\n', ""
        if "marquez" in argv:
            return 1, "", "no such service: marquez"
        return 0, "line1\nline2\n", ""

    monkeypatch.setattr(ce, "run_cmd", fake_run)
    m = ce.Manifest(_alert(), offline=False)
    ce.collect_docker(_alert(), proj, out, m, 30)
    assert m.data["surfaces"]["docker_ps"]["status"] == "ok"
    assert m.data["surfaces"]["docker_logs_airflow"]["status"] == "ok"
    assert m.data["surfaces"]["docker_logs_marquez"]["status"] == "unavailable"
    assert (out / "docker_logs_airflow.log").read_text().startswith("line1")


def test_beeline_refuses_non_read_sql(workspace):
    _ws, proj = workspace
    with pytest.raises(ValueError):
        ce.beeline(proj, "DELETE FROM unity.bronze.x")
    with pytest.raises(ValueError):
        ce.beeline(proj, "RESTORE TABLE unity.gold.x TO VERSION AS OF 1")


def test_se_collection_never_filters_by_ds(workspace, monkeypatch, tmp_path: Path):
    _ws, proj = workspace
    seen: list[str] = []

    def fake_beeline(project_root, sql):
        seen.append(sql)
        return "meta_dq_run_id,meta_dq_run_datetime\nabc,2026-10-14 15:00:00\n"

    monkeypatch.setattr(ce, "beeline", fake_beeline)
    m = ce.Manifest(_alert(), offline=False)
    ce.collect_se(["unity.bronze.synthea_patients"], proj, tmp_path, m)
    assert all("ds" not in s.lower().split("where")[-1] for s in seen if "where" in s.lower())
    assert all("meta_dq_run_date =" not in s for s in seen)
    assert m.data["surfaces"]["se_stats"]["tables_with_rows"] == ["unity.bronze.synthea_patients"]


def test_offline_preserves_precollected_bundle(workspace):
    ws, _proj = workspace
    alert_dir = ws / "outputs" / "rca" / "v1" / "ALERT-1-reconciliation_bronze"
    ev = alert_dir / "evidence"
    ev.mkdir(parents=True)
    (alert_dir / "alert.json").write_text(json.dumps(_alert()))
    (ev / "airflow_task_log_try3.log").write_text("SE_RUN_MISSING_FOR_DS=2026-10-14\n")
    (ev / "se_stats.json").write_text("{}")
    (ev / "manifest.json").write_text(
        json.dumps(
            {
                "collected_at": "2026-10-14T15:31:02+00:00",
                "surfaces": {
                    "airflow_task_log": {
                        "status": "ok",
                        "file": "airflow_task_log_try3.log",
                        "try_number": 3,
                    },
                    "se_stats": {"status": "ok", "file": "se_stats.json", "tables": 2},
                    "marquez_runs": {"status": "unavailable", "reason": "no jobs"},
                },
            }
        )
    )
    rc = ce.main(
        ["--alert", str(alert_dir / "alert.json"), "--offline", "--workspace-root", str(ws)]
    )
    assert rc == 0
    m = json.loads((ev / "manifest.json").read_text())
    assert m["surfaces"]["airflow_task_log"] == {
        "status": "ok",
        "file": "airflow_task_log_try3.log",
        "try_number": 3,
        "pre_collected": True,
    }
    assert (
        m["surfaces"]["se_stats"]["pre_collected"] is True
        and m["surfaces"]["se_stats"]["tables"] == 2
    )
    assert m["surfaces"]["marquez_runs"]["status"] == "unavailable"
    assert m["surfaces"]["uc_health"]["status"] == "skipped"
    assert m["pre_collected_at"] == "2026-10-14T15:31:02+00:00"
    assert (ev / "airflow_task_log_try3.log").read_text().startswith("SE_RUN_MISSING")


def test_task_log_requests_json_not_text_plain(monkeypatch):
    """Airflow 3.2 answers 406 to Accept: text/plain; the client must ask for JSON."""
    seen: dict = {}

    def fake_get(url, headers=None, timeout=0):
        seen["accept"] = (headers or {}).get("Accept")
        return 200, '{"content": [{"event": "line one"}, {"event": "line two"}]}'

    monkeypatch.setattr(rca_common, "http_get", fake_get)
    client = rca_common.AirflowClient(api="http://x/api/v2")
    client._token = "t"
    text = client.task_log("dag", "run", "task", 1)
    assert seen["accept"] == "application/json"
    assert text == "line one\nline two"


def test_beeline_failure_on_every_table_is_unavailable(workspace, monkeypatch, tmp_path: Path):
    _ws, proj = workspace

    def dead_beeline(project_root, sql):
        raise RuntimeError("Failed to open new session: java.net.ConnectException")

    monkeypatch.setattr(ce, "beeline", dead_beeline)
    m = ce.Manifest(_alert(), offline=False)
    ce.collect_se(["unity.bronze.synthea_allergies"], proj, tmp_path, m)
    ce.collect_delta(["unity.bronze.synthea_allergies"], proj, tmp_path, m)
    for surface in ("se_stats", "se_errors", "delta_history"):
        entry = m.data["surfaces"][surface]
        assert entry["status"] == "unavailable", surface
        assert "ConnectException" in entry["reason"]
        assert entry["file"].endswith(".json")  # the error file is still written for the report


def test_beeline_partial_failure_stays_ok_with_tables_failed(workspace, monkeypatch, tmp_path):
    _ws, proj = workspace

    def flaky_beeline(project_root, sql):
        if "synthea_claims" in sql:
            raise RuntimeError("table not found")
        return "meta_dq_run_id,meta_dq_run_datetime\nabc,2026-10-14 15:00:00\n"

    monkeypatch.setattr(ce, "beeline", flaky_beeline)
    m = ce.Manifest(_alert(), offline=False)
    tables = ["unity.bronze.synthea_patients", "unity.bronze.synthea_claims"]
    ce.collect_se(tables, proj, tmp_path, m)
    entry = m.data["surfaces"]["se_stats"]
    assert entry["status"] == "ok"
    assert entry["tables_failed"] == ["unity.bronze.synthea_claims"]
    assert entry["tables_with_rows"] == ["unity.bronze.synthea_patients"]
