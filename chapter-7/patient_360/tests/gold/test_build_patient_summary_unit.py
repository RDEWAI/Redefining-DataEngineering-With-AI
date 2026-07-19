"""Unit tests for gold/build_patient_summary.py (consumer denorm table).

Covers (per create-gold SKILL Phase 4 + STORY-05-001 AC5):

* Schema invariant: build() output columns == DMS §4 OUTPUT_COLUMNS (29, no `ds`).
* is_current=True filter: non-current SCD2 patient rows are excluded (LLD §6.2).
* Join correctness: one positive patient (facts present) + one orphan (no facts);
  counts COALESCE to 0/False, arrays NULL for the orphan.
* ARRAY<STRUCT> denorm shape: field names match DMS §4 exactly
  (allergies: description/severity; conditions: snomed_code/description/onset_date;
  medications: rxnorm_code/description/status); NULL severity1 -> 'Unknown'.
* DQ-before-write wiring: run_dq called once (table, action_if_failed='fail')
  before the insertInto to unity.gold.patient_summary.
* Empty-input behavior: required Silver input empty -> ValueError (LLD §5.3 Fail).
"""

from __future__ import annotations

import datetime as dt
from unittest import mock

import pytest

pyspark = pytest.importorskip("pyspark", reason="pyspark not installed")

from patient_360.gold import build_patient_summary as bps  # noqa: E402


@pytest.fixture(scope="module")
def spark():
    from pyspark.sql import SparkSession

    delta = pytest.importorskip("delta", reason="delta-spark not installed")
    builder = (
        SparkSession.builder.master("local[1]")
        .appName("test_build_patient_summary")
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
            .appName("test_build_patient_summary")
            .getOrCreate()
        )
    yield s


# --- source Silver builders -------------------------------------------------

_PATIENT_COLS = [
    "patient_id",
    "first_name",
    "middle_name",
    "last_name",
    "prefix",
    "suffix",
    "birth_date",
    "death_date",
    "patient_status",
    "calculated_age",
    "gender",
    "race",
    "ethnicity",
    "marital_status",
    "address",
    "city",
    "state",
    "zip",
    "is_current",
]


def _patients_df(spark, rows):
    from pyspark.sql import types as T

    schema = T.StructType(
        [
            T.StructField("patient_id", T.StringType(), True),
            T.StructField("first_name", T.StringType(), True),
            T.StructField("middle_name", T.StringType(), True),
            T.StructField("last_name", T.StringType(), True),
            T.StructField("prefix", T.StringType(), True),
            T.StructField("suffix", T.StringType(), True),
            T.StructField("birth_date", T.DateType(), True),
            T.StructField("death_date", T.DateType(), True),
            T.StructField("patient_status", T.StringType(), True),
            T.StructField("calculated_age", T.IntegerType(), True),
            T.StructField("gender", T.StringType(), True),
            T.StructField("race", T.StringType(), True),
            T.StructField("ethnicity", T.StringType(), True),
            T.StructField("marital_status", T.StringType(), True),
            T.StructField("address", T.StringType(), True),
            T.StructField("city", T.StringType(), True),
            T.StructField("state", T.StringType(), True),
            T.StructField("zip", T.StringType(), True),
            T.StructField("is_current", T.BooleanType(), True),
        ]
    )
    return spark.createDataFrame([tuple(r[c] for c in _PATIENT_COLS) for r in rows], schema)


def _patient_row(patient_id, is_current=True, **ov):
    base = {c: None for c in _PATIENT_COLS}
    base.update(
        {
            "patient_id": patient_id,
            "first_name": "First",
            "last_name": "Last",
            "birth_date": dt.date(1980, 1, 1),
            "patient_status": "ALIVE",
            "calculated_age": 46,
            "is_current": is_current,
        }
    )
    base.update(ov)
    return base


def _conditions_df(spark, rows):
    from pyspark.sql import types as T

    cols = ["patient_id", "condition_status", "snomed_code", "condition_description", "onset_date"]
    schema = T.StructType(
        [
            T.StructField("patient_id", T.StringType(), True),
            T.StructField("condition_status", T.StringType(), True),
            T.StructField("snomed_code", T.StringType(), True),
            T.StructField("condition_description", T.StringType(), True),
            T.StructField("onset_date", T.DateType(), True),
            # ds: silver facts are ds-partitioned; the gold builder reads via
            # _read_fact_current (latest ds). One shared ds keeps all rows.
            T.StructField("ds", T.StringType(), True),
        ]
    )
    return spark.createDataFrame(
        [tuple(r[c] for c in cols) + ("2026-07-18",) for r in rows], schema
    )


