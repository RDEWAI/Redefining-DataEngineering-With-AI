"""Unit tests for gold/build_patient_clinical_history.py (encounter-grain denorm).

Covers (per create-gold SKILL Phase 4 + STORY-05-002 AC5):

* Schema invariant: build() output columns == DMS §4 OUTPUT_COLUMNS (24, no `ds`).
* is_current=True filter: non-current SCD2 dim versions excluded (LLD §6.2) — a
  non-current provider version is not used; a patient with only a non-current
  version drops its encounters (STM row 31 inner join on current patients).
* Join correctness: one positive encounter (facts + provider + org present) and one
  orphan encounter (no facts, no provider/org); counts COALESCE to 0, names NULL.
* active_careplan_count: only care plans with stop_date IS NULL are counted
  (DMS §3.9 active-plan semantics; STM `careplan_status` column absent in silver).
* DQ-before-write wiring: run_dq called once (table, action_if_failed='fail')
  before the insertInto to unity.gold.patient_clinical_history.
* Empty-input behavior: required Silver input empty -> ValueError (LLD §5.3 Fail).
"""

from __future__ import annotations

import datetime as dt
from unittest import mock

import pytest

pyspark = pytest.importorskip("pyspark", reason="pyspark not installed")

from patient_360.gold import build_patient_clinical_history as bpch  # noqa: E402


@pytest.fixture(scope="module")
def spark():
    from pyspark.sql import SparkSession

    delta = pytest.importorskip("delta", reason="delta-spark not installed")
    builder = (
        SparkSession.builder.master("local[1]")
        .appName("test_build_patient_clinical_history")
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
            .appName("test_build_patient_clinical_history")
            .getOrCreate()
        )
    yield s


# --- source Silver builders -------------------------------------------------

_ENCOUNTER_COLS = [
    "encounter_id",
    "patient_id",
    "provider_id",
    "organization_id",
    "encounter_class",
    "encounter_description",
    "start_date",
    "stop_date",
    "encounter_duration_hours",
    "los_days",
    "is_30_day_readmission",
    "reason_description",
]


def _encounters_df(spark, rows):
    from pyspark.sql import types as T

    schema = T.StructType(
        [
            T.StructField("encounter_id", T.StringType(), True),
            T.StructField("patient_id", T.StringType(), True),
            T.StructField("provider_id", T.StringType(), True),
            T.StructField("organization_id", T.StringType(), True),
            T.StructField("encounter_class", T.StringType(), True),
            T.StructField("encounter_description", T.StringType(), True),
            T.StructField("start_date", T.TimestampType(), True),
            T.StructField("stop_date", T.TimestampType(), True),
            T.StructField("encounter_duration_hours", T.DoubleType(), True),
            T.StructField("los_days", T.IntegerType(), True),
            T.StructField("is_30_day_readmission", T.BooleanType(), True),
            T.StructField("reason_description", T.StringType(), True),
        ]
    )
    return spark.createDataFrame([tuple(r[c] for c in _ENCOUNTER_COLS) for r in rows], schema)


def _encounter_row(encounter_id, patient_id, **ov):
    base = {c: None for c in _ENCOUNTER_COLS}
    base.update(
        {
            "encounter_id": encounter_id,
            "patient_id": patient_id,
            "encounter_class": "OUTPATIENT",
            "start_date": dt.datetime(2026, 1, 1, 9, 0, 0),
            "is_30_day_readmission": False,
        }
    )
    base.update(ov)
    return base


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


def _patient_row(patient_id, is_current=True, **ov):
    base = {
        "patient_id": patient_id,
        "first_name": "First",
        "last_name": "Last",
        "birth_date": dt.date(1980, 1, 1),
        "is_current": is_current,
    }
    base.update(ov)
    return base


def _providers_df(spark, rows):
    from pyspark.sql import types as T

    cols = ["provider_id", "provider_name", "organization_id", "is_current"]
    schema = T.StructType(
        [
            T.StructField("provider_id", T.StringType(), True),
            T.StructField("provider_name", T.StringType(), True),
            T.StructField("organization_id", T.StringType(), True),
            T.StructField("is_current", T.BooleanType(), True),
        ]
    )
    return spark.createDataFrame([tuple(r[c] for c in cols) for r in rows], schema)


