"""
Interactive DuckDB shell for querying the Patient 360 Delta warehouse.

All Delta tables are pre-registered as views so you can query by name.
No Spark, no metastore, no JARs needed.

Usage:
    uv run python duckdb_shell.py             # interactive shell
    uv run python duckdb_shell.py "SELECT count(*) FROM bronze.patients"
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

WAREHOUSE = Path(__file__).parent / "warehouse"


def setup(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("INSTALL delta; LOAD delta;")

    for db_dir in sorted(WAREHOUSE.iterdir()):
        if not db_dir.is_dir():
            continue
        db = db_dir.name.replace(".db", "")
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {db}")
        for tbl_dir in sorted(db_dir.iterdir()):
            if not tbl_dir.is_dir() or "_delta_log" in tbl_dir.name:
                continue
            tbl = tbl_dir.name
            location = str(tbl_dir.resolve())
            con.execute(
                f"CREATE OR REPLACE VIEW {db}.{tbl} "
                f"AS SELECT * FROM delta_scan('{location}')"
            )
            print(f"  {db}.{tbl}")


def interactive(con: duckdb.DuckDBPyConnection) -> None:
    print("\nType SQL queries. Type 'exit' or Ctrl-D to quit.\n")
    while True:
        try:
            sql = input("duckdb> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not sql:
            continue
        if sql.lower() in ("exit", "quit"):
            break
        try:
            con.execute(sql)
            con.fetchmany  # probe
            result = con.fetchall()
            desc = con.description
            if desc:
                headers = [d[0] for d in desc]
                widths = [max(len(h), max((len(str(r[i])) for r in result), default=0)) for i, h in enumerate(headers)]
                print("  ".join(h.ljust(w) for h, w in zip(headers, widths)))
                print("  ".join("-" * w for w in widths))
                for row in result:
                    print("  ".join(str(v).ljust(w) for v, w in zip(row, widths)))
        except Exception as e:
            print(f"Error: {e}")


def main() -> None:
    con = duckdb.connect()

    print("\nLoading Delta tables from warehouse/...\n")
    setup(con)
    print("\nReady. Example queries:")
    print("  SELECT patient_id, first, last FROM bronze.patients LIMIT 5;")
    print("  SELECT count(*) FROM bronze.encounters;")
    print("  SHOW ALL TABLES;")

    if len(sys.argv) > 1:
        sql = " ".join(sys.argv[1:])
        result = con.execute(sql).fetchdf()
        print(result.to_string(index=False))
    else:
        interactive(con)


if __name__ == "__main__":
    main()
