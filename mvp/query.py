"""
Interactive query helper for the Patient 360 Delta warehouse.

Usage:
    uv run python query.py                     # show row counts for all tables
    uv run python query.py bronze.patients 10  # show 10 rows from a table
    uv run python query.py silver.dim_patients # show silver dims

Reads Delta tables directly by path — no metastore required.
"""

from __future__ import annotations

import sys

from patient_360.utils.spark import get_spark

WAREHOUSE = "warehouse"


def read(spark, table: str):
    """Read a Delta table by path. Format: <database>.<table>"""
    db, tbl = table.split(".")
    return spark.read.format("delta").load(f"{WAREHOUSE}/{db}.db/{tbl}")


def main():
    spark = get_spark(warehouse_path=WAREHOUSE)
    spark.sparkContext.setLogLevel("ERROR")

    args = sys.argv[1:]

    if not args:
        # Default: show row counts for all available tables
        import os
        print(f"\n{'Table':<35} {'Rows':>12}")
        print("-" * 50)
        for db in ["bronze", "silver", "gold"]:
            db_path = f"{WAREHOUSE}/{db}.db"
            if not os.path.exists(db_path):
                continue
            for tbl in sorted(os.listdir(db_path)):
                tbl_path = f"{db_path}/{tbl}"
                if os.path.isdir(tbl_path) and "_delta_log" not in tbl:
                    try:
                        count = spark.read.format("delta").load(tbl_path).count()
                        print(f"{db}.{tbl:<30} {count:>12,}")
                    except Exception:
                        pass
        print()
    else:
        # Show rows from specified table
        table = args[0]
        limit = int(args[1]) if len(args) > 1 else 20
        print(f"\n=== {table} (top {limit} rows) ===")
        read(spark, table).show(limit, truncate=False)

    spark.stop()


if __name__ == "__main__":
    main()
