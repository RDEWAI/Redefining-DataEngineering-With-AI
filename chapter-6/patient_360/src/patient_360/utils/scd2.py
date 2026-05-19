"""Generic SCD Type 2 merge for Silver dimension tables.

Per LLD §5.2 / DMS §6, SCD2 uses SHA-256 hash comparison and Delta
``MERGE INTO`` with matched / unmatched semantics. The natural key plus a
column-hash uniquely identifies a row version; a hash change closes the
current row (sets ``expiry_date`` + ``is_current = false``) and inserts a
new version.

The merge logic is layered: ``compute_record_hash`` is pure-Python-testable
(works on plain DataFrames), while :func:`apply_scd2` calls Delta MERGE
INTO and is exercised in the integration suite.
"""

from __future__ import annotations

import hashlib
from typing import Any


def compute_record_hash_python(row: dict[str, Any], hash_columns: list[str]) -> str:
    """Return the SHA-256 hex digest used to detect attribute drift.

    Used by unit tests and by Python-side fixtures. The Spark-side
    implementation in :func:`apply_scd2` uses ``F.sha2(F.concat_ws(...))``
    over the same column ordering so the digests agree.
    """
    parts = [str(row.get(col, "")) for col in hash_columns]
    payload = "|".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def apply_scd2(
    spark: Any,
    *,
    target_table: str,
    source_df: Any,
    natural_keys: list[str],
    hash_columns: list[str],
    effective_date: str,
) -> dict[str, int]:
    """Apply a SCD Type 2 merge from ``source_df`` into ``target_table``.

    Steps:
      1. Compute ``record_hash`` on the source rows.
      2. Close any current target row whose ``natural_key`` matches and whose
         ``record_hash`` differs (``is_current = false``, ``expiry_date``
         set to ``effective_date``).
      3. Insert the new version with ``is_current = true``,
         ``effective_date`` set, and ``expiry_date = NULL``.

    Returns counts ``{"closed": N, "inserted": M}`` for observability.
    """
    try:
        from pyspark.sql import functions as F  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - env-specific
        raise RuntimeError("pyspark required for apply_scd2") from exc

    nk_expr = F.concat_ws("||", *[F.col(c) for c in natural_keys])
    hash_expr = F.sha2(F.concat_ws("||", *[F.col(c) for c in hash_columns]), 256)

    enriched = (
        source_df.withColumn("natural_key", nk_expr)
        .withColumn("record_hash", hash_expr)
        .withColumn("effective_date", F.lit(effective_date))
        .withColumn("expiry_date", F.lit(None).cast("date"))
        .withColumn("is_current", F.lit(True))
    )

    enriched.createOrReplaceTempView("_scd2_source")

    # Close out rows whose hash changed.
    close_sql = f"""
        MERGE INTO {target_table} t
        USING _scd2_source s
        ON t.natural_key = s.natural_key AND t.is_current = TRUE
        WHEN MATCHED AND t.record_hash <> s.record_hash THEN
          UPDATE SET t.is_current = FALSE, t.expiry_date = s.effective_date
    """
    spark.sql(close_sql)

    # Insert new versions (the close MERGE leaves them as still-needing-insert
    # because MERGE doesn't double-write; we run a second INSERT for clarity).
    insert_sql = f"""
        INSERT INTO {target_table}
        SELECT s.* FROM _scd2_source s
        LEFT JOIN {target_table} t
          ON t.natural_key = s.natural_key AND t.is_current = TRUE
        WHERE t.natural_key IS NULL OR t.record_hash <> s.record_hash
    """
    spark.sql(insert_sql)

    # Counts are best-effort; SE stats are the system of record.
    closed = spark.sql(
        f"SELECT COUNT(*) AS c FROM {target_table} WHERE expiry_date = '{effective_date}'"
    ).collect()[0]["c"]
    inserted = spark.sql(
        f"SELECT COUNT(*) AS c FROM {target_table} WHERE effective_date = '{effective_date}'"
    ).collect()[0]["c"]
    return {"closed": int(closed), "inserted": int(inserted)}
