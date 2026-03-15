"""
Integration tests for bronze ingestion using real Synthea CSV data.

These tests run against the actual data/raw/ directory and verify
that real schemas, row counts, and partition logic work end-to-end.

Marked with @pytest.mark.integration so they can be run separately:
    pytest tests/test_bronze/test_ingest_integration.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pyspark.sql import SparkSession

from patient_360.bronze.ingest import ingest, ingest_all
from patient_360.bronze.schemas import TABLE_REGISTRY

REAL_DATA_PATH = Path(__file__).parents[3] / "data" / "raw"

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def ingested(spark: SparkSession) -> dict[str, int]:
    """Run ingest_all once for all integration tests and return row counts."""
    if not REAL_DATA_PATH.exists():
        pytest.skip("Real Synthea data not found at data/raw/")

    ingest_all(spark, ds="2026-03-06", raw_path=REAL_DATA_PATH)

    return {
        table: spark.table(f"bronze.{table}").count()
        for table in TABLE_REGISTRY
    }


class TestRealDataIngestion:
    def test_all_tables_loaded(self, ingested: dict):
        """All 10 registered tables should be present."""
        assert set(ingested.keys()) == set(TABLE_REGISTRY.keys())

    def test_patients_row_count(self, ingested: dict):
        """patients should have rows (Synthea generates ~5K patients)."""
        assert ingested["patients"] > 0

    def test_encounters_larger_than_patients(self, ingested: dict):
        """encounters should have more rows than patients."""
        assert ingested["encounters"] > ingested["patients"]

    def test_observations_is_largest_table(self, ingested: dict):
        """observations is the largest Synthea table by far."""
        assert ingested["observations"] == max(ingested.values())

    def test_payers_is_small_reference_table(self, ingested: dict):
        """payers is a tiny reference table — should be < 100 rows."""
        assert ingested["payers"] < 100

    def test_ds_partition_present_on_all_tables(self, spark: SparkSession, ingested: dict):
        """Every bronze table must have ds column with the correct load date."""
        for table in TABLE_REGISTRY:
            df = spark.table(f"bronze.{table}")
            assert "ds" in df.columns, f"ds column missing on bronze.{table}"
            bad_rows = df.filter("ds != '2026-03-06'").count()
            assert bad_rows == 0, f"Wrong ds values in bronze.{table}"

    def test_ingested_at_not_null_on_all_tables(self, spark: SparkSession, ingested: dict):
        """ingested_at audit column must be populated on every row."""
        for table in TABLE_REGISTRY:
            df = spark.table(f"bronze.{table}")
            assert "ingested_at" in df.columns, f"ingested_at missing on bronze.{table}"
            null_count = df.filter("ingested_at IS NULL").count()
            assert null_count == 0, f"{null_count} null ingested_at rows in bronze.{table}"

    def test_no_null_patient_ids(self, spark: SparkSession, ingested: dict):
        """patients.id must never be null — it is the PK."""
        df = spark.table("bronze.patients")
        null_ids = df.filter("id IS NULL").count()
        assert null_ids == 0

    def test_no_null_encounter_ids(self, spark: SparkSession, ingested: dict):
        """encounters.id must never be null — it is the PK."""
        df = spark.table("bronze.encounters")
        null_ids = df.filter("id IS NULL").count()
        assert null_ids == 0
