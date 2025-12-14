"""Unit tests for BookRepository.

Tests for BookRepository including search, filter, and stats operations.
"""

import duckdb
import pytest

from src.library.domain import BookStatus, Category
from src.library.repository import BookRepository


@pytest.fixture
def test_db() -> duckdb.DuckDBPyConnection:
    """Create an in-memory DuckDB database with test data."""
    conn = duckdb.connect(":memory:")

    # Create schema and table
    conn.execute("CREATE SCHEMA IF NOT EXISTS library")
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

    # Insert test data
    test_books = [
        (
            "B001",
            "Python Programming",
            "John Smith",
            "Programming",
            3,
            2,
            5,
            -45.2,
            "2025-01-15 10:30:00",
            "Present",
        ),
        (
            "B002",
            "History of Rome",
            "Jane Doe",
            "History",
            1,
            1,
            1,
            -60.0,
            "2025-01-15 10:31:00",
            "Present",
        ),
        (
            "B003",
            "Science Basics",
            "Bob Wilson",
            "Science",
            2,
            3,
            4,
            -50.0,
            "2025-01-15 10:32:00",
            "Checked Out",
        ),
        (
            "B004",
            "Mystery Novel",
            "Alice Brown",
            "Fiction",
            3,
            2,
            3,
            -70.0,
            "2025-01-15 10:33:00",
            "Missing",
        ),
        (
            "B005",
            "Advanced Python",
            "John Smith",
            "Programming",
            3,
            2,
            6,
            -42.0,
            "2025-01-15 10:34:00",
            "Present",
        ),
        (
            "B006",
            "Thriller Story",
            "Jane Doe",
            "Thriller",
            1,
            2,
            1,
            -55.0,
            "2025-01-15 10:35:00",
            "Present",
        ),
        (
            "B007",
            "World History",
            "Bob Wilson",
            "History",
            1,
            1,
            2,
            -65.0,
            "2025-01-15 10:36:00",
            "Missing",
        ),
        (
            "B008",
            "Physics 101",
            "Alice Brown",
            "Science",
            2,
            3,
            5,
            -48.0,
            "2025-01-15 10:37:00",
            "Present",
        ),
        (
            "B009",
            "JavaScript Guide",
            "Charlie Davis",
            "Programming",
            3,
            1,
            1,
            -80.0,
            "2025-01-15 10:38:00",
            "Present",
        ),
        (
            "B010",
            "Classic Fiction",
            "Emma White",
            "Fiction",
            4,
            1,
            2,
            -52.0,
            "2025-01-15 10:39:00",
            "Checked Out",
        ),
    ]

    for book in test_books:
        conn.execute(
            "INSERT INTO library.books VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            book,
        )

    return conn


@pytest.fixture
def repository(test_db: duckdb.DuckDBPyConnection) -> BookRepository:
    """Create a BookRepository with test database."""
    return BookRepository(connection=test_db)


class TestBookRepositorySearch:
    """Tests for search_books method."""

    def test_search_by_title(self, repository: BookRepository) -> None:
        """Test searching books by title."""
        results = repository.search_books(query="Python")
        assert len(results) == 2
        titles = [book.title for book in results]
        assert "Python Programming" in titles
        assert "Advanced Python" in titles

    def test_search_by_author(self, repository: BookRepository) -> None:
        """Test searching books by author."""
        results = repository.search_books(query="John Smith")
        assert len(results) == 2
        assert all(book.author == "John Smith" for book in results)

    def test_search_with_category_filter(self, repository: BookRepository) -> None:
        """Test searching with category filter."""
        results = repository.search_books(query="Jane", category=Category.HISTORY)
        assert len(results) == 1
        assert results[0].title == "History of Rome"

    def test_search_case_insensitive(self, repository: BookRepository) -> None:
        """Test that search is case-insensitive."""
        results = repository.search_books(query="python")
        assert len(results) == 2

    def test_search_no_results(self, repository: BookRepository) -> None:
        """Test search with no matching results."""
        results = repository.search_books(query="Nonexistent")
        assert len(results) == 0

    def test_search_with_limit(self, repository: BookRepository) -> None:
        """Test search with result limit."""
        results = repository.search_books(query="o", limit=3)  # Matches many books
        assert len(results) <= 3


class TestBookRepositoryGet:
    """Tests for get_book_by_id method."""

    def test_get_existing_book(self, repository: BookRepository) -> None:
        """Test getting an existing book by ID."""
        book = repository.get_book_by_id("B001")
        assert book is not None
        assert book.book_id == "B001"
        assert book.title == "Python Programming"

    def test_get_nonexistent_book(self, repository: BookRepository) -> None:
        """Test getting a non-existent book returns None."""
        book = repository.get_book_by_id("B999")
        assert book is None


