"""Unit tests for gold/build_patient_billing_summary.py (encounter-grain billing denorm).

Covers (per create-gold SKILL Phase 4 + STORY-05-003 AC5):

* Schema invariant: build() output columns == DMS §4 OUTPUT_COLUMNS (21, no `ds`).
* is_current=True filter: non-current SCD2 patient / payer / provider rows are
  excluded (LLD §6.2).
* Join correctness: one positive encounter (matching claim + primary/secondary payer
  + provider) and one orphan encounter (no claim); costs COALESCE to 0, claim/payer
  fields NULL, outstanding_amount = 0 for the orphan.
* Denormalization shape: primary/secondary payer names and provider name are pulled
  from the current-state reference dims (the billing table's denorm; DMS §4 has no
  ARRAY<STRUCT> columns).
* DQ-before-write wiring: run_dq called once (table, action_if_failed='fail') before
  the insertInto to unity.gold.patient_billing_summary.
* Empty-input behavior: required Silver input (clinical_encounters) empty -> ValueError
  (LLD §5.3 Fail).
"""

from __future__ import annotations

import datetime as dt
from unittest import mock

import pytest

pyspark = pytest.importorskip("pyspark", reason="pyspark not installed")

from patient_360.gold import build_patient_billing_summary as bpbs  # noqa: E402


@pytest.fixture(scope="module")
def spark():
    from pyspark.sql import SparkSession

    delta = pytest.importorskip("delta", reason="delta-spark not installed")
    builder = (
        SparkSession.builder.master("local[1]")
        .appName("test_build_patient_billing_summary")
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
            .appName("test_build_patient_billing_summary")
            .getOrCreate()
        )
    yield s


# --- source Silver builders -------------------------------------------------


def _encounters_df(spark, rows):
    from pyspark.sql import types as T

    cols = [
        "encounter_id",
        "patient_id",
        "encounter_class",
        "provider_id",
        "base_encounter_cost",
        "total_claim_cost",
        "payer_coverage",
        "total_visit_cost",
    ]
    schema = T.StructType(
        [
            T.StructField("encounter_id", T.StringType(), True),
            T.StructField("patient_id", T.StringType(), True),
            T.StructField("encounter_class", T.StringType(), True),
            T.StructField("provider_id", T.StringType(), True),
            T.StructField("base_encounter_cost", T.DoubleType(), True),
            T.StructField("total_claim_cost", T.DoubleType(), True),
            T.StructField("payer_coverage", T.DoubleType(), True),
            T.StructField("total_visit_cost", T.DoubleType(), True),
        ]
    )
    return spark.createDataFrame([tuple(r[c] for c in cols) for r in rows], schema)


def _patients_df(spark, rows):
    from pyspark.sql import types as T

    cols = ["patient_id", "first_name", "last_name", "birth_date", "is_current"]
    schema = T.StructType(
        [
            T.StructField("patient_id", T.StringType(), True),
            T.StructField("first_name", T.StringType(), True),
            T.StructField("last_name", T.StringType(), True),
            T.StructField("birth_date", T.DateType(), True),
            T.StructField("is_current", T.BooleanType(), True),
        ]
    )
    return spark.createDataFrame([tuple(r[c] for c in cols) for r in rows], schema)


def _claims_df(spark, rows):
    from pyspark.sql import types as T

    cols = [
        "claim_id",
        "appointment_id",
        "primary_payer_id",
        "secondary_payer_id",
        "service_date",
        "status_primary",
        "outstanding_primary",
        "outstanding_secondary",
        "outstanding_patient",
    ]
    schema = T.StructType(
        [
            T.StructField("claim_id", T.StringType(), True),
            T.StructField("appointment_id", T.StringType(), True),
            T.StructField("primary_payer_id", T.StringType(), True),
            T.StructField("secondary_payer_id", T.StringType(), True),
            T.StructField("service_date", T.DateType(), True),
            T.StructField("status_primary", T.StringType(), True),
            T.StructField("outstanding_primary", T.DoubleType(), True),
            T.StructField("outstanding_secondary", T.DoubleType(), True),
            T.StructField("outstanding_patient", T.DoubleType(), True),
        ]
    )
    return spark.createDataFrame([tuple(r[c] for c in cols) for r in rows], schema)


def _payers_df(spark, rows):
    from pyspark.sql import types as T

    cols = ["payer_id", "payer_name", "is_current"]
    schema = T.StructType(
        [
            T.StructField("payer_id", T.StringType(), True),
            T.StructField("payer_name", T.StringType(), True),
            T.StructField("is_current", T.BooleanType(), True),
        ]
    )
    return spark.createDataFrame([tuple(r[c] for c in cols) for r in rows], schema)


