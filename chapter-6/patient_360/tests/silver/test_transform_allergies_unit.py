"""Unit tests for silver/transform_allergies.py (cleansed fact).

Covers (mirrors test_transform_organizations_unit.py conventions):

* Schema invariant: _cleanse output columns == OUTPUT_COLUMNS.
* Positive STM transformation: TRIM ids, SEVERITY1 present passes through.
* Negative/edge: NULL SEVERITY1 -> severity1 == 'Unknown' (COALESCE).
* _record_hash present + 64-char hex.
* DQ-before-write wiring: run_dq once (table, action_if_failed='fail') before
  the insertInto to unity.silver.<TABLE>.
* Empty-input behavior: EMPTY=fail -> ValueError, run_dq NOT called.
"""

from __future__ import annotations

import datetime as dt
import re
from unittest import mock

import pytest

pyspark = pytest.importorskip("pyspark", reason="pyspark not installed")

from patient_360.silver import transform_allergies  # noqa: E402

_BRONZE_COLS = [
    "PATIENT",
    "ENCOUNTER",
    "CODE",
    "START",
    "STOP",
    "SYSTEM",
    "DESCRIPTION",
    "TYPE",
    "CATEGORY",
    "REACTION1",
    "DESCRIPTION1",
    "SEVERITY1",
    "REACTION2",
    "DESCRIPTION2",
    "SEVERITY2",
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
        .appName("test_transform_allergies")
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
            .appName("test_transform_allergies")
            .getOrCreate()
        )
    yield s


def _bronze_row(**overrides):
    base = {c: None for c in _BRONZE_COLS}
    base.update(
        {
            "PATIENT": " pat-001 ",
            "ENCOUNTER": " enc-001 ",
            "CODE": "419474003",
            "START": "2026-05-01",
            "STOP": "2026-06-01",
            "SYSTEM": " SNOMED-CT ",
            "DESCRIPTION": " Allergy to peanuts ",
            "TYPE": " allergy ",
            "CATEGORY": " food ",
            "REACTION1": "247472004",
            "DESCRIPTION1": " Hives ",
            "SEVERITY1": " MODERATE ",
            "REACTION2": "271807003",
            "DESCRIPTION2": " Eruption ",
            "SEVERITY2": " MILD ",
            "_ingested_at": dt.datetime(2026, 6, 1, 0, 0, 0),
            "_source_batch_id": "synthea_allergies:2026-06-01",
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
        out = transform_allergies._cleanse(_bronze_df(spark, [_bronze_row()]), "2026-06-01")
        assert set(out.columns) == set(transform_allergies.OUTPUT_COLUMNS)

    def test_stm_transformations(self, spark):
        out = transform_allergies._cleanse(_bronze_df(spark, [_bronze_row()]), "2026-06-01")
        r = out.collect()[0]
        assert r["patient_id"] == "pat-001"  # TRIM(PATIENT)
        assert r["code_system"] == "SNOMED-CT"  # TRIM(SYSTEM)
        assert r["severity1"] == "MODERATE"  # TRIM(SEVERITY1), present
        assert r["allergy_description"] == "Allergy to peanuts"

    def test_null_severity1_coalesces_unknown(self, spark):
        out = transform_allergies._cleanse(
            _bronze_df(spark, [_bronze_row(SEVERITY1=None)]), "2026-06-01"
        )
        assert out.collect()[0]["severity1"] == "Unknown"

    def test_record_hash_present_and_hex(self, spark):
        out = transform_allergies._cleanse(_bronze_df(spark, [_bronze_row()]), "2026-06-01")
        assert "_record_hash" in out.columns
        h = out.collect()[0]["_record_hash"]
        assert h is not None and _HEX64.match(h)


class TestTransformWiring:
    def test_runs_dq_before_write(self, spark):
        bronze = _bronze_df(spark, [_bronze_row()])
        with (
            mock.patch.object(transform_allergies, "read_bronze_delta", return_value=bronze),
            mock.patch.object(transform_allergies.se_runner, "run_dq") as m_dq,
        ):
            m_dq.return_value = mock.MagicMock()
            transform_allergies.transform(spark, env="DEV", ds="2026-06-01")

        m_dq.assert_called_once()
        assert m_dq.call_args.kwargs["table"] == "clinical_allergies"
        assert m_dq.call_args.kwargs["action_if_failed"] == "fail"
        writer = m_dq.return_value.select.return_value.write.mode.return_value
        writer.insertInto.assert_called_once_with("unity.silver.clinical_allergies")

    def test_empty_input_fails_task(self, spark):
        empty = _bronze_df(spark, [_bronze_row()]).limit(0)
        with (
            mock.patch.object(transform_allergies, "read_bronze_delta", return_value=empty),
            mock.patch.object(transform_allergies.se_runner, "run_dq") as m_dq,
        ):
            with pytest.raises(ValueError, match="empty bronze input"):
                transform_allergies.transform(spark, env="DEV", ds="2026-06-01")
            m_dq.assert_not_called()
