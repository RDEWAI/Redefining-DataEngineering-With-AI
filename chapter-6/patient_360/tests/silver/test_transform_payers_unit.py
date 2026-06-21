"""Unit tests for silver/transform_payers.py (STORY-03-004).

Scope (story Verification block / AC1-AC5):

* AC1: bronze read via read_bronze_delta (path-based external Delta).
* AC2: only DMS §3.13 columns are projected — no PHI / non-DMS column can leak
       (payers source carries no PHI, so the boundary is structural).
* AC3: apply_scd2 invoked with the DMS §6 natural-key + hash-column tuple.
* AC4: inline SE (run_dq) called with action_if_failed='fail' BEFORE the merge.
* AC5: STM transformations (TRIM, DEFAULT, casts) + the SCD2 change-detection
       paths (hash-changed / hash-same / new-record) — the change-detection
       paths against a real Delta MERGE live in ``test_scd2_unit.py``; here we
       assert the documented natural-key / hash-column tuple is wired through.

The transform-level tests mock ``run_dq`` and ``apply_scd2`` so they assert on
the cleansing + wiring without booting Delta.
"""

from __future__ import annotations

import datetime as dt
from unittest import mock

import pytest

pyspark = pytest.importorskip("pyspark", reason="pyspark not installed")

from patient_360.silver import transform_payers  # noqa: E402

# Bronze columns the transform reads (uppercase Synthea + pipeline metadata).
_BRONZE_COLS = [
    "Id",
    "NAME",
    "OWNERSHIP",
    "ADDRESS",
    "CITY",
    "STATE_HEADQUARTERED",
    "ZIP",
    "PHONE",
    "AMOUNT_COVERED",
    "AMOUNT_UNCOVERED",
    "REVENUE",
    "COVERED_ENCOUNTERS",
    "UNCOVERED_ENCOUNTERS",
    "UNIQUE_CUSTOMERS",
    "MEMBER_MONTHS",
    "ds",
    "_ingested_at",
    "_source_batch_id",
]

# Expected Silver column set produced by _cleanse (no SCD2 system cols yet —
# those are stamped inside apply_scd2). Mirrors DMS §3.13.
_EXPECTED_SILVER_COLS = {
    "payer_id",
    "payer_name",
    "ownership",
    "address",
    "city",
    "state",
    "zip",
    "phone",
    "amount_covered",
    "amount_uncovered",
    "revenue",
    "covered_encounters",
    "uncovered_encounters",
    "unique_customers",
    "member_months",
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
        .appName("test_transform_payers")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
    )
    try:
        s = delta.configure_spark_with_delta_pip(builder).getOrCreate()
    except Exception:  # pragma: no cover - offline / no-jar env
        s = SparkSession.builder.master("local[1]").appName("test_transform_payers").getOrCreate()
    yield s
    # Do not stop() — the JVM/session is shared across silver test modules in
    # a single pytest process; pytest tears the JVM down at process exit.


def _bronze_row(**overrides):
    base = {c: None for c in _BRONZE_COLS}
    base.update(
        {
            "Id": " pay-001 ",
            "NAME": None,  # exercises DEFAULT 'UNKNOWN'
            "OWNERSHIP": " GOVERNMENT ",
            "ADDRESS": " 1 main st ",
            "CITY": " boston ",
            "STATE_HEADQUARTERED": "MA",
            "ZIP": "02118",
            "PHONE": " 555-0100 ",
            "AMOUNT_COVERED": 1234.5,
            "AMOUNT_UNCOVERED": 678.9,
            "REVENUE": 4242.42,
            "COVERED_ENCOUNTERS": 100,
            "UNCOVERED_ENCOUNTERS": 20,
            "UNIQUE_CUSTOMERS": 50,
            "MEMBER_MONTHS": 600,
            "_ingested_at": dt.datetime(2026, 6, 1, 0, 0, 0),
            "_source_batch_id": "synthea_payers:2026-06-01",
        }
    )
    base.update(overrides)
    return base


