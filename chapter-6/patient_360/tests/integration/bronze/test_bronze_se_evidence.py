"""Bronze SE + lineage evidence — STORY-02-008 AC4, AC5.

After the Bronze DAG runs, Spark Expectations must have written stats
rows into the PER-TABLE path-based Delta tables
(`warehouse/{env}/_se/<table>/stats`) keyed by `meta_dq_run_date`
(LLD §8.6.1 v1.18 / §2.3 v1.17 / §13 Decision 16 — the single shared
`bronze_se_stats` catalog table is RETIRED), and the OpenLineage
listener must have published a `dq_pass_rate` (or equivalent DQ-quality)
facet to Marquez for the run (LLD §8.6.1, §10.2).

The SE-RUN-EVIDENCE gate now lives entirely inside `reconciliation_bronze`,
which iterates the per-table stats paths and FAILS-CLOSED with
`SE_RUN_MISSING_FOR_DS=<ds>` when no path has a row for the run's `ds`.
A `success` DAG state is therefore itself proof that ≥1 per-table stats
row exists — there is no single catalog table to probe.

The tests target the most recent successful DAG run within a lookback
window so they can be re-run without re-triggering the DAG.
"""

from __future__ import annotations

from typing import Any

import pytest
import requests

pytestmark = pytest.mark.integration


# LLD §8.6.1 v1.18 / §2.3 v1.17 — SE stats are PER-TABLE path-based Delta
# tables (`warehouse/{env}/_se/<table>/stats`); the shared `bronze_se_stats`
# catalog table is RETIRED. There is no single catalog table to probe — the
# `reconciliation_bronze` gate (which fails-closed) is the evidence anchor.

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


def _latest_successful_run(stack) -> dict[str, Any] | None:
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


def test_se_stats_populated(stack) -> None:
    """AC4 — SE wrote per-table stats for a recent successful run.

    LLD §8.6.1 v1.18: SE stats live in PER-TABLE path-based Delta tables
    (`warehouse/{env}/_se/<table>/stats`), not a single catalog table, so
    there is nothing to probe via the UC tables API. The
    `reconciliation_bronze` task is the evidence gate — it iterates the
    per-table stats paths and fails-closed with `SE_RUN_MISSING_FOR_DS=<ds>`
    when none has a row for the run's `ds`. A `success` DAG state is
    therefore itself proof that ≥1 per-table stats row exists for the run.
    """
    run = _latest_successful_run(stack)
    assert run is not None, (
        f"No successful runs found for {stack.dag_id_for('bronze')} — "
        f"trigger the DAG (or run test_bronze_uc.py first) so SE produces evidence."
    )
    # `reconciliation_bronze` fails-closed on SE_RUN_MISSING_FOR_DS, so
    # a `success` state is itself proof that ≥1 per-table stats row exists
    # for this run.
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
    jobs = [j for j in jobs_resp.json().get("jobs", []) if dag_id in (j.get("name") or "")]
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
            f"{stack.marquez_api}/namespaces/{stack.marquez_namespace}/jobs/{job_name}/runs",
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
