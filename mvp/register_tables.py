"""
Register all Delta tables in the Hive metastore so they are queryable by name
in any Spark session (spark-sql shell, pyspark shell, run_local.py).

Run once after pipeline execution — idempotent, safe to re-run.

Usage:
    uv run python register_tables.py
"""

from __future__ import annotations

import os
from pathlib import Path

from patient_360.utils.spark import get_spark

WAREHOUSE = "warehouse"


def register_all(spark) -> None:
    warehouse_path = Path(__file__).parent / WAREHOUSE

    for db_dir in sorted(warehouse_path.iterdir()):
        if not db_dir.is_dir():
            continue

        # db_dir name is like "bronze.db" → database name is "bronze"
        db_name = db_dir.name.replace(".db", "")
        spark.sql(f"CREATE DATABASE IF NOT EXISTS {db_name}")

        for tbl_dir in sorted(db_dir.iterdir()):
            if not tbl_dir.is_dir() or "_delta_log" in tbl_dir.name:
                continue

            tbl_name = tbl_dir.name
            location = str(tbl_dir.resolve())

            spark.sql(f"""
                CREATE TABLE IF NOT EXISTS {db_name}.{tbl_name}
                USING delta
                LOCATION '{location}'
            """)
            print(f"  registered {db_name}.{tbl_name}")

    print("\nDone. All Delta tables are now available in the metastore.")
    print("Start a shell with:  make spark-sql  or  make pyspark-shell")


def main():
    spark = get_spark(app_name="register_tables", warehouse_path=WAREHOUSE)
    spark.sparkContext.setLogLevel("ERROR")

    print(f"\nRegistering Delta tables from {WAREHOUSE}/\n")
    register_all(spark)
    spark.stop()


if __name__ == "__main__":
    main()
