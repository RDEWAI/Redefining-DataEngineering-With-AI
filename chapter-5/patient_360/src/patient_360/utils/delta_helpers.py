"""Delta Lake write helpers.

Per LLD §4.5: idempotent partition replacement via ``replaceWhere``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from pyspark.sql import DataFrame


def replace_where(df: DataFrame, table: str, ds: str) -> None:
    """Append ``df`` to Delta ``table`` using ``replaceWhere ds = '<ds>'``.

    Parameters
    ----------
    df:
        DataFrame to write.
    table:
        Fully qualified table identifier (e.g. ``unity.bronze.synthea_patients``).
    ds:
        Partition date as ``YYYY-MM-DD``.
    """
    if not table:
        raise ValueError("table must be a non-empty string")
    if not ds:
        raise ValueError("ds must be a non-empty string")
    (
        df.write.mode("append")
        .format("delta")
        .partitionBy("ds")
        .option("replaceWhere", f"ds = '{ds}'")
        .saveAsTable(table)
    )


def build_replace_where_clause(ds: str) -> str:
    """Return the ``replaceWhere`` predicate for a given partition date."""
    if not ds:
        raise ValueError("ds must be a non-empty string")
    return f"ds = '{ds}'"