def _medications_df(spark, rows):
    from pyspark.sql import types as T

    cols = ["patient_id", "medication_status", "rxnorm_code", "medication_description"]
    schema = T.StructType(
        [T.StructField(c, T.StringType(), True) for c in cols]
        # ds: latest-ds fact read via _read_fact_current; one shared ds.
        + [T.StructField("ds", T.StringType(), True)]
    )
    return spark.createDataFrame(
        [tuple(r[c] for c in cols) + ("2026-07-18",) for r in rows], schema
    )


def _allergies_df(spark, rows):
    from pyspark.sql import types as T

    cols = ["patient_id", "allergy_description", "severity1"]
    schema = T.StructType(
        [T.StructField(c, T.StringType(), True) for c in cols]
        # ds: latest-ds fact read via _read_fact_current; one shared ds.
        + [T.StructField("ds", T.StringType(), True)]
    )
    return spark.createDataFrame(
        [tuple(r[c] for c in cols) + ("2026-07-18",) for r in rows], schema
    )


def _encounters_df(spark, rows):
    from pyspark.sql import types as T

    cols = ["patient_id", "start_date", "encounter_class", "is_30_day_readmission"]
    schema = T.StructType(
        [
            T.StructField("patient_id", T.StringType(), True),
            T.StructField("start_date", T.DateType(), True),
            T.StructField("encounter_class", T.StringType(), True),
            T.StructField("is_30_day_readmission", T.BooleanType(), True),
            # ds: latest-ds fact read via _read_fact_current; one shared ds.
            T.StructField("ds", T.StringType(), True),
        ]
    )
    return spark.createDataFrame(
        [tuple(r[c] for c in cols) + ("2026-07-18",) for r in rows], schema
    )


def _tables(spark, patients, conditions=None, medications=None, allergies=None, encounters=None):
    return {
        "unity.silver.clinical_patients": _patients_df(spark, patients),
        "unity.silver.clinical_conditions": _conditions_df(spark, conditions or []),
        "unity.silver.clinical_medications": _medications_df(spark, medications or []),
        "unity.silver.clinical_allergies": _allergies_df(spark, allergies or []),
        "unity.silver.clinical_encounters": _encounters_df(spark, encounters or []),
    }


def _mock_spark(tables):
    m = mock.MagicMock()
    m.table.side_effect = lambda fqn: tables[fqn]
    return m


def _run_build(tables, env="PROD"):
    """Run build() with run_dq as a passthrough and insertInto stubbed out."""
    with (
        mock.patch.object(bps.se_runner, "run_dq", side_effect=lambda df, **kw: df),
        mock.patch(
            "pyspark.sql.readwriter.DataFrameWriter.insertInto",
            new=lambda self, name: None,
        ),
    ):
        return bps.build(_mock_spark(tables), env=env, ds="2026-07-12")


# --- fixtures for a fully-populated positive patient + an orphan ------------

_POS = "pat-A"
_ORPHAN = "pat-C"


def _full_tables(spark):
    return _tables(
        spark,
        patients=[_patient_row(_POS), _patient_row(_ORPHAN)],
        conditions=[
            {
                "patient_id": _POS,
                "condition_status": "ACTIVE",
                "snomed_code": "44054006",
                "condition_description": "Diabetes",
                "onset_date": dt.date(2020, 3, 1),
            },
            {
                "patient_id": _POS,
                "condition_status": "RESOLVED",  # excluded from active count/array
                "snomed_code": "999",
                "condition_description": "Old",
                "onset_date": dt.date(2010, 1, 1),
            },
        ],
        medications=[
            {
                "patient_id": _POS,
                "medication_status": "Active",
                "rxnorm_code": "rx-1",
                "medication_description": "Metformin",
            },
            {
                "patient_id": _POS,
                "medication_status": "Stopped",  # excluded
                "rxnorm_code": "rx-2",
                "medication_description": "OldMed",
            },
        ],
        allergies=[
            {"patient_id": _POS, "allergy_description": "Penicillin", "severity1": "HIGH"},
            {"patient_id": _POS, "allergy_description": "Peanut", "severity1": None},
        ],
        encounters=[
            {
                "patient_id": _POS,
                "start_date": dt.date(2026, 1, 1),
                "encounter_class": "OUTPATIENT",
                "is_30_day_readmission": False,
            },
            {
                "patient_id": _POS,
                "start_date": dt.date(2026, 6, 1),
                "encounter_class": "INPATIENT",
                "is_30_day_readmission": True,
            },
        ],
    )


