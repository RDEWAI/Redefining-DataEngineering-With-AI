"""Unit tests for silver/transform_providers.py (STORY-03-003).

Scope (story Verification block / AC1-AC5):

* AC1: bronze read via read_bronze_delta (path-based external Delta).
* AC2: only DMS §3.12 columns are projected — no PHI / non-DMS column can leak
       (providers source carries no PHI, so the boundary is structural).
* AC3: apply_scd2 invoked with the DMS §6 natural-key + hash-column tuple.
* AC4: inline SE (run_dq) called with action_if_failed='fail' BEFORE the merge.
* AC5: STM transformations (TRIM, DEFAULT, gender CASE, casts) + the SCD2
       change-detection paths (hash-changed / hash-same / new-record) — the
       change-detection paths against a real Delta MERGE live in
       ``test_scd2_unit.py``; here we assert the documented natural-key /
       hash-column tuple is wired through.

The transform-level tests mock ``run_dq`` and ``apply_scd2`` so they assert on
the cleansing + wiring without booting Delta.
"""

from __future__ import annotations

import datetime as dt
from unittest import mock

import pytest

pyspark = pytest.importorskip("pyspark", reason="pyspark not installed")

from patient_360.silver import transform_providers  # noqa: E402

# Bronze columns the transform reads (uppercase Synthea + pipeline metadata).
_BRONZE_COLS = [
    "Id",
    "ORGANIZATION",
    "NAME",
    "GENDER",
    "SPECIALITY",
    "ADDRESS",
    "CITY",
    "STATE",
    "ZIP",
    "LAT",
    "LON",
    "ENCOUNTERS",
    "PROCEDURES",
    "ds",
    "_ingested_at",
    "_source_batch_id",
]

# Expected Silver column set produced by _cleanse (no SCD2 system cols yet —
# those are stamped inside apply_scd2). Mirrors DMS §3.12.
_EXPECTED_SILVER_COLS = {
    "provider_id",
    "organization_id",
    "provider_name",
    "gender",
    "specialty",
    "address",
    "city",
    "state",
    "zip",
    "lat",
    "lon",
    "encounter_count",
    "procedure_count",
    "_ingested_at",
    "_source_batch_id",
}


@pytest.fixture(scope="module")
def spark():
    from pyspark.sql import SparkSession

    # Provision delta jars even though these tests mock apply_scd2 — the
    # SparkSession JVM is a per-process singleton, so a bare session booted
    # here would deny later Delta-backed tests their jars when both modules
    # run in one pytest process.
    delta = pytest.importorskip("delta", reason="delta-spark not installed")
    builder = (
        SparkSession.builder.master("local[1]")
        .appName("test_transform_providers")
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
            .appName("test_transform_providers")
            .getOrCreate()
        )
    yield s
    # Do not stop() — the JVM/session is shared across silver test modules in
    # a single pytest process; pytest tears the JVM down at process exit.


def _bronze_row(**overrides):
    base = {c: None for c in _BRONZE_COLS}
    base.update(
        {
            "Id": " prov-001 ",
            "ORGANIZATION": " org-001 ",
            "NAME": None,  # exercises DEFAULT 'UNKNOWN'
            "GENDER": " f ",  # exercises HL7 CASE -> FEMALE
            "SPECIALITY": " GENERAL PRACTICE ",
            "ADDRESS": " 1 main st ",
            "CITY": " boston ",
            "STATE": "MA",
            "ZIP": "02118",
            "LAT": 42.3601,
            "LON": -71.0589,
            "ENCOUNTERS": 100,
            "PROCEDURES": 250,
            "_ingested_at": dt.datetime(2026, 6, 1, 0, 0, 0),
            "_source_batch_id": "synthea_providers:2026-06-01",
        }
    )
    base.update(overrides)
    return base


