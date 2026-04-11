"""
Generate conf/init.sql for the interactive spark-sql shell.

With Unity Catalog as the metastore, table metadata persists across sessions.
No manual CREATE TABLE registration is needed — this script just generates a
context-setting init file so the shell starts in the right catalog.

Called automatically by `make spark-sql`.

Usage:
    uv run python generate_init_sql.py
"""

from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).parent / "conf" / "init.sql"


def main() -> None:
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(
        "-- Unity Catalog persists table metadata across sessions.\n"
        "-- Tables are available immediately without manual registration.\n"
        "SHOW DATABASES;\n"
    )
    print(f"Written init.sql to {OUT}")


if __name__ == "__main__":
    main()
