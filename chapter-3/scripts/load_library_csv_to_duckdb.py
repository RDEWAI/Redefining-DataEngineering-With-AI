#!/usr/bin/env python3
"""Load library CSV data into DuckDB database.

This script loads the library_dataset_random.csv file into a DuckDB database
with the library schema. It creates the schema and table if they don't exist,
and validates the data during loading.

Usage:
    python scripts/load_library_csv_to_duckdb.py [--db-path PATH] [--csv-path PATH]

Example:
    python scripts/load_library_csv_to_duckdb.py
    python scripts/load_library_csv_to_duckdb.py --db-path data/duckdb/library.db
"""

import argparse
import sys
from pathlib import Path

import duckdb

# Default paths relative to chapter-3 directory
SCRIPT_DIR = Path(__file__).parent
CHAPTER_DIR = SCRIPT_DIR.parent
DEFAULT_CSV_PATH = CHAPTER_DIR / "data" / "raw" / "library" / "library_dataset_random.csv"
DEFAULT_DB_PATH = CHAPTER_DIR / "data" / "duckdb" / "chapter3.db"


def create_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the library schema if it doesn't exist."""
    conn.execute("CREATE SCHEMA IF NOT EXISTS library")
    print("✓ Created schema 'library'")


def create_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the library.books table with all constraints."""
    # Drop existing table if it exists (for fresh load)
    conn.execute("DROP TABLE IF EXISTS library.books")

    # Create table with constraints
    conn.execute("""
        CREATE TABLE library.books (
            book_id VARCHAR PRIMARY KEY,
            title VARCHAR NOT NULL,
            author VARCHAR NOT NULL,
            category VARCHAR NOT NULL CHECK (category IN ('Programming', 'History', 'Science', 'Fiction', 'Thriller')),
            cabinet INTEGER NOT NULL CHECK (cabinet >= 1),
            rack INTEGER NOT NULL CHECK (rack >= 1),
            row INTEGER NOT NULL CHECK (row >= 1),
            signal_strength FLOAT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            status VARCHAR NOT NULL CHECK (status IN ('Present', 'Missing', 'Checked Out'))
        )
    """)
    print("✓ Created table 'library.books'")


def create_indexes(conn: duckdb.DuckDBPyConnection) -> None:
    """Create indexes for common query patterns."""
    conn.execute("CREATE INDEX IF NOT EXISTS idx_books_category ON library.books(category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_books_status ON library.books(status)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_books_location ON library.books(cabinet, rack, row)"
    )
    # Note: DuckDB doesn't support partial indexes, so we use a full index on signal_strength
    conn.execute("CREATE INDEX IF NOT EXISTS idx_books_signal ON library.books(signal_strength)")
    print("✓ Created indexes")


def load_csv(conn: duckdb.DuckDBPyConnection, csv_path: Path) -> int:
    """Load CSV data into the library.books table.

    Args:
        conn: DuckDB connection
        csv_path: Path to the CSV file

    Returns:
        Number of records loaded

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV data is invalid
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    # Load CSV with column mapping
    conn.execute(f"""
        INSERT INTO library.books
        SELECT
            Book_ID as book_id,
            Title as title,
            Author as author,
            Category as category,
            Cabinet as cabinet,
            Rack as rack,
            Row as row,
            Signal_Strength as signal_strength,
            Timestamp as timestamp,
            Status as status
        FROM read_csv('{csv_path}', header=true, auto_detect=true)
    """)

    # Get record count
    result = conn.execute("SELECT COUNT(*) FROM library.books").fetchone()
    count = result[0] if result else 0

    print(f"✓ Loaded {count} records from CSV")
    return count


