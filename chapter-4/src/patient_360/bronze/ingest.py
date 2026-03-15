"""Bronze ingestion — generic CSV → Delta table, partitioned by ds."""

from __future__ import annotations

import logging
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType

from patient_360.bronze.schemas import TABLE_REGISTRY
from patient_360.utils.delta import save_as_delta_table

logger = logging.getLogger(__name__)

RAW_DATA_PATH = Path(__file__).parents[4] / "data" / "raw"


def ingest(
    spark: SparkSession,
    table_name: str,
    schema: StructType,
    csv_file: str,
    ds: str,
    raw_path: Path = RAW_DATA_PATH,
    database: str = "bronze",
) -> DataFrame:
    """
    Read a single CSV source file and write it to a bronze Delta table
    partitioned by ds.

    Args:
        spark:      Active SparkSession.
        table_name: Target table name (e.g. "patients"). Written to bronze.<table_name>.
        schema:     Expected source schema (enforced on read).
        csv_file:   CSV filename under raw_path (e.g. "patients.csv").
        ds:         Load date string "YYYY-MM-DD" used as the partition value.
        raw_path:   Path to raw CSV directory.
        database:   Target database/schema name.

    Returns:
        The ingested DataFrame (with ds column added) for downstream use / testing.

    Raises:
        FileNotFoundError: If the CSV file does not exist at raw_path / csv_file.
    """
    csv_path = raw_path / csv_file
    if not csv_path.exists():
        raise FileNotFoundError(f"Source file not found: {csv_path}")

    logger.info("Ingesting %s from %s (ds=%s)", table_name, csv_path, ds)

    spark.sql(f"CREATE DATABASE IF NOT EXISTS {database}")

    df = (
        spark.read.format("csv")
        .option("header", "true")
        .option("timestampFormat", "yyyy-MM-dd'T'HH:mm:ssZ")
        .schema(schema)
        .load(str(csv_path))
        .withColumn("ds", F.lit(ds))
        .withColumn("ingested_at", F.current_timestamp())
    )

    target = f"{database}.{table_name}"

    save_as_delta_table(
        spark, df, target,
        mode="overwrite",
        partition_by=["ds"],
        replace_where=f"ds = '{ds}'",
    )

    count = df.count()
    logger.info("Wrote %d rows to %s (ds=%s)", count, target, ds)

    return df


def ingest_all(
    spark: SparkSession,
    ds: str,
    raw_path: Path = RAW_DATA_PATH,
    database: str = "bronze",
) -> None:
    """
    Ingest all registered source tables for a given load date.

    Iterates TABLE_REGISTRY — one ingest() call per table.
    No table-specific logic here; all config lives in schemas.py.

    Args:
        spark:    Active SparkSession.
        ds:       Load date string "YYYY-MM-DD".
        raw_path: Path to raw CSV directory.
        database: Target database/schema name.
    """
    for table_name, (csv_file, schema) in TABLE_REGISTRY.items():
        ingest(
            spark=spark,
            table_name=table_name,
            schema=schema,
            csv_file=csv_file,
            ds=ds,
            raw_path=raw_path,
            database=database,
        )

    logger.info("Bronze ingestion complete for ds=%s (%d tables)", ds, len(TABLE_REGISTRY))