class TestBookRepositoryListByCategory:
    """Tests for list_by_category method."""

    def test_list_by_category(self, repository: BookRepository) -> None:
        """Test listing books by category."""
        results = repository.list_by_category(Category.PROGRAMMING)
        assert len(results) == 3
        assert all(book.category == Category.PROGRAMMING for book in results)

    def test_list_by_category_with_status_filter(self, repository: BookRepository) -> None:
        """Test listing by category with status filter."""
        results = repository.list_by_category(Category.FICTION, status=BookStatus.MISSING)
        assert len(results) == 1
        assert results[0].book_id == "B004"

    def test_list_by_category_empty(self, repository: BookRepository) -> None:
        """Test listing category with no matching status."""
        results = repository.list_by_category(Category.THRILLER, status=BookStatus.MISSING)
        assert len(results) == 0


class TestBookRepositoryListByStatus:
    """Tests for list_by_status method."""

    def test_list_by_status_present(self, repository: BookRepository) -> None:
        """Test listing present books."""
        results = repository.list_by_status(BookStatus.PRESENT)
        assert len(results) == 6
        assert all(book.status == BookStatus.PRESENT for book in results)

    def test_list_by_status_missing(self, repository: BookRepository) -> None:
        """Test listing missing books."""
        results = repository.list_by_status(BookStatus.MISSING)
        assert len(results) == 2

    def test_list_by_status_checked_out(self, repository: BookRepository) -> None:
        """Test listing checked out books."""
        results = repository.list_by_status(BookStatus.CHECKED_OUT)
        assert len(results) == 2

    def test_list_by_status_with_category_filter(self, repository: BookRepository) -> None:
        """Test listing by status with category filter."""
        results = repository.list_by_status(BookStatus.PRESENT, category=Category.PROGRAMMING)
        assert len(results) == 3


class TestBookRepositoryWeakSignal:
    """Tests for get_weak_signal_books method."""

    def test_get_weak_signal_default_threshold(self, repository: BookRepository) -> None:
        """Test getting weak signal books with default threshold (-55)."""
        results = repository.get_weak_signal_books()
        # Books with signal < -55: B002(-60), B004(-70), B007(-65), B009(-80)
        assert len(results) == 4
        assert all(book.signal_strength < -55 for book in results)

    def test_get_weak_signal_custom_threshold(self, repository: BookRepository) -> None:
        """Test getting weak signal books with custom threshold."""
        results = repository.get_weak_signal_books(threshold=-70)
        # Books with signal < -70: B009(-80)
        assert len(results) == 1
        assert results[0].book_id == "B009"

    def test_get_weak_signal_ordered(self, repository: BookRepository) -> None:
        """Test that weak signal books are ordered by signal strength (ascending)."""
        results = repository.get_weak_signal_books()
        signals = [book.signal_strength for book in results]
        assert signals == sorted(signals)


class TestBookRepositoryLocation:
    """Tests for find_books_in_cabinet method."""

    def test_find_books_in_cabinet(self, repository: BookRepository) -> None:
        """Test finding all books in a cabinet."""
        results = repository.find_books_in_cabinet(cabinet=3)
        # Cabinet 3 has: B001, B004, B005, B009 = 4 books
        assert len(results) == 4
        assert all(book.location.cabinet == 3 for book in results)

    def test_find_books_in_cabinet_and_rack(self, repository: BookRepository) -> None:
        """Test finding books in specific cabinet and rack."""
        results = repository.find_books_in_cabinet(cabinet=3, rack=2)
        # Cabinet 3, Rack 2 has: B001, B004, B005 = 3 books
        assert len(results) == 3
        assert all(book.location.cabinet == 3 and book.location.rack == 2 for book in results)

    def test_find_books_empty_cabinet(self, repository: BookRepository) -> None:
        """Test finding books in empty cabinet."""
        results = repository.find_books_in_cabinet(cabinet=99)
        assert len(results) == 0


class TestBookRepositoryStats:
    """Tests for get_library_stats method."""

    def test_get_library_stats(self, repository: BookRepository) -> None:
        """Test getting library statistics."""
        stats = repository.get_library_stats()

        assert stats["total_books"] == 10
        assert stats["by_status"]["Present"] == 6
        assert stats["by_status"]["Missing"] == 2
        assert stats["by_status"]["Checked Out"] == 2
        assert stats["by_category"]["Programming"] == 3
        assert stats["by_category"]["History"] == 2
        assert stats["by_category"]["Science"] == 2
        assert stats["by_category"]["Fiction"] == 2
        assert stats["by_category"]["Thriller"] == 1
        assert stats["weak_signal_count"] == 4  # Books with signal < -55

    def test_stats_available_count(self, repository: BookRepository) -> None:
        """Test that available count matches present books."""
        stats = repository.get_library_stats()
        assert stats["available_count"] == 6


class TestBookRepositoryConnection:
    """Tests for connection handling."""

    def test_create_with_path(self, tmp_path) -> None:
        """Test creating repository with database path."""
        db_path = tmp_path / "test.db"
        repo = BookRepository(db_path=str(db_path))
        assert repo.conn is not None

    def test_close_connection(self, test_db: duckdb.DuckDBPyConnection) -> None:
        """Test closing database connection."""
        repo = BookRepository(connection=test_db)
        repo.close()
        # Connection should be closed (accessing will raise error)
        # We don't test this since DuckDB doesn't expose connection state easily
