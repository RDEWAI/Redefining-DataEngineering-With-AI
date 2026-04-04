#!/usr/bin/env python3
"""Load library CSV data into DuckDB database.

This script loads the library_dataset_random.csv file into a DuckDB database
with the library schema. It creates the schema and table if they don't exist,
and validates the data during loading.

Usage:
    python scripts/load_library_csv_to_duckdb.py [--db-path PATH] [--csv-path PATH]
    python scripts/load_library_csv_to_duckdb.py --include-lending

Example:
    python scripts/load_library_csv_to_duckdb.py
    python scripts/load_library_csv_to_duckdb.py --db-path data/duckdb/library.db
    python scripts/load_library_csv_to_duckdb.py --include-lending  # Also load lending data
"""

import argparse
import sys
from pathlib import Path

import duckdb

# Default paths relative to chapter-2 directory
SCRIPT_DIR = Path(__file__).parent
CHAPTER_DIR = SCRIPT_DIR.parent
DEFAULT_CSV_PATH = CHAPTER_DIR / "data" / "raw" / "library" / "library_dataset_random.csv"
DEFAULT_LENDING_CSV_PATH = CHAPTER_DIR / "data" / "raw" / "library" / "lending_data.csv"
DEFAULT_REPLENISH_CSV_PATH = CHAPTER_DIR / "data" / "raw" / "library" / "replenish_data.csv"
DEFAULT_DB_PATH = CHAPTER_DIR / "data" / "duckdb" / "chapter2.db"


def create_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the library schema if it doesn't exist."""
    conn.execute("CREATE SCHEMA IF NOT EXISTS library")
    print("✓ Created schema 'library'")


def create_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the library.books table with all constraints."""
    # Drop existing tables if they exist (for fresh load)
    # Must drop dependent tables first due to foreign key constraints on books
    conn.execute("DROP TABLE IF EXISTS library.replenish_embeddings")
    conn.execute("DROP TABLE IF EXISTS library.replenish")
    conn.execute("DROP TABLE IF EXISTS library.lending_embeddings")
    conn.execute("DROP TABLE IF EXISTS library.lending")
    conn.execute("DROP TABLE IF EXISTS library.book_embeddings")
    # Also drop legacy sales tables if present (renamed to lending)
    conn.execute("DROP TABLE IF EXISTS library.sales_embeddings")
    conn.execute("DROP TABLE IF EXISTS library.sales")
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

    # Load CSV with column mapping (use resolved path to prevent injection)
    safe_path = str(csv_path.resolve())
    conn.execute(
        """
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
        FROM read_csv($1, header=true, auto_detect=true)
        """,
        [safe_path],
    )

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
# Lending data functions
# =============================================================================


def create_lending_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the library.lending table with all constraints."""
    # Drop existing table if it exists (for fresh load)
    conn.execute("DROP TABLE IF EXISTS library.lending")

    # Create table with constraints
    conn.execute("""
        CREATE TABLE library.lending (
            loan_id VARCHAR PRIMARY KEY,
            book_id VARCHAR NOT NULL REFERENCES library.books(book_id),
            loan_date DATE NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity >= 1),
            lending_fee DECIMAL(10,2) NOT NULL CHECK (lending_fee > 0),
            total_fees DECIMAL(10,2) NOT NULL,
            fee_waiver DECIMAL(5,2) NOT NULL DEFAULT 0 CHECK (fee_waiver >= 0 AND fee_waiver <= 100),
            payment_method VARCHAR NOT NULL CHECK (payment_method IN ('Credit Card', 'Debit Card', 'Cash', 'Digital Wallet')),
            patron_id VARCHAR NOT NULL,
            patron_segment VARCHAR NOT NULL CHECK (patron_segment IN ('Individual', 'Corporate', 'Educational', 'Government')),
            region VARCHAR NOT NULL CHECK (region IN ('Northeast', 'Southeast', 'Midwest', 'West', 'International')),
            channel VARCHAR NOT NULL CHECK (channel IN ('In-Store', 'Online', 'Phone Order', 'Partner'))
        )
    """)
    print("✓ Created table 'library.lending'")


