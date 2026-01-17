"""Integration tests for data loading.

End-to-end tests for CSV loading into DuckDB.
"""

from pathlib import Path

import duckdb
import pytest

from src.agentic.library.domain import BookStatus, Category
from src.agentic.library.repository import BookRepository

# Path to the actual library CSV file
LIBRARY_CSV_PATH = (
    Path(__file__).parent.parent.parent / "data" / "raw" / "library" / "library_dataset_random.csv"
)


@pytest.fixture(scope="module")
def loaded_db(tmp_path_factory) -> duckdb.DuckDBPyConnection:
    """Load CSV data into a temporary DuckDB database."""
    if not LIBRARY_CSV_PATH.exists():
        pytest.skip(f"Library CSV not found at {LIBRARY_CSV_PATH}")

    # Create temporary database (use chapter2.db name to avoid catalog confusion)
    db_path = tmp_path_factory.mktemp("data") / "chapter2.db"
    conn = duckdb.connect(str(db_path))

    # Create schema and table
    conn.execute("CREATE SCHEMA IF NOT EXISTS library")
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

    # Load CSV data
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
        FROM read_csv('{LIBRARY_CSV_PATH}', header=true)
    """)

    return conn


@pytest.fixture
def repository(loaded_db: duckdb.DuckDBPyConnection) -> BookRepository:
    """Create a BookRepository with loaded database."""
    return BookRepository(connection=loaded_db)


class TestDataLoadVerification:
    """Tests to verify CSV data loaded correctly."""

    def test_record_count(self, loaded_db: duckdb.DuckDBPyConnection) -> None:
        """Verify 200 records loaded from CSV."""
        result = loaded_db.execute("SELECT COUNT(*) FROM library.books").fetchone()
        assert result is not None
        assert result[0] == 200, f"Expected 200 records, got {result[0]}"

    def test_all_categories_present(self, loaded_db: duckdb.DuckDBPyConnection) -> None:
        """Verify all expected categories are in the data."""
        result = loaded_db.execute(
            "SELECT DISTINCT category FROM library.books ORDER BY category"
        ).fetchall()
        categories = [row[0] for row in result]

        expected_categories = ["Fiction", "History", "Programming", "Science", "Thriller"]
        assert sorted(categories) == expected_categories

    def test_all_statuses_present(self, loaded_db: duckdb.DuckDBPyConnection) -> None:
        """Verify all expected statuses are in the data."""
        result = loaded_db.execute(
            "SELECT DISTINCT status FROM library.books ORDER BY status"
        ).fetchall()
        statuses = [row[0] for row in result]

        expected_statuses = ["Checked Out", "Missing", "Present"]
        assert sorted(statuses) == expected_statuses

    def test_book_ids_unique(self, loaded_db: duckdb.DuckDBPyConnection) -> None:
        """Verify all book IDs are unique."""
        result = loaded_db.execute("""
            SELECT COUNT(*) as total, COUNT(DISTINCT book_id) as unique_count
            FROM library.books
        """).fetchone()

        assert result is not None
        assert result[0] == result[1], "Book IDs are not unique"

    def test_book_id_format(self, loaded_db: duckdb.DuckDBPyConnection) -> None:
        """Verify book IDs follow expected format (B followed by digits)."""
        result = loaded_db.execute("""
            SELECT COUNT(*) FROM library.books
            WHERE book_id NOT SIMILAR TO 'B[0-9]+'
        """).fetchone()

        assert result is not None
        assert result[0] == 0, "Some book IDs don't match expected format"

    def test_signal_strength_range(self, loaded_db: duckdb.DuckDBPyConnection) -> None:
        """Verify signal strength values are in expected range."""
        result = loaded_db.execute("""
            SELECT MIN(signal_strength), MAX(signal_strength) FROM library.books
        """).fetchone()

        assert result is not None
        min_signal, max_signal = result
        # RFID signals typically range from -30 to -90 dBm
        assert min_signal >= -100, f"Signal too weak: {min_signal}"
        assert max_signal <= 0, f"Signal too strong: {max_signal}"

    def test_positive_locations(self, loaded_db: duckdb.DuckDBPyConnection) -> None:
        """Verify all location values are positive."""
        result = loaded_db.execute("""
            SELECT COUNT(*) FROM library.books
            WHERE cabinet < 1 OR rack < 1 OR row < 1
        """).fetchone()

        assert result is not None
        assert result[0] == 0, "Some location values are not positive"


class TestRepositoryWithRealData:
    """Tests for BookRepository using real CSV data."""

    def test_search_books(self, repository: BookRepository) -> None:
        """Test searching books returns results."""
        results = repository.search_books(query="the")
        assert len(results) > 0

    def test_get_existing_book(self, repository: BookRepository) -> None:
        """Test getting an existing book."""
        book = repository.get_book_by_id("B001")
        assert book is not None
        assert book.book_id == "B001"

    def test_list_by_category(self, repository: BookRepository) -> None:
        """Test listing books by category."""
        for category in Category:
            results = repository.list_by_category(category)
            assert len(results) >= 0
            for book in results:
                assert book.category == category

    def test_list_by_status(self, repository: BookRepository) -> None:
        """Test listing books by status."""
        for status in BookStatus:
            results = repository.list_by_status(status)
            assert len(results) >= 0
            for book in results:
                assert book.status == status

    def test_get_library_stats(self, repository: BookRepository) -> None:
        """Test getting library statistics."""
        stats = repository.get_library_stats()

        assert stats["total_books"] == 200
        assert sum(stats["by_category"].values()) == 200
        assert sum(stats["by_status"].values()) == 200

    def test_get_weak_signal_books(self, repository: BookRepository) -> None:
        """Test finding books with weak signal."""
        results = repository.get_weak_signal_books()
        # All returned books should have weak signal
        for book in results:
            assert book.has_weak_signal

    def test_find_books_in_cabinet(self, repository: BookRepository) -> None:
        """Test finding books in a cabinet."""
        # Get any valid cabinet number from the data
        results = repository.find_books_in_cabinet(cabinet=1)
        for book in results:
            assert book.location.cabinet == 1


class TestDataIntegrity:
    """Tests for data integrity and constraints."""

    def test_no_null_required_fields(self, loaded_db: duckdb.DuckDBPyConnection) -> None:
        """Verify no NULL values in required fields."""
        fields = [
            "book_id",
            "title",
            "author",
            "description",
            "category",
            "cabinet",
            "rack",
            "row",
            "signal_strength",
            "timestamp",
            "status",
        ]

        for field in fields:
            result = loaded_db.execute(
                f"SELECT COUNT(*) FROM library.books WHERE {field} IS NULL"
            ).fetchone()
            assert result is not None
            assert result[0] == 0, f"Found NULL values in {field}"

    def test_no_empty_strings(self, loaded_db: duckdb.DuckDBPyConnection) -> None:
        """Verify no empty strings in text fields."""
        text_fields = ["book_id", "title", "author", "category", "status"]

        for field in text_fields:
            result = loaded_db.execute(
                f"SELECT COUNT(*) FROM library.books WHERE TRIM({field}) = ''"
            ).fetchone()
            assert result is not None
            assert result[0] == 0, f"Found empty strings in {field}"
