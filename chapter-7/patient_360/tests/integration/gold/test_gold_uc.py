"""Gold integration test — STORY-05-005 AC1, AC2, AC3.

Triggers the ``patient360_hourly_v1`` DAG against the local Airflow REST
API (Airflow 3.x ``/api/v2``, JWT bearer auth), waits for the run to land,
then asserts:

* AC1 — the DAG (Gold builders + ``reconciliation_gold``) runs to success
  on local Airflow [LLD §4.2].
* AC2 — all 3 Gold consumer tables are registered in Unity Catalog OSS at
  ``unity.gold.*`` [LLD §3.2 / §5.3 / §5.4].
* AC3 — ``patient_summary`` holds exactly 5,767 rows (one per current
  patient; DQ-FLD-106 / NFR-4) [DQS §4, LLD §10.4].

AC3 is enforced by the ``reconciliation_gold`` task, which fails closed
with a non-``success`` state when ``patient_summary`` row count !=
``EXPECTED_PATIENT_COUNT`` (see ``patient_360.gold.reconciliation``:
``check_patient_completeness`` / DQ-FLD-106 / DQ-REC-010). Unity Catalog
OSS exposes no row-count endpoint, so the test asserts the fail-closed
gate task instance reached ``success`` — that is itself proof the count
equals 5,767 — mirroring the Bronze SE-evidence idiom.

Mirrors the Bronze integration suite (tests/integration/bronze/) — same
DAG-trigger + UC-table-probe pattern, HTTP-only (no data plane). All
authenticated Airflow calls carry the ``Authorization: Bearer`` header
from the shared ``airflow_headers`` fixture.

Every test here consumes the shared session-scoped ``successful_gold_run``
fixture (tests/integration/conftest.py) rather than triggering its own run.
That makes the whole Gold integration suite order-independent: the
``test_gold_se_evidence`` module (collected first, alphabetically) and this
module read evidence from the SAME fresh successful run instead of racing to
trigger / scan for an arbitrary latest-successful run.
"""

from __future__ import annotations

from typing import Any

import pytest
import requests

pytestmark = pytest.mark.integration


# LLD §5.3 / §5.4 Gold TaskGroup (`gold_build`) — 3 consumer tables under
# `unity.gold.*`. Read from the LLD Gold task inventory at generation time;
# NOT a uniform f-string (patient_clinical_history's builder task drops the
# `patient_` prefix), but the UC table names below carry the full names.
LAYER_TABLES: tuple[str, ...] = (
    "patient_summary",
    "patient_clinical_history",
    "patient_billing_summary",
)

# DQ-FLD-106 / NFR-4 / DQS §4 — current-patient completeness baseline.
# `patient_360.gold.reconciliation.EXPECTED_PATIENT_COUNT` == 5767; the
# `reconciliation_gold` task fails closed if patient_summary row count
# diverges from this value.
EXPECTED_PATIENT_COUNT = 5767

# The layer-terminal reconciliation gate task in `patient360_hourly_v1`
# (LLD §4.2, §5.5; STORY-05-006). Its `success` state is the anchor for
# the row-count (AC3) and allergy-completeness (AC4) assertions.
RECONCILIATION_TASK_ID = "reconciliation_gold"


# ---------------------------------------------------------------- helpers


def _task_instance_state(
    stack, dag_id: str, run_id: str, task_id: str, headers: dict[str, str]
) -> str | None:
    """Return the state of a single task instance within a DAG run."""
    resp = requests.get(
        f"{stack.airflow_api}/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}",
        headers=headers,
        timeout=10,
    )
    if resp.status_code == 404:
        pytest.fail(f"Task instance {dag_id}/{run_id}/{task_id} not found (is the task wired?)")
    resp.raise_for_status()
    return resp.json().get("state")


# ---------------------------------------------------------------- tests


def test_dag_runs(successful_gold_run: dict[str, Any]) -> None:
    """AC1 — `patient360_hourly_v1` runs Gold tasks + `reconciliation_gold`
    to success on local Airflow [LLD §4.2].

    Consumes the shared session-scoped ``successful_gold_run`` fixture, which
    guarantees the run reached ``success`` (fast-path reuse of a recent run,
    else a fresh trigger polled to completion)."""
    assert successful_gold_run["state"] == "success", successful_gold_run


def test_3_gold_tables_in_uc(stack, successful_gold_run) -> None:
    """AC2 — the 3 Gold consumer tables are registered in Unity Catalog OSS
    under `unity.gold.*` [LLD §3.2]."""
    resp = requests.get(
        f"{stack.uc_uri}/tables",
        params={
            "catalog_name": stack.uc_catalog,
            "schema_name": stack.uc_schema_for("gold"),
        },
        timeout=10,
    )
    resp.raise_for_status()
    body = resp.json() or {}
    listed = {t.get("name") for t in body.get("tables", []) if t.get("name")}

    missing = [t for t in LAYER_TABLES if t not in listed]
    assert not missing, (
        f"Missing Gold tables in {stack.uc_catalog}.{stack.uc_schema_for('gold')}: "
        f"{missing}. Found: {sorted(listed)}"
    )


def test_patient_summary_count_5767(stack, successful_gold_run, airflow_headers) -> None:
    """AC3 — `patient_summary` holds exactly 5,767 rows (DQ-FLD-106 / NFR-4)
    [DQS §4, LLD §10.4].

    Unity Catalog OSS exposes no row-count endpoint, so the assertion rides
    the `reconciliation_gold` fail-closed gate: that task computes
    `patient_summary` row count and fails the run when it != 5,767
    (`patient_360.gold.reconciliation.check_patient_completeness`,
    DQ-REC-010). A `success` task-instance state for `reconciliation_gold`
    within this run is therefore proof the count == EXPECTED_PATIENT_COUNT.
    """
    dag_id = stack.dag_id_for("gold")
    run_id = successful_gold_run["dag_run_id"]
    state = _task_instance_state(
        stack,
        dag_id=dag_id,
        run_id=run_id,
        task_id=RECONCILIATION_TASK_ID,
        headers=airflow_headers,
    )
    assert state == "success", (
        f"{RECONCILIATION_TASK_ID} ended in state {state!r} for run {run_id}; it fails closed "
        f"when patient_summary row count != {EXPECTED_PATIENT_COUNT} (DQ-FLD-106 / NFR-4)."
    )