def _providers_df(spark, rows):
    from pyspark.sql import types as T

    cols = ["provider_id", "provider_name", "is_current"]
    schema = T.StructType(
        [
            T.StructField("provider_id", T.StringType(), True),
            T.StructField("provider_name", T.StringType(), True),
            T.StructField("is_current", T.BooleanType(), True),
        ]
    )
    return spark.createDataFrame([tuple(r[c] for c in cols) for r in rows], schema)


def _tables(spark, encounters, patients, claims=None, payers=None, providers=None):
    return {
        "unity.silver.clinical_encounters": _encounters_df(spark, encounters),
        "unity.silver.clinical_patients": _patients_df(spark, patients),
        "unity.silver.billing_claims": _claims_df(spark, claims or []),
        "unity.silver.reference_payers": _payers_df(spark, payers or []),
        "unity.silver.reference_providers": _providers_df(spark, providers or []),
    }


def _mock_spark(tables):
    m = mock.MagicMock()
    m.table.side_effect = lambda fqn: tables[fqn]
    return m


def _run_build(tables, env="PROD"):
    """Run build() with run_dq as a passthrough and insertInto stubbed out."""
    with (
        mock.patch.object(bpbs.se_runner, "run_dq", side_effect=lambda df, **kw: df),
        mock.patch(
            "pyspark.sql.readwriter.DataFrameWriter.insertInto",
            new=lambda self, name: None,
        ),
    ):
        return bpbs.build(_mock_spark(tables), env=env, ds="2026-07-12")


# --- fixtures: one positive encounter (full claim) + one orphan encounter ---

_POS = "enc-A"
_ORPHAN = "enc-B"
_PAT = "pat-A"


def _full_tables(spark):
    return _tables(
        spark,
        encounters=[
            {
                "encounter_id": _POS,
                "patient_id": _PAT,
                "encounter_class": "INPATIENT",
                "provider_id": "prov-1",
                "base_encounter_cost": 100.0,
                "total_claim_cost": 250.0,
                "payer_coverage": 200.0,
                "total_visit_cost": 300.0,
            },
            {
                "encounter_id": _ORPHAN,
                "patient_id": _PAT,
                "encounter_class": "AMBULATORY",
                "provider_id": "prov-1",
                "base_encounter_cost": None,  # COALESCE -> 0
                "total_claim_cost": None,
                "payer_coverage": None,
                "total_visit_cost": None,
            },
        ],
        patients=[
            {
                "patient_id": _PAT,
                "first_name": "Ada",
                "last_name": "Byron",
                "birth_date": dt.date(1980, 1, 1),
                "is_current": True,
            },
            {
                "patient_id": _PAT,  # stale version, must be excluded
                "first_name": "Ada-OLD",
                "last_name": "Byron",
                "birth_date": dt.date(1980, 1, 1),
                "is_current": False,
            },
        ],
        claims=[
            {
                "claim_id": "clm-1",
                "appointment_id": _POS,
                "primary_payer_id": "pay-1",
                "secondary_payer_id": "pay-2",
                "service_date": dt.date(2026, 5, 1),
                "status_primary": "CLOSED",
                "outstanding_primary": 10.0,
                "outstanding_secondary": 5.0,
                "outstanding_patient": 2.0,
            },
        ],
        payers=[
            {"payer_id": "pay-1", "payer_name": "Aetna", "is_current": True},
            {"payer_id": "pay-1", "payer_name": "Aetna-OLD", "is_current": False},
            {"payer_id": "pay-2", "payer_name": "BlueCross", "is_current": True},
        ],
        providers=[
            {"provider_id": "prov-1", "provider_name": "Dr House", "is_current": True},
            {"provider_id": "prov-1", "provider_name": "Dr House-OLD", "is_current": False},
        ],
    )


class TestSchema:
    def test_output_columns_match_dms(self, spark):
        out = _run_build(_full_tables(spark))
        assert list(out.columns) == list(bpbs.OUTPUT_COLUMNS)
        assert len(bpbs.OUTPUT_COLUMNS) == 21
        assert "ds" not in bpbs.OUTPUT_COLUMNS

    def test_grain_one_row_per_encounter(self, spark):
        out = _run_build(_full_tables(spark))
        rows = out.collect()
        assert len(rows) == 2
        assert {r["encounter_id"] for r in rows} == {_POS, _ORPHAN}