def _organizations_df(spark, rows):
    from pyspark.sql import types as T

    cols = ["organization_id", "organization_name", "is_current"]
    schema = T.StructType(
        [
            T.StructField("organization_id", T.StringType(), True),
            T.StructField("organization_name", T.StringType(), True),
            T.StructField("is_current", T.BooleanType(), True),
        ]
    )
    return spark.createDataFrame([tuple(r[c] for c in cols) for r in rows], schema)


def _enc_fk_df(spark, rows):
    """A minimal silver fact carrying only encounter_id (count sources)."""
    from pyspark.sql import types as T

    schema = T.StructType([T.StructField("encounter_id", T.StringType(), True)])
    return spark.createDataFrame([(r,) for r in rows], schema)


def _careplans_df(spark, rows):
    from pyspark.sql import types as T

    cols = ["encounter_id", "stop_date"]
    schema = T.StructType(
        [
            T.StructField("encounter_id", T.StringType(), True),
            T.StructField("stop_date", T.DateType(), True),
        ]
    )
    return spark.createDataFrame([tuple(r[c] for c in cols) for r in rows], schema)


def _tables(
    spark,
    encounters,
    patients,
    providers=None,
    organizations=None,
    conditions=None,
    procedures=None,
    medications=None,
    observations=None,
    immunizations=None,
    careplans=None,
):
    return {
        "unity.silver.clinical_encounters": _encounters_df(spark, encounters),
        "unity.silver.clinical_patients": _patients_df(spark, patients),
        "unity.silver.reference_providers": _providers_df(spark, providers or []),
        "unity.silver.reference_organizations": _organizations_df(spark, organizations or []),
        "unity.silver.clinical_conditions": _enc_fk_df(spark, conditions or []),
        "unity.silver.clinical_procedures": _enc_fk_df(spark, procedures or []),
        "unity.silver.clinical_medications": _enc_fk_df(spark, medications or []),
        "unity.silver.clinical_observations": _enc_fk_df(spark, observations or []),
        "unity.silver.clinical_immunizations": _enc_fk_df(spark, immunizations or []),
        "unity.silver.clinical_careplans": _careplans_df(spark, careplans or []),
    }


def _mock_spark(tables):
    m = mock.MagicMock()
    m.table.side_effect = lambda fqn: tables[fqn]
    return m


def _run_build(tables, env="PROD"):
    """Run build() with run_dq as a passthrough and insertInto stubbed out."""
    with (
        mock.patch.object(bpch.se_runner, "run_dq", side_effect=lambda df, **kw: df),
        mock.patch(
            "pyspark.sql.readwriter.DataFrameWriter.insertInto",
            new=lambda self, name: None,
        ),
    ):
        return bpch.build(_mock_spark(tables), env=env, ds="2026-07-12")


# --- fixtures: a fully-populated positive encounter + an orphan encounter ---

_POS = "enc-A"
_ORPHAN = "enc-Z"
_PAT = "pat-1"
_PROV = "prov-1"
_ORG = "org-1"


def _full_tables(spark):
    return _tables(
        spark,
        encounters=[
            _encounter_row(
                _POS,
                _PAT,
                provider_id=_PROV,
                organization_id=_ORG,
                encounter_class="INPATIENT",
                is_30_day_readmission=True,
            ),
            _encounter_row(_ORPHAN, _PAT),  # no provider/org, no facts
        ],
        patients=[_patient_row(_PAT)],
        providers=[
            {
                "provider_id": _PROV,
                "provider_name": "Dr Current",
                "organization_id": _ORG,
                "is_current": True,
            },
            {
                "provider_id": _PROV,
                "provider_name": "Dr Old",
                "organization_id": _ORG,
                "is_current": False,
            },
        ],
        organizations=[
            {"organization_id": _ORG, "organization_name": "General Hospital", "is_current": True},
        ],
        conditions=[_POS, _POS],  # 2 conditions on the positive encounter
        procedures=[_POS],
        medications=[_POS, _POS, _POS],
        observations=[_POS],
        immunizations=[_POS],
        careplans=[
            {"encounter_id": _POS, "stop_date": None},  # active
            {"encounter_id": _POS, "stop_date": dt.date(2025, 1, 1)},  # inactive
        ],
    )


