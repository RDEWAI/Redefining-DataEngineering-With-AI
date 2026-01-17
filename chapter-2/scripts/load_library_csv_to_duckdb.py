#!/usr/bin/env python3
"""Load library CSV data into DuckDB database.

This script loads the library_dataset_random.csv file into a DuckDB database
with the library schema. It creates the schema and table if they don't exist,
and validates the data during loading.

Usage:
    python scripts/load_library_csv_to_duckdb.py [--db-path PATH] [--csv-path PATH]
    python scripts/load_library_csv_to_duckdb.py --include-sales

Example:
    python scripts/load_library_csv_to_duckdb.py
    python scripts/load_library_csv_to_duckdb.py --db-path data/duckdb/library.db
    python scripts/load_library_csv_to_duckdb.py --include-sales  # Also load sales data
"""

import argparse
import sys
from pathlib import Path

import duckdb

# Default paths relative to chapter-2 directory
SCRIPT_DIR = Path(__file__).parent
CHAPTER_DIR = SCRIPT_DIR.parent
DEFAULT_CSV_PATH = CHAPTER_DIR / "data" / "raw" / "library" / "library_dataset_random.csv"
DEFAULT_SALES_CSV_PATH = CHAPTER_DIR / "data" / "raw" / "library" / "sales_data.csv"
DEFAULT_DB_PATH = CHAPTER_DIR / "data" / "duckdb" / "chapter2.db"


def create_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the library schema if it doesn't exist."""
    conn.execute("CREATE SCHEMA IF NOT EXISTS library")
    print("✓ Created schema 'library'")


def create_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the library.books table with all constraints."""
    # Drop existing tables if they exist (for fresh load)
    # Must drop sales tables first due to foreign key constraint on books
    conn.execute("DROP TABLE IF EXISTS library.sales_embeddings")
    conn.execute("DROP TABLE IF EXISTS library.sales")
    conn.execute("DROP TABLE IF EXISTS library.book_embeddings")
    conn.execute("DROP TABLE IF EXISTS library.books")

    # Create table with constraints
    conn.execute("""
        CREATE TABLE library.books (
            book_id VARCHAR PRIMARY KEY,
            title VARCHAR NOT NULL,
            author VARCHAR NOT NULL,
            description VARCHAR NOT NULL,
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
            Description as description,
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
    for field in ["book_id", "title", "author", "description", "category", "status"]:
        result = conn.execute(
            f"SELECT COUNT(*) FROM library.books WHERE {field} IS NULL"
        ).fetchone()
        if result and result[0] > 0:
            errors.append(f"Found {result[0]} NULL values in {field}")

    # Check description length constraints (50-300 characters)
    result = conn.execute("""
        SELECT COUNT(*) FROM library.books
        WHERE LENGTH(description) < 50 OR LENGTH(description) > 500
    """).fetchone()
    if result and result[0] > 0:
        errors.append(
            f"Found {result[0]} descriptions outside length constraints (50-500 characters)"
        )

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


# =============================================================================
# Sales data functions
# =============================================================================


def create_sales_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the library.sales table with all constraints."""
    # Drop existing table if it exists (for fresh load)
    conn.execute("DROP TABLE IF EXISTS library.sales")

    # Create table with constraints
    conn.execute("""
        CREATE TABLE library.sales (
            sale_id VARCHAR PRIMARY KEY,
            book_id VARCHAR NOT NULL REFERENCES library.books(book_id),
            sale_date DATE NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity >= 1),
            unit_price DECIMAL(10,2) NOT NULL CHECK (unit_price > 0),
            total_amount DECIMAL(10,2) NOT NULL,
            discount DECIMAL(5,2) NOT NULL DEFAULT 0 CHECK (discount >= 0 AND discount <= 100),
            payment_method VARCHAR NOT NULL CHECK (payment_method IN ('Credit Card', 'Debit Card', 'Cash', 'Digital Wallet')),
            customer_id VARCHAR NOT NULL,
            customer_segment VARCHAR NOT NULL CHECK (customer_segment IN ('Individual', 'Corporate', 'Educational', 'Government')),
            region VARCHAR NOT NULL CHECK (region IN ('Northeast', 'Southeast', 'Midwest', 'West', 'International')),
            channel VARCHAR NOT NULL CHECK (channel IN ('In-Store', 'Online', 'Phone Order', 'Partner'))
        )
    """)
    print("✓ Created table 'library.sales'")


def create_sales_indexes(conn: duckdb.DuckDBPyConnection) -> None:
    """Create indexes for common sales query patterns."""
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_book_id ON library.sales(book_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON library.sales(sale_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_segment ON library.sales(customer_segment)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_region ON library.sales(region)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_channel ON library.sales(channel)")
    print("✓ Created sales indexes")


def load_sales_csv(conn: duckdb.DuckDBPyConnection, csv_path: Path) -> int:
    """Load sales CSV data into the library.sales table.

    Args:
        conn: DuckDB connection
        csv_path: Path to the sales CSV file

    Returns:
        Number of records loaded

    Raises:
        FileNotFoundError: If CSV file doesn't exist
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Sales CSV file not found: {csv_path}")

    # Load CSV - column names match directly
    conn.execute(f"""
        INSERT INTO library.sales
        SELECT
            sale_id,
            book_id,
            sale_date,
            quantity,
            unit_price,
            total_amount,
            discount,
            payment_method,
            customer_id,
            customer_segment,
            region,
            channel
        FROM read_csv('{csv_path}', header=true, auto_detect=true)
    """)

    # Get record count
    result = conn.execute("SELECT COUNT(*) FROM library.sales").fetchone()
    count = result[0] if result else 0

    print(f"✓ Loaded {count} sales records from CSV")
    return count


