"""Populate the `columns:` block of `contracts/synthea_<table>.yml` from
the actual Synthea source schema in DuckDB.

Bronze is a landing zone — its schema mirrors the source. The DMS doesn't
define Bronze columns (it's a logical model focused on Silver/Gold), so
the StructType source of truth for the ingestion runner is the source
itself, captured into the contract YAML by this script.

Inputs:  $RAW_DB / DESCRIBE synthea.<table>
Outputs: contracts/synthea_<table>.yml  (preserves every other field;
         replaces only the `columns:` block)

Run from the chapter-5 directory:
    uv run python patient_360/scripts/sync_bronze_contracts.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import duckdb
import yaml

# DuckDB DESCRIBE returns SQL type names; map to the vocabulary the
# runner's `_type_map()` accepts (ingestion_runner._type_map).
DUCKDB_TO_CONTRACT_TYPE: dict[str, str] = {
    "VARCHAR": "string",
    "TEXT": "string",
    "BIGINT": "bigint",
    "INTEGER": "integer",
    "INT": "integer",
    "SMALLINT": "integer",
    "HUGEINT": "bigint",
    "DOUBLE": "double",
    "FLOAT": "float",
    "REAL": "float",
    "DECIMAL": "double",
    "BOOLEAN": "boolean",
    "BOOL": "boolean",
    "DATE": "date",
    "TIMESTAMP": "timestamp",
    "TIMESTAMP_NS": "timestamp",
    "TIMESTAMP_MS": "timestamp",
    "TIMESTAMP_S": "timestamp",
    "TIME": "string",
    "BLOB": "string",
}

DEFAULT_RAW_DB = Path("../../data/duckdb/raw.db")
DEFAULT_CONTRACTS_DIR = Path("patient_360/contracts")
BRONZE_PREFIX = "synthea_"


def _norm_duckdb_type(t: str) -> str:
    """Strip parameterisation (e.g. ``DECIMAL(18,2)``) and look up."""
    base = t.split("(", 1)[0].strip().upper()
    if base not in DUCKDB_TO_CONTRACT_TYPE:
        raise ValueError(f"Unmapped DuckDB type: {t!r}")
    return DUCKDB_TO_CONTRACT_TYPE[base]


def fetch_source_columns(con: duckdb.DuckDBPyConnection, table: str) -> list[dict[str, Any]]:
    """Return the source schema for ``synthea.<table>`` as contract rows."""
    rows = con.execute(f"DESCRIBE synthea.{table}").fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        name = row[0]
        duckdb_type = row[1]
        # DESCRIBE row shape: (column_name, column_type, null, key, default, extra)
        nullable = (row[2] != "NO") if len(row) > 2 and row[2] is not None else True
        out.append(
            {
                "name": name,
                "type": _norm_duckdb_type(duckdb_type),
                "nullable": bool(nullable),
            }
        )
    return out


def update_contract_yaml(contract_path: Path, columns: list[dict[str, Any]]) -> bool:
    """Replace ``columns:`` in ``contract_path``. Returns True if changed."""
    data = yaml.safe_load(contract_path.read_text()) or {}
    if data.get("columns") == columns:
        return False
    data["columns"] = columns
    contract_path.write_text(yaml.safe_dump(data, sort_keys=False))
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-db",
        type=Path,
        default=DEFAULT_RAW_DB,
        help="Path to the DuckDB raw.db (default: ../../data/duckdb/raw.db)",
    )
    parser.add_argument(
        "--contracts-dir",
        type=Path,
        default=DEFAULT_CONTRACTS_DIR,
        help="Directory of contract YAMLs (default: patient_360/contracts)",
    )
    args = parser.parse_args(argv)

    if not args.raw_db.is_file():
        print(f"ERROR: raw.db not found at {args.raw_db}", file=sys.stderr)
        return 2

    contracts = sorted(args.contracts_dir.glob(f"{BRONZE_PREFIX}*.yml"))
    if not contracts:
        print(f"ERROR: no {BRONZE_PREFIX}*.yml under {args.contracts_dir}", file=sys.stderr)
        return 2

    con = duckdb.connect(str(args.raw_db), read_only=True)
    updated = 0
    for contract_path in contracts:
        table = contract_path.stem.removeprefix(BRONZE_PREFIX)
        try:
            cols = fetch_source_columns(con, table)
        except duckdb.CatalogException:
            print(f"  SKIP {contract_path.name}: synthea.{table} not in raw.db")
            continue
        changed = update_contract_yaml(contract_path, cols)
        status = "UPDATED" if changed else "matches"
        print(f"  {status:7s} {contract_path.name}  ({len(cols)} columns)")
        if changed:
            updated += 1

    print(f"\n{updated} contract(s) updated; {len(contracts) - updated} already current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