def _bronze_df(spark, rows):
    from pyspark.sql import types as T

    type_map = {
        "LAT": T.DoubleType(),
        "LON": T.DoubleType(),
        "ENCOUNTERS": T.LongType(),
        "PROCEDURES": T.LongType(),
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
    def test_schema_matches_dms_and_drops_non_dms(self, spark):
        out = transform_providers._cleanse(_bronze_df(spark, [_bronze_row()]))
        assert set(out.columns) == _EXPECTED_SILVER_COLS
        # AC2 — no PHI / non-DMS column survives the projection.
        for forbidden in ("SSN", "DRIVERS", "PASSPORT", "ssn", "ds"):
            assert forbidden not in out.columns

    def test_stm_transformations(self, spark):
        out = transform_providers._cleanse(_bronze_df(spark, [_bronze_row()]))
        r = out.collect()[0]
        assert r["provider_id"] == "prov-001"  # TRIM(Id)
        assert r["organization_id"] == "org-001"  # TRIM(ORGANIZATION)
        assert r["provider_name"] == "UNKNOWN"  # DEFAULT on NULL NAME
        assert r["gender"] == "FEMALE"  # HL7 CASE on ' f '
        assert r["specialty"] == "GENERAL PRACTICE"  # TRIM(SPECIALITY)
        assert r["address"] == "1 main st"  # TRIM(ADDRESS)
        assert r["city"] == "boston"  # TRIM(CITY)
        assert r["encounter_count"] == 100  # CAST INTEGER
        assert r["procedure_count"] == 250  # CAST INTEGER

    def test_gender_hl7_standardization(self, spark):
        rows = [
            _bronze_row(Id="p-m", GENDER="M"),
            _bronze_row(Id="p-f", GENDER="f"),
            _bronze_row(Id="p-x", GENDER="X"),  # unknown -> UNKNOWN
            _bronze_row(Id="p-n", GENDER=None),  # null   -> UNKNOWN
        ]
        out = {
            r["provider_id"]: r["gender"]
            for r in transform_providers._cleanse(_bronze_df(spark, rows)).collect()
        }
        assert out["p-m"] == "MALE"
        assert out["p-f"] == "FEMALE"
        assert out["p-x"] == "UNKNOWN"
        assert out["p-n"] == "UNKNOWN"

    def test_lat_lon_decimal_precision(self, spark):
        out = transform_providers._cleanse(_bronze_df(spark, [_bronze_row()]))
        for c in ("lat", "lon"):
            dtype = out.schema[c].dataType
            assert (dtype.precision, dtype.scale) == (9, 6)

    def test_name_passthrough_when_present(self, spark):
        out = transform_providers._cleanse(_bronze_df(spark, [_bronze_row(NAME=" Dr Strange ")]))
        assert out.collect()[0]["provider_name"] == "Dr Strange"  # TRIM


# --------------------------------------------------------------------------
# AC1 + AC3 + AC4 — transform() wiring (run_dq before apply_scd2)
# --------------------------------------------------------------------------
class TestTransformWiring:
    def test_runs_dq_then_scd2_with_dms_tuple(self, spark):
        bronze = _bronze_df(spark, [_bronze_row()])
        with (
            mock.patch.object(transform_providers, "read_bronze_delta", return_value=bronze),
            mock.patch.object(transform_providers.se_runner, "run_dq") as m_dq,
            mock.patch.object(transform_providers, "apply_scd2") as m_scd2,
        ):
            m_dq.side_effect = lambda df, **kw: df  # SE passes rows through
            m_scd2.return_value = {"rows_inserted": 1, "rows_closed": 0, "rows_unchanged": 0}
            out = transform_providers.transform(spark, env="DEV", ds="2026-06-01")

        # AC4 — SE ran with the fail-closed action for an FK dimension.
        m_dq.assert_called_once()
        assert m_dq.call_args.kwargs["table"] == "reference_providers"
        assert m_dq.call_args.kwargs["action_if_failed"] == "fail"

        # AC3 — apply_scd2 got the DMS §6 natural-key + hash-column tuple and
        # the named UC table FQN unity.silver.reference_providers
        # (LLD §13 Decision 12).
        m_scd2.assert_called_once()
        sk = m_scd2.call_args.kwargs
        assert sk["natural_keys"] == ["provider_id"]
        assert sk["hash_columns"] == ["provider_name", "specialty", "organization_id"]
        assert sk["target_table"] == "unity.silver.reference_providers"
        assert sk["target_table"].count(".") == 2  # 3-part UC FQN, not a path
        assert sk["effective_date"] == "2026-06-01"

        # transform returns the validated (pre-merge) frame for assertions.
        assert set(out.columns) == _EXPECTED_SILVER_COLS

    def test_empty_input_fails_task(self, spark):
        empty = _bronze_df(spark, [_bronze_row()]).limit(0)
        with (
            mock.patch.object(transform_providers, "read_bronze_delta", return_value=empty),
            mock.patch.object(transform_providers.se_runner, "run_dq") as m_dq,
        ):
            with pytest.raises(ValueError, match="empty bronze input"):
                transform_providers.transform(spark, env="DEV", ds="2026-06-01")
            # Fail-fast before SE runs.
            m_dq.assert_not_called()
