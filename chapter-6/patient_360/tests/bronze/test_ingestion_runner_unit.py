"""STORY-02-001 — Bronze ingestion runner unit tests.

Covers the acceptance criteria for the 2026-05-12 pivot LLD shape:

* AC1 — argparse exposes ``--config-path`` and ``--ds`` (plus ``--env``).
* AC2 — Column contract is derived from the source itself (DuckDB
  ``DESCRIBE`` for DuckDB sources; CSV header for CSV sources) — no
  ``StructType`` enforcement from ``contracts/{table}.yml``.
* AC3 — Metadata columns ``ds`` / ``_ingested_at`` / ``_source_batch_id``
  are appended before write.
* AC4 — Bronze write uses path-based Delta under
  ``${PATIENT360_PROJECT_ROOT}/warehouse/{env}/bronze/<table>/``;
  ``saveAsTable`` is forbidden.
* AC7 — SparkSession is built with DeltaCatalog (no UCSingleCatalog) and
  the warehouse root is resolved via ``PATIENT360_PROJECT_ROOT``.
* AC8 — Source-type ``csv`` is the default; ``duckdb`` is allowed only
  for the LLD §5.1 allow-listed small reference tables.

PySpark is required for the metadata-column assertions; if it is missing
from the local dev env those tests are skipped rather than failing the
suite (mirrors the convention used in ``tests/silver``).
"""

from __future__ import annotations

import inspect
import textwrap
from pathlib import Path

import pytest


# Skip the PySpark-dependent half of the suite when pyspark is not
# installed; the argparse + contract tests are pure-Python and always run.
pyspark = pytest.importorskip("pyspark", reason="pyspark not installed", exc_type=ImportError)


# ---------------------------------------------------------------------------
# Import target. Wrapped because the module emits a fail-closed ImportError
# diagnostic if se_runner is broken — see test_ingestion_runner_failclosed.
# ---------------------------------------------------------------------------
from patient_360.bronze import ingestion_runner as runner  # noqa: E402


# ---------------------------------------------------------------------------
# AC1 — argparse
# ---------------------------------------------------------------------------
class TestArgparse:
    def test_required_args_parse(self) -> None:
        ns = runner.parse_args(
            [
                "--config-path",
                "airflow/configs/patients.yml",
                "--ds",
                "2026-05-11",
            ]
        )
        assert ns.config_path == "airflow/configs/patients.yml"
        assert ns.ds == "2026-05-11"
        # --env defaults to DEV when not supplied (LLD §5.4 / §7.1)
        assert ns.env == "DEV"

    def test_env_choice_accepted(self) -> None:
        ns = runner.parse_args(
            [
                "--config-path",
                "x.yml",
                "--ds",
                "2026-05-11",
                "--env",
                "PROD",
            ]
        )
        assert ns.env == "PROD"

    def test_missing_config_path_errors(self) -> None:
        with pytest.raises(SystemExit):
            runner.parse_args(["--ds", "2026-05-11"])

    def test_missing_ds_errors(self) -> None:
        with pytest.raises(SystemExit):
            runner.parse_args(["--config-path", "x.yml"])

    def test_invalid_env_rejected(self) -> None:
        with pytest.raises(SystemExit):
            runner.parse_args(
                [
                    "--config-path",
                    "x.yml",
                    "--ds",
                    "2026-05-11",
                    "--env",
                    "QA",  # not a valid runtime env; QA is the SE mapping
                ]
            )


