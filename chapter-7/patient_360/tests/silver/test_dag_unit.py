"""Unit tests for the silver_dimensions TaskGroup wiring (STORY-03-007).

Validates the shared ``patient360_hourly_v1`` DAG parses cleanly and now
exposes the four silver-dimension tasks under the ``silver_dimensions``
TaskGroup, each downstream of ``reconciliation_bronze`` per LLD §4.2,
§4.3. The DAG is imported via importlib so failures point at the exact
file rather than at a pytest-collection symptom.

Scope (per STORY-03-007 Verification block):

* AC1: ``silver_dimensions`` group with the 4 ``transform_*_silver`` tasks
* AC2: each silver-dim task is a ``SparkSubmitOperator`` submitting
  ``run_silver_transform.py`` (NOT a PythonOperator)
* AC3/AC5: all four silver-dim tasks are downstream of
  ``reconciliation_bronze``
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DAG_FILE = REPO_ROOT / "airflow" / "dags" / "patient360_hourly_v1.py"

SILVER_DIM_TABLES = ("patients", "organizations", "providers", "payers")
EXPECTED_SILVER_TASK_IDS = {f"silver_dimensions.transform_{t}_silver" for t in SILVER_DIM_TABLES}


# Skip the whole module when airflow is not installed (lightweight
# `uv sync` without the airflow extra) — clear skip, not a scary
# ImportError at collection.
pytest.importorskip("airflow", reason="airflow not installed in this env")


@pytest.fixture(scope="module")
def monkeypatch_module():
    """Module-scoped MonkeyPatch (built-in fixture is function-scoped,
    incompatible with the module-scoped ``dag_module`` fixture)."""
    mp = pytest.MonkeyPatch()
    try:
        yield mp
    finally:
        mp.undo()


@pytest.fixture(scope="module")
def dag_module(monkeypatch_module):
    """Import the DAG file as a module and return it.

    Uses ``spec_from_file_location`` so the test is decoupled from
    PYTHONPATH layout. ``AIRFLOW_CONFIGS_DIR`` points at the repo configs
    so the Bronze TaskGroup materialises (the silver group is built
    independently of those configs).
    """
    monkeypatch_module.setenv("AIRFLOW_CONFIGS_DIR", str(REPO_ROOT / "airflow" / "configs"))
    spec = importlib.util.spec_from_file_location("patient360_hourly_v1_dag_silver", DAG_FILE)
    assert spec is not None and spec.loader is not None, f"Could not load DAG spec for {DAG_FILE}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dag_file_exists():
    """STORY-03-007 AC1: shared DAG file is at the expected path."""
    assert DAG_FILE.is_file(), f"Expected DAG file at {DAG_FILE}"


def test_silver_dimensions_group_exposes_four_tasks(dag_module):
    """AC1: the 4 transform_*_silver tasks live under silver_dimensions."""
    dag = dag_module.dag_instance
    task_ids = set(dag.task_ids)
    missing = EXPECTED_SILVER_TASK_IDS - task_ids
    assert not missing, (
        "silver_dimensions TaskGroup is missing expected tasks "
        f"{sorted(missing)}; got silver tasks "
        f"{sorted(t for t in task_ids if t.startswith('silver_dimensions.'))}"
    )
    silver_tasks = {t for t in task_ids if t.startswith("silver_dimensions.")}
    assert silver_tasks == EXPECTED_SILVER_TASK_IDS, (
        f"Unexpected silver_dimensions membership: {sorted(silver_tasks)}"
    )


def test_silver_dim_tasks_are_spark_submit_operators(dag_module):
    """AC2: each silver-dim task is a SparkSubmitOperator submitting the
    run_silver_transform.py shim with a --table selector (NOT a
    PythonOperator)."""
    dag = dag_module.dag_instance
    for task_id in EXPECTED_SILVER_TASK_IDS:
        task = dag.get_task(task_id)
        assert type(task).__name__ == "SparkSubmitOperator", (
            f"{task_id} must be a SparkSubmitOperator per LLD §4.2 "
            f"(2026-05-12 pivot); got {type(task).__name__}"
        )
        # The parameterised shim is selected via --table; assert the
        # right table flag reaches the application_args.
        table = task_id.removeprefix("silver_dimensions.transform_").removesuffix("_silver")
        args = list(getattr(task, "application_args", []) or [])
        assert "run_silver_transform.py" in str(getattr(task, "application", "")), (
            f"{task_id} must submit run_silver_transform.py; "
            f"got application={getattr(task, 'application', None)!r}"
        )
        assert "--table" in args and table in args, (
            f"{task_id} application_args must select --table {table}; got {args}"
        )


def test_silver_dim_tasks_downstream_of_reconciliation_bronze(dag_module):
    """AC3/AC5: every silver-dim task runs AFTER reconciliation_bronze
    (LLD §4.3: RC1 --> SD1 & SD2 & SD3 & SD4)."""
    dag = dag_module.dag_instance
    recon = dag.get_task("reconciliation_bronze")
    downstream = recon.downstream_task_ids
    missing = EXPECTED_SILVER_TASK_IDS - set(downstream)
    assert not missing, (
        "reconciliation_bronze must be upstream of all four silver-dim "
        f"tasks (LLD §4.3); missing downstream edges to {sorted(missing)}"
    )
    # And symmetrically: each silver-dim task lists reconciliation_bronze
    # as its (only relevant) upstream.
    for task_id in EXPECTED_SILVER_TASK_IDS:
        task = dag.get_task(task_id)
        assert "reconciliation_bronze" in task.upstream_task_ids, (
            f"{task_id} must have reconciliation_bronze upstream; "
            f"got {sorted(task.upstream_task_ids)}"
        )
