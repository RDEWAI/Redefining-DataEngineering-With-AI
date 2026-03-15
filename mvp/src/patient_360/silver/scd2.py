"""Reusable SCD Type 2 function — Delta Lake MERGE INTO pattern."""

from __future__ import annotations

import logging

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import BooleanType, DateType

from patient_360.utils.delta import save_as_delta_table

logger = logging.getLogger(__name__)


def apply_scd2(
    spark: SparkSession,
    source_df: DataFrame,
    target_table: str,
    natural_key: str,
    tracked_columns: list[str],
    ds: str,
) -> None:
    """
    Apply SCD Type 2 merge to a Delta target table.

    On every run:
      - Net-new natural keys → INSERT as current row
      - Changed rows (hash mismatch) → EXPIRE old row, INSERT new version
      - Unchanged rows → no-op

    SCD Type 2 columns added automatically:
      surrogate_key, start_ts, end_ts, dim_is_current,
      record_hash, dw_created_at, dw_updated_at

    Args:
        spark:           Active SparkSession.
        source_df:       Incoming source DataFrame (bronze, pre-transformed).
        target_table:    Fully qualified target table (e.g. "silver.dim_patients").
        natural_key:     Business key column name (e.g. "patient_id").
        tracked_columns: Columns whose changes trigger a new SCD2 version.
        ds:              Load date string "YYYY-MM-DD".
    """
    # ── 1. Compute record hash from tracked columns ───────────────────────────
    hash_expr = F.sha2(
        F.concat_ws("|", *[F.col(c).cast("string") for c in tracked_columns]), 256
    )
    source_with_hash = source_df.withColumn("record_hash", hash_expr)

    # ── 2. First load — create table and insert all rows as current ───────────
    if not _delta_table_exists(spark, target_table):
        logger.info("First load for %s — creating table", target_table)
        # Use overwrite so stale Delta files at the path are replaced cleanly.
        _insert_as_current(spark, source_with_hash, target_table, ds, mode="overwrite")
        return

    # ── 3. Expire changed rows ────────────────────────────────────────────────
    # MERGE: for rows where natural_key matches and hash differs → expire old row
    (
        DeltaTable.forName(spark, target_table).alias("t")
        .merge(
            source_with_hash.alias("s"),
            f"t.{natural_key} = s.{natural_key} AND t.dim_is_current = true",
        )
        .whenMatchedUpdate(
            condition="t.record_hash != s.record_hash",
            set={
                "dim_is_current":    "false",
                "end_ts":   f"date_sub(to_date('{ds}'), 1)",
                "dw_updated_at": "current_timestamp()",
            },
        )
        .execute()
    )

    # ── 4. Insert new versions (changed rows + net-new rows) ──────────────────
    # After step 3, changed rows no longer have a current record.
    # left_anti join gives us all source rows that have no current target row.
    current_keys = (
        spark.table(target_table)
        .filter(F.col("dim_is_current") == True)  # noqa: E712
        .select(natural_key)
    )
    new_rows = source_with_hash.join(current_keys, on=natural_key, how="left_anti")

    if new_rows.isEmpty():
        logger.info("No changes detected for %s (ds=%s)", target_table, ds)
        return

    _insert_as_current(spark, new_rows, target_table, ds)
    logger.info("SCD2 complete for %s (ds=%s)", target_table, ds)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _insert_as_current(
    spark: SparkSession, df: DataFrame, target_table: str, ds: str, mode: str = "append"
) -> None:
    """Add SCD2 metadata columns and write rows to the target Delta table."""
    enriched = (
        df
        .withColumn("surrogate_key",  F.expr("uuid()"))
        .withColumn("start_ts", F.to_date(F.lit(ds)))
        .withColumn("end_ts",    F.lit(None).cast(DateType()))
        .withColumn("dim_is_current",     F.lit(True).cast(BooleanType()))
        .withColumn("dw_created_at",  F.current_timestamp())
        .withColumn("dw_updated_at",  F.current_timestamp())
    )
    save_as_delta_table(spark, enriched, target_table, mode=mode)


def _delta_table_exists(spark: SparkSession, table_name: str) -> bool:
    """Return True if the Delta table exists in the catalog."""
    try:
        spark.table(table_name)
        return True
    except Exception:
        return False