class TestIsCurrentFilter:
    def test_non_current_patient_excluded(self, spark):
        # Only a stale (is_current=False) patient version exists -> inner join drops
        # every encounter, yielding zero rows.
        tables = _tables(
            spark,
            encounters=[
                {
                    "encounter_id": _POS,
                    "patient_id": _PAT,
                    "encounter_class": "INPATIENT",
                    "provider_id": "prov-1",
                    "base_encounter_cost": 1.0,
                    "total_claim_cost": 1.0,
                    "payer_coverage": 1.0,
                    "total_visit_cost": 1.0,
                }
            ],
            patients=[
                {
                    "patient_id": _PAT,
                    "first_name": "Ada",
                    "last_name": "Byron",
                    "birth_date": dt.date(1980, 1, 1),
                    "is_current": False,
                }
            ],
        )
        out = _run_build(tables)
        assert out.count() == 0

    def test_current_dim_versions_used(self, spark):
        out = _run_build(_full_tables(spark))
        row = {r["encounter_id"]: r for r in out.collect()}[_POS]
        assert row["first_name"] == "Ada"  # not Ada-OLD
        assert row["primary_payer_name"] == "Aetna"  # not Aetna-OLD
        assert row["provider_name"] == "Dr House"  # not Dr House-OLD


class TestJoinCorrectness:
    def test_positive_encounter_denorm(self, spark):
        out = _run_build(_full_tables(spark))
        row = {r["encounter_id"]: r for r in out.collect()}[_POS]
        assert row["patient_id"] == _PAT
        assert row["claim_id"] == "clm-1"
        assert row["primary_payer_id"] == "pay-1"
        assert row["primary_payer_name"] == "Aetna"
        assert row["secondary_payer_id"] == "pay-2"
        assert row["secondary_payer_name"] == "BlueCross"
        assert row["provider_name"] == "Dr House"
        assert row["claim_status"] == "CLOSED"
        assert row["service_date"] == dt.date(2026, 5, 1)
        assert float(row["base_encounter_cost"]) == 100.0
        assert float(row["total_visit_cost"]) == 300.0
        # outstanding_amount = 10 + 5 + 2
        assert float(row["outstanding_amount"]) == 17.0

    def test_orphan_encounter_defaults(self, spark):
        out = _run_build(_full_tables(spark))
        row = {r["encounter_id"]: r for r in out.collect()}[_ORPHAN]
        # no matching claim -> claim/payer fields NULL
        assert row["claim_id"] is None
        assert row["primary_payer_id"] is None
        assert row["primary_payer_name"] is None
        assert row["secondary_payer_name"] is None
        assert row["service_date"] is None
        # costs COALESCE to 0; outstanding sums 3 NULLs -> 0
        assert float(row["base_encounter_cost"]) == 0.0
        assert float(row["total_claim_cost"]) == 0.0
        assert float(row["payer_coverage"]) == 0.0
        assert float(row["total_visit_cost"]) == 0.0
        assert float(row["outstanding_amount"]) == 0.0
        # provider still resolves (encounter carries provider_id)
        assert row["provider_name"] == "Dr House"


class TestDqWiring:
    def test_runs_dq_before_write(self, spark):
        tables = _full_tables(spark)
        with mock.patch.object(bpbs.se_runner, "run_dq") as m_dq:
            m_dq.return_value = mock.MagicMock()
            bpbs.build(_mock_spark(tables), env="PROD", ds="2026-07-12")

        m_dq.assert_called_once()
        assert m_dq.call_args.kwargs["table"] == "patient_billing_summary"
        assert m_dq.call_args.kwargs["action_if_failed"] == "fail"
        assert m_dq.call_args.kwargs["env"] == "PROD"
        writer = m_dq.return_value.select.return_value.write.mode.return_value
        writer.insertInto.assert_called_once_with("unity.gold.patient_billing_summary")


class TestEmptyInput:
    def test_empty_encounters_raises(self, spark):
        tables = _tables(
            spark,
            encounters=[],
            patients=[
                {
                    "patient_id": _PAT,
                    "first_name": "Ada",
                    "last_name": "Byron",
                    "birth_date": dt.date(1980, 1, 1),
                    "is_current": True,
                }
            ],
        )
        with (
            mock.patch.object(bpbs.se_runner, "run_dq") as m_dq,
            mock.patch(
                "pyspark.sql.readwriter.DataFrameWriter.insertInto",
                new=lambda self, name: None,
            ),
            pytest.raises(ValueError, match="empty"),
        ):
            bpbs.build(_mock_spark(tables), env="PROD", ds="2026-07-12")
        m_dq.assert_not_called()
