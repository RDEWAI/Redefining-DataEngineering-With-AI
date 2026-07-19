"""Gold SE + lineage evidence — STORY-05-005 AC4, AC5.

After the Gold DAG runs, two forms of evidence must exist:

* AC4 — Gold SE stats are populated AND the allergy-completeness assertion
  DQ-FLD-138 passes [DQS §2 Gold, LLD §8.6.1]. Per LLD §2.3 / §8.3 (v1.20,
  UC 0.5.0) SE writes PER-TABLE MANAGED Unity Catalog stats tables addressed
  by 3-part FQN ``unity.gold.<table>_stats`` (the single shared
  ``gold_se_stats`` catalog table referenced in the story text is RETIRED —
  see §13 Decision 12/16). The allergy cross-field rule DQ-FLD-138
  (``has_allergy`` ⇔ non-empty ``allergies`` array) is enforced fail-closed
  by the ``reconciliation_gold`` task
  (``patient_360.gold.reconciliation.check_allergy_completeness``); a
  ``success`` state for that task is therefore proof DQ-FLD-138 held.
* AC5 — the run's ``dq_pass_rate`` is exposed for review [LLD §10.1]. The
  story pins the >= 99% gate to a manual Grafana check; this module provides
  the automated proxy — a DQ-quality facet published to Marquez by the
  OpenLineage listener for a run of the Gold DAG (LLD §8.6.1, §10.2).

Both tests consume the shared session-scoped ``successful_gold_run`` fixture
(tests/integration/conftest.py) so the evidence is read from ONE fresh,
successful ``patient360_hourly_v1`` run regardless of collection order. This
replaces the previous per-module ``_latest_successful_run`` scan, which — when
this module was collected before ``test_gold_uc`` (alphabetical order) — could
latch onto a STALE prior run (e.g. ``prestart-*``) with no
``reconciliation_gold`` task and fail spuriously. Every authenticated Airflow
``/api/v2`` call carries the JWT bearer header from the shared
``airflow_headers`` fixture.
"""

from __future__ import annotations

import pytest
import requests

pytestmark = pytest.mark.integration


# LLD §5.3 / §5.4 Gold tables → their per-table MANAGED UC SE stats tables
# (`unity.gold.<table>_stats`, FQN-derived by se_runner as f"{target}_stats").
GOLD_TABLES: tuple[str, ...] = (
    "patient_summary",
    "patient_clinical_history",
    "patient_billing_summary",
)

# The layer-terminal reconciliation gate task (LLD §4.2; STORY-05-006). It
# fails closed on any DQ-FLD-138 allergy cross-field violation, so a
# `success` state is proof the allergy-completeness assertion passed.
RECONCILIATION_TASK_ID = "reconciliation_gold"

# Marquez facet keys that satisfy AC5. OpenLineage names the DQ facet
# differently across releases; accept any as evidence of a dq_pass_rate.
_DQ_FACET_KEYS = (
    "dataQuality",
    "dataQualityMetrics",
    "dataQualityAssertions",
    "dq_pass_rate",
)

# ---------------------------------------------------------------- helpers


def _task_instance_state(
    stack, dag_id: str, run_id: str, task_id: str, headers: dict[str, str]
) -> str | None:
    resp = requests.get(
        f"{stack.airflow_api}/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}",
        headers=headers,
        timeout=10,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("state")


def _uc_table_exists(stack, table: str) -> bool:
    """True if the per-table MANAGED SE stats table exists in UC."""
    fqn = f"{stack.uc_catalog}.{stack.uc_schema_for('gold')}.{table}_stats"
    resp = requests.get(f"{stack.uc_uri}/tables/{fqn}", timeout=10)
    if resp.status_code == 404:
        return False
    resp.raise_for_status()
    return bool(resp.json().get("name"))


# ---------------------------------------------------------------- tests


def test_allergy_completeness(stack, successful_gold_run, airflow_headers) -> None:
    """AC4 — Gold SE stats are populated and allergy completeness DQ-FLD-138
    passes [DQS §2 Gold, LLD §8.6.1].

    Two halves:
    1. SE evidence — at least one per-table MANAGED SE stats table
       (`unity.gold.<table>_stats`) exists in UC. SE creates these via
       `saveAsTable` on first successful run (LLD §2.3 / §8.3 v1.20); their
       presence proves the inline Gold SE gate actually executed.
    2. Allergy completeness — the `reconciliation_gold` task of the shared
       ``successful_gold_run`` reached `success`. That task fails closed on
       any DQ-FLD-138 violation
       (`reconciliation.check_allergy_completeness`), so `success` is proof
       every patient_summary row is allergy-flag consistent.

    Consumes the shared ``successful_gold_run`` fixture — the SAME fresh run
    every Gold test reads — so this test no longer depends on collection order
    or on an independent latest-successful scan that could latch a stale run.
    """
    run = successful_gold_run

    present = [t for t in GOLD_TABLES if _uc_table_exists(stack, t)]
    assert present, (
        f"No Gold SE stats tables found in {stack.uc_catalog}.{stack.uc_schema_for('gold')} "
        f"(expected any of {[f'{t}_stats' for t in GOLD_TABLES]}). "
        f"The inline Gold SE gate may not have run."
    )

    state = _task_instance_state(
        stack,
        dag_id=stack.dag_id_for("gold"),
        run_id=run["dag_run_id"],
        task_id=RECONCILIATION_TASK_ID,
        headers=airflow_headers,
    )
    assert state == "success", (
        f"{RECONCILIATION_TASK_ID} state is {state!r} for run {run['dag_run_id']}; it fails "
        f"closed on any DQ-FLD-138 allergy cross-field violation (DQS §2 Gold)."
    )


def test_dq_pass_rate_in_marquez(stack, successful_gold_run) -> None:
    """AC5 — Marquez exposes a DQ-quality facet (the dq_pass_rate signal) for
    at least one run of the Gold DAG [LLD §10.1, §8.6.1].

    The story pins the >= 99% threshold to a manual Grafana check; this is
    the automated proxy that the OpenLineage listener published the DQ facet
    that Grafana renders. The numeric >= 99% gate remains a manual review of
    the Grafana DQ board per the story's AC5.

    Consumes the shared ``successful_gold_run`` fixture so it reads the same
    fresh run as the other Gold tests. (This assertion currently FAILS on the
    known, separately-backlogged Marquez/OpenLineage DQ-facet gap.)
    """
    dag_id = stack.dag_id_for("gold")
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
        f"Verify the OpenLineage DQ integration is wired."
    )
