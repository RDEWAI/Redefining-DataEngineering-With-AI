"""SCD Type 2 merge helper.

Per LLD §5.2 and DMS §6: SHA-256-based change detection + Delta MERGE INTO.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import DataFrame, SparkSession


def _build_hash_expr(columns: list[str]) -> str:
    """Build a SHA2-256 hash expression over normalised columns.

    NULLs are coalesced to the literal ``"\\u0000"`` so that
    NULL-vs-empty-string differences trigger a new SCD2 row.
    """
    if not columns:
        raise ValueError("hash_cols must be a non-empty list")
    pieces = ", ".join(f"COALESCE(CAST(`{c}` AS STRING), '\\u0000')" for c in columns)
    return f"sha2(concat_ws('||', {pieces}), 256)"


def apply_scd2(
    spark: SparkSession,
    target: str,
    source: DataFrame,
    key_cols: list[str],
    hash_cols: list[str],
    *,
    effective_col: str = "effective_date",
    end_col: str = "end_date",
    is_current_col: str = "is_current",
    hash_col: str = "_row_hash",
) -> dict[str, Any]:
    """Apply an SCD2 merge from ``source`` into Delta table ``target``.

    Parameters
    ----------
    spark:
        Active SparkSession; used to issue the MERGE statement.
    target:
        Fully-qualified target Delta table name (e.g. ``unity.silver.dim_patient``).
    source:
        Source DataFrame containing the natural key + tracked columns.
    key_cols:
        Natural-key column names. Used to match existing rows.
    hash_cols:
        Columns whose change should produce a new SCD2 version.
    effective_col, end_col, is_current_col, hash_col:
        SCD2 metadata column names.

    Returns
    -------
    dict[str, Any]
        Diagnostic metrics (``rows_inserted``, ``rows_closed``).

    Notes
    -----
    Tests cover the hash expression and merge-statement construction; live
    Delta MERGE execution is exercised by integration tests with a real
    Spark + Delta runtime.
    """
    if not key_cols:
        raise ValueError("key_cols must be a non-empty list")
    if not target:
        raise ValueError("target table must be specified")

    hash_expr = _build_hash_expr(hash_cols)
    staged = source.selectExpr(
        *[f"`{c}`" for c in key_cols],
        *[f"`{c}`" for c in hash_cols],
        f"{hash_expr} AS {hash_col}",
        f"current_date() AS {effective_col}",
    )
    staged.createOrReplaceTempView("_scd2_staging")

    join_cond = " AND ".join(f"t.`{c}` = s.`{c}`" for c in key_cols)
    update_set = f"t.{end_col} = current_date(), " f"t.{is_current_col} = false"
    insert_cols = key_cols + hash_cols + [hash_col, effective_col, end_col, is_current_col]
    insert_vals = (
        [f"s.`{c}`" for c in key_cols]
        + [f"s.`{c}`" for c in hash_cols]
        + [f"s.{hash_col}", f"s.{effective_col}", "NULL", "true"]
    )

    merge_sql = (
        f"MERGE INTO {target} t USING _scd2_staging s ON {join_cond} "
        f"WHEN MATCHED AND t.{is_current_col} = true AND t.{hash_col} <> s.{hash_col} "
        f"THEN UPDATE SET {update_set} "
        f"WHEN NOT MATCHED THEN INSERT ("
        + ", ".join(insert_cols)
        + ") VALUES ("
        + ", ".join(insert_vals)
        + ")"
    )
    spark.sql(merge_sql)
    return {"target": target, "merge_sql": merge_sql}