# ---------------------------------------------------------------------------
# AC2 — source-derived column contract (no StructType enforcement)
# ---------------------------------------------------------------------------
class TestSourceDerivedContract:
    def test_csv_header_columns_reads_header_row(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "patients.csv"
        csv_path.write_text("id,birthdate,ssn_hash\np1,1990-01-01,abc\n")
        cols = runner.csv_header_columns(path=csv_path)
        assert cols == ["id", "birthdate", "ssn_hash"]

    def test_csv_header_columns_empty_file_raises(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("")
        with pytest.raises(ValueError, match="empty"):
            runner.csv_header_columns(path=csv_path)

    def test_csv_header_columns_strips_whitespace(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "x.csv"
        csv_path.write_text(" id , birthdate \np1,1990-01-01\n")
        assert runner.csv_header_columns(path=csv_path) == ["id", "birthdate"]

    def test_describe_duckdb_columns_requires_query_or_table(self) -> None:
        # Validation precedes the duckdb import in the runner, so this
        # exercises pure-Python control flow.
        with pytest.raises(ValueError, match="query.*table"):
            runner.describe_duckdb_columns(database=":memory:")

    def test_no_struct_type_enforcement_helpers(self) -> None:
        # LLD §2.3 (2026-05-12 pivot) — Bronze is a permissive landing zone.
        # The legacy `build_struct_type_from_contract` / `load_contract_schema`
        # helpers MUST be removed so a regression to StructType enforcement
        # is loud at import time.
        assert not hasattr(runner, "build_struct_type_from_contract")
        assert not hasattr(runner, "load_contract_schema")

    def test_runner_source_has_no_structtype_reference(self) -> None:
        # Belt-and-suspenders: the runner module source must not mention
        # StructType (the forbidden_grep AC2 invariant).
        src = inspect.getsource(runner)
        assert "StructType" not in src, (
            "ingestion_runner.py must not reference StructType "
            "(LLD §2.3, 2026-05-12 pivot)"
        )


# ---------------------------------------------------------------------------
# AC3 — metadata-column additions
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def spark():
    from pyspark.sql import SparkSession

    s = (
        SparkSession.builder.master("local[1]")
        .appName("test_ingestion_runner")
        .getOrCreate()
    )
    yield s
    s.stop()


class TestMetadataColumns:
    def test_add_metadata_columns_appends_three_cols(self, spark) -> None:
        from pyspark.sql import types as T

        schema = T.StructType(
            [T.StructField("id", T.StringType(), False)]
        )
        df = spark.createDataFrame([("p1",), ("p2",)], schema=schema)

        out = runner.add_metadata_columns(df, table="synthea_patients", ds="2026-05-11")

        assert set(out.columns) == {
            "id",
            "ds",
            "_ingested_at",
            "_source_batch_id",
        }
        rows = out.collect()
        assert all(r["ds"] == "2026-05-11" for r in rows)
        assert all(r["_source_batch_id"] == "synthea_patients:2026-05-11" for r in rows)
        assert all(r["_ingested_at"] is not None for r in rows)

    def test_metadata_column_types(self, spark) -> None:
        from pyspark.sql import types as T

        schema = T.StructType([T.StructField("id", T.StringType(), False)])
        df = spark.createDataFrame([("p1",)], schema=schema)
        out = runner.add_metadata_columns(df, table="x", ds="2026-05-11")
        types = {f.name: f.dataType for f in out.schema.fields}
        assert isinstance(types["ds"], T.StringType)
        assert isinstance(types["_ingested_at"], T.TimestampType)
        assert isinstance(types["_source_batch_id"], T.StringType)


# ---------------------------------------------------------------------------
# AC4 — path-based Delta output composition (no saveAsTable, no FQN)
# ---------------------------------------------------------------------------
class TestBronzeOutputPath:
    def test_output_path_uses_project_root_and_env(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("PATIENT360_PROJECT_ROOT", str(tmp_path))
        out = runner.bronze_output_path(env="DEV", table="synthea_patients")
        assert out == str(tmp_path / "warehouse" / "dev" / "bronze" / "synthea_patients")

    def test_output_path_lowercases_env(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setenv("PATIENT360_PROJECT_ROOT", str(tmp_path))
        out = runner.bronze_output_path(env="PROD", table="synthea_encounters")
        assert "/warehouse/prod/bronze/synthea_encounters" in out

    def test_output_path_falls_back_to_cwd(self, monkeypatch) -> None:
        monkeypatch.delenv("PATIENT360_PROJECT_ROOT", raising=False)
        out = runner.bronze_output_path(env="DEV", table="synthea_payers")
        assert out.endswith("/warehouse/dev/bronze/synthea_payers")

    def test_compose_target_table_helper_removed(self) -> None:
        # AC4 forbidden_grep — the legacy 3-part FQN composer must be gone.
        assert not hasattr(runner, "compose_target_table")

    def test_runner_source_forbids_save_as_table(self) -> None:
        src = inspect.getsource(runner)
        assert "saveAsTable" not in src, (
            "ingestion_runner.py must not use saveAsTable "
            "(LLD §13 Decision 15, 2026-05-12)"
        )
        assert "unity.bronze" not in src, (
            "ingestion_runner.py must not reference unity.bronze.* "
            "(LLD §13 Decision 12, 2026-05-12)"
        )

    def test_runner_source_uses_replace_where_save(self) -> None:
        src = inspect.getsource(runner)
        assert ".save(" in src
        assert "replaceWhere" in src
        assert "warehouse" in src


# ---------------------------------------------------------------------------
# AC7 — SparkSession wiring is DeltaCatalog + Derby (no UCSingleCatalog)
# ---------------------------------------------------------------------------
class TestSparkSessionWiring:
    def test_build_spark_delegates_to_helper(self, monkeypatch) -> None:
        captured: dict[str, object] = {}

        def fake_build(*, app_name: str, env: str):
            captured["app_name"] = app_name
            captured["env"] = env
            return object()

        monkeypatch.setattr(
            "patient_360.utils.delta_helpers.build_spark_session",
            fake_build,
        )
        runner.build_spark(app_name="bronze_ingest_x", env="STAGING")
        assert captured["app_name"] == "bronze_ingest_x"
        assert captured["env"] == "STAGING"

    def test_build_spark_defaults_to_dev(self, monkeypatch) -> None:
        captured: dict[str, object] = {}

        def fake_build(*, app_name: str, env: str):
            captured["env"] = env
            return object()

        monkeypatch.setattr(
            "patient_360.utils.delta_helpers.build_spark_session",
            fake_build,
        )
        runner.build_spark(app_name="bronze_ingest_x")
        assert captured["env"] == "DEV"

    def test_runner_source_forbids_ucsinglecatalog(self) -> None:
        src = inspect.getsource(runner)
        assert "UCSingleCatalog" not in src, (
            "ingestion_runner.py must not reference UCSingleCatalog "
            "(LLD §13 Decision 12, 2026-05-12)"
        )

    def test_runner_source_uses_project_root_env(self) -> None:
        src = inspect.getsource(runner)
        assert "PATIENT360_PROJECT_ROOT" in src


# ---------------------------------------------------------------------------
# AC8 — source-selection rule (CSV default; DuckDB allow-list only)
# ---------------------------------------------------------------------------
class TestSourceSelection:
    def test_duckdb_allow_list_matches_lld(self) -> None:
        # LLD §5.1 — DuckDB is only allowed for the six small reference
        # tables whose raw CSV is < 100 MB.
        assert runner.DUCKDB_ALLOWED_TABLES == frozenset(
            {
                "synthea_organizations",
                "synthea_providers",
                "synthea_payers",
                "synthea_careplans",
                "synthea_allergies",
                "synthea_immunizations",
            }
        )

    def test_read_source_rejects_duckdb_for_large_table(self) -> None:
        with pytest.raises(ValueError, match="not in the LLD §5.1 allow-list"):
            runner.read_source(
                spark=object(),  # unreachable — error fires before spark use
                source_cfg={"type": "duckdb", "database": ":memory:", "table": "x"},
                table="synthea_observations",
            )

    def test_read_source_rejects_unsupported_type(self) -> None:
        with pytest.raises(ValueError, match="Unsupported source type"):
            runner.read_source(
                spark=object(),
                source_cfg={"type": "json", "path": "/tmp/x.json"},
                table="synthea_patients",
            )
