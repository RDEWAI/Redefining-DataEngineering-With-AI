"""Unit tests for silver/transform_observations.py (cleansed fact).

Covers (mirrors test_transform_organizations_unit.py conventions):

* Schema invariant: _cleanse output columns == OUTPUT_COLUMNS.
* Positive STM transformation: TRIM strips whitespace on value / units.
* Negative/edge: NULL VALUE passes through as NULL observation_value.
* _record_hash present + 64-char hex.
* DQ-before-write wiring: run_dq once (table, action_if_failed='fail') before
  the insertInto to unity.silver.<TABLE>.
* Empty-input behavior: EMPTY=write_empty -> 0-row frame w/ OUTPUT_COLUMNS,
  run_dq NOT called (insertInto stubbed to no-op).
"""

from __future__ import annotations

import datetime as dt
import re
from unittest import mock

import pytest

pyspark = pytest.importorskip("pyspark", reason="pyspark not installed")

from patient_360.silver import transform_observations  # noqa: E402

_BRONZE_COLS = [
    "PATIENT",
    "ENCOUNTER",
    "CODE",
    "DATE",
    "CATEGORY",
    "DESCRIPTION",
    "VALUE",
    "UNITS",
    "TYPE",
    "ds",
    "_ingested_at",
    "_source_batch_id",
]

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


@pytest.fixture(scope="module")
def spark():
    from pyspark.sql import SparkSession

    delta = pytest.importorskip("delta", reason="delta-spark not installed")
    builder = (
        SparkSession.builder.master("local[1]")
        .appName("test_transform_observations")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
    )
    try:
        s = delta.configure_spark_with_delta_pip(builder).getOrCreate()
    except Exception:  # pragma: no cover - offline / no-jar env
        s = (
            SparkSession.builder.master("local[1]")
            .appName("test_transform_observations")
            .getOrCreate()
        )
    yield s


def _bronze_row(**overrides):
    base = {c: None for c in _BRONZE_COLS}
    base.update(
        {
            "PATIENT": " pat-001 ",
            "ENCOUNTER": " enc-001 ",
            "CODE": "8302-2",
            "DATE": "2026-05-01 10:00:00",
            "CATEGORY": " vital-signs ",
            "DESCRIPTION": " Body Height ",
            "VALUE": " 170.5 ",
            "UNITS": " cm ",
            "TYPE": " numeric ",
            "_ingested_at": dt.datetime(2026, 6, 1, 0, 0, 0),
            "_source_batch_id": "synthea_observations:2026-06-01",
        }
    )
    base.update(overrides)
    return base


def _bronze_df(spark, rows):
    from pyspark.sql import types as T

    type_map = {"_ingested_at": T.TimestampType()}
    schema = T.StructType(
        [T.StructField(c, type_map.get(c, T.StringType()), True) for c in _BRONZE_COLS]
    )
    return spark.createDataFrame([tuple(r[c] for c in _BRONZE_COLS) for r in rows], schema)


class TestCleanse:
    def test_schema_invariant(self, spark):
        out = transform_observations._cleanse(_bronze_df(spark, [_bronze_row()]), "2026-06-01")
        assert set(out.columns) == set(transform_observations.OUTPUT_COLUMNS)

    def test_stm_transformations(self, spark):
        out = transform_observations._cleanse(_bronze_df(spark, [_bronze_row()]), "2026-06-01")
        r = out.collect()[0]
        assert r["patient_id"] == "pat-001"  # TRIM(PATIENT)
        assert r["observation_value"] == "170.5"  # TRIM(VALUE)
        assert r["units"] == "cm"  # TRIM(UNITS)
        assert r["loinc_code"] == "8302-2"  # TRIM(CODE)

    def test_null_value_passes_through(self, spark):
        out = transform_observations._cleanse(
            _bronze_df(spark, [_bronze_row(VALUE=None)]), "2026-06-01"
        )
        assert out.collect()[0]["observation_value"] is None

    def test_record_hash_present_and_hex(self, spark):
        out = transform_observations._cleanse(_bronze_df(spark, [_bronze_row()]), "2026-06-01")
        assert "_record_hash" in out.columns
        h = out.collect()[0]["_record_hash"]
        assert h is not None and _HEX64.match(h)


class TestTransformWiring:
    def test_runs_dq_before_write(self, spark):
        bronze = _bronze_df(spark, [_bronze_row()])
        with (
            mock.patch.object(transform_observations, "read_bronze_delta", return_value=bronze),
            mock.patch.object(transform_observations.se_runner, "run_dq") as m_dq,
        ):
            m_dq.return_value = mock.MagicMock()
            transform_observations.transform(spark, env="DEV", ds="2026-06-01")

        m_dq.assert_called_once()
        assert m_dq.call_args.kwargs["table"] == "clinical_observations"
        assert m_dq.call_args.kwargs["action_if_failed"] == "fail"
        writer = m_dq.return_value.select.return_value.write.mode.return_value
        writer.insertInto.assert_called_once_with("unity.silver.clinical_observations")

    def test_empty_input_writes_empty(self, spark, monkeypatch):
        monkeypatch.setattr(
            "pyspark.sql.readwriter.DataFrameWriter.insertInto",
            lambda self, name: None,
        )
        empty = _bronze_df(spark, [_bronze_row()]).limit(0)
        with (
            mock.patch.object(transform_observations, "read_bronze_delta", return_value=empty),
            mock.patch.object(transform_observations.se_runner, "run_dq") as m_dq,
        ):
            out = transform_observations.transform(spark, env="DEV", ds="2026-06-01")

        assert out.count() == 0
        assert list(out.columns) == list(transform_observations.OUTPUT_COLUMNS)
        m_dq.assert_not_called()
