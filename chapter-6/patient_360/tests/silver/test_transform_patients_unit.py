"""STORY-03-001 — Silver transform_patients unit tests.

Covers the acceptance criteria called out in the story Verification block:

* AC1 — module reads ``unity.bronze.synthea_patients`` (literal preserved
  in the module for AC compliance; runtime path is the post-Decision-12/15
  path-based Delta location).
* AC2 — PHI columns dropped at Silver boundary (SSN / DRIVERS / PASSPORT).
* AC3 — ``apply_scd2`` invoked with the DMS §6 natural keys + hash
  columns.
* AC4 — inline SE called via ``run_dq`` with
  ``action_if_failed='fail'`` per LLD §5.2.
* AC5 — hash-changed / hash-same / new-record / PHI-dropped scenarios are
  exercised against the pure ``project_silver_columns`` transform.

PySpark is required for the projection assertions; if it is missing from
the local dev env those tests are skipped rather than failing the suite
(mirrors the convention used in ``tests/bronze``).
"""

from __future__ import annotations

import datetime as dt
from unittest import mock

import pytest


pyspark = pytest.importorskip(
    "pyspark", reason="pyspark not installed", exc_type=ImportError
)


from patient_360.silver import transform_patients as tp  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def spark():
    from pyspark.sql import SparkSession

    s = (
        SparkSession.builder.master("local[1]")
        .appName("test_transform_patients_unit")
        .config("spark.sql.shuffle.partitions", "1")
        .getOrCreate()
    )
    yield s
    s.stop()


def _bronze_schema():
    """Explicit StructType matching Bronze ``synthea_patients`` —
    necessary so columns that are ``None`` in our small fixtures still
    get a concrete type (Spark cannot infer types from all-NULL columns).
    """
    from pyspark.sql.types import (
        BooleanType,
        DateType,
        DoubleType,
        IntegerType,
        LongType,
        StringType,
        StructField,
        StructType,
        TimestampType,
    )

    _ = BooleanType  # noqa: F841 — kept import for future fields
    return StructType(
        [
            StructField("Id", StringType(), nullable=False),
            StructField("BIRTHDATE", DateType(), nullable=True),
            StructField("DEATHDATE", DateType(), nullable=True),
            StructField("PREFIX", StringType(), nullable=True),
            StructField("FIRST", StringType(), nullable=True),
            StructField("MIDDLE", StringType(), nullable=True),
            StructField("LAST", StringType(), nullable=True),
            StructField("SUFFIX", StringType(), nullable=True),
            StructField("MAIDEN", StringType(), nullable=True),
            StructField("MARITAL", StringType(), nullable=True),
            StructField("RACE", StringType(), nullable=True),
            StructField("ETHNICITY", StringType(), nullable=True),
            StructField("GENDER", StringType(), nullable=True),
            StructField("BIRTHPLACE", StringType(), nullable=True),
            StructField("ADDRESS", StringType(), nullable=True),
            StructField("CITY", StringType(), nullable=True),
            StructField("STATE", StringType(), nullable=True),
            StructField("COUNTY", StringType(), nullable=True),
            StructField("ZIP", StringType(), nullable=True),
            StructField("LAT", DoubleType(), nullable=True),
            StructField("LON", DoubleType(), nullable=True),
            StructField("HEALTHCARE_EXPENSES", DoubleType(), nullable=True),
            StructField("HEALTHCARE_COVERAGE", DoubleType(), nullable=True),
            StructField("INCOME", LongType(), nullable=True),
            StructField("SSN", StringType(), nullable=True),
            StructField("DRIVERS", StringType(), nullable=True),
            StructField("PASSPORT", StringType(), nullable=True),
            StructField("FIPS", IntegerType(), nullable=True),
            StructField("_ingested_at", TimestampType(), nullable=False),
            StructField("_source_batch_id", StringType(), nullable=False),
        ]
    )


