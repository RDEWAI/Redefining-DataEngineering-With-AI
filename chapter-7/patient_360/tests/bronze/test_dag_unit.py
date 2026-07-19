"""Unit tests for the patient360_hourly_v1 DAG (STORY-02-006).

Validates the DAG parses cleanly and exposes the 13 Bronze ingestion
tasks + ``reconciliation_bronze`` per LLD §4.1, §4.2, §8.6.1. The tests
import the DAG module via importlib so failures point at the exact
file rather than at a pytest-collection symptom.

Scope (per story Verification block):

* AC1: file_exists + dag_id ``patient360_hourly_v1``
* AC2: ``build_bronze_taskgroup`` is the source of Bronze fan-out
* AC3: ``reconciliation_bronze`` task exists downstream of Bronze
* AC4: ``max_active_runs=1`` + env-dependent ``max_active_tasks``
  (LLD §4.1: DEV=1, STAGING=8, PROD=16; resolved from ``PATIENT360_ENV``,
  default DEV)
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DAG_FILE = REPO_ROOT / "airflow" / "dags" / "patient360_hourly_v1.py"


# Skip the entire module when airflow is not installed (e.g. lightweight
# `uv sync` without the airflow extra). The DAG parser test relies on
# `airflow.sdk`; pytest should report a clear skip reason instead of a
# scary ImportError.
pytest.importorskip("airflow", reason="airflow not installed in this env")


@pytest.fixture(scope="module")
def monkeypatch_module():
    """Module-scoped MonkeyPatch.

    pytest's built-in ``monkeypatch`` fixture is function-scoped, which
    is incompatible with our module-scoped ``dag_module`` fixture
    (importing the DAG is expensive — we only want to do it once per
    test module). MonkeyPatch's public class supports manual lifecycle.
    """
    mp = pytest.MonkeyPatch()
    try:
        yield mp
    finally:
        mp.undo()


@pytest.fixture(scope="module")
def patched_spark_submit():
    """Replace ``build_spark_submit_task`` with a thin EmptyOperator factory.

    The real wrapper instantiates a ``SparkSubmitOperator`` with Spark
    provider kwargs (driver_cores, executor_memory, etc.) that are not
    accepted by every provider point release. Unit tests for the DAG
    only care about graph shape — task ids and upstream/downstream
    edges — so we substitute EmptyOperator, which is a real
    BaseOperator and integrates with TaskGroup / DAG just like the
    Spark operator would.
    """
    from airflow.providers.standard.operators.empty import (  # type: ignore[import-not-found]
        EmptyOperator,
    )

    def _fake_task(*, task_id: str, **_: object):
        return EmptyOperator(task_id=task_id)

    # The factory imports build_spark_submit_task lazily inside its
    # function body, so we patch the source module instead of the
    # factory's namespace.
    with mock.patch(
        "patient_360.bronze.spark_submit_wrapper.build_spark_submit_task",
        side_effect=_fake_task,
    ):
        yield


@pytest.fixture(scope="module")
def dag_module(monkeypatch_module, patched_spark_submit):
    """Import the DAG file as a module and return it.

    Uses spec_from_file_location so the test is decoupled from
    PYTHONPATH layout — the file path is the contract. The DAG reads
    ``AIRFLOW_CONFIGS_DIR`` for the per-table YAML root; point it at
    the repo's ``airflow/configs/`` so the Bronze TaskGroup actually
    materialises 13 tasks during this test.
    """
    monkeypatch_module.setenv("AIRFLOW_CONFIGS_DIR", str(REPO_ROOT / "airflow" / "configs"))
    spec = importlib.util.spec_from_file_location("patient360_hourly_v1_dag", DAG_FILE)
    assert spec is not None and spec.loader is not None, f"Could not load DAG spec for {DAG_FILE}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dag_file_exists():
    """AC1: DAG file is at the expected path."""
    assert DAG_FILE.is_file(), f"Expected DAG file at {DAG_FILE} — STORY-02-006 AC1"


def test_dag_id_and_schedule(dag_module):
    """AC1: dag_id and hourly schedule per LLD §4.1."""
    dag = dag_module.dag_instance
    assert dag.dag_id == "patient360_hourly_v1"
    # Airflow normalises ``0 * * * *`` to the cron string; we compare
    # the raw schedule arg via the dag's stored ``schedule_interval``
    # or ``timetable``. Either attribute is acceptable across Airflow
    # 3.x point releases — assert one of the two.
    schedule_repr = getattr(dag, "schedule_interval", None) or repr(dag.timetable)
    assert "0 * * * *" in str(schedule_repr) or "hourly" in str(schedule_repr).lower()


def test_dag_concurrency_and_max_active_runs(dag_module):
    """AC4: max_active_runs=1, env-dependent max_active_tasks, DEV catchup=False.

    The ``dag_module`` fixture imports the DAG with no ``PATIENT360_ENV``
    set, so concurrency resolves to the DEV default of 1 (LLD §4.1 —
    an 8 GB laptop OOMs running 13 SparkSubmit tasks in parallel) and
    ``catchup`` resolves to the DEV value of False (LLD §4.1; STAGING/PROD
    enable backfill — see ``test_catchup_is_env_dependent``).
    """
    dag = dag_module.dag_instance
    assert dag.max_active_runs == 1
    # Airflow 3.x renamed ``concurrency`` to ``max_active_tasks``; both
    # are surfaced on the DAG object. DEV default = 1 (LLD §4.1).
    assert dag.max_active_tasks == 1
    assert dag.catchup is False  # DEV default per LLD §4.1 (STAGING/PROD=True; see test_catchup_is_env_dependent)


@pytest.mark.parametrize(
    ("env", "expected"),
    [("DEV", 1), ("STAGING", 8), ("PROD", 16)],
)
def test_max_active_tasks_is_env_dependent(
    monkeypatch_module, patched_spark_submit, env, expected
):
    """AC4: max_active_tasks varies by PATIENT360_ENV per LLD §4.1
    (DEV=1, STAGING=8, PROD=16). Re-imports the DAG under each env."""
    monkeypatch_module.setenv("AIRFLOW_CONFIGS_DIR", str(REPO_ROOT / "airflow" / "configs"))
    monkeypatch_module.setenv("PATIENT360_ENV", env)
    spec = importlib.util.spec_from_file_location(
        f"patient360_hourly_v1_dag_{env}", DAG_FILE
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.dag_instance.max_active_tasks == expected


@pytest.mark.parametrize(("env", "expected"), [("DEV", False), ("STAGING", True), ("PROD", True)])
def test_catchup_is_env_dependent(monkeypatch_module, patched_spark_submit, env, expected):
    """AC4/LLD §4.1: catchup is env-tiered (DEV=False, STAGING/PROD=True)."""
    monkeypatch_module.setenv("AIRFLOW_CONFIGS_DIR", str(REPO_ROOT / "airflow" / "configs"))
    monkeypatch_module.setenv("PATIENT360_ENV", env)
    spec = importlib.util.spec_from_file_location(f"patient360_hourly_v1_dag_catchup_{env}", DAG_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.dag_instance.catchup is expected


def test_dag_exposes_14_bronze_layer_tasks(dag_module):
    """AC2/AC3: 13 ingest_* tasks under bronze_ingestion group +
    reconciliation_bronze for 14 layer-scoped tasks total."""
    dag = dag_module.dag_instance
    task_ids = set(dag.task_ids)

    # 13 Bronze ingestion tasks live under the ``bronze_ingestion``
    # TaskGroup, so their fully-qualified ids are prefixed.
    bronze_task_ids = {t for t in task_ids if t.startswith("bronze_ingestion.ingest_")}
    assert len(bronze_task_ids) == 13, (
        "Expected 13 Bronze ingestion tasks under bronze_ingestion "
        f"TaskGroup, got {len(bronze_task_ids)}: {sorted(bronze_task_ids)}"
    )

    # Reconciliation task (AC3).
    assert "reconciliation_bronze" in task_ids, (
        f"Expected reconciliation_bronze task, got: {sorted(task_ids)}"
    )


def test_reconciliation_downstream_of_bronze(dag_module):
    """AC3: reconciliation_bronze runs AFTER the Bronze TaskGroup."""
    dag = dag_module.dag_instance
    recon = dag.get_task("reconciliation_bronze")
    upstream_ids = recon.upstream_task_ids
    # Every Bronze ingestion task must be upstream of reconciliation.
    bronze_upstream = {t for t in upstream_ids if t.startswith("bronze_ingestion.ingest_")}
    assert len(bronze_upstream) == 13, (
        "reconciliation_bronze must be downstream of all 13 Bronze "
        f"ingestion tasks (LLD §4.3); upstream={sorted(upstream_ids)}"
    )
