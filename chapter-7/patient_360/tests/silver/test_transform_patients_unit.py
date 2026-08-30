"""Unit tests for silver/transform_patients.py (STORY-03-001).

Scope (story Verification block / AC1-AC5):

* AC1: bronze read via read_bronze_delta (path-based external Delta).
* AC2: PHI columns (SSN, DRIVERS, PASSPORT) + FIPS dropped at Silver boundary.
* AC3: apply_scd2 invoked with the DMS §6 natural-key + hash-column tuple.
* AC4: inline SE (run_dq) called with action_if_failed='fail' BEFORE the merge.
* AC5: STM transformations (INITCAP, gender map, derived age/status) +
       SCD2 change-detection paths (hash-changed / hash-same / new-record).

The transform-level tests mock ``run_dq`` and ``apply_scd2`` so they assert
on the cleansing + wiring without booting Delta. The SCD2 change-detection
paths against a real Delta MERGE live in ``test_scd2_unit.py``.
"""

from __future__ import annotations

import datetime as dt
from unittest import mock

import pytest

pyspark = pytest.importorskip("pyspark", reason="pyspark not installed")

from patient_360.silver import transform_patients  # noqa: E402

# Bronze columns the transform reads (uppercase Synthea + pipeline metadata),
# including the PHI columns that MUST be dropped.
_BRONZE_COLS = [
    "Id",
    "BIRTHDATE",
    "DEATHDATE",
    "SSN",
    "DRIVERS",
    "PASSPORT",
    "PREFIX",
    "FIRST",
    "MIDDLE",
    "LAST",
    "SUFFIX",
    "MAIDEN",
    "MARITAL",
    "RACE",
    "ETHNICITY",
    "GENDER",
    "BIRTHPLACE",
    "ADDRESS",
    "CITY",
    "STATE",
    "COUNTY",
    "FIPS",
    "ZIP",
    "LAT",
    "LON",
    "HEALTHCARE_EXPENSES",
    "HEALTHCARE_COVERAGE",
    "INCOME",
    "ds",
    "_ingested_at",
    "_source_batch_id",
]

# Expected Silver column set produced by _cleanse (no SCD2 system cols yet —
# those are stamped inside apply_scd2).
_EXPECTED_SILVER_COLS = {
    "patient_id",
    "birth_date",
    "death_date",
    "prefix",
    "first_name",
    "middle_name",
    "last_name",
    "suffix",
    "maiden_name",
    "marital_status",
    "race",
    "ethnicity",
    "gender",
    "birth_place",
    "address",
    "city",
    "state",
    "county",
    "zip",
    "lat",
    "lon",
    "healthcare_expenses",
    "healthcare_coverage",
    "income",
    "calculated_age",
    "patient_status",
    "_ingested_at",
    "_source_batch_id",
}


@pytest.fixture(scope="module")
def spark():
    from pyspark.sql import SparkSession

    # Provision delta jars even though these tests mock apply_scd2 — the
    # SparkSession JVM is a per-process singleton, so a bare session booted
    # here would deny later Delta-backed tests (e.g. test_scd2_unit) their
    # jars when both modules run in one pytest process.
    delta = pytest.importorskip("delta", reason="delta-spark not installed")
    builder = (
        SparkSession.builder.master("local[1]")
        .appName("test_transform_patients")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
    )
    try:
        s = delta.configure_spark_with_delta_pip(builder).getOrCreate()
    except Exception:  # pragma: no cover - offline / no-jar env
        s = SparkSession.builder.master("local[1]").appName("test_transform_patients").getOrCreate()
    yield s
    # Do not stop() — the JVM/session is shared across silver test modules in
    # a single pytest process; stopping here would break a sibling module's
    # session. pytest tears the JVM down at process exit.


def _bronze_row(**overrides):
    base = {c: None for c in _BRONZE_COLS}
    base.update(
        {
            "Id": " p-001 ",
            "BIRTHDATE": dt.date(1990, 1, 1),
            "DEATHDATE": None,
            "SSN": "999-11-2222",
            "DRIVERS": "S99",
            "PASSPORT": "X123",
            "FIRST": " john ",
            "LAST": " doe ",
            "GENDER": "m",
            "RACE": "white",
            "ETHNICITY": "nonhispanic",
            "MARITAL": "M",
            "ADDRESS": None,  # exercises DEFAULT 'UNKNOWN'
            "CITY": "boston",
            "STATE": "MA",
            "COUNTY": "Suffolk",
            "ZIP": "02118",
            "HEALTHCARE_EXPENSES": 1000.5,
            "HEALTHCARE_COVERAGE": 800.25,
            "INCOME": 50000,
            "_ingested_at": dt.datetime(2026, 6, 1, 0, 0, 0),
            "_source_batch_id": "synthea_patients:2026-06-01",
        }
    )
    base.update(overrides)
    return base


def _bronze_df(spark, rows):
    from pyspark.sql import types as T

    type_map = {
        "BIRTHDATE": T.DateType(),
        "DEATHDATE": T.DateType(),
        "FIPS": T.LongType(),
        "LAT": T.DoubleType(),
        "LON": T.DoubleType(),
        "HEALTHCARE_EXPENSES": T.DoubleType(),
        "HEALTHCARE_COVERAGE": T.DoubleType(),
        "INCOME": T.LongType(),
        "_ingested_at": T.TimestampType(),
    }
    schema = T.StructType(
        [T.StructField(c, type_map.get(c, T.StringType()), True) for c in _BRONZE_COLS]
    )
    return spark.createDataFrame([tuple(r[c] for c in _BRONZE_COLS) for r in rows], schema)