def validate_sales_data(conn: duckdb.DuckDBPyConnection) -> bool:
    """Validate loaded sales data meets expected constraints.

    Returns:
        True if validation passes, False otherwise
    """
    errors = []

    # Check record count (should be > 0)
    result = conn.execute("SELECT COUNT(*) FROM library.sales").fetchone()
    count = result[0] if result else 0
    if count == 0:
        errors.append("No sales records found")

    # Check for duplicate sale IDs
    result = conn.execute("""
        SELECT COUNT(*) - COUNT(DISTINCT sale_id) as duplicates
        FROM library.sales
    """).fetchone()
    if result and result[0] > 0:
        errors.append(f"Found {result[0]} duplicate sale IDs")

    # Check foreign key integrity (all book_ids exist)
    result = conn.execute("""
        SELECT COUNT(*) FROM library.sales s
        WHERE NOT EXISTS (SELECT 1 FROM library.books b WHERE b.book_id = s.book_id)
    """).fetchone()
    if result and result[0] > 0:
        errors.append(f"Found {result[0]} sales with invalid book_id references")

    # Check customer segments
    result = conn.execute("""
        SELECT DISTINCT customer_segment FROM library.sales
        WHERE customer_segment NOT IN ('Individual', 'Corporate', 'Educational', 'Government')
    """).fetchall()
    if result:
        invalid = [row[0] for row in result]
        errors.append(f"Invalid customer segments: {invalid}")

    # Check regions
    result = conn.execute("""
        SELECT DISTINCT region FROM library.sales
        WHERE region NOT IN ('Northeast', 'Southeast', 'Midwest', 'West', 'International')
    """).fetchall()
    if result:
        invalid = [row[0] for row in result]
        errors.append(f"Invalid regions: {invalid}")

    # Check channels
    result = conn.execute("""
        SELECT DISTINCT channel FROM library.sales
        WHERE channel NOT IN ('In-Store', 'Online', 'Phone Order', 'Partner')
    """).fetchall()
    if result:
        invalid = [row[0] for row in result]
        errors.append(f"Invalid channels: {invalid}")

    if errors:
        print("✗ Sales validation failed:")
        for error in errors:
            print(f"  - {error}")
        return False

    print("✓ Sales data validation passed")
    return True


def print_sales_summary(conn: duckdb.DuckDBPyConnection) -> None:
    """Print summary statistics about the loaded sales data."""
    print("\n📊 Sales Data Summary:")

    # Total sales
    result = conn.execute("""
        SELECT
            COUNT(*) as total_sales,
            SUM(total_amount) as total_revenue,
            SUM(quantity) as total_units,
            COUNT(DISTINCT customer_id) as unique_customers
        FROM library.sales
    """).fetchone()
    print(f"  Total sales: {result[0]}")
    print(f"  Total revenue: ${result[1]:,.2f}")
    print(f"  Total units sold: {result[2]}")
    print(f"  Unique customers: {result[3]}")

    # By segment
    result = conn.execute("""
        SELECT customer_segment, COUNT(*) as count, SUM(total_amount) as revenue
        FROM library.sales
        GROUP BY customer_segment
        ORDER BY revenue DESC
    """).fetchall()
    print("  By customer segment:")
    for segment, count, revenue in result:
        print(f"    - {segment}: {count} sales (${revenue:,.2f})")

    # By region
    result = conn.execute("""
        SELECT region, COUNT(*) as count
        FROM library.sales
        GROUP BY region
        ORDER BY count DESC
    """).fetchall()
    print("  By region:")
    for region, count in result:
        print(f"    - {region}: {count}")

    # By channel
    result = conn.execute("""
        SELECT channel, COUNT(*) as count
        FROM library.sales
        GROUP BY channel
        ORDER BY count DESC
    """).fetchall()
    print("  By channel:")
    for channel, count in result:
        print(f"    - {channel}: {count}")


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
    parser.add_argument(
        "--sales-csv-path",
        type=Path,
        default=DEFAULT_SALES_CSV_PATH,
        help=f"Path to sales CSV file (default: {DEFAULT_SALES_CSV_PATH})",
    )
    parser.add_argument(
        "--include-sales",
        action="store_true",
        help="Also load sales data into the database",
    )
    args = parser.parse_args()

    print(f"Loading library data from: {args.csv_path}")
    print(f"Into database: {args.db_path}")
    if args.include_sales:
        print(f"Also loading sales from: {args.sales_csv_path}")
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

        # Load sales data if requested
        sales_count = 0
        if args.include_sales:
            print("\n" + "=" * 50)
            print("Loading sales data...")
            print("=" * 50)

            # Create sales table (after books so FK works)
            create_sales_table(conn)

            # Load sales CSV
            sales_count = load_sales_csv(conn, args.sales_csv_path)

            # Create sales indexes
            create_sales_indexes(conn)

            # Validate sales data
            if not validate_sales_data(conn):
                print("\n⚠️  Sales data loaded but validation failed.")
                conn.close()
                return 1

            # Print sales summary
            print_sales_summary(conn)

        # Close connection
        conn.close()

        print("\n✅ Data loading complete!")
        print(f"   Database: {args.db_path}")
        print(f"   Book records: {record_count}")
        if args.include_sales:
            print(f"   Sales records: {sales_count}")

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