class TestSchema:
    def test_output_columns_match_dms(self, spark):
        out = _run_build(_full_tables(spark))
        assert list(out.columns) == list(bps.OUTPUT_COLUMNS)
        assert len(bps.OUTPUT_COLUMNS) == 29
        assert "ds" not in bps.OUTPUT_COLUMNS


class TestIsCurrentFilter:
    def test_non_current_patient_excluded(self, spark):
        tables = _tables(
            spark,
            patients=[_patient_row("cur", is_current=True), _patient_row("old", is_current=False)],
        )
        out = _run_build(tables)
        ids = {r["patient_id"] for r in out.collect()}
        assert ids == {"cur"}


class TestJoinCorrectness:
    def test_positive_patient_aggregates(self, spark):
        out = _run_build(_full_tables(spark))
        row = {r["patient_id"]: r for r in out.collect()}[_POS]
        assert row["active_condition_count"] == 1  # only ACTIVE
        assert row["active_medication_count"] == 1  # only Active
        assert row["has_allergy"] is True
        assert row["encounter_count"] == 2
        assert row["recent_encounter_date"] == dt.date(2026, 6, 1)
        assert row["recent_encounter_class"] == "INPATIENT"  # latest start_date
        assert row["has_30day_readmission_history"] is True

    def test_orphan_patient_defaults(self, spark):
        out = _run_build(_full_tables(spark))
        row = {r["patient_id"]: r for r in out.collect()}[_ORPHAN]
        assert row["active_condition_count"] == 0
        assert row["active_medication_count"] == 0
        assert row["has_allergy"] is False
        assert row["encounter_count"] == 0
        assert row["has_30day_readmission_history"] is False
        assert row["recent_encounter_date"] is None
        assert row["recent_encounter_class"] is None
        assert row["allergies"] is None
        assert row["conditions"] is None
        assert row["medications"] is None


class TestArrayStructShape:
    def test_denorm_struct_field_names(self, spark):
        out = _run_build(_full_tables(spark))
        dtypes = dict(out.dtypes)
        assert dtypes["allergies"] == "array<struct<description:string,severity:string>>"
        assert dtypes["conditions"] == (
            "array<struct<snomed_code:string,description:string,onset_date:date>>"
        )
        assert dtypes["medications"] == (
            "array<struct<rxnorm_code:string,description:string,status:string>>"
        )

    def test_null_severity_becomes_unknown(self, spark):
        out = _run_build(_full_tables(spark))
        row = {r["patient_id"]: r for r in out.collect()}[_POS]
        severities = {a["severity"] for a in row["allergies"]}
        assert severities == {"HIGH", "Unknown"}

    def test_active_only_scoping_in_arrays(self, spark):
        out = _run_build(_full_tables(spark))
        row = {r["patient_id"]: r for r in out.collect()}[_POS]
        assert [c["description"] for c in row["conditions"]] == ["Diabetes"]
        assert [m["description"] for m in row["medications"]] == ["Metformin"]
        assert row["conditions"][0]["snomed_code"] == "44054006"
        assert row["medications"][0]["rxnorm_code"] == "rx-1"
        assert row["medications"][0]["status"] == "Active"


class TestDqWiring:
    def test_runs_dq_before_write(self, spark):
        tables = _full_tables(spark)
        with mock.patch.object(bps.se_runner, "run_dq") as m_dq:
            m_dq.return_value = mock.MagicMock()
            bps.build(_mock_spark(tables), env="PROD", ds="2026-07-12")

        m_dq.assert_called_once()
        assert m_dq.call_args.kwargs["table"] == "patient_summary"
        assert m_dq.call_args.kwargs["action_if_failed"] == "fail"
        assert m_dq.call_args.kwargs["env"] == "PROD"
        writer = m_dq.return_value.select.return_value.write.mode.return_value
        writer.insertInto.assert_called_once_with("unity.gold.patient_summary")


class TestEmptyInput:
    def test_empty_patients_raises(self, spark):
        tables = _tables(spark, patients=[])
        with (
            mock.patch.object(bps.se_runner, "run_dq") as m_dq,
            mock.patch(
                "pyspark.sql.readwriter.DataFrameWriter.insertInto",
                new=lambda self, name: None,
            ),
            pytest.raises(ValueError, match="empty"),
        ):
            bps.build(_mock_spark(tables), env="PROD", ds="2026-07-12")
        m_dq.assert_not_called()
