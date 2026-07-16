"""STORY-02-001 — Bronze ingestion runner unit tests (UC re-adoption 2026-06-18).

Covers the AC categories called out in LLD §2.3 / §13 Decision 12/15 and
the story acceptance criteria:

* AC1 — argparse exposes ``--config-path`` and ``--ds`` (plus ``--env``).
* AC2 — Bronze contract is SOURCE-DERIVED: ``read_source`` reflects whatever
  the source emits (CSV header / DuckDB ``SELECT *``); no ``StructType``
  enforcement (Bronze is a permissive landing zone — DMS owns Silver/Gold).
* AC3 — Metadata columns ``ds`` / ``_ingested_at`` / ``_source_batch_id``
  are appended before write.
* AC4 — :func:`compose_target_table` builds the 3-part ``unity.bronze.<table>``
  from config keys (no hardcoded literal); :func:`write_bronze` uses a plain
  ``insertInto`` (idempotency via dynamic partition overwrite — NO
  ``replaceWhere``, never ``saveAsTable``).
* AC7 — ``catalog_bronze_catalog_name`` / ``catalog_bronze_schema`` are
  the only catalog/schema sources; missing keys raise.

PySpark is required for the metadata-column assertions; if it is missing
from the local dev env those tests are skipped rather than failing the
suite (mirrors the convention used in ``tests/silver``).
"""

from __future__ import annotations

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
    """Bronze is a permissive landing zone (LLD §2.3): the column contract
    comes from the source itself, not a hand-written StructType."""

    def test_no_structtype_enforcement_symbols(self) -> None:
        # The StructType-enforcement helpers were removed at the 2026-06-18
        # re-adoption; their continued absence is the AC2 contract.
        assert not hasattr(runner, "build_struct_type_from_contract")
        assert not hasattr(runner, "load_contract_schema")

    def test_read_source_csv_uses_header(self, monkeypatch) -> None:
        """CSV source: column contract derives from the header row; the
        runner passes header=true and never imposes a StructType."""
        calls: dict[str, object] = {}

        class _Reader:
            def format(self, fmt):
                calls["format"] = fmt
                return self

            def option(self, k, v):
                calls.setdefault("options", {})[k] = v  # type: ignore[union-attr]
                return self

            def load(self, path):
                calls["path"] = path
                return "DF"

            def schema(self, *_a, **_kw):  # pragma: no cover - must not be hit
                raise AssertionError("read_source must not apply a StructType")

        class _Spark:
            read = _Reader()

        out = runner.read_source(
            _Spark(),
            source_cfg={"type": "csv", "path": "data/raw/patients.csv", "header": True},
        )
        assert out == "DF"
        assert calls["format"] == "csv"
        assert calls["options"]["header"] == "true"  # type: ignore[index]

    def test_read_source_rejects_unknown_type(self) -> None:
        class _Spark:  # pragma: no cover - never reaches read
            pass

        with pytest.raises(ValueError, match="Unsupported source type"):
            runner.read_source(_Spark(), source_cfg={"type": "avro", "path": "x"})


# ---------------------------------------------------------------------------
# AC3 — metadata-column additions
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def spark():
    from pyspark.sql import SparkSession

    s = SparkSession.builder.master("local[1]").appName("test_ingestion_runner").getOrCreate()
    yield s
    s.stop()


class TestMetadataColumns:
    def test_add_metadata_columns_appends_four_cols(self, spark) -> None:
        from pyspark.sql import types as T

        schema = T.StructType([T.StructField("id", T.StringType(), False)])
        df = spark.createDataFrame([("p1",), ("p2",)], schema=schema)

        out = runner.add_metadata_columns(
            df,
            table="synthea_patients",
            ds="2026-05-11",
            source_file="data/raw_delta/patients.csv",
        )

        assert set(out.columns) == {
            "id",
            "ds",
            "_ingested_at",
            "_source_batch_id",
            "_source_file",
        }
        rows = out.collect()
        assert all(r["ds"] == "2026-05-11" for r in rows)
        assert all(r["_source_batch_id"] == "synthea_patients:2026-05-11" for r in rows)
        assert all(r["_ingested_at"] is not None for r in rows)
        assert all(r["_source_file"] == "data/raw_delta/patients.csv" for r in rows)

    def test_source_file_null_when_unset(self, spark) -> None:
        # LLD §2.3 (1.19) — column must still exist (arity parity with the
        # pre-created Delta table) but carry SQL NULL when no source path.
        from pyspark.sql import types as T

        schema = T.StructType([T.StructField("id", T.StringType(), False)])
        df = spark.createDataFrame([("p1",)], schema=schema)
        out = runner.add_metadata_columns(df, table="x", ds="2026-05-11")
        assert "_source_file" in out.columns
        assert out.collect()[0]["_source_file"] is None

    def test_metadata_column_types(self, spark) -> None:
        from pyspark.sql import types as T

        schema = T.StructType([T.StructField("id", T.StringType(), False)])
        df = spark.createDataFrame([("p1",)], schema=schema)
        out = runner.add_metadata_columns(
            df, table="x", ds="2026-05-11", source_file="data/raw_delta/x.csv"
        )
        types = {f.name: f.dataType for f in out.schema.fields}
        assert isinstance(types["ds"], T.StringType)
        assert isinstance(types["_ingested_at"], T.TimestampType)
        assert isinstance(types["_source_batch_id"], T.StringType)
        assert isinstance(types["_source_file"], T.StringType)


