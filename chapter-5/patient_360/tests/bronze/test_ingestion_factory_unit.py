"""STORY-02-002 — Bronze TaskGroup factory unit tests.

Covers the three AC categories from the story file:

* AC1 — :func:`build_bronze_taskgroup` returns a TaskGroup with N tasks
  (one per YAML) for empty / single-file / 13-file ``configs_dir``.
* AC2 — Indirectly: the factory delegates to ``spark_submit_wrapper``,
  which is responsible for ``--config-path`` / compute knobs. We assert
  the wrapper is called once per YAML with the right ``task_id`` and
  ``config_path``.
* AC3 — explicit empty / single / 13-file parametrisation below.

Airflow is required for the import paths (``airflow.sdk.TaskGroup``,
``SparkSubmitOperator``). When Airflow is missing the suite is skipped
rather than failing — matches the convention used by
``test_ingestion_runner_unit.py``.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

# Airflow is the only hard import dep for the factory; skip cleanly when
# absent so this test still works on a stripped-down dev shell.
pytest.importorskip("airflow", reason="airflow not installed", exc_type=ImportError)


@pytest.fixture
def configs_dir(tmp_path: Path) -> Path:
    """Empty configs dir — used as the baseline; per-test population follows."""
    d = tmp_path / "configs"
    d.mkdir()
    return d


def _write_config(configs_dir: Path, table: str, suffix: str = ".yml") -> Path:
    """Drop a minimal per-table YAML; contents don't matter to the factory.

    The factory only globs filenames at parse time — the runner reads
    contents. Keep this fixture minimal so the test isolates filename-driven
    behaviour.
    """
    p = configs_dir / f"{table}{suffix}"
    p.write_text(f"table: {table}\n")
    return p


@pytest.fixture
def fake_dag():
    """Return a real Airflow DAG. TaskGroup needs a DAG to attach to."""
    from airflow.sdk import DAG  # type: ignore[import-not-found]

    return DAG(dag_id="test_factory_dag", schedule=None, start_date=None)


@pytest.fixture
def patched_wrapper():
    """Patch the SparkSubmit task builder so we don't need a real Spark conn.

    The factory imports ``build_spark_submit_task`` lazily from
    ``patient_360.bronze.spark_submit_wrapper`` (so the module stays
    importable in non-Airflow contexts). We patch the *source* module
    here -- the lazy import inside the factory then resolves to our
    mock at call time.
    """
    import patient_360.bronze.spark_submit_wrapper as wrapper_mod

    with mock.patch.object(
        wrapper_mod,
        "build_spark_submit_task",
        autospec=False,
        create=True,
    ) as m:
        # Each call must return *something* so the TaskGroup context
        # finishes cleanly; a MagicMock is fine.
        m.side_effect = lambda **kwargs: mock.MagicMock(name=f"task:{kwargs['task_id']}")
        yield m


# ---------------------------------------------------------------------------
# AC1 / AC3 — empty / single / 13-file scenarios
# ---------------------------------------------------------------------------
class TestBuildBronzeTaskgroup:
    """Empty / single / 13-file parametrisation (story AC3)."""

    def test_empty_configs_dir_returns_taskgroup_with_zero_tasks(
        self, fake_dag, configs_dir, patched_wrapper
    ) -> None:
        """Empty dir: TaskGroup is created, wrapper is never called.

        Important — the factory must not raise here; an empty dir is the
        legitimate state of a freshly scaffolded project before any
        per-table YAML lands. The DAG still has to parse.
        """
        from patient_360.bronze.ingestion_factory import (
            TASKGROUP_ID,
            build_bronze_taskgroup,
        )

        tg = build_bronze_taskgroup(fake_dag, configs_dir=configs_dir)

        assert tg.group_id == TASKGROUP_ID
        assert patched_wrapper.call_count == 0

    def test_single_yaml_creates_one_task(
        self, fake_dag, configs_dir, patched_wrapper
    ) -> None:
        """One YAML in / one wrapper call out — task_id derives from stem."""
        from patient_360.bronze.ingestion_factory import build_bronze_taskgroup

        cfg = _write_config(configs_dir, "patients")

        build_bronze_taskgroup(fake_dag, configs_dir=configs_dir)

        assert patched_wrapper.call_count == 1
        call = patched_wrapper.call_args_list[0].kwargs
        assert call["task_id"] == "ingest_patients"
        assert call["config_path"] == str(cfg)

    def test_thirteen_yaml_files_creates_thirteen_tasks_sorted(
        self, fake_dag, configs_dir, patched_wrapper
    ) -> None:
        """LLD §5.1 cardinality: factory emits 13 tasks for the 13 source tables.

        Names are intentionally drawn from the LLD §5.1 / DMS Bronze
        table list so this test also pins the table-name convention to
        the actual project. Task ids are asserted in sorted order to
        lock in the determinism the LLD §13 Decision 8 requires.
        """
        from patient_360.bronze.ingestion_factory import build_bronze_taskgroup

        tables = [
            "allergies",
            "careplans",
            "conditions",
            "encounters",
            "immunizations",
            "medications",
            "observations",
            "organizations",
            "patients",
            "payer_transitions",
            "payers",
            "procedures",
            "providers",
        ]
        for t in tables:
            _write_config(configs_dir, t)

        build_bronze_taskgroup(fake_dag, configs_dir=configs_dir)

        assert patched_wrapper.call_count == 13
        seen_task_ids = [
            c.kwargs["task_id"] for c in patched_wrapper.call_args_list
        ]
        # Sorted alphabetically by table stem — predictable for downstream
        # dependency wiring.
        assert seen_task_ids == [f"ingest_{t}" for t in sorted(tables)]


# ---------------------------------------------------------------------------
# Path resolution — LLD §2.3 contract
# ---------------------------------------------------------------------------
class TestConfigsDirResolution:
    """The factory MUST resolve configs_dir in arg > env > absolute-default order."""

    def test_explicit_arg_wins_over_env(
        self, monkeypatch, fake_dag, configs_dir, patched_wrapper
    ) -> None:
        """Explicit kwarg must override ``AIRFLOW_CONFIGS_DIR``."""
        from patient_360.bronze.ingestion_factory import build_bronze_taskgroup

        monkeypatch.setenv("AIRFLOW_CONFIGS_DIR", "/nonexistent/from/env")
        _write_config(configs_dir, "patients")

        build_bronze_taskgroup(fake_dag, configs_dir=configs_dir)

        # The single config in the explicit dir wins — the bogus env path
        # is ignored entirely.
        assert patched_wrapper.call_count == 1

    def test_env_var_used_when_kwarg_omitted(
        self, monkeypatch, fake_dag, tmp_path, patched_wrapper
    ) -> None:
        """When kwarg is None, ``AIRFLOW_CONFIGS_DIR`` is consulted."""
        from patient_360.bronze.ingestion_factory import build_bronze_taskgroup

        env_dir = tmp_path / "from_env"
        env_dir.mkdir()
        _write_config(env_dir, "encounters")
        monkeypatch.setenv("AIRFLOW_CONFIGS_DIR", str(env_dir))

        build_bronze_taskgroup(fake_dag)

        assert patched_wrapper.call_count == 1
        assert (
            patched_wrapper.call_args_list[0].kwargs["task_id"]
            == "ingest_encounters"
        )

    def test_missing_dir_does_not_raise(
        self, monkeypatch, fake_dag, patched_wrapper, tmp_path
    ) -> None:
        """A missing dir must yield an empty TaskGroup, not a hard fail.

        Airflow imports the DAG at parse time; raising here would take
        the whole scheduler down. The factory logs WARNING and returns
        an empty group.
        """
        from patient_360.bronze.ingestion_factory import build_bronze_taskgroup

        monkeypatch.delenv("AIRFLOW_CONFIGS_DIR", raising=False)
        missing = tmp_path / "does_not_exist"

        tg = build_bronze_taskgroup(fake_dag, configs_dir=missing)

        assert patched_wrapper.call_count == 0
        assert tg.group_id == "bronze_ingestion"


# ---------------------------------------------------------------------------
# Filename hygiene
# ---------------------------------------------------------------------------
class TestFilenameHandling:
    def test_yaml_extension_also_picked_up(
        self, fake_dag, configs_dir, patched_wrapper
    ) -> None:
        """Both ``.yml`` and ``.yaml`` are accepted (LLD §5.1)."""
        from patient_360.bronze.ingestion_factory import build_bronze_taskgroup

        _write_config(configs_dir, "patients", suffix=".yml")
        _write_config(configs_dir, "encounters", suffix=".yaml")

        build_bronze_taskgroup(fake_dag, configs_dir=configs_dir)

        ids = sorted(c.kwargs["task_id"] for c in patched_wrapper.call_args_list)
        assert ids == ["ingest_encounters", "ingest_patients"]

    def test_duplicate_stem_yml_wins_over_yaml(
        self, fake_dag, configs_dir, patched_wrapper
    ) -> None:
        """If both ``patients.yml`` and ``patients.yaml`` exist, ``.yml`` wins.

        Prevents two tasks targeting the same Bronze table — the runner
        would race on the same ``replaceWhere`` partition.
        """
        from patient_360.bronze.ingestion_factory import build_bronze_taskgroup

        yml = _write_config(configs_dir, "patients", suffix=".yml")
        _write_config(configs_dir, "patients", suffix=".yaml")

        build_bronze_taskgroup(fake_dag, configs_dir=configs_dir)

        assert patched_wrapper.call_count == 1
        assert patched_wrapper.call_args_list[0].kwargs["config_path"] == str(yml)

    def test_hidden_files_ignored(
        self, fake_dag, configs_dir, patched_wrapper
    ) -> None:
        """Editor scratch files (``.foo.yml``) must not become tasks."""
        from patient_360.bronze.ingestion_factory import build_bronze_taskgroup

        _write_config(configs_dir, "patients")
        scratch = configs_dir / ".tmp.yml"
        scratch.write_text("table: tmp\n")

        build_bronze_taskgroup(fake_dag, configs_dir=configs_dir)

        assert patched_wrapper.call_count == 1


# ---------------------------------------------------------------------------
# Wrapper delegation — AC2 (config-path + compute knobs)
# ---------------------------------------------------------------------------
class TestWrapperDelegation:
    def test_pipeline_cfg_and_conn_forwarded(
        self, fake_dag, configs_dir, patched_wrapper
    ) -> None:
        """Caller's pipeline_cfg + conn_id must reach the wrapper unchanged."""
        from patient_360.bronze.ingestion_factory import build_bronze_taskgroup

        _write_config(configs_dir, "patients")
        pipeline_cfg = {"compute_spark_driver_memory": "4g"}

        build_bronze_taskgroup(
            fake_dag,
            configs_dir=configs_dir,
            pipeline_cfg=pipeline_cfg,
            spark_conn_id="spark_prod",
            operator_kwargs={"retries": 3},
        )

        call = patched_wrapper.call_args_list[0].kwargs
        assert call["pipeline_cfg"] == pipeline_cfg
        assert call["spark_conn_id"] == "spark_prod"
        assert call["operator_kwargs"] == {"retries": 3}

    def test_none_pipeline_cfg_replaced_with_empty_dict(
        self, fake_dag, configs_dir, patched_wrapper
    ) -> None:
        """Passing ``pipeline_cfg=None`` is allowed; wrapper sees ``{}``.

        Lets a smoke DAG parse before the runtime config file exists —
        the wrapper applies its own defaults (LLD §6.1) downstream.
        """
        from patient_360.bronze.ingestion_factory import build_bronze_taskgroup

        _write_config(configs_dir, "patients")

        build_bronze_taskgroup(fake_dag, configs_dir=configs_dir, pipeline_cfg=None)

        call = patched_wrapper.call_args_list[0].kwargs
        assert call["pipeline_cfg"] == {}