def validate_data(conn: duckdb.DuckDBPyConnection) -> bool:
    """Validate loaded data meets expected constraints.

    Returns:
        True if validation passes, False otherwise
    """
    errors = []

    # Check record count
    result = conn.execute("SELECT COUNT(*) FROM library.books").fetchone()
    count = result[0] if result else 0
    if count != 200:
        errors.append(f"Expected 200 records, found {count}")

    # Check for duplicate book IDs
    result = conn.execute("""
        SELECT COUNT(*) - COUNT(DISTINCT book_id) as duplicates
        FROM library.books
    """).fetchone()
    if result and result[0] > 0:
        errors.append(f"Found {result[0]} duplicate book IDs")

    # Check categories
    result = conn.execute("""
        SELECT DISTINCT category FROM library.books
        WHERE category NOT IN ('Programming', 'History', 'Science', 'Fiction', 'Thriller')
    """).fetchall()
    if result:
        invalid_cats = [row[0] for row in result]
        errors.append(f"Invalid categories found: {invalid_cats}")

    # Check statuses
    result = conn.execute("""
        SELECT DISTINCT status FROM library.books
        WHERE status NOT IN ('Present', 'Missing', 'Checked Out')
    """).fetchall()
    if result:
        invalid_stats = [row[0] for row in result]
        errors.append(f"Invalid statuses found: {invalid_stats}")

    # Check for NULL values in required fields
    for field in ["book_id", "title", "author", "category", "status"]:
        result = conn.execute(
            f"SELECT COUNT(*) FROM library.books WHERE {field} IS NULL"
        ).fetchone()
        if result and result[0] > 0:
            errors.append(f"Found {result[0]} NULL values in {field}")

    if errors:
        print("✗ Validation failed:")
        for error in errors:
            print(f"  - {error}")
        return False

    print("✓ Data validation passed")
    return True


def print_summary(conn: duckdb.DuckDBPyConnection) -> None:
    """Print summary statistics about the loaded data."""
    print("\n📊 Data Summary:")

    # Total books
    result = conn.execute("SELECT COUNT(*) FROM library.books").fetchone()
    print(f"  Total books: {result[0]}")

    # By status
    result = conn.execute("""
        SELECT status, COUNT(*) as count
        FROM library.books
        GROUP BY status
        ORDER BY status
    """).fetchall()
    print("  By status:")
    for status, count in result:
        print(f"    - {status}: {count}")

    # By category
    result = conn.execute("""
        SELECT category, COUNT(*) as count
        FROM library.books
        GROUP BY category
        ORDER BY category
    """).fetchall()
    print("  By category:")
    for category, count in result:
        print(f"    - {category}: {count}")

    # Weak signal count
    result = conn.execute("""
        SELECT COUNT(*) FROM library.books
        WHERE signal_strength < -55
    """).fetchone()
    print(f"  Books with weak signal: {result[0]}")


def main() -> int:
    """Main entry point for the script.

    Returns:
        0 on success, 1 on error
    """
    parser = argparse.ArgumentParser(description="Load library CSV data into DuckDB database")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Path to DuckDB database file (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help=f"Path to CSV file (default: {DEFAULT_CSV_PATH})",
    )
    args = parser.parse_args()

    print(f"Loading library data from: {args.csv_path}")
    print(f"Into database: {args.db_path}")
    print()

    try:
        # Ensure database directory exists
        args.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Connect to database
        conn = duckdb.connect(str(args.db_path))

        # Create schema and table
        create_schema(conn)
        create_table(conn)

        # Load CSV data
        record_count = load_csv(conn, args.csv_path)

        # Create indexes
        create_indexes(conn)

        # Validate data
        if not validate_data(conn):
            print("\n⚠️  Data loaded but validation failed. Please check the CSV file.")
            conn.close()
            return 1

        # Print summary
        print_summary(conn)

        # Close connection
        conn.close()

        print("\n✅ Data loading complete!")
        print(f"   Database: {args.db_path}")
        print(f"   Records: {record_count}")

        return 0

    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print("   Make sure the CSV file exists at the specified path.")
        return 1

    except duckdb.Error as e:
        print(f"\n❌ Database error: {e}")
        return 1

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
