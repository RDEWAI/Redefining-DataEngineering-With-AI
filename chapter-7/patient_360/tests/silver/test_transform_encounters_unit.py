"""Unit tests for silver/transform_encounters.py (cleansed fact).

Covers (mirrors test_transform_organizations_unit.py conventions):

* Schema invariant: _cleanse output columns == OUTPUT_COLUMNS.
* Positive STM transformation: TRIM on ids, COALESCE cost -> 0.
* Negative/edge: NULL STOP -> NULL duration / non-readmission default False.
* _record_hash present + 64-char hex.
* DQ-before-write wiring: run_dq called once (table, action_if_failed='fail')
  before the insertInto to unity.silver.<TABLE>.
* Empty-input behavior: EMPTY=fail -> ValueError, run_dq NOT called.
"""

from __future__ import annotations

import datetime as dt
import re
from unittest import mock

import pytest

pyspark = pytest.importorskip("pyspark", reason="pyspark not installed")

from patient_360.silver import transform_encounters  # noqa: E402

# Uppercase Synthea source columns _cleanse reads, plus pipeline metadata.
_BRONZE_COLS = [
    "Id",
    "PATIENT",
    "ORGANIZATION",
    "PROVIDER",
    "PAYER",
    "ENCOUNTERCLASS",
    "CODE",
    "DESCRIPTION",
    "START",
    "STOP",
    "BASE_ENCOUNTER_COST",
    "TOTAL_CLAIM_COST",
    "PAYER_COVERAGE",
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
        .appName("test_transform_encounters")
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
            .appName("test_transform_encounters")
            .getOrCreate()
        )
    yield s
    # Do not stop() — JVM/session shared across silver test modules.


def _bronze_row(**overrides):
    base = {c: None for c in _BRONZE_COLS}
    base.update(
        {
            "Id": " enc-001 ",
            "PATIENT": " pat-001 ",
            "ORGANIZATION": " org-001 ",
            "PROVIDER": " prov-001 ",
            "PAYER": " pay-001 ",
            "ENCOUNTERCLASS": " ambulatory ",
            "CODE": "185349003",
            "DESCRIPTION": " Encounter for check up ",
            "START": "2026-05-01 08:00:00",
            "STOP": "2026-05-01 09:30:00",
            "BASE_ENCOUNTER_COST": 100.50,
            "TOTAL_CLAIM_COST": 250.75,
            "PAYER_COVERAGE": 200.00,
            "REASONCODE": "162673000",
            "REASONDESCRIPTION": " General examination ",
            "_ingested_at": dt.datetime(2026, 6, 1, 0, 0, 0),
            "_source_batch_id": "synthea_encounters:2026-06-01",
        }
    )
    base.update(overrides)
    return base


def _bronze_df(spark, rows):
    from pyspark.sql import types as T

    type_map = {
        "BASE_ENCOUNTER_COST": T.DoubleType(),
        "TOTAL_CLAIM_COST": T.DoubleType(),
        "PAYER_COVERAGE": T.DoubleType(),
        "_ingested_at": T.TimestampType(),
    }
    schema = T.StructType(
        [T.StructField(c, type_map.get(c, T.StringType()), True) for c in _BRONZE_COLS]
    )
    return spark.createDataFrame([tuple(r[c] for c in _BRONZE_COLS) for r in rows], schema)


class TestCleanse:
    def test_schema_invariant(self, spark):
        out = transform_encounters._cleanse(_bronze_df(spark, [_bronze_row()]), "2026-06-01")
        assert set(out.columns) == set(transform_encounters.OUTPUT_COLUMNS)

    def test_stm_transformations(self, spark):
        out = transform_encounters._cleanse(_bronze_df(spark, [_bronze_row()]), "2026-06-01")
        r = out.collect()[0]
        assert r["encounter_id"] == "enc-001"  # TRIM(Id)
        assert r["patient_id"] == "pat-001"  # TRIM(PATIENT)
        assert r["encounter_class"] == "AMBULATORY"  # UPPER(TRIM(ENCOUNTERCLASS))
        assert str(r["base_encounter_cost"]) == "100.50"

    def test_null_cost_defaults_to_zero(self, spark):
        out = transform_encounters._cleanse(
            _bronze_df(spark, [_bronze_row(BASE_ENCOUNTER_COST=None)]), "2026-06-01"
        )
        assert str(out.collect()[0]["base_encounter_cost"]) == "0.00"

    def test_null_stop_yields_null_duration(self, spark):
        out = transform_encounters._cleanse(
            _bronze_df(spark, [_bronze_row(STOP=None)]), "2026-06-01"
        )
        r = out.collect()[0]
        assert r["encounter_duration_hours"] is None
        # non-INPATIENT row never flags as a 30-day readmission.
        assert r["is_30_day_readmission"] is False

    def test_record_hash_present_and_hex(self, spark):
        out = transform_encounters._cleanse(_bronze_df(spark, [_bronze_row()]), "2026-06-01")
        assert "_record_hash" in out.columns
        h = out.collect()[0]["_record_hash"]
        assert h is not None and _HEX64.match(h)


class TestTransformWiring:
    def test_runs_dq_before_write(self, spark):
        bronze = _bronze_df(spark, [_bronze_row()])
        with (
            mock.patch.object(transform_encounters, "read_bronze_delta", return_value=bronze),
            mock.patch.object(transform_encounters.se_runner, "run_dq") as m_dq,
        ):
            m_dq.return_value = mock.MagicMock()  # no-op .select(...).write... chain
            transform_encounters.transform(spark, env="DEV", ds="2026-06-01")

        m_dq.assert_called_once()
        assert m_dq.call_args.kwargs["table"] == "clinical_encounters"
        assert m_dq.call_args.kwargs["action_if_failed"] == "fail"
        # validated frame written via insertInto to the 3-part UC FQN.
        writer = m_dq.return_value.select.return_value.write.mode.return_value
        writer.insertInto.assert_called_once_with("unity.silver.clinical_encounters")

    def test_empty_input_fails_task(self, spark):
        empty = _bronze_df(spark, [_bronze_row()]).limit(0)
        with (
            mock.patch.object(transform_encounters, "read_bronze_delta", return_value=empty),
            mock.patch.object(transform_encounters.se_runner, "run_dq") as m_dq,
        ):
            with pytest.raises(ValueError, match="empty bronze input"):
                transform_encounters.transform(spark, env="DEV", ds="2026-06-01")
            m_dq.assert_not_called()
