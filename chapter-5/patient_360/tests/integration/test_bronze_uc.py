"""End-to-end Bronze integration test — STORY-02-007.

Triggers ``patient360_hourly_v1`` against the local Airflow + Unity
Catalog OSS docker stack, waits for completion, then asserts:

- All 13 ``unity.bronze.synthea_*`` tables landed in UC.
- ``unity.bronze.bronze_se_stats`` has ≥ 1 row with the run's
  ``meta_dq_run_id`` (LLD §8.6.1).
- At least the 6 critical ``<table>_error`` Delta tables exist
  (created by SE — LLD §8.2).
- ``reconciliation_bronze`` succeeded (no SE_RUN_MISSING_FOR_DS).
- Source row counts match Bronze row counts within ±1 % (DQS §4).

Marked ``integration`` so unit suites skip it. Requires a running
docker-compose stack and ``airflow`` CLI on PATH.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

DAG_ID = "patient360_hourly_v1"
UC_CATALOG = "unity"
UC_SCHEMA = "bronze"
UC_BASE = os.environ.get("UC_URI", "http://localhost:8080")
DEFAULT_DS = os.environ.get("BRONZE_INT_DS", time.strftime("%Y-%m-%d"))
EXPECTED_TABLES = {
    f"synthea_{t}"
    for t in (
        "patients",
        "encounters",
        "conditions",
        "medications",
        "observations",
        "allergies",
        "immunizations",
        "procedures",
        "claims",
        "careplans",
        "organizations",
        "providers",
        "payers",
    )
}
CRITICAL_TABLES = {
    "synthea_patients",
    "synthea_encounters",
    "synthea_allergies",
    "synthea_organizations",
    "synthea_providers",
    "synthea_payers",
}


def _airflow_available() -> bool:
    return shutil.which("airflow") is not None


def _uc_get(path: str):
    import requests  # local import to keep collection working without requests

    return requests.get(f"{UC_BASE}/api/2.1/unity-catalog/{path}", timeout=10)


# --------------------------------------------------------------------------- #
# DAG trigger + poll                                                          #
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def dag_run_id():
    if not _airflow_available():
        pytest.skip("airflow CLI not available")
    subprocess.check_output(
        ["airflow", "dags", "trigger", DAG_ID, "--conf", json.dumps({"ds": DEFAULT_DS})],
        text=True,
    )
    # Poll for completion (max 10 minutes per AC).
    deadline = time.time() + 600
    while time.time() < deadline:
        runs = subprocess.check_output(
            ["airflow", "dags", "list-runs", "-d", DAG_ID, "-o", "json"],
            text=True,
        )
        runs_j = json.loads(runs) if runs.strip() else []
        latest = runs_j[0] if runs_j else None
        if latest and latest.get("state") in {"success", "failed"}:
            assert latest["state"] == "success", f"DAG run failed: {latest}"
            return latest.get("run_id") or latest.get("dag_run_id")
        time.sleep(15)
    pytest.fail("DAG run did not complete within 10 minutes")


def test_dag_trigger(dag_run_id):
    assert dag_run_id, "DAG trigger returned no run id"


# --------------------------------------------------------------------------- #
# UC table existence                                                          #
# --------------------------------------------------------------------------- #


def test_uc_tables_exist(dag_run_id):
    pytest.importorskip("requests")
    r = _uc_get(f"tables?catalog_name={UC_CATALOG}&schema_name={UC_SCHEMA}")
    r.raise_for_status()
    names = {t["name"] for t in r.json().get("tables", [])}
    missing = EXPECTED_TABLES - names
    assert not missing, f"missing UC tables: {missing}"


# --------------------------------------------------------------------------- #
# SE artefacts                                                                 #
# --------------------------------------------------------------------------- #


def test_se_stats_populated(dag_run_id):
    pytest.importorskip("pyspark")
    from patient_360.bronze.ingestion_runner import _build_spark

    spark = _build_spark("test_se_stats")
    try:
        n = spark.sql(
            f"SELECT count(*) AS n FROM {UC_CATALOG}.{UC_SCHEMA}.bronze_se_stats "
            f"WHERE meta_dq_run_id = '{dag_run_id}' "
            f"AND meta_dq_run_date = '{DEFAULT_DS}'"
        ).collect()[0]["n"]
        assert n >= 1, "bronze_se_stats has no rows for this run_id/ds"
    finally:
        spark.stop()


def test_se_error_tables(dag_run_id):
    pytest.importorskip("requests")
    r = _uc_get(f"tables?catalog_name={UC_CATALOG}&schema_name={UC_SCHEMA}")
    r.raise_for_status()
    names = {t["name"] for t in r.json().get("tables", [])}
    expected = {f"{t}_error" for t in CRITICAL_TABLES}
    missing = expected - names
    assert not missing, f"missing SE _error tables: {missing}"


def test_se_artifacts(dag_run_id):
    """Aggregated assertion — both stats AND error tables exist."""
    test_se_stats_populated(dag_run_id)
    test_se_error_tables(dag_run_id)


# --------------------------------------------------------------------------- #
# Reconciliation                                                              #
# --------------------------------------------------------------------------- #


def test_reconciliation_passes(dag_run_id):
    if not _airflow_available():
        pytest.skip("airflow CLI not available")
    state = subprocess.check_output(
        ["airflow", "tasks", "states-for-dag-run", DAG_ID, dag_run_id, "-o", "json"],
        text=True,
    )
    states = json.loads(state) if state.strip() else []
    recon = next((s for s in states if s.get("task_id") == "reconciliation_bronze"), None)
    assert recon is not None, "reconciliation_bronze task not found"
    assert recon["state"] == "success", f"reconciliation_bronze did not succeed: {recon}"


# --------------------------------------------------------------------------- #
# Row-count parity                                                            #
# --------------------------------------------------------------------------- #


def test_row_count_parity(dag_run_id):
    pytest.importorskip("pyspark")
    pytest.importorskip("duckdb")
    import duckdb

    from patient_360.bronze.ingestion_runner import _build_spark

    db_path = os.environ.get("DUCKDB_PATH", "data/duckdb/raw.db")
    if not Path(db_path).exists():
        pytest.skip(f"DuckDB source not present: {db_path}")

    src_con = duckdb.connect(db_path, read_only=True)
    spark = _build_spark("test_parity")
    try:
        for table in sorted(EXPECTED_TABLES):
            src_table = table.replace("synthea_", "")
            src_n = src_con.execute(f'SELECT count(*) FROM synthea."{src_table}"').fetchone()[0]
            br_n = spark.sql(
                f"SELECT count(*) AS n FROM {UC_CATALOG}.{UC_SCHEMA}.{table} "
                f"WHERE ds = '{DEFAULT_DS}'"
            ).collect()[0]["n"]
            if src_n == 0:
                assert br_n == 0, f"{table}: bronze rows {br_n} vs source 0"
                continue
            tol = max(1, src_n * 0.01)
            assert abs(br_n - src_n) <= tol, (
                f"{table}: bronze {br_n} vs source {src_n} " f"(tolerance ±1% = {tol})"
            )
    finally:
        spark.stop()
        src_con.close()