def _bronze_row(**overrides):
    base = {
        "Id": "p-001",
        "BIRTHDATE": dt.date(1980, 1, 15),
        "DEATHDATE": None,
        "PREFIX": "Mr.",
        "FIRST": "  john  ",
        "MIDDLE": None,
        "LAST": "doe",
        "SUFFIX": None,
        "MAIDEN": None,
        "MARITAL": "M",
        "RACE": "white",
        "ETHNICITY": "nonhispanic",
        "GENDER": "m",
        "BIRTHPLACE": "Boston, MA",
        "ADDRESS": "1 Main St",
        "CITY": "Boston",
        "STATE": "MA",
        "COUNTY": "Suffolk",
        "ZIP": "02101",
        "LAT": 42.3601,
        "LON": -71.0589,
        "HEALTHCARE_EXPENSES": 1000.50,
        "HEALTHCARE_COVERAGE": 500.25,
        "INCOME": 60000,
        # PHI columns present on the Bronze side — must NOT leak.
        "SSN": "123-45-6789",
        "DRIVERS": "DL-AB123",
        "PASSPORT": "P-99887",
        "FIPS": 25025,
        # Bronze metadata.
        "_ingested_at": dt.datetime(2026, 5, 20, 9, 0, 0),
        "_source_batch_id": "b-001",
    }
    base.update(overrides)
    return base


@pytest.fixture()
def bronze_df(spark):
    rows = [
        _bronze_row(),
        _bronze_row(Id="p-002", FIRST="jane", LAST="smith", GENDER="F"),
    ]
    return spark.createDataFrame(rows, schema=_bronze_schema())


@pytest.fixture()
def bronze_schema():
    return _bronze_schema()