def _bronze_df(spark, rows):
    from pyspark.sql import types as T

    type_map = {
        "AMOUNT_COVERED": T.DoubleType(),
        "AMOUNT_UNCOVERED": T.DoubleType(),
        "REVENUE": T.DoubleType(),
        "COVERED_ENCOUNTERS": T.LongType(),
        "UNCOVERED_ENCOUNTERS": T.LongType(),
        "UNIQUE_CUSTOMERS": T.LongType(),
        "MEMBER_MONTHS": T.LongType(),
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
        out = transform_payers._cleanse(_bronze_df(spark, [_bronze_row()]))
        assert set(out.columns) == _EXPECTED_SILVER_COLS
        # AC2 — no PHI / non-DMS column survives the projection.
        for forbidden in ("SSN", "DRIVERS", "PASSPORT", "ssn", "ds"):
            assert forbidden not in out.columns

    def test_stm_transformations(self, spark):
        out = transform_payers._cleanse(_bronze_df(spark, [_bronze_row()]))
        r = out.collect()[0]
        assert r["payer_id"] == "pay-001"  # TRIM(Id)
        assert r["payer_name"] == "UNKNOWN"  # DEFAULT on NULL NAME
        assert r["ownership"] == "GOVERNMENT"  # TRIM(OWNERSHIP)
        assert r["address"] == "1 main st"  # TRIM(ADDRESS)
        assert r["city"] == "boston"  # TRIM(CITY)
        assert r["state"] == "MA"  # TRIM(STATE_HEADQUARTERED)
        assert r["phone"] == "555-0100"  # TRIM(PHONE)
        assert r["covered_encounters"] == 100  # CAST INTEGER
        assert r["uncovered_encounters"] == 20  # CAST INTEGER
        assert r["unique_customers"] == 50  # CAST INTEGER
        assert r["member_months"] == 600  # CAST INTEGER

    def test_name_passthrough_when_present(self, spark):
        out = transform_payers._cleanse(_bronze_df(spark, [_bronze_row(NAME=" Aetna ")]))
        assert out.collect()[0]["payer_name"] == "Aetna"  # TRIM

    def test_decimal_widths(self, spark):
        out = transform_payers._cleanse(_bronze_df(spark, [_bronze_row()]))
        # STM v3 — amount_covered / amount_uncovered are DECIMAL(14,2).
        for c in ("amount_covered", "amount_uncovered"):
            dtype = out.schema[c].dataType
            assert (dtype.precision, dtype.scale) == (14, 2)
        # DMS §3.13 — revenue is DECIMAL(12,2).
        rev = out.schema["revenue"].dataType
        assert (rev.precision, rev.scale) == (12, 2)


# --------------------------------------------------------------------------
# AC1 + AC3 + AC4 — transform() wiring (run_dq before apply_scd2)
# --------------------------------------------------------------------------
class TestTransformWiring:
    def test_runs_dq_then_scd2_with_dms_tuple(self, spark):
        bronze = _bronze_df(spark, [_bronze_row()])
        with (
            mock.patch.object(transform_payers, "read_bronze_delta", return_value=bronze),
            mock.patch.object(transform_payers.se_runner, "run_dq") as m_dq,
            mock.patch.object(transform_payers, "apply_scd2") as m_scd2,
        ):
            m_dq.side_effect = lambda df, **kw: df  # SE passes rows through
            m_scd2.return_value = {"rows_inserted": 1, "rows_closed": 0, "rows_unchanged": 0}
            out = transform_payers.transform(spark, env="DEV", ds="2026-06-01")

        # AC4 — SE ran with the fail-closed action for an FK dimension.
        m_dq.assert_called_once()
        assert m_dq.call_args.kwargs["table"] == "reference_payers"
        assert m_dq.call_args.kwargs["action_if_failed"] == "fail"

        # AC3 — apply_scd2 got the DMS §6 natural-key + hash-column tuple and
        # the named UC table FQN unity.silver.reference_payers
        # (LLD §13 Decision 12).
        m_scd2.assert_called_once()
        sk = m_scd2.call_args.kwargs
        assert sk["natural_keys"] == ["payer_id"]
        assert sk["hash_columns"] == ["payer_name", "ownership"]
        assert sk["target_table"] == "unity.silver.reference_payers"
        assert sk["target_table"].count(".") == 2  # 3-part UC FQN, not a path
        assert sk["effective_date"] == "2026-06-01"

        # transform returns the validated (pre-merge) frame for assertions.
        assert set(out.columns) == _EXPECTED_SILVER_COLS

    def test_empty_input_fails_task(self, spark):
        empty = _bronze_df(spark, [_bronze_row()]).limit(0)
        with (
            mock.patch.object(transform_payers, "read_bronze_delta", return_value=empty),
            mock.patch.object(transform_payers.se_runner, "run_dq") as m_dq,
        ):
            with pytest.raises(ValueError, match="empty bronze input"):
                transform_payers.transform(spark, env="DEV", ds="2026-06-01")
            # Fail-fast before SE runs.
            m_dq.assert_not_called()
