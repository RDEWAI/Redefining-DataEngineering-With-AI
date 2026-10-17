"""Unit tests for find_alert.py (alert intake) and the LLD §8.5 classifier."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import find_alert  # noqa: E402
import rca_common  # noqa: E402


# --------------------------------------------------------------------------
# Classifier
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "task_id", "condition", "severity"),
    [
        (
            "SE_RUN_MISSING_FOR_DS=2026-10-14 layer=bronze",
            "reconciliation_bronze",
            "Pipeline task failure after all retries",
            "CRITICAL",
        ),
        (
            "GOLD_RECON_FAILED_FOR_DS=2026-10-14 — 2 check(s) failed: DQ-STA-017",
            "reconciliation_gold",
            "Row count drop > 5% from baseline (query_dq)",
            "CRITICAL",
        ),
        (
            "java.net.ConnectException: Connection refused (localhost:8080)",
            "ingest_patients",
            "UC OSS unreachable after circuit-breaker retries",
            "CRITICAL",
        ),
        (
            "spark-submit ... Error code is: -9",
            "transform_encounters_silver",
            "Pipeline task failure after all retries",
            "CRITICAL",
        ),
        (
            "ModuleNotFoundError: No module named 'spark_expectations'",
            "ingest_claims",
            "SE ImportError at runtime",
            "CRITICAL",
        ),
        (
            "row_dq failed",
            "transform_allergies_silver",
            "Allergy DQ failure (any clinical_allergies rule)",
            "CRITICAL",
        ),
        (
            "AirflowTaskTimeout: Timeout, PID: 42",
            "build_patient_summary_gold",
            "Pipeline runtime > 45 min",
            "WARNING",
        ),
        (
            "something unexpected",
            "build_patient_summary_gold",
            "Pipeline task failure after all retries",
            "CRITICAL",
        ),
    ],
)
def test_classify_maps_markers_to_lld_85(text, task_id, condition, severity):
    rule = rca_common.classify(text, task_id)
    assert rule.condition == condition
    assert rule.severity == severity


def test_explicit_markers_win_over_allergy_task_name():
    """Live RCA 2026-10-15: ingest_allergies failed on a UC outage and was mislabelled
    as an allergy DQ failure because the old rule matched the task name alone."""
    uc = rca_common.classify(
        "SparkExpectationsMiscException: error occurred while saving the data into the "
        "stats table unity.bronze.synthea_allergies_stats\njava.net.ConnectException",
        "bronze_ingestion.ingest_allergies",
    )
    assert uc.condition == "UC OSS unreachable after circuit-breaker retries"
    gate = rca_common.classify("SE_RUN_MISSING_FOR_DS=2026-10-14", "transform_allergies_silver")
    assert gate.failure_class.startswith("SE run-evidence gate")
    catalog = rca_common.classify(
        "NoSuchCatalogException: Catalog not found: unity", "bronze_ingestion.ingest_allergies"
    )
    assert catalog.condition == "UC OSS unreachable after circuit-breaker retries"


def test_allergy_rule_needs_a_dq_signal():
    dq = rca_common.classify(
        "rule DQ_FLD_034 action_if_failed: fail breached", "transform_allergies_silver"
    )
    assert "Allergy" in dq.condition
    assert dq.response_time == "10 min"
    # same table, no DQ signal and no explicit marker -> generic task failure, not allergy DQ
    plain = rca_common.classify("something unexpected", "transform_allergies_silver")
    assert plain.condition == "Pipeline task failure after all retries"


def test_ds_from_run_id():
    assert rca_common.ds_from_run_id("scheduled__2026-10-14T15:00:00+00:00") == "2026-10-14"
    assert rca_common.ds_from_run_id("manual__abc") is None
    assert rca_common.ds_from_run_id(None) is None


def test_validate_alert_contract():
    good = json.loads((SCRIPTS.parent / "examples" / "ALERT-example.json").read_text())
    assert rca_common.validate_alert(good) == []
    bad = dict(good, severity="HIGH", source="airflow", dag_id=None, extra="x")
    problems = rca_common.validate_alert(bad)
    assert any("severity" in p for p in problems)
    assert any("dag_id" in p for p in problems)
    assert any("unknown fields" in p for p in problems)


# --------------------------------------------------------------------------
# Intake modes with a mocked Airflow client
# --------------------------------------------------------------------------
class FakeAirflow:
    """Stands in for rca_common.AirflowClient; GET-only surface used by find_alert."""

    def __init__(self, logs: dict[str, str] | None = None):
        self.logs = logs or {}
        self.calls: list[str] = []

    def dags(self, limit=100):
        return [{"dag_id": "patient360_hourly_v1"}]

    def dag_runs(self, dag_id, state="failed", limit=5):
        self.calls.append(f"dag_runs:{dag_id}:{state}")
        return [
            {
                "dag_run_id": "scheduled__2026-10-14T15:00:00+00:00",
                "state": "failed",
                "end_date": "2026-10-14T15:30:12+00:00",
            }
        ]

    def task_instances(self, dag_id, run_id, limit=200):
        return [
            {
                "task_id": "ingest_patients",
                "state": "success",
                "try_number": 1,
                "end_date": "2026-10-14T15:05:00+00:00",
            },
            {
                "task_id": "reconciliation_bronze",
                "state": "failed",
                "try_number": 3,
                "end_date": "2026-10-14T15:30:12+00:00",
            },
            {
                "task_id": "transform_patients_silver",
                "state": "upstream_failed",
                "try_number": 0,
                "end_date": "2026-10-14T15:30:13+00:00",
            },
        ]

    def task_log(self, dag_id, run_id, task_id, try_number):
        key = f"{task_id}:{try_number}"
        if key not in self.logs:
            raise rca_common.HttpError(404, key, "not found")
        return self.logs[key]


def test_latest_picks_the_failed_task_not_upstream_failed():
    client = FakeAirflow(
        {"reconciliation_bronze:3": "...\nSE_RUN_MISSING_FOR_DS=2026-10-14 layer=bronze env=DEV\n"}
    )
    alert = find_alert.latest(client, "DEV")
    assert alert["task_id"] == "reconciliation_bronze"
    assert alert["try_number"] == 3
    assert alert["ds"] == "2026-10-14"
    assert alert["message"].startswith("SE_RUN_MISSING_FOR_DS=2026-10-14")
    assert alert["severity"] == "CRITICAL"
    assert alert["alert_id"].endswith("-reconciliation_bronze")
    assert rca_common.validate_alert(alert) == []


def test_dag_task_two_part_spec():
    client = FakeAirflow()
    alert = find_alert.dag_task(client, "patient360_hourly_v1/reconciliation_bronze", "DEV")
    assert alert["dag_id"] == "patient360_hourly_v1"
    assert alert["source"] == "airflow"


def test_dag_task_unknown_task_exits():
    with pytest.raises(SystemExit):
        find_alert.dag_task(FakeAirflow(), "patient360_hourly_v1/no_such_task", "DEV")


def test_missing_log_is_tolerated():
    alert = find_alert.latest(FakeAirflow(), "DEV")  # no logs at all → 404 everywhere
    assert alert["task_id"] == "reconciliation_bronze"
    assert "failed" in alert["message"]


def test_from_text_binds_to_matching_log():
    client = FakeAirflow(
        {"reconciliation_bronze:3": "boom\nGOLD_RECON_FAILED_FOR_DS=2026-10-14 x\n"}
    )
    alert = find_alert.from_text(client, "GOLD_RECON_FAILED_FOR_DS=2026-10-14 x", "DEV")
    assert alert["source"] == "airflow"
    assert alert["task_id"] == "reconciliation_bronze"


def test_from_text_without_airflow_builds_manual_alert():
    alert = find_alert.from_text(None, "Error code is: -9", "DEV")
    assert alert["source"] == "manual"
    assert "OOM" in alert["failure_class"]
    assert rca_common.validate_alert(alert) == []


def test_from_file_fills_defaults(tmp_path: Path):
    p = tmp_path / "ALERT-x.json"
    p.write_text(
        json.dumps(
            {
                "task_id": "ingest_claims",
                "message": "No module named 'spark_expectations'",
                "run_id": "scheduled__2026-10-01T00:00:00+00:00",
            }
        )
    )
    alert = find_alert.from_file(p, "STAGING")
    assert alert["env"] == "STAGING"
    assert alert["ds"] == "2026-10-01"
    assert alert["condition"] == "SE ImportError at runtime"
    assert alert["alert_id"].startswith("ALERT-")


def test_cli_writes_alert_json(tmp_path: Path, monkeypatch):
    ws = tmp_path / "ws"
    (ws / "outputs" / "stories").mkdir(parents=True)
    proj = ws / "proj"
    (proj / "src" / "proj").mkdir(parents=True)
    (proj / "pyproject.toml").write_text("[project]\nname='proj'\n")
    example = SCRIPTS.parent / "examples" / "ALERT-example.json"
    rc = find_alert.main([str(example), "--no-airflow", "--workspace-root", str(ws)])
    assert rc == 0
    written = (
        ws
        / "outputs"
        / "rca"
        / "v1"
        / "ALERT-20261014T153012Z-reconciliation_bronze"
        / "alert.json"
    )
    assert written.is_file()
    assert json.loads(written.read_text())["task_id"] == "reconciliation_bronze"