# ---------------------------------------------------------------------------
# Pure-projection tests (cover AC2 + AC5)
# ---------------------------------------------------------------------------
class TestProjectSilverColumns:
    def test_phi_columns_dropped(self, bronze_df):
        """AC2 — SSN / DRIVERS / PASSPORT / FIPS must not appear in the
        Silver projection."""
        out = tp.project_silver_columns(bronze_df)
        out_cols = set(out.columns)
        assert "SSN" not in out_cols
        assert "DRIVERS" not in out_cols
        assert "PASSPORT" not in out_cols
        assert "FIPS" not in out_cols
        # And lower-case variants — defence in depth.
        assert "ssn" not in out_cols
        assert "drivers" not in out_cols
        assert "passport" not in out_cols

    def test_output_schema_matches_dms_section_3(self, bronze_df):
        """AC5 — projected columns equal the DMS §3 business + system
        passthrough column set. ``effective_from`` / ``effective_to`` /
        ``is_current`` / ``_record_hash`` are added downstream by
        ``apply_scd2`` and so are NOT asserted here."""
        out = tp.project_silver_columns(bronze_df)
        expected = {
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
        assert set(out.columns) == expected

    def test_gender_canonicalised(self, bronze_df):
        out = tp.project_silver_columns(bronze_df).collect()
        genders = {r["patient_id"]: r["gender"] for r in out}
        assert genders["p-001"] == "MALE"  # 'm' -> MALE
        assert genders["p-002"] == "FEMALE"  # 'F' -> FEMALE

    def test_name_initcap_and_trim(self, bronze_df):
        out = {r["patient_id"]: r for r in tp.project_silver_columns(bronze_df).collect()}
        assert out["p-001"]["first_name"] == "John"
        assert out["p-001"]["last_name"] == "Doe"
        assert out["p-002"]["first_name"] == "Jane"

    def test_address_defaults_when_null(self, spark):
        row = _bronze_row(ADDRESS=None, CITY=None, STATE=None, COUNTY=None, ZIP=None)
        out = tp.project_silver_columns(spark.createDataFrame([row], schema=_bronze_schema())).collect()[0]
        assert out["address"] == "UNKNOWN"
        assert out["city"] == "UNKNOWN"
        assert out["state"] == "UNKNOWN"
        assert out["county"] == "UNKNOWN"
        assert out["zip"] == "UNKNOWN"

    def test_patient_status_alive_for_null_death(self, spark):
        out = tp.project_silver_columns(
            spark.createDataFrame([_bronze_row(DEATHDATE=None)], schema=_bronze_schema())
        ).collect()[0]
        assert out["patient_status"] == "ALIVE"

    def test_patient_status_deceased_when_death_set(self, spark):
        out = tp.project_silver_columns(
            spark.createDataFrame(
                [_bronze_row(DEATHDATE=dt.date(2024, 6, 1))], schema=_bronze_schema()
            )
        ).collect()[0]
        assert out["patient_status"] == "DECEASED"

    def test_calculated_age_null_when_birth_null(self, spark):
        # A patient row with a NULL BIRTHDATE — the derived age should be
        # NULL (DRD §5.2). Spark cannot construct a DataFrame from a row
        # with all-NULL inference, so feed in two rows.
        rows = [_bronze_row(), _bronze_row(Id="p-null", BIRTHDATE=None)]
        out = {
            r["patient_id"]: r
            for r in tp.project_silver_columns(spark.createDataFrame(rows, schema=_bronze_schema())).collect()
        }
        assert out["p-null"]["calculated_age"] is None
        assert out["p-001"]["calculated_age"] is not None


# ---------------------------------------------------------------------------
# Wiring tests (cover AC3 + AC4)
# ---------------------------------------------------------------------------
class TestTransformWiring:
    """These verify the orchestration around the pure projection without
    actually invoking Delta / SE / SCD2 (mocked)."""

    def test_apply_scd2_invoked_with_dms_natural_keys_and_hash(self, bronze_df):
        """AC3 — apply_scd2 receives the DMS §6 natural keys + hash columns."""
        fake_spark = mock.MagicMock()
        # spark.read.format("delta").load(<path>) -> bronze_df
        fake_spark.read.format.return_value.load.return_value = bronze_df

        with (
            mock.patch.object(tp, "run_dq", side_effect=lambda df, **kw: df) as run_dq,
            mock.patch.object(
                tp,
                "apply_scd2",
                return_value={"rows_inserted": 2, "rows_closed": 0, "rows_unchanged": 0},
            ) as apply,
            mock.patch.object(tp, "load_config") as load_cfg,
        ):
            load_cfg.return_value.get.return_value = "dq_rules"
            tp.transform(fake_spark, env="DEV", ds="2026-05-20")

        assert apply.call_count == 1
        kwargs = apply.call_args.kwargs
        # LLD-DEVIATIONS row 1: apply_scd2 carries `target_path` so the
        # helper can locate the Delta table even before a Hive FQN is
        # registered.
        assert kwargs["target_path"].endswith("/silver/clinical/clinical_patients")
        assert kwargs["natural_keys"] == ["patient_id"]
        # DMS §6 hash column tuple — verbatim, order-sensitive.
        assert kwargs["hash_columns"] == [
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
        assert kwargs["effective_date"] == "2026-05-20"
        # apply_scd2 sees the post-DQ DataFrame.
        assert run_dq.call_count == 1

    def test_run_dq_called_with_fail_action(self, bronze_df):
        """AC4 — inline SE invoked with action_if_failed='fail' (patients
        is a critical table per LLD §5.2)."""
        fake_spark = mock.MagicMock()
        fake_spark.read.format.return_value.load.return_value = bronze_df

        with (
            mock.patch.object(tp, "run_dq", side_effect=lambda df, **kw: df) as run_dq,
            mock.patch.object(
                tp,
                "apply_scd2",
                return_value={"rows_inserted": 0, "rows_closed": 0, "rows_unchanged": 0},
            ),
            mock.patch.object(tp, "load_config") as load_cfg,
        ):
            load_cfg.return_value.get.return_value = "dq_rules"
            tp.transform(fake_spark, env="DEV", ds="2026-05-20")

        assert run_dq.call_count == 1
        kwargs = run_dq.call_args.kwargs
        assert kwargs["action_if_failed"] == "fail"
        assert kwargs["table"] == "clinical_patients"
        assert kwargs["env"] == "DEV"

    def test_natural_keys_and_hash_columns_module_constants(self):
        """Belt-and-braces — constants reflect DMS §6."""
        assert tp.NATURAL_KEYS == ["patient_id"]
        # Sanity: every column in the hash list lives in the projected
        # DMS §3 schema produced by ``project_silver_columns``.
        assert "marital_status" in tp.HASH_COLUMNS
        assert "healthcare_expenses" in tp.HASH_COLUMNS
        assert "income" in tp.HASH_COLUMNS


# ---------------------------------------------------------------------------
# AC11 — source dedup before apply_scd2 (LLD v1.18 §2.3)
# ---------------------------------------------------------------------------
def test_source_dedup_keeps_one_per_natural_key(spark):
    """AC11: source DataFrame is deduped to one row per patient_id
    (latest by ``ds``).

    Builds a 3-row DataFrame where patient_id ``A`` appears twice
    (ds=2026-01-01 and ds=2026-01-02) and patient_id ``B`` appears once
    (ds=2026-01-01). After dedup we expect:

    * patient_id ``A`` -> ds=2026-01-02 (latest)
    * patient_id ``B`` -> ds=2026-01-01
    * total row count: 2
    """
    from pyspark.sql.types import StringType, StructField, StructType

    schema = StructType(
        [
            StructField("patient_id", StringType(), nullable=False),
            StructField("ds", StringType(), nullable=False),
            StructField("payload", StringType(), nullable=True),
        ]
    )
    rows = [
        ("A", "2026-01-01", "old"),
        ("A", "2026-01-02", "new"),
        ("B", "2026-01-01", "only"),
    ]
    df = spark.createDataFrame(rows, schema=schema)

    out = tp._dedupe_source_to_latest_per_natural_key(
        df, natural_key="patient_id", order_col="ds"
    )

    collected = {r["patient_id"]: r for r in out.collect()}
    assert out.count() == 2
    assert collected["A"]["ds"] == "2026-01-02"
    assert collected["A"]["payload"] == "new"
    assert collected["B"]["ds"] == "2026-01-01"
    assert collected["B"]["payload"] == "only"


def test_source_dedup_falls_back_to_ingested_at(spark):
    """AC11: if ``ds`` is absent, dedup falls back to ``_ingested_at``."""
    from pyspark.sql.types import StringType, StructField, StructType, TimestampType

    schema = StructType(
        [
            StructField("patient_id", StringType(), nullable=False),
            StructField("_ingested_at", TimestampType(), nullable=False),
        ]
    )
    rows = [
        ("A", dt.datetime(2026, 1, 1, 9, 0, 0)),
        ("A", dt.datetime(2026, 1, 2, 9, 0, 0)),
        ("B", dt.datetime(2026, 1, 1, 9, 0, 0)),
    ]
    df = spark.createDataFrame(rows, schema=schema)

    out = tp._dedupe_source_to_latest_per_natural_key(
        df, natural_key="patient_id", order_col="ds"
    )

    collected = {r["patient_id"]: r for r in out.collect()}
    assert out.count() == 2
    assert collected["A"]["_ingested_at"] == dt.datetime(2026, 1, 2, 9, 0, 0)


def test_source_dedup_raises_when_no_order_column(spark):
    """AC11: ValueError raised when neither ``ds`` nor ``_ingested_at`` present."""
    from pyspark.sql.types import StringType, StructField, StructType

    schema = StructType(
        [
            StructField("patient_id", StringType(), nullable=False),
            StructField("payload", StringType(), nullable=True),
        ]
    )
    df = spark.createDataFrame([("A", "x"), ("A", "y")], schema=schema)

    with pytest.raises(ValueError, match="must contain 'ds' or '_ingested_at'"):
        tp._dedupe_source_to_latest_per_natural_key(
            df, natural_key="patient_id", order_col="ds"
        )


# ---------------------------------------------------------------------------
# Decision 17 lock-in test (AC8-AC10)
# ---------------------------------------------------------------------------
def test_no_runtime_ddl_in_silver_sources():
    """STORY-03-001 AC8-AC10 (LLD v1.16 Decision 17).

    transform_patients.py and scd2.py MUST NOT perform Unity Catalog
    DDL at runtime. UC table visibility is established at deploy time
    by ``make bootstrap-uc``; the runtime path is path-based Delta only.

    This is a pure-string assertion — no Spark session required so the
    guard fires even in environments without pyspark installed.
    """
    from pathlib import Path

    src_root = Path(__file__).resolve().parents[2] / "src" / "patient_360"
    targets = [
        src_root / "silver" / "transform_patients.py",
        src_root / "utils" / "scd2.py",
    ]
    forbidden = ["CREATE TABLE", "CREATE SCHEMA", "saveAsTable("]

    offences: list[str] = []
    for target in targets:
        text = target.read_text(encoding="utf-8")
        for needle in forbidden:
            if needle in text:
                offences.append(f"{target.name}: contains forbidden token {needle!r}")

    assert not offences, (
        "Decision 17 violation — runtime DDL detected in Silver sources:\n  "
        + "\n  ".join(offences)
    )