# --------------------------------------------------------------------------
# AC2 + AC5 — cleansing: schema invariant + STM transformations
# --------------------------------------------------------------------------
class TestCleanse:
    def test_schema_matches_dms_and_drops_phi(self, spark):
        out = transform_patients._cleanse(_bronze_df(spark, [_bronze_row()]))
        assert set(out.columns) == _EXPECTED_SILVER_COLS
        # AC2 — PHI / non-clinical never present in the projection.
        for forbidden in ("SSN", "DRIVERS", "PASSPORT", "FIPS", "ssn"):
            assert forbidden not in out.columns

    def test_stm_transformations(self, spark):
        out = transform_patients._cleanse(_bronze_df(spark, [_bronze_row()]))
        r = out.collect()[0]
        assert r["patient_id"] == "p-001"  # TRIM(Id)
        assert r["first_name"] == "John"  # INITCAP(TRIM(FIRST))
        assert r["last_name"] == "Doe"  # INITCAP(TRIM(LAST))
        assert r["gender"] == "MALE"  # CASE 'm' -> MALE
        assert r["race"] == "WHITE"  # UPPER(TRIM(RACE))
        assert r["address"] == "UNKNOWN"  # DEFAULT on NULL address
        assert r["patient_status"] == "ALIVE"  # death_date IS NULL
        assert r["calculated_age"] == 36  # 2026 - 1990

    def test_deceased_status_and_age_to_deathdate(self, spark):
        row = _bronze_row(DEATHDATE=dt.date(2020, 1, 1))
        out = transform_patients._cleanse(_bronze_df(spark, [row]))
        r = out.collect()[0]
        assert r["patient_status"] == "DECEASED"
        assert r["calculated_age"] == 30  # 2020 - 1990

    def test_unknown_gender_maps_to_unknown(self, spark):
        out = transform_patients._cleanse(_bronze_df(spark, [_bronze_row(GENDER="X")]))
        assert out.collect()[0]["gender"] == "UNKNOWN"


# --------------------------------------------------------------------------
# AC1 + AC3 + AC4 — transform() wiring (run_dq before apply_scd2)
# --------------------------------------------------------------------------
class TestTransformWiring:
    def _patch_cfg(self):
        cfg = mock.Mock()
        cfg.get.return_value = "warehouse/dev"
        return cfg

    def test_runs_dq_then_scd2_with_dms_tuple(self, spark):
        bronze = _bronze_df(spark, [_bronze_row()])
        with (
            mock.patch.object(transform_patients, "read_bronze_delta", return_value=bronze),
            mock.patch.object(transform_patients, "load_config", return_value=self._patch_cfg()),
            mock.patch.object(transform_patients.se_runner, "run_dq") as m_dq,
            mock.patch.object(transform_patients, "apply_scd2") as m_scd2,
        ):
            m_dq.side_effect = lambda df, **kw: df  # SE passes rows through
            m_scd2.return_value = {"rows_inserted": 1, "rows_closed": 0, "rows_unchanged": 0}
            out = transform_patients.transform(spark, env="DEV", ds="2026-06-01")

        # AC4 — SE ran with the fail-closed action for a required table.
        m_dq.assert_called_once()
        assert m_dq.call_args.kwargs["table"] == "clinical_patients"
        assert m_dq.call_args.kwargs["action_if_failed"] == "fail"

        # AC3 — apply_scd2 got the DMS §6 natural-key + hash-column tuple
        # and the named UC table FQN unity.silver.clinical_patients (LLD §13
        # Decision 12).
        m_scd2.assert_called_once()
        sk = m_scd2.call_args.kwargs
        assert sk["natural_keys"] == ["patient_id"]
        assert sk["hash_columns"] == [
            "first_name",
            "last_name",
            "maiden_name",
            "address",
            "city",
            "state",
            "county",
            "zip",
            "marital_status",
            "healthcare_expenses",
            "healthcare_coverage",
            "income",
        ]
        assert sk["target_table"] == "unity.silver.clinical_patients"
        assert sk["target_table"].count(".") == 2  # 3-part UC FQN, not a path
        assert sk["effective_date"] == "2026-06-01"

        # transform returns the validated (pre-merge) frame for assertions.
        assert set(out.columns) == _EXPECTED_SILVER_COLS

    def test_empty_input_fails_task(self, spark):
        empty = _bronze_df(spark, [_bronze_row()]).limit(0)
        with (
            mock.patch.object(transform_patients, "read_bronze_delta", return_value=empty),
            mock.patch.object(transform_patients, "load_config", return_value=self._patch_cfg()),
            mock.patch.object(transform_patients.se_runner, "run_dq") as m_dq,
        ):
            with pytest.raises(ValueError, match="empty bronze input"):
                transform_patients.transform(spark, env="DEV", ds="2026-06-01")
            # Fail-fast before SE runs.
            m_dq.assert_not_called()
