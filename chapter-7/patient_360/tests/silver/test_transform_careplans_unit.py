"""Unit tests for silver/transform_careplans.py (cleansed fact).

Scope:

* Schema invariant: ``_cleanse`` projects exactly ``OUTPUT_COLUMNS``.
* STM transformations: TRIM strips whitespace; careplan_id == TRIM(Id).
* Edge: STOP present casts to a date.
* _record_hash present and a 64-char hex digest.
* DQ-before-write wiring: run_dq called once (action_if_failed='fail') and the
  validated frame is written via insertInto to unity.silver.<TABLE>.
* Empty-input (write_empty): returns a 0-row OUTPUT_COLUMNS frame, run_dq NOT
  called.

These tests mock ``read_bronze_delta`` / ``run_dq`` so the wiring is asserted
without booting Delta.
"""

from __future__ import annotations

import datetime as dt
import re
from unittest import mock

import pytest

pyspark = pytest.importorskip("pyspark", reason="pyspark not installed")

from patient_360.silver import transform_careplans as T_MOD  # noqa: E402

# Every uppercase source column _cleanse references via F.col(...) + metadata.
_BRONZE_COLS = [
    "Id",
    "PATIENT",
    "ENCOUNTER",
    "START",
    "STOP",
    "CODE",
    "DESCRIPTION",
    "REASONCODE",
    "REASONDESCRIPTION",
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
        .appName("test_transform_careplans")
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
            .appName("test_transform_careplans")
            .getOrCreate()
        )
    yield s
    # Do not stop() — JVM/session shared across silver test modules.


def _bronze_row(**overrides):
    base = {c: None for c in _BRONZE_COLS}
    base.update(
        {
            "Id": " cp-001 ",
            "PATIENT": " pat-001 ",
            "ENCOUNTER": " enc-001 ",
            "START": dt.date(2026, 5, 30),
            "STOP": dt.date(2026, 6, 5),
            "CODE": 734163000,
            "DESCRIPTION": " Care plan ",
            "REASONCODE": 444814009,
            "REASONDESCRIPTION": " Viral sinusitis ",
            "_ingested_at": dt.datetime(2026, 6, 1, 0, 0, 0),
            "_source_batch_id": "synthea_careplans:2026-06-01",
        }
    )
    base.update(overrides)
    return base


def _bronze_df(spark, rows):
    from pyspark.sql import types as T

    type_map = {
        "START": T.DateType(),
        "STOP": T.DateType(),
        "CODE": T.LongType(),
        "REASONCODE": T.LongType(),
        "_ingested_at": T.TimestampType(),
    }
    schema = T.StructType(
        [T.StructField(c, type_map.get(c, T.StringType()), True) for c in _BRONZE_COLS]
    )
    return spark.createDataFrame([tuple(r[c] for c in _BRONZE_COLS) for r in rows], schema)


class TestCleanse:
    def test_schema_matches_output_columns(self, spark):
        out = T_MOD._cleanse(_bronze_df(spark, [_bronze_row()]), "2026-06-01")
        assert set(out.columns) == set(T_MOD.OUTPUT_COLUMNS)

    def test_stm_transformations(self, spark):
        out = T_MOD._cleanse(_bronze_df(spark, [_bronze_row()]), "2026-06-01")
        r = out.collect()[0]
        assert r["careplan_id"] == "cp-001"  # TRIM(Id)
        assert r["patient_id"] == "pat-001"  # TRIM(PATIENT)
        assert r["encounter_id"] == "enc-001"  # TRIM(ENCOUNTER)
        assert r["snomed_code"] == "734163000"  # CAST(CODE AS STRING)
        assert r["careplan_description"] == "Care plan"  # TRIM
        assert r["reason_description"] == "Viral sinusitis"  # TRIM

    def test_stop_casts_to_date(self, spark):
        from pyspark.sql import types as T

        out = T_MOD._cleanse(_bronze_df(spark, [_bronze_row()]), "2026-06-01")
        assert isinstance(out.schema["stop_date"].dataType, T.DateType)
        assert out.collect()[0]["stop_date"] == dt.date(2026, 6, 5)

    def test_record_hash_is_64_char_hex(self, spark):
        out = T_MOD._cleanse(_bronze_df(spark, [_bronze_row()]), "2026-06-01")
        assert "_record_hash" in out.columns
        h = out.collect()[0]["_record_hash"]
        assert _HEX64.match(h)


class TestTransformWiring:
    def test_runs_dq_before_write(self, spark):
        bronze = _bronze_df(spark, [_bronze_row()])
        with (
            mock.patch.object(T_MOD, "read_bronze_delta", return_value=bronze),
            mock.patch.object(T_MOD.se_runner, "run_dq") as m_dq,
        ):
            m_dq.return_value = mock.MagicMock()
            T_MOD.transform(spark, env="DEV", ds="2026-06-01")

        m_dq.assert_called_once()
        assert m_dq.call_args.kwargs["table"] == T_MOD.TABLE
        assert m_dq.call_args.kwargs["action_if_failed"] == "fail"
        (
            m_dq.return_value.select.return_value.write.mode.return_value.insertInto
        ).assert_called_once_with(f"unity.silver.{T_MOD.TABLE}")

    def test_empty_input_writes_empty_and_skips_dq(self, spark, monkeypatch):
        empty = _bronze_df(spark, [_bronze_row()]).limit(0)
        monkeypatch.setattr(
            "pyspark.sql.readwriter.DataFrameWriter.insertInto",
            lambda self, name: None,
        )
        with (
            mock.patch.object(T_MOD, "read_bronze_delta", return_value=empty),
            mock.patch.object(T_MOD.se_runner, "run_dq") as m_dq,
        ):
            out = T_MOD.transform(spark, env="DEV", ds="2026-06-01")

        assert out.count() == 0
        assert set(out.columns) == set(T_MOD.OUTPUT_COLUMNS)
        m_dq.assert_not_called()
