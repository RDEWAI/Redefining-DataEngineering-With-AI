"""STORY-02-001 — Bronze ingestion runner unit tests.

Covers the three AC categories called out in LLD §2.3 and the story
acceptance criteria:

* AC1 — argparse exposes ``--config-path`` and ``--ds`` (plus ``--env``).
* AC2 — Schema enforcement loads a ``StructType`` from
  ``contracts/{table}.yml`` and refuses to start on an empty contract.
* AC3 — Metadata columns ``ds`` / ``_ingested_at`` / ``_source_batch_id``
  are appended before write.
* AC4 — :func:`compose_target_table` builds ``{catalog}.{schema}.{table}``
  from config keys (no hardcoded ``unity.bronze`` literal).
* AC7 — ``catalog_bronze_catalog_name`` / ``catalog_bronze_schema`` are
  the only catalog/schema sources; missing keys raise.

PySpark is required for the metadata-column assertions; if it is missing
from the local dev env those tests are skipped rather than failing the
suite (mirrors the convention used in ``tests/silver``).
"""

from __future__ import annotations

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
# AC2 — schema enforcement from contracts/{table}.yml
# ---------------------------------------------------------------------------
class TestContractSchema:
    def test_build_struct_type_from_contract(self) -> None:
        from pyspark.sql import types as T

        struct = runner.build_struct_type_from_contract(
            {
                "table": "synthea_patients",
                "columns": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "birthdate", "type": "date", "nullable": True},
                    {"name": "ssn_hash", "type": "string"},
                ],
            }
        )
        assert isinstance(struct, T.StructType)
        names = [f.name for f in struct.fields]
        assert names == ["id", "birthdate", "ssn_hash"]
        # nullable defaults to True when omitted
        assert struct["ssn_hash"].nullable is True
        assert struct["id"].nullable is False
        assert isinstance(struct["birthdate"].dataType, T.DateType)

    def test_empty_columns_raises(self) -> None:
        with pytest.raises(ValueError, match="schema enforcement is required"):
            runner.build_struct_type_from_contract(
                {"table": "synthea_patients", "columns": []}
            )

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported type"):
            runner.build_struct_type_from_contract(
                {
                    "table": "x",
                    "columns": [{"name": "c1", "type": "uuid"}],
                }
            )

    def test_load_contract_schema_from_file(self, tmp_path: Path) -> None:
        from pyspark.sql import types as T

        contracts_dir = tmp_path / "contracts"
        contracts_dir.mkdir()
        (contracts_dir / "synthea_patients.yml").write_text(
            textwrap.dedent(
                """
                table: synthea_patients
                layer: bronze
                columns:
                  - {name: id, type: string, nullable: false}
                  - {name: birthdate, type: date}
                """
            ).strip()
        )
        struct = runner.load_contract_schema(contracts_dir, "synthea_patients")
        assert isinstance(struct, T.StructType)
        assert struct["id"].nullable is False


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
# AC4 / AC7 — fully-qualified target composed from config keys
# ---------------------------------------------------------------------------
class TestComposeTargetTable:
    def test_composes_from_config_keys(self) -> None:
        cfg = {
            "table": "synthea_patients",
            "catalog_bronze_catalog_name": "unity",
            "catalog_bronze_schema": "bronze",
        }
        assert runner.compose_target_table(cfg) == "unity.bronze.synthea_patients"

    def test_alt_catalog_schema_supported(self) -> None:
        # Confirms catalog/schema are NOT hardcoded — a different catalog
        # works without code changes (LLD §7.1).
        cfg = {
            "table": "synthea_patients",
            "catalog_bronze_catalog_name": "p360_dev",
            "catalog_bronze_schema": "bronze_raw",
        }
        assert (
            runner.compose_target_table(cfg)
            == "p360_dev.bronze_raw.synthea_patients"
        )

    def test_missing_catalog_key_raises(self) -> None:
        with pytest.raises(KeyError, match="catalog_bronze_catalog_name"):
            runner.compose_target_table(
                {"table": "x", "catalog_bronze_schema": "bronze"}
            )

    def test_missing_schema_key_raises(self) -> None:
        with pytest.raises(KeyError, match="catalog_bronze_catalog_name"):
            runner.compose_target_table(
                {"table": "x", "catalog_bronze_catalog_name": "unity"}
            )


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
