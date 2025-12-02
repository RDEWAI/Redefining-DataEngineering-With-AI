#!/usr/bin/env python3
"""
Load raw Synthea CSV files into DuckDB tables.

This script loads all CSV files from data/raw/ into DuckDB tables
in the synthea schema at data/duckdb/raw.db.

Usage:
    python scripts/load_raw_csv_to_duckdb.py
    # OR via Makefile:
    make load-raw-data

Exit Codes:
    0: Success - all CSV files loaded successfully
    1: Prerequisites not met (missing files, environment not set up)
    2: Invalid CSV format or schema error
    3: DuckDB connection or execution error
"""

import time
from pathlib import Path
from typing import List, Tuple

import duckdb

# Constants
RAW_DIR = Path("data/raw")
DB_PATH = Path("data/duckdb/raw.db")
SCHEMA_NAME = "synthea"


class PrerequisiteError(Exception):
    """Raised when prerequisites for data loading are not met."""

    pass


def validate_prerequisites(raw_dir: Path = RAW_DIR) -> None:
    """
    Validate that all prerequisites for data loading are met.

    Args:
        raw_dir: Path to the raw data directory (default: data/raw)

    Raises:
        PrerequisiteError: If prerequisites are not met, with actionable message
    """
    # Check if raw directory exists
    if not raw_dir.exists():
        raise PrerequisiteError(
            f"Raw data directory not found: {raw_dir}\n"
            "  Run 'make raw-data-copy' first to extract CSV files."
        )

    # Check if directory contains CSV files
    csv_files = list(raw_dir.glob("*.csv"))
    if not csv_files:
        raise PrerequisiteError(
            f"No CSV files found in {raw_dir}\n"
            "  Run 'make raw-data-copy' first to extract CSV files."
        )


def get_table_name(csv_path: Path) -> str:
    """
    Extract table name from CSV filename.

    Args:
        csv_path: Path to CSV file

    Returns:
        Table name (filename without .csv extension)

    Example:
        >>> get_table_name(Path('data/raw/patients.csv'))
        'patients'
    """
    return csv_path.stem


def discover_csv_files(raw_dir: Path = RAW_DIR) -> List[Path]:
    """
    Discover all CSV files in the raw data directory.

    Args:
        raw_dir: Path to directory containing CSV files (default: data/raw)

    Returns:
        List of Path objects for each CSV file, sorted alphabetically

    Raises:
        FileNotFoundError: If raw_dir does not exist
    """
    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw data directory not found: {raw_dir}")

    csv_files = sorted(raw_dir.glob("*.csv"))
    return csv_files


def create_schema_if_not_exists(
    conn: duckdb.DuckDBPyConnection, schema: str = SCHEMA_NAME
) -> None:
    """
    Create the schema if it doesn't exist.

    Args:
        conn: DuckDB connection object
        schema: Name of schema to create (default: synthea)
    """
    conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")


def load_csv_to_table(
    conn: duckdb.DuckDBPyConnection,
    csv_path: Path,
    table_name: str,
    schema: str = SCHEMA_NAME,
) -> int:
    """
    Load a single CSV file into a DuckDB table.

    Args:
        conn: DuckDB connection object
        csv_path: Path to CSV file
        table_name: Name of table to create
        schema: Schema name (default: synthea)

    Returns:
        Number of rows loaded

    Raises:
        duckdb.Error: If table creation or CSV loading fails
    """
    # Use CREATE OR REPLACE for idempotent loading
    conn.execute(
        f"""
        CREATE OR REPLACE TABLE {schema}.{table_name} AS
        SELECT * FROM read_csv('{csv_path}', auto_detect=true)
        """
    )

    # Get row count
    result = conn.execute(f"SELECT COUNT(*) FROM {schema}.{table_name}").fetchone()
    return result[0] if result else 0


def load_all_csvs(
    conn: duckdb.DuckDBPyConnection,
    csv_files: List[Path],
    schema: str = SCHEMA_NAME,
) -> List[Tuple[str, int]]:
    """
    Load all CSV files into DuckDB tables.

    Args:
        conn: DuckDB connection object
        csv_files: List of CSV file paths
        schema: Schema name (default: synthea)

    Returns:
        List of tuples (table_name, row_count) for each loaded table
    """
    results = []
    total_files = len(csv_files)

    for idx, csv_path in enumerate(csv_files, 1):
        table_name = get_table_name(csv_path)
        print(f"[{idx}/{total_files}] Loading {table_name}...")

        row_count = load_csv_to_table(conn, csv_path, table_name, schema)
        print(f"  ✓ Loaded {row_count:,} rows")

        results.append((table_name, row_count))

    return results


def print_summary(results: List[Tuple[str, int]], elapsed: float) -> None:
    """
    Print a summary of the loading process.

    Args:
        results: List of (table_name, row_count) tuples
        elapsed: Elapsed time in seconds
    """
    total_tables = len(results)
    total_rows = sum(count for _, count in results)

    print(f"\n✅ Summary:")
    print(f"  Tables created: {total_tables}")
    print(f"  Total rows loaded: {total_rows:,}")
    print(f"  Time elapsed: {elapsed:.2f}s")


def main() -> int:
    """
    Main entry point for CSV loading script.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    start_time = time.time()

    try:
        # Validate prerequisites first
        print("[1/4] Checking prerequisites...")
        validate_prerequisites(RAW_DIR)
        print("  ✓ Prerequisites validated")

        # Discover CSV files
        print("\n[2/4] Discovering CSV files...")
        csv_files = discover_csv_files(RAW_DIR)
        print(f"  ✓ Found {len(csv_files)} CSV files")

        # Ensure DuckDB directory exists
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Connect to DuckDB and load data
        print(f"\n[3/4] Loading CSV files into DuckDB...")
        conn = duckdb.connect(str(DB_PATH))

        try:
            # Create schema
            create_schema_if_not_exists(conn, SCHEMA_NAME)

            # Load all CSV files
            results = load_all_csvs(conn, csv_files, SCHEMA_NAME)

            # Calculate elapsed time and print summary
            elapsed = time.time() - start_time
            print(f"\n[4/4] Loading complete!")
            print_summary(results, elapsed)
            print(f"\nDuckDB tables available in: {DB_PATH} ({SCHEMA_NAME} schema)")

            return 0

        finally:
            conn.close()

    except PrerequisiteError as e:
        print(f"ERROR: {e}")
        return 1

    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("  Run 'make raw-data-copy' first.")
        return 1

    except duckdb.Error as e:
        print(f"ERROR: DuckDB error: {e}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