class TestSchema:
    def test_output_columns_match_dms(self, spark):
        out = _run_build(_full_tables(spark))
        assert list(out.columns) == list(bpch.OUTPUT_COLUMNS)
        assert len(bpch.OUTPUT_COLUMNS) == 24
        assert "ds" not in bpch.OUTPUT_COLUMNS


class TestIsCurrentFilter:
    def test_noncurrent_provider_version_excluded(self, spark):
        out = _run_build(_full_tables(spark))
        row = {r["encounter_id"]: r for r in out.collect()}[_POS]
        assert row["provider_name"] == "Dr Current"

    def test_noncurrent_patient_drops_encounter(self, spark):
        tables = _tables(
            spark,
            encounters=[_encounter_row("e-cur", "p-cur"), _encounter_row("e-old", "p-old")],
            patients=[
                _patient_row("p-cur", is_current=True),
                _patient_row("p-old", is_current=False),
            ],
        )
        out = _run_build(tables)
        ids = {r["encounter_id"] for r in out.collect()}
        assert ids == {"e-cur"}


class TestJoinCorrectness:
    def test_positive_encounter_counts(self, spark):
        out = _run_build(_full_tables(spark))
        row = {r["encounter_id"]: r for r in out.collect()}[_POS]
        assert row["patient_id"] == _PAT
        assert row["first_name"] == "First"
        assert row["provider_name"] == "Dr Current"
        assert row["organization_name"] == "General Hospital"
        assert row["condition_count"] == 2
        assert row["procedure_count"] == 1
        assert row["medication_count"] == 3
        assert row["observation_count"] == 1
        assert row["immunization_count"] == 1
        assert row["active_careplan_count"] == 1  # only stop_date IS NULL
        assert row["is_30_day_readmission"] is True

    def test_orphan_encounter_defaults(self, spark):
        out = _run_build(_full_tables(spark))
        row = {r["encounter_id"]: r for r in out.collect()}[_ORPHAN]
        assert row["condition_count"] == 0
        assert row["procedure_count"] == 0
        assert row["medication_count"] == 0
        assert row["observation_count"] == 0
        assert row["immunization_count"] == 0
        assert row["active_careplan_count"] == 0
        assert row["provider_name"] is None
        assert row["organization_name"] is None


class TestCareplanActive:
    def test_only_active_careplans_counted(self, spark):
        tables = _tables(
            spark,
            encounters=[_encounter_row("e1", _PAT)],
            patients=[_patient_row(_PAT)],
            careplans=[
                {"encounter_id": "e1", "stop_date": None},
                {"encounter_id": "e1", "stop_date": None},
                {"encounter_id": "e1", "stop_date": dt.date(2024, 6, 1)},
            ],
        )
        out = _run_build(tables)
        row = {r["encounter_id"]: r for r in out.collect()}["e1"]
        assert row["active_careplan_count"] == 2


class TestDqWiring:
    def test_runs_dq_before_write(self, spark):
        tables = _full_tables(spark)
        with mock.patch.object(bpch.se_runner, "run_dq") as m_dq:
            m_dq.return_value = mock.MagicMock()
            bpch.build(_mock_spark(tables), env="PROD", ds="2026-07-12")

        m_dq.assert_called_once()
        assert m_dq.call_args.kwargs["table"] == "patient_clinical_history"
        assert m_dq.call_args.kwargs["action_if_failed"] == "fail"
        assert m_dq.call_args.kwargs["env"] == "PROD"
        writer = m_dq.return_value.select.return_value.write.mode.return_value
        writer.insertInto.assert_called_once_with("unity.gold.patient_clinical_history")


class TestEmptyInput:
    def test_empty_encounters_raises(self, spark):
        tables = _tables(spark, encounters=[], patients=[_patient_row(_PAT)])
        with (
            mock.patch.object(bpch.se_runner, "run_dq") as m_dq,
            mock.patch(
                "pyspark.sql.readwriter.DataFrameWriter.insertInto",
                new=lambda self, name: None,
            ),
            pytest.raises(ValueError, match="empty"),
        ):
            bpch.build(_mock_spark(tables), env="PROD", ds="2026-07-12")
        m_dq.assert_not_called()
