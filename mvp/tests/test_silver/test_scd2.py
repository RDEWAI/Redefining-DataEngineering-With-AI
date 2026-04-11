"""Tests for the reusable SCD Type 2 function."""

from __future__ import annotations

import pytest
from pyspark.sql import SparkSession
from pyspark.sql.types import StringType, StructField, StructType

from patient_360.silver.scd2 import apply_scd2

SCHEMA = StructType([
    StructField("patient_id", StringType(), nullable=False),
    StructField("name",       StringType(), nullable=True),
    StructField("city",       StringType(), nullable=True),
])

TRACKED = ["name", "city"]
TARGET  = "silver.scd2_test_patients"
DS1     = "2026-03-01"
DS2     = "2026-03-06"


@pytest.fixture(autouse=True)
def drop_target(spark: SparkSession):
    """Drop the test table before each test to ensure isolation."""
    spark.sql(f"DROP TABLE IF EXISTS {TARGET}")
    yield
    spark.sql(f"DROP TABLE IF EXISTS {TARGET}")


class TestSCD2FirstLoad:
    def test_first_load_inserts_all_rows(self, spark: SparkSession):
        """All source rows should be inserted as current on first run."""
        source = spark.createDataFrame(
            [("p1", "Alice", "Boston"), ("p2", "Bob", "Denver")], schema=SCHEMA
        )
        apply_scd2(spark, source, TARGET, "patient_id", TRACKED, DS1)

        result = spark.table(TARGET)
        assert result.count() == 2

    def test_first_load_all_rows_are_current(self, spark: SparkSession):
        """All rows on first load should have dim_is_current=True."""
        source = spark.createDataFrame([("p1", "Alice", "Boston")], schema=SCHEMA)
        apply_scd2(spark, source, TARGET, "patient_id", TRACKED, DS1)

        result = spark.table(TARGET)
        assert result.filter("dim_is_current = false").count() == 0

    def test_first_load_start_ts_set_to_ds(self, spark: SparkSession):
        """start_ts should match the ds argument."""
        source = spark.createDataFrame([("p1", "Alice", "Boston")], schema=SCHEMA)
        apply_scd2(spark, source, TARGET, "patient_id", TRACKED, DS1)

        row = spark.table(TARGET).collect()[0]
        assert str(row.start_ts) == DS1

    def test_first_load_end_ts_is_null(self, spark: SparkSession):
        """end_ts should be NULL for all rows on first load (current rows)."""
        source = spark.createDataFrame([("p1", "Alice", "Boston")], schema=SCHEMA)
        apply_scd2(spark, source, TARGET, "patient_id", TRACKED, DS1)

        result = spark.table(TARGET)
        assert result.filter("end_ts IS NOT NULL").count() == 0

    def test_first_load_surrogate_key_generated(self, spark: SparkSession):
        """Each row should have a non-null surrogate_key."""
        source = spark.createDataFrame([("p1", "Alice", "Boston")], schema=SCHEMA)
        apply_scd2(spark, source, TARGET, "patient_id", TRACKED, DS1)

        result = spark.table(TARGET)
        assert result.filter("surrogate_key IS NULL").count() == 0


class TestSCD2ChangedRows:
    def _setup(self, spark: SparkSession):
        """Load initial data."""
        source = spark.createDataFrame(
            [("p1", "Alice", "Boston"), ("p2", "Bob", "Denver")], schema=SCHEMA
        )
        apply_scd2(spark, source, TARGET, "patient_id", TRACKED, DS1)

    def test_changed_row_expires_old_version(self, spark: SparkSession):
        """Old row should be expired (dim_is_current=False) when tracked column changes."""
        self._setup(spark)
        updated = spark.createDataFrame(
            [("p1", "Alice", "Austin"), ("p2", "Bob", "Denver")], schema=SCHEMA
        )
        apply_scd2(spark, updated, TARGET, "patient_id", TRACKED, DS2)

        expired = spark.table(TARGET).filter("patient_id = 'p1' AND dim_is_current = false")
        assert expired.count() == 1

    def test_changed_row_inserts_new_version(self, spark: SparkSession):
        """A new current row should be inserted when a tracked column changes."""
        self._setup(spark)
        updated = spark.createDataFrame(
            [("p1", "Alice", "Austin"), ("p2", "Bob", "Denver")], schema=SCHEMA
        )
        apply_scd2(spark, updated, TARGET, "patient_id", TRACKED, DS2)

        new_current = spark.table(TARGET).filter("patient_id = 'p1' AND dim_is_current = true")
        assert new_current.count() == 1
        assert new_current.collect()[0].city == "Austin"

    def test_changed_row_total_versions(self, spark: SparkSession):
        """Total rows for changed patient should be 2 (one expired + one current)."""
        self._setup(spark)
        updated = spark.createDataFrame(
            [("p1", "Alice", "Austin"), ("p2", "Bob", "Denver")], schema=SCHEMA
        )
        apply_scd2(spark, updated, TARGET, "patient_id", TRACKED, DS2)

        all_versions = spark.table(TARGET).filter("patient_id = 'p1'")
        assert all_versions.count() == 2

    def test_expired_row_has_correct_end_ts(self, spark: SparkSession):
        """Expired row's end_ts should be DS2 - 1 day."""
        self._setup(spark)
        updated = spark.createDataFrame(
            [("p1", "Alice", "Austin"), ("p2", "Bob", "Denver")], schema=SCHEMA
        )
        apply_scd2(spark, updated, TARGET, "patient_id", TRACKED, DS2)

        expired = spark.table(TARGET).filter("patient_id = 'p1' AND dim_is_current = false").collect()[0]
        assert str(expired.end_ts) == "2026-03-05"  # DS2 - 1


class TestSCD2UnchangedRows:
    def test_unchanged_row_no_new_version(self, spark: SparkSession):
        """Unchanged rows should not produce additional versions."""
        source = spark.createDataFrame([("p1", "Alice", "Boston")], schema=SCHEMA)
        apply_scd2(spark, source, TARGET, "patient_id", TRACKED, DS1)
        apply_scd2(spark, source, TARGET, "patient_id", TRACKED, DS2)

        result = spark.table(TARGET)
        assert result.count() == 1
        assert result.filter("dim_is_current = true").count() == 1

    def test_unchanged_row_remains_current(self, spark: SparkSession):
        """Unchanged row should still have dim_is_current=True after a second run."""
        source = spark.createDataFrame([("p1", "Alice", "Boston")], schema=SCHEMA)
        apply_scd2(spark, source, TARGET, "patient_id", TRACKED, DS1)
        apply_scd2(spark, source, TARGET, "patient_id", TRACKED, DS2)

        result = spark.table(TARGET).filter("patient_id = 'p1'").collect()[0]
        assert result.dim_is_current is True


class TestSCD2NetNewRows:
    def test_net_new_row_inserted_as_current(self, spark: SparkSession):
        """A natural key never seen before should be inserted as a current row."""
        source = spark.createDataFrame([("p1", "Alice", "Boston")], schema=SCHEMA)
        apply_scd2(spark, source, TARGET, "patient_id", TRACKED, DS1)

        source2 = spark.createDataFrame(
            [("p1", "Alice", "Boston"), ("p2", "Bob", "Denver")], schema=SCHEMA
        )
        apply_scd2(spark, source2, TARGET, "patient_id", TRACKED, DS2)

        new_row = spark.table(TARGET).filter("patient_id = 'p2'")
        assert new_row.count() == 1
        assert new_row.collect()[0].dim_is_current is True
