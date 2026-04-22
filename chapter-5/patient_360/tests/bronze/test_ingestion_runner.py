"""Unit tests for ``patient_360.bronze.ingestion_runner``.

Config-loading and schema-building tests run with no Spark cluster. Tests
that touch ``DataFrame`` APIs are skipped when pyspark is not installed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pyspark = pytest.importorskip("pyspark")

from patient_360.bronze.ingestion_runner import (  # noqa: E402
    EmptyInputError,
    IngestionConfigError,
    TableConfig,
    _DQ_ENV_MAP,
    _parse_spark_type,
    add_metadata_columns,
    ingest,
    load_struct_type,
    load_table_config,
)
from pyspark.sql import SparkSession  # noqa: E402
from pyspark.sql.types import (  # noqa: E402
    DateType,
    DecimalType,
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructType,
    TimestampType,
)


@pytest.fixture(scope="session")
def spark() -> SparkSession:
    return (
        SparkSession.builder.master("local[1]")
        .appName("ingestion_runner_tests")
        .config("spark.sql.shuffle.partitions", "1")
        .getOrCreate()
    )


def _write_yaml(path: Path, payload: dict) -> Path:
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


def _valid_config_payload(table: str = "patients") -> dict:
    return {
        "table": table,
        "source": {
            "schema": "synthea",
            "table": f"synthea.{table}",
            "format": "csv",
            "path": f"data/raw/{table}.csv",
        },
        "schema_ref": f"contracts/{table}.yml",
        "output_path": "warehouse/{env}/bronze/synthea_" + table + "/",
        "metadata_columns": ["ds", "_ingested_at", "_source_batch_id"],
        "empty_input_behavior": "fail",
        "dq_rules_table": table,
        "se_action_if_failed": "fail",
        "retries": 3,
        "timeout_minutes": 30,
    }


class TestLoadTableConfig:
    def test_valid_config_round_trips(self, tmp_path: Path) -> None:
        cfg = load_table_config(_write_yaml(tmp_path / "patients.yml", _valid_config_payload()))
        assert cfg.table == "patients"
        assert cfg.source_format == "csv"
        assert cfg.source_path == "data/raw/patients.csv"
        assert cfg.empty_input_behavior == "fail"
        assert cfg.metadata_columns == ("ds", "_ingested_at", "_source_batch_id")

    def test_source_table_fully_qualified(self, tmp_path: Path) -> None:
        cfg = load_table_config(_write_yaml(tmp_path / "patients.yml", _valid_config_payload()))
        assert cfg.source_table == "synthea.patients"

    def test_resolved_output_path_interpolates_env(self, tmp_path: Path) -> None:
        cfg = load_table_config(_write_yaml(tmp_path / "patients.yml", _valid_config_payload()))
        assert cfg.resolved_output_path("PROD", "2026-04-18") == (
            "warehouse/PROD/bronze/synthea_patients/"
        )

    def test_quarantine_path_default(self, tmp_path: Path) -> None:
        cfg = load_table_config(_write_yaml(tmp_path / "patients.yml", _valid_config_payload()))
        assert cfg.resolved_quarantine_path("DEV") == (
            "warehouse/DEV/quarantine/bronze/patients/"
        )

    def test_quarantine_path_from_yaml(self, tmp_path: Path) -> None:
        payload = _valid_config_payload()
        payload["quarantine_path"] = "custom/{env}/q/patients/"
        cfg = load_table_config(_write_yaml(tmp_path / "patients.yml", payload))
        assert cfg.resolved_quarantine_path("STAGING") == "custom/STAGING/q/patients/"

    def test_missing_required_key_raises(self, tmp_path: Path) -> None:
        payload = _valid_config_payload()
        payload.pop("schema_ref")
        with pytest.raises(IngestionConfigError, match="schema_ref"):
            load_table_config(_write_yaml(tmp_path / "bad.yml", payload))

    def test_invalid_empty_input_behavior_raises(self, tmp_path: Path) -> None:
        payload = _valid_config_payload()
        payload["empty_input_behavior"] = "ignore"
        with pytest.raises(IngestionConfigError, match="empty_input_behavior"):
            load_table_config(_write_yaml(tmp_path / "bad.yml", payload))

    def test_invalid_se_action_raises(self, tmp_path: Path) -> None:
        payload = _valid_config_payload()
        payload["se_action_if_failed"] = "quarantine"
        with pytest.raises(IngestionConfigError, match="se_action_if_failed"):
            load_table_config(_write_yaml(tmp_path / "bad.yml", payload))

    def test_non_mapping_yaml_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yml"
        path.write_text("- just a list\n", encoding="utf-8")
        with pytest.raises(IngestionConfigError, match="mapping"):
            load_table_config(path)


class TestParseSparkType:
    @pytest.mark.parametrize(
        ("type_name", "expected"),
        [
            ("string", StringType()),
            ("varchar", StringType()),
            ("text", StringType()),
            ("int", IntegerType()),
            ("integer", IntegerType()),
            ("bigint", LongType()),
            ("long", LongType()),
            ("double", DoubleType()),
            ("float", DoubleType()),
            ("date", DateType()),
            ("timestamp", TimestampType()),
        ],
    )
    def test_primitive_dispatch(self, type_name, expected) -> None:
        assert _parse_spark_type(type_name) == expected

    def test_decimal_default_precision_and_scale(self) -> None:
        assert _parse_spark_type("decimal") == DecimalType(18, 2)

    def test_decimal_with_explicit_precision(self) -> None:
        assert _parse_spark_type("decimal(20, 4)") == DecimalType(20, 4)

    def test_unsupported_type_raises(self) -> None:
        with pytest.raises(IngestionConfigError, match="unsupported column type"):
            _parse_spark_type("uuid")


class TestLoadStructType:
    def test_builds_struct_from_contract(self, tmp_path: Path) -> None:
        contract = {
            "table": "patients",
            "columns": [
                {"name": "id", "type": "string", "nullable": False},
                {"name": "age", "type": "int", "nullable": True},
                {"name": "salary", "type": "decimal(10, 2)", "nullable": True},
            ],
        }
        struct = load_struct_type(_write_yaml(tmp_path / "patients.yml", contract))
        assert isinstance(struct, StructType)
        assert [f.name for f in struct.fields] == ["id", "age", "salary"]
        assert struct["id"].nullable is False
        assert struct["salary"].dataType == DecimalType(10, 2)

    def test_missing_contract_raises(self, tmp_path: Path) -> None:
        with pytest.raises(IngestionConfigError, match="contract file not found"):
            load_struct_type(tmp_path / "nope.yml")

    def test_empty_contract_raises(self, tmp_path: Path) -> None:
        with pytest.raises(IngestionConfigError, match="no `columns` block"):
            load_struct_type(_write_yaml(tmp_path / "empty.yml", {"table": "patients"}))


class TestAddMetadataColumns:
    def test_adds_full_metadata_set(self, spark: SparkSession) -> None:
        df = spark.createDataFrame([(1,), (2,)], ["id"])
        out = add_metadata_columns(
            df, ds="2026-04-18",
            columns=("ds", "_ingested_at", "_source_batch_id"),
            table="patients",
        )
        assert {"ds", "_ingested_at", "_source_batch_id"}.issubset(out.columns)
        rows = out.collect()
        assert all(row.ds == "2026-04-18" for row in rows)
        assert all(row._source_batch_id == "patients:2026-04-18" for row in rows)

    def test_respects_subset(self, spark: SparkSession) -> None:
        df = spark.createDataFrame([(1,)], ["id"])
        out = add_metadata_columns(df, ds="2026-04-18", columns=("ds",))
        assert "_ingested_at" not in out.columns
        assert "_source_batch_id" not in out.columns

    def test_batch_id_defaults_when_table_missing(self, spark: SparkSession) -> None:
        df = spark.createDataFrame([(1,)], ["id"])
        out = add_metadata_columns(df, ds="2026-04-18", columns=("_source_batch_id",))
        assert out.collect()[0]._source_batch_id == "unknown:2026-04-18"


class TestIngestEmptyBehavior:
    def _make_cfg(self, behavior: str, tmp_path: Path) -> Path:
        payload = _valid_config_payload("test_table")
        payload["empty_input_behavior"] = behavior
        payload["source"]["path"] = str(tmp_path / "empty.csv")
        payload["schema_ref"] = str(tmp_path / "contract.yml")
        payload["output_path"] = str(tmp_path / "out/{env}/{ds}/")
        (tmp_path / "empty.csv").write_text("id\n", encoding="utf-8")
        _write_yaml(
            tmp_path / "contract.yml",
            {"table": "test_table", "columns": [{"name": "id", "type": "string"}]},
        )
        return _write_yaml(tmp_path / "cfg.yml", payload)

    def test_fail_behavior_raises_empty_input_error(
        self, spark: SparkSession, tmp_path: Path
    ) -> None:
        cfg_path = self._make_cfg("fail", tmp_path)
        with pytest.raises(EmptyInputError):
            ingest(spark, cfg_path, ds="2026-04-18", env="DEV")

    def test_write_empty_behavior_does_not_raise_empty_input_error(
        self, spark: SparkSession, tmp_path: Path
    ) -> None:
        cfg_path = self._make_cfg("write_empty", tmp_path)
        with pytest.raises(Exception) as exc_info:
            ingest(spark, cfg_path, ds="2026-04-18", env="DEV")
        assert not isinstance(exc_info.value, EmptyInputError)


class TestDqEnvMap:
    @pytest.mark.parametrize(
        ("runtime_env", "expected_dq_env"),
        [
            ("DEV", "DEV"),
            ("STAGING", "QA"),
            ("PROD", "PROD"),
        ],
    )
    def test_env_mapping(self, runtime_env: str, expected_dq_env: str) -> None:
        assert _DQ_ENV_MAP[runtime_env] == expected_dq_env

    def test_map_is_exhaustive_for_three_runtime_envs(self) -> None:
        assert set(_DQ_ENV_MAP.keys()) == {"DEV", "STAGING", "PROD"}


class TestTableConfigImmutable:
    def test_frozen_dataclass(self) -> None:
        cfg = TableConfig(
            table="t", source_schema="s", source_table="synthea.t",
            source_format="csv", source_path="p", schema_ref=Path("x"),
            output_path_template="o", metadata_columns=("ds",),
            empty_input_behavior="fail", dq_rules_table="t",
            se_action_if_failed="fail",
        )
        with pytest.raises((AttributeError, Exception)):
            cfg.table = "other"  # type: ignore[misc]