# ---------------------------------------------------------------------------
# AC4 / AC7 — 3-part UC target composed from config keys + insertInto write
# ---------------------------------------------------------------------------
class TestComposeTargetTable:
    def test_composes_three_part_uc_name(self) -> None:
        cfg = {
            "table": "synthea_patients",
            "catalog_bronze_catalog_name": "unity",
            "catalog_bronze_schema": "bronze",
        }
        assert runner.compose_target_table(cfg) == "unity.bronze.synthea_patients"

    def test_alt_catalog_schema_supported(self) -> None:
        # Confirms catalog/schema are NOT hardcoded — a different catalog
        # works without code changes (LLD §7.1 / §13 Decision 12).
        cfg = {
            "table": "synthea_patients",
            "catalog_bronze_catalog_name": "p360_dev",
            "catalog_bronze_schema": "bronze_raw",
        }
        assert runner.compose_target_table(cfg) == "p360_dev.bronze_raw.synthea_patients"

    def test_missing_catalog_key_raises(self) -> None:
        with pytest.raises(KeyError, match="catalog_bronze_catalog_name"):
            runner.compose_target_table({"table": "x", "catalog_bronze_schema": "bronze"})

    def test_missing_schema_key_raises(self) -> None:
        with pytest.raises(KeyError, match="catalog_bronze_catalog_name"):
            runner.compose_target_table({"table": "x", "catalog_bronze_catalog_name": "unity"})


class TestWriteBronze:
    """AC4 — the runner inserts into the pre-created UC table via a plain
    ``insertInto``; idempotency comes from dynamic partition overwrite, so
    ``replaceWhere`` must NOT be used (``insertInto`` silently ignores it and
    re-runs would append/double — LLD §13 Decision 15, change log 1.14). It
    never calls ``saveAsTable``."""

    def test_write_uses_plain_insert_into_no_replace_where(self) -> None:
        recorded: dict[str, object] = {}

        class _Writer:
            def mode(self, m):
                recorded["mode"] = m
                return self

            def option(self, k, v):  # pragma: no cover - guarded below
                recorded.setdefault("options", {})[k] = v  # type: ignore[union-attr]
                return self

            def insertInto(self, tbl):
                recorded["insertInto"] = tbl

            def saveAsTable(self, *_a, **_kw):  # pragma: no cover
                raise AssertionError(
                    "write_bronze must not call saveAsTable (UCSingleCatalog "
                    "rejects CTAS/RTAS — LLD §13 Decision 12/15)"
                )

        class _DF:
            write = _Writer()

        runner.write_bronze(_DF(), target_table="unity.bronze.synthea_patients", ds="2026-05-11")
        assert recorded["mode"] == "overwrite"
        assert recorded["insertInto"] == "unity.bronze.synthea_patients"
        # replaceWhere is forbidden alongside insertInto (LLD §13 Decision 15):
        # insertInto silently ignores it, so it must never be passed.
        assert "options" not in recorded


# ---------------------------------------------------------------------------
# AC7 — UC_URI env var resolution (no hardcoded literal at call site)
# ---------------------------------------------------------------------------
class TestUcUriResolution:
    def test_uc_uri_env_var_consumed(self, monkeypatch) -> None:
        captured: dict[str, object] = {}

        def fake_build(*, app_name: str, uc_uri: str):
            captured["app_name"] = app_name
            captured["uc_uri"] = uc_uri
            return object()

        monkeypatch.setattr(
            "patient_360.utils.delta_helpers.build_spark_session",
            fake_build,
        )
        monkeypatch.setenv("UC_URI", "http://uc.test:8080")
        runner.build_spark(app_name="bronze_ingest_x")
        assert captured["uc_uri"] == "http://uc.test:8080"

    def test_uc_uri_falls_back_to_default(self, monkeypatch) -> None:
        captured: dict[str, object] = {}

        def fake_build(*, app_name: str, uc_uri: str):
            captured["uc_uri"] = uc_uri
            return object()

        monkeypatch.setattr(
            "patient_360.utils.delta_helpers.build_spark_session",
            fake_build,
        )
        monkeypatch.delenv("UC_URI", raising=False)
        runner.build_spark(app_name="bronze_ingest_x")
        assert captured["uc_uri"] == runner.DEFAULT_UC_URI
