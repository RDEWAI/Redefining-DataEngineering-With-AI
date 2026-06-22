"""Bronze integration test — STORY-02-008 AC1-AC3.

Triggers the `patient360_hourly_v1` DAG against the local Airflow REST
API, waits for the run to land, then asserts every Bronze Delta table
declared in LLD §4.2 is registered in Unity Catalog OSS at
`{catalog}.{schema}.{table}` with the three metadata columns required
by LLD §2.3 (`ds`, `_ingested_at`, `_source_batch_id`).
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import pytest
import requests

pytestmark = pytest.mark.integration


# LLD §4.2 Bronze TaskGroup — 13 source tables, one Delta table each.
LAYER_TABLES: tuple[str, ...] = (
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

# LLD §2.3 ingestion runner contract (change log 1.19) — four metadata
# columns are added to every Bronze table before the Delta write.
METADATA_COLUMNS: tuple[str, ...] = (
    "ds",
    "_ingested_at",
    "_source_batch_id",
    "_source_file",
)


# ---------------------------------------------------------------- helpers


def _trigger_dag(stack, dag_id: str) -> str:
    run_id = f"integration-{uuid.uuid4().hex[:8]}"
    resp = requests.post(
        f"{stack.airflow_api}/dags/{dag_id}/dagRuns",
        json={"dag_run_id": run_id},
        auth=stack.airflow_auth(),
        timeout=10,
    )
    if resp.status_code not in (200, 201):
        pytest.fail(f"Airflow refused to trigger {dag_id} (HTTP {resp.status_code}): {resp.text}")
    return run_id


def _poll_run(stack, dag_id: str, run_id: str, deadline_sec: int = 1800) -> dict[str, Any]:
    """Poll until the run reaches a terminal state or the deadline elapses."""
    started = time.monotonic()
    while time.monotonic() - started < deadline_sec:
        resp = requests.get(
            f"{stack.airflow_api}/dags/{dag_id}/dagRuns/{run_id}",
            auth=stack.airflow_auth(),
            timeout=10,
        )
        resp.raise_for_status()
        payload = resp.json()
        state = payload.get("state")
        if state in ("success", "failed"):
            return payload
        time.sleep(10)
    pytest.fail(f"DAG run {dag_id}/{run_id} did not complete within {deadline_sec}s")


# ---------------------------------------------------------------- fixtures


@pytest.fixture(scope="module")
def successful_dag_run(stack) -> dict[str, Any]:
    dag_id = stack.dag_id_for("bronze")
    run_id = _trigger_dag(stack, dag_id)
    payload = _poll_run(stack, dag_id, run_id)
    if payload.get("state") != "success":
        pytest.fail(f"DAG run {dag_id}/{run_id} ended in state {payload.get('state')!r}: {payload}")
    return payload


# ---------------------------------------------------------------- tests


def test_dag_run_succeeds(successful_dag_run: dict[str, Any]) -> None:
    """AC1 — `patient360_hourly_v1` triggers and completes successfully."""
    assert successful_dag_run["state"] == "success", successful_dag_run


def test_13_bronze_tables_in_uc(stack, successful_dag_run) -> None:
    """AC2 — every Bronze table is registered in Unity Catalog OSS."""
    resp = requests.get(
        f"{stack.uc_uri}/tables",
        params={
            "catalog_name": stack.uc_catalog,
            "schema_name": stack.uc_schema_for("bronze"),
        },
        timeout=10,
    )
    resp.raise_for_status()
    body = resp.json() or {}
    listed = {t.get("name") for t in body.get("tables", []) if t.get("name")}

    missing = [t for t in LAYER_TABLES if t not in listed]
    assert not missing, (
        f"Missing Bronze tables in {stack.uc_catalog}.{stack.uc_schema_for('bronze')}: "
        f"{missing}. Found: {sorted(listed)}"
    )


@pytest.mark.parametrize("table", LAYER_TABLES)
def test_metadata_columns_populated(stack, successful_dag_run, table: str) -> None:
    """AC3 — every Bronze table carries the three metadata columns from LLD §2.3."""
    catalog = stack.uc_catalog
    schema = stack.uc_schema_for("bronze")
    full = f"{catalog}.{schema}.{table}"
    resp = requests.get(f"{stack.uc_uri}/tables/{full}", timeout=10)
    if resp.status_code == 404:
        pytest.fail(f"UC table {full} not found")
    resp.raise_for_status()
    columns = {c.get("name") for c in resp.json().get("columns", []) if c.get("name")}
    missing = [c for c in METADATA_COLUMNS if c not in columns]
    assert not missing, (
        f"Table {full} is missing metadata columns {missing}. Columns: {sorted(columns)}"
    )
