"""Tests for bronze ingestion layer."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from pyspark.sql import SparkSession
from pyspark.sql.types import StringType, StructField, StructType

from patient_360.bronze.ingest import ingest

# ── Minimal test schema ───────────────────────────────────────────────────────

TEST_SCHEMA = StructType([
    StructField("id", StringType(), nullable=False),
    StructField("name", StringType(), nullable=True),
    StructField("city", StringType(), nullable=True),
])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_csv(path: Path, rows: list[dict]) -> None:
    """Write a list of dicts to a CSV file."""
    csv_file = path / "test_table.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestIngest:
    def test_ingest_writes_correct_row_count(self, spark: SparkSession, ds: str, tmp_path: Path):
        """Ingested table should contain the same number of rows as the source CSV."""
        rows = [
            {"id": "p1", "name": "Alice", "city": "Boston"},
            {"id": "p2", "name": "Bob",   "city": "Denver"},
            {"id": "p3", "name": "Carol", "city": "Austin"},
        ]
        _write_csv(tmp_path, rows)

        df = ingest(
            spark=spark,
            table_name="test_row_count",
            schema=TEST_SCHEMA,
            csv_file="test_table.csv",
            ds=ds,
            raw_path=tmp_path,
        )

        assert df.count() == 3

    def test_ingest_adds_ds_partition_column(self, spark: SparkSession, ds: str, tmp_path: Path):
        """Every row must carry the ds partition value."""
        rows = [{"id": "p1", "name": "Alice", "city": "Boston"}]
        _write_csv(tmp_path, rows)

        df = ingest(
            spark=spark,
            table_name="test_ds_partition",
            schema=TEST_SCHEMA,
            csv_file="test_table.csv",
            ds=ds,
            raw_path=tmp_path,
        )

        assert "ds" in df.columns
        assert all(r.ds == ds for r in df.select("ds").collect())

    def test_ingest_adds_ingested_at_column(self, spark: SparkSession, ds: str, tmp_path: Path):
        """Ingested table must include an ingested_at audit timestamp."""
        rows = [{"id": "p1", "name": "Alice", "city": "Boston"}]
        _write_csv(tmp_path, rows)

        df = ingest(
            spark=spark,
            table_name="test_ingested_at",
            schema=TEST_SCHEMA,
            csv_file="test_table.csv",
            ds=ds,
            raw_path=tmp_path,
        )

        assert "ingested_at" in df.columns
        assert df.filter("ingested_at IS NULL").count() == 0

    def test_ingest_enforces_schema(self, spark: SparkSession, ds: str, tmp_path: Path):
        """Columns not in the schema must not appear in the output."""
        rows = [{"id": "p1", "name": "Alice", "city": "Boston", "extra_col": "dropped"}]
        _write_csv(tmp_path, rows)

        df = ingest(
            spark=spark,
            table_name="test_schema_enforcement",
            schema=TEST_SCHEMA,
            csv_file="test_table.csv",
            ds=ds,
            raw_path=tmp_path,
        )

        assert "extra_col" not in df.columns
        assert "id" in df.columns

    def test_ingest_raises_on_missing_file(self, spark: SparkSession, ds: str, tmp_path: Path):
        """Should raise FileNotFoundError when CSV does not exist."""
        with pytest.raises(FileNotFoundError, match="Source file not found"):
            ingest(
                spark=spark,
                table_name="test_missing",
                schema=TEST_SCHEMA,
                csv_file="nonexistent.csv",
                ds=ds,
                raw_path=tmp_path,
            )

    def test_ingest_multiple_ds_partitions_are_independent(
        self, spark: SparkSession, tmp_path: Path
    ):
        """
        Running ingest twice with different ds values should produce two
        independent partitions — not overwrite each other.
        """
        rows = [{"id": "p1", "name": "Alice", "city": "Boston"}]
        _write_csv(tmp_path, rows)

        ingest(spark=spark, table_name="test_multi_ds", schema=TEST_SCHEMA,
               csv_file="test_table.csv", ds="2026-03-05", raw_path=tmp_path)
        ingest(spark=spark, table_name="test_multi_ds", schema=TEST_SCHEMA,
               csv_file="test_table.csv", ds="2026-03-06", raw_path=tmp_path)

        table_df = spark.table("bronze.test_multi_ds")
        partitions = {r.ds for r in table_df.select("ds").distinct().collect()}
        assert "2026-03-05" in partitions
        assert "2026-03-06" in partitions
        assert table_df.count() == 2
