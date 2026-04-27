"""Unit tests for the Bronze ingestion runner.

Spark-dependent assertions skip when pyspark is not installed.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from patient_360.bronze import ingestion_runner as IR

# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _write_cfg(tmp_path: Path, **overrides) -> Path:
    cfg = {
        "table": "synthea_patients",
        "target": "unity.bronze.synthea_patients",
        "source": {"schema": "synthea", "table": "patients", "format": "csv", "path": "/tmp/x.csv"},
        "schema_ref": "contracts/synthea_patients.yml",
        "metadata_columns": ["ds", "_ingested_at", "_source_batch_id"],
        "empty_input_behavior": "fail",
        "dq_rules_table": "synthea_patients",
        "se_action_if_failed": "fail",
        "quarantine_path": "warehouse/{env}/quarantine/bronze/{table}/",
    }
    cfg.update(overrides)
    p = tmp_path / "patients.yml"
    p.write_text(yaml.safe_dump(cfg))
    return p


# --------------------------------------------------------------------------- #
# load_table_config                                                           #
# --------------------------------------------------------------------------- #


def test_load_table_config_happy_path(tmp_path):
    p = _write_cfg(tmp_path)
    cfg = IR.load_table_config(p)
    assert cfg.table == "synthea_patients"
    assert cfg.target == "unity.bronze.synthea_patients"
    assert cfg.empty_input_behavior == "fail"
    assert cfg.se_action_if_failed == "fail"
    assert cfg.metadata_columns == ["ds", "_ingested_at", "_source_batch_id"]
    assert cfg.quarantine_path_template == "warehouse/{env}/quarantine/bronze/{table}/"


def test_load_table_config_missing_file(tmp_path):
    with pytest.raises(IR.ConfigError, match="not found"):
        IR.load_table_config(tmp_path / "nope.yml")


def test_load_table_config_missing_required_keys(tmp_path):
    p = tmp_path / "broken.yml"
    p.write_text(yaml.safe_dump({"table": "x"}))
    with pytest.raises(IR.ConfigError, match="Missing required keys"):
        IR.load_table_config(p)


def test_load_table_config_invalid_empty_input(tmp_path):
    p = _write_cfg(tmp_path, empty_input_behavior="bogus")
    with pytest.raises(IR.ConfigError, match="empty_input_behavior"):
        IR.load_table_config(p)


def test_load_table_config_invalid_se_action(tmp_path):
    p = _write_cfg(tmp_path, se_action_if_failed="explode")
    with pytest.raises(IR.ConfigError, match="se_action_if_failed"):
        IR.load_table_config(p)


def test_resolved_quarantine_path(tmp_path):
    p = _write_cfg(tmp_path)
    cfg = IR.load_table_config(p)
    assert (
        cfg.resolved_quarantine_path("dev") == "warehouse/dev/quarantine/bronze/synthea_patients/"
    )


# --------------------------------------------------------------------------- #
# _DQ_ENV_MAP                                                                  #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "runtime,expected",
    [
        ("DEV", "DEV"),
        ("STAGING", "QA"),
        ("PROD", "PROD"),
    ],
)
def test_dq_env_map(runtime, expected):
    assert IR._DQ_ENV_MAP[runtime] == expected


# --------------------------------------------------------------------------- #
# _parse_spark_type / load_struct_type                                         #
# --------------------------------------------------------------------------- #


pytest.importorskip("pyspark")


def test_parse_spark_type_primitives():
    from pyspark.sql import types as T

    assert isinstance(IR._parse_spark_type("VARCHAR"), T.StringType)
    assert isinstance(IR._parse_spark_type("INT"), T.IntegerType)
    assert isinstance(IR._parse_spark_type("BIGINT"), T.LongType)
    assert isinstance(IR._parse_spark_type("DOUBLE"), T.DoubleType)
    assert isinstance(IR._parse_spark_type("BOOLEAN"), T.BooleanType)
    assert isinstance(IR._parse_spark_type("DATE"), T.DateType)
    assert isinstance(IR._parse_spark_type("TIMESTAMP"), T.TimestampType)


def test_parse_spark_type_decimal():
    from pyspark.sql import types as T

    t = IR._parse_spark_type("DECIMAL(10,2)")
    assert isinstance(t, T.DecimalType)
    assert t.precision == 10 and t.scale == 2


def test_parse_spark_type_unsupported():
    with pytest.raises(IR.ConfigError, match="Unsupported"):
        IR._parse_spark_type("UUID_BLOB")


def test_load_struct_type(tmp_path):
    contract = tmp_path / "c.yml"
    contract.write_text(
        dedent("""
        table: synthea_patients
        columns:
          - {name: Id, type: VARCHAR, nullable: false}
          - {name: BIRTHDATE, type: DATE, nullable: true}
        """)
    )
    schema = IR.load_struct_type(contract)
    assert [f.name for f in schema.fields] == ["Id", "BIRTHDATE"]
    assert schema.fields[0].nullable is False


# --------------------------------------------------------------------------- #
# add_metadata_columns                                                         #
# --------------------------------------------------------------------------- #


def test_add_metadata_columns_deterministic_batch_id():
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.appName("test_add_meta").master("local[1]").getOrCreate()
    try:
        df = spark.createDataFrame([(1,)], ["id"])
        out = IR.add_metadata_columns(df, table="t", ds="2026-04-27")
        cols = out.columns
        assert "ds" in cols
        assert "_ingested_at" in cols
        assert "_source_batch_id" in cols
        row = out.collect()[0]
        assert row["_source_batch_id"] == "t:2026-04-27"
        assert row["ds"] == "2026-04-27"
    finally:
        spark.stop()