def create_lending_indexes(conn: duckdb.DuckDBPyConnection) -> None:
    """Create indexes for common lending query patterns."""
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lending_book_id ON library.lending(book_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lending_date ON library.lending(loan_date)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_lending_segment ON library.lending(patron_segment)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lending_region ON library.lending(region)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lending_channel ON library.lending(channel)")
    print("✓ Created lending indexes")


def load_lending_csv(conn: duckdb.DuckDBPyConnection, csv_path: Path) -> int:
    """Load lending CSV data into the library.lending table.

    Args:
        conn: DuckDB connection
        csv_path: Path to the lending CSV file

    Returns:
        Number of records loaded

    Raises:
        FileNotFoundError: If CSV file doesn't exist
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Lending CSV file not found: {csv_path}")

    # Load CSV - column names match directly (use resolved path to prevent injection)
    safe_path = str(csv_path.resolve())
    conn.execute(
        """
        INSERT INTO library.lending
        SELECT
            loan_id,
            book_id,
            loan_date,
            quantity,
            lending_fee,
            total_fees,
            fee_waiver,
            payment_method,
            patron_id,
            patron_segment,
            region,
            channel
        FROM read_csv($1, header=true, auto_detect=true)
        """,
        [safe_path],
    )

    # Get record count
    result = conn.execute("SELECT COUNT(*) FROM library.lending").fetchone()
    count = result[0] if result else 0

    print(f"✓ Loaded {count} lending records from CSV")
    return count


def validate_lending_data(conn: duckdb.DuckDBPyConnection) -> bool:
    """Validate loaded lending data meets expected constraints.

    Returns:
        True if validation passes, False otherwise
    """
    errors = []

    # Check record count (should be > 0)
    result = conn.execute("SELECT COUNT(*) FROM library.lending").fetchone()
    count = result[0] if result else 0
    if count == 0:
        errors.append("No lending records found")

    # Check for duplicate loan IDs
    result = conn.execute("""
        SELECT COUNT(*) - COUNT(DISTINCT loan_id) as duplicates
        FROM library.lending
    """).fetchone()
    if result and result[0] > 0:
        errors.append(f"Found {result[0]} duplicate loan IDs")

    # Check foreign key integrity (all book_ids exist)
    result = conn.execute("""
        SELECT COUNT(*) FROM library.lending l
        WHERE NOT EXISTS (SELECT 1 FROM library.books b WHERE b.book_id = l.book_id)
    """).fetchone()
    if result and result[0] > 0:
        errors.append(f"Found {result[0]} loans with invalid book_id references")

    # Check patron segments
    result = conn.execute("""
        SELECT DISTINCT patron_segment FROM library.lending
        WHERE patron_segment NOT IN ('Individual', 'Corporate', 'Educational', 'Government')
    """).fetchall()
    if result:
        invalid = [row[0] for row in result]
        errors.append(f"Invalid patron segments: {invalid}")

    # Check regions
    result = conn.execute("""
        SELECT DISTINCT region FROM library.lending
        WHERE region NOT IN ('Northeast', 'Southeast', 'Midwest', 'West', 'International')
    """).fetchall()
    if result:
        invalid = [row[0] for row in result]
        errors.append(f"Invalid regions: {invalid}")

    # Check channels
    result = conn.execute("""
        SELECT DISTINCT channel FROM library.lending
        WHERE channel NOT IN ('In-Store', 'Online', 'Phone Order', 'Partner')
    """).fetchall()
    if result:
        invalid = [row[0] for row in result]
        errors.append(f"Invalid channels: {invalid}")

    if errors:
        print("✗ Lending validation failed:")
        for error in errors:
            print(f"  - {error}")
        return False

    print("✓ Lending data validation passed")
    return True


def print_lending_summary(conn: duckdb.DuckDBPyConnection) -> None:
    """Print summary statistics about the loaded lending data."""
    print("\n📊 Lending Data Summary:")

    # Total loans
    result = conn.execute("""
        SELECT
            COUNT(*) as total_loans,
            SUM(total_fees) as total_fees,
            SUM(quantity) as total_units,
            COUNT(DISTINCT patron_id) as unique_patrons
        FROM library.lending
    """).fetchone()
    print(f"  Total loans: {result[0]}")
    print(f"  Total fees: ${result[1]:,.2f}")
    print(f"  Total copies lent: {result[2]}")
    print(f"  Unique patrons: {result[3]}")

    # By segment
    result = conn.execute("""
        SELECT patron_segment, COUNT(*) as count, SUM(total_fees) as fees
        FROM library.lending
        GROUP BY patron_segment
        ORDER BY fees DESC
    """).fetchall()
    print("  By patron segment:")
    for segment, count, fees in result:
        print(f"    - {segment}: {count} loans (${fees:,.2f})")

    # By region
    result = conn.execute("""
        SELECT region, COUNT(*) as count
        FROM library.lending
        GROUP BY region
        ORDER BY count DESC
    """).fetchall()
    print("  By region:")
    for region, count in result:
        print(f"    - {region}: {count}")

    # By channel
    result = conn.execute("""
        SELECT channel, COUNT(*) as count
        FROM library.lending
        GROUP BY channel
        ORDER BY count DESC
    """).fetchall()
    print("  By channel:")
    for channel, count in result:
        print(f"    - {channel}: {count}")


# =============================================================================
# Replenish data functions
# =============================================================================


def create_replenish_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the library.replenish table with all constraints."""
    conn.execute("DROP TABLE IF EXISTS library.replenish")

    conn.execute("""
        CREATE TABLE library.replenish (
            replenish_id VARCHAR PRIMARY KEY,
            book_id VARCHAR NOT NULL REFERENCES library.books(book_id),
            replenish_date DATE NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity >= 1),
            unit_cost DECIMAL(10,2) NOT NULL CHECK (unit_cost >= 0),
            total_cost DECIMAL(10,2) NOT NULL CHECK (total_cost >= 0),
            discount_pct DECIMAL(5,2) NOT NULL DEFAULT 0 CHECK (discount_pct >= 0 AND discount_pct <= 100),
            supplier VARCHAR NOT NULL CHECK (supplier IN ('Ingram', 'Baker & Taylor', 'Brodart', 'Direct Publisher', 'Amazon Business')),
            replenish_type VARCHAR NOT NULL CHECK (replenish_type IN ('New Acquisition', 'Replacement', 'Restock', 'Donation', 'Return Processing')),
            condition VARCHAR NOT NULL CHECK (condition IN ('New', 'Refurbished', 'Used - Good', 'Used - Fair')),
            funding_source VARCHAR NOT NULL CHECK (funding_source IN ('Operating Budget', 'Grant', 'Donation Fund', 'Special Collection', 'Emergency Fund')),
            priority VARCHAR NOT NULL CHECK (priority IN ('Urgent', 'High', 'Normal', 'Low'))
        )
    """)
    print("✓ Created table 'library.replenish'")


def create_replenish_indexes(conn: duckdb.DuckDBPyConnection) -> None:
    """Create indexes for common replenish query patterns."""
    conn.execute("CREATE INDEX IF NOT EXISTS idx_replenish_book_id ON library.replenish(book_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_replenish_date ON library.replenish(replenish_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_replenish_supplier ON library.replenish(supplier)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_replenish_type ON library.replenish(replenish_type)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_replenish_priority ON library.replenish(priority)"
    )
    print("✓ Created replenish indexes")


def load_replenish_csv(conn: duckdb.DuckDBPyConnection, csv_path: Path) -> int:
    """Load replenish CSV data into the library.replenish table.

    Args:
        conn: DuckDB connection
        csv_path: Path to the replenish CSV file

    Returns:
        Number of records loaded

    Raises:
        FileNotFoundError: If CSV file doesn't exist
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Replenish CSV file not found: {csv_path}")

    # Use resolved path to prevent injection
    safe_path = str(csv_path.resolve())
    conn.execute(
        """
        INSERT INTO library.replenish
        SELECT
            replenish_id,
            book_id,
            replenish_date,
            quantity,
            unit_cost,
            total_cost,
            discount_pct,
            supplier,
            replenish_type,
            condition,
            funding_source,
            priority
        FROM read_csv($1, header=true, auto_detect=true)
        """,
        [safe_path],
    )

    result = conn.execute("SELECT COUNT(*) FROM library.replenish").fetchone()
    count = result[0] if result else 0

    print(f"✓ Loaded {count} replenish records from CSV")
    return count


def validate_replenish_data(conn: duckdb.DuckDBPyConnection) -> bool:
    """Validate loaded replenish data meets expected constraints.

    Returns:
        True if validation passes, False otherwise
    """
    errors = []

    # Check record count (should be > 0)
    result = conn.execute("SELECT COUNT(*) FROM library.replenish").fetchone()
    count = result[0] if result else 0
    if count == 0:
        errors.append("No replenish records found")

    # Check for duplicate replenish IDs
    result = conn.execute("""
        SELECT COUNT(*) - COUNT(DISTINCT replenish_id) as duplicates
        FROM library.replenish
    """).fetchone()
    if result and result[0] > 0:
        errors.append(f"Found {result[0]} duplicate replenish IDs")

    # Check foreign key integrity (all book_ids exist)
    result = conn.execute("""
        SELECT COUNT(*) FROM library.replenish r
        WHERE NOT EXISTS (SELECT 1 FROM library.books b WHERE b.book_id = r.book_id)
    """).fetchone()
    if result and result[0] > 0:
        errors.append(f"Found {result[0]} replenish records with invalid book_id references")

    # Check suppliers
    result = conn.execute("""
        SELECT DISTINCT supplier FROM library.replenish
        WHERE supplier NOT IN ('Ingram', 'Baker & Taylor', 'Brodart', 'Direct Publisher', 'Amazon Business')
    """).fetchall()
    if result:
        invalid = [row[0] for row in result]
        errors.append(f"Invalid suppliers: {invalid}")

    # Check replenish types
    result = conn.execute("""
        SELECT DISTINCT replenish_type FROM library.replenish
        WHERE replenish_type NOT IN ('New Acquisition', 'Replacement', 'Restock', 'Donation', 'Return Processing')
    """).fetchall()
    if result:
        invalid = [row[0] for row in result]
        errors.append(f"Invalid replenish types: {invalid}")

    # Check conditions
    result = conn.execute("""
        SELECT DISTINCT condition FROM library.replenish
        WHERE condition NOT IN ('New', 'Refurbished', 'Used - Good', 'Used - Fair')
    """).fetchall()
    if result:
        invalid = [row[0] for row in result]
        errors.append(f"Invalid conditions: {invalid}")

    if errors:
        print("✗ Replenish validation failed:")
        for error in errors:
            print(f"  - {error}")
        return False

    print("✓ Replenish data validation passed")
    return True


def print_replenish_summary(conn: duckdb.DuckDBPyConnection) -> None:
    """Print summary statistics about the loaded replenish data."""
    print("\n📊 Replenish Data Summary:")

    result = conn.execute("""
        SELECT
            COUNT(*) as total_records,
            SUM(total_cost) as total_cost,
            SUM(quantity) as total_units,
            COUNT(DISTINCT book_id) as unique_books
        FROM library.replenish
    """).fetchone()
    if result is None:
        print("  No replenish data found")
        return
    print(f"  Total records: {result[0]}")
    print(f"  Total cost: ${result[1]:,.2f}")
    print(f"  Total copies added: {result[2]}")
    print(f"  Unique books replenished: {result[3]}")

    # By supplier
    result = conn.execute("""
        SELECT supplier, COUNT(*) as count, SUM(total_cost) as cost
        FROM library.replenish
        GROUP BY supplier
        ORDER BY cost DESC
    """).fetchall()
    print("  By supplier:")
    for supplier, count, cost in result:
        print(f"    - {supplier}: {count} records (${cost:,.2f})")

    # By type
    result = conn.execute("""
        SELECT replenish_type, COUNT(*) as count
        FROM library.replenish
        GROUP BY replenish_type
        ORDER BY count DESC
    """).fetchall()
    print("  By type:")
    for rtype, count in result:
        print(f"    - {rtype}: {count}")


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
        "--lending-csv-path",
        type=Path,
        default=DEFAULT_LENDING_CSV_PATH,
        help=f"Path to lending CSV file (default: {DEFAULT_LENDING_CSV_PATH})",
    )
    parser.add_argument(
        "--include-lending",
        action="store_true",
        help="Also load lending data into the database",
    )
    parser.add_argument(
        "--replenish-csv-path",
        type=Path,
        default=DEFAULT_REPLENISH_CSV_PATH,
        help=f"Path to replenish CSV file (default: {DEFAULT_REPLENISH_CSV_PATH})",
    )
    parser.add_argument(
        "--include-replenish",
        action="store_true",
        help="Also load replenish data into the database",
    )
    args = parser.parse_args()

    print(f"Loading library data from: {args.csv_path}")
    print(f"Into database: {args.db_path}")
    if args.include_lending:
        print(f"Also loading lending from: {args.lending_csv_path}")
    if args.include_replenish:
        print(f"Also loading replenish from: {args.replenish_csv_path}")
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

        # Load lending data if requested
        lending_count = 0
        if args.include_lending:
            print("\n" + "=" * 50)
            print("Loading lending data...")
            print("=" * 50)

            # Create lending table (after books so FK works)
            create_lending_table(conn)

            # Load lending CSV
            lending_count = load_lending_csv(conn, args.lending_csv_path)

            # Create lending indexes
            create_lending_indexes(conn)

            # Validate lending data
            if not validate_lending_data(conn):
                print("\n⚠️  Lending data loaded but validation failed.")
                conn.close()
                return 1

            # Print lending summary
            print_lending_summary(conn)

        # Load replenish data if requested
        replenish_count = 0
        if args.include_replenish:
            print("\n" + "=" * 50)
            print("Loading replenish data...")
            print("=" * 50)

            # Create replenish table (after books so FK works)
            create_replenish_table(conn)

            # Load replenish CSV
            replenish_count = load_replenish_csv(conn, args.replenish_csv_path)

            # Create replenish indexes
            create_replenish_indexes(conn)

            # Validate replenish data
            if not validate_replenish_data(conn):
                print("\n⚠️  Replenish data loaded but validation failed.")
                conn.close()
                return 1

            # Print replenish summary
            print_replenish_summary(conn)

        # Close connection
        conn.close()

        print("\n✅ Data loading complete!")
        print(f"   Database: {args.db_path}")
        print(f"   Book records: {record_count}")
        if args.include_lending:
            print(f"   Lending records: {lending_count}")
        if args.include_replenish:
            print(f"   Replenish records: {replenish_count}")

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
