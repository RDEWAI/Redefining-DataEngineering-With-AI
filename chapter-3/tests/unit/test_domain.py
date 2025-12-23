"""Unit tests for library domain classes.

Tests for Book, BookStatus, Category, and Location domain objects.
"""

from datetime import datetime

import pytest

from src.agentic.library.domain import (
    Book,
    BookStatus,
    Category,
    Location,
)


class TestBookStatus:
    """Tests for BookStatus enum."""

    def test_status_values(self) -> None:
        """Verify all expected status values exist."""
        assert BookStatus.PRESENT.value == "Present"
        assert BookStatus.MISSING.value == "Missing"
        assert BookStatus.CHECKED_OUT.value == "Checked Out"

    def test_status_from_string(self) -> None:
        """Test creating status from string value."""
        assert BookStatus("Present") == BookStatus.PRESENT
        assert BookStatus("Missing") == BookStatus.MISSING
        assert BookStatus("Checked Out") == BookStatus.CHECKED_OUT

    def test_invalid_status_raises_error(self) -> None:
        """Test that invalid status raises ValueError."""
        with pytest.raises(ValueError):
            BookStatus("Invalid")


class TestCategory:
    """Tests for Category enum."""

    def test_category_values(self) -> None:
        """Verify all expected category values exist."""
        assert Category.PROGRAMMING.value == "Programming"
        assert Category.HISTORY.value == "History"
        assert Category.SCIENCE.value == "Science"
        assert Category.FICTION.value == "Fiction"
        assert Category.THRILLER.value == "Thriller"

    def test_category_from_string(self) -> None:
        """Test creating category from string value."""
        assert Category("Programming") == Category.PROGRAMMING
        assert Category("History") == Category.HISTORY
        assert Category("Science") == Category.SCIENCE
        assert Category("Fiction") == Category.FICTION
        assert Category("Thriller") == Category.THRILLER

    def test_invalid_category_raises_error(self) -> None:
        """Test that invalid category raises ValueError."""
        with pytest.raises(ValueError):
            Category("Romance")


class TestLocation:
    """Tests for Location dataclass."""

    def test_location_creation(self) -> None:
        """Test creating a location."""
        loc = Location(cabinet=3, rack=2, row=5)
        assert loc.cabinet == 3
        assert loc.rack == 2
        assert loc.row == 5

    def test_location_str(self) -> None:
        """Test location string representation."""
        loc = Location(cabinet=3, rack=2, row=5)
        assert str(loc) == "Cabinet 3, Rack 2, Row 5"

    def test_location_equality(self) -> None:
        """Test location equality."""
        loc1 = Location(cabinet=3, rack=2, row=5)
        loc2 = Location(cabinet=3, rack=2, row=5)
        loc3 = Location(cabinet=1, rack=1, row=1)
        assert loc1 == loc2
        assert loc1 != loc3


class TestBook:
    """Tests for Book dataclass."""

    @pytest.fixture
    def sample_book(self) -> Book:
        """Create a sample book for testing."""
        return Book(
            book_id="B001",
            title="Python Programming",
            author="John Smith",
            description="A comprehensive guide to Python programming covering best practices and design patterns.",
            category=Category.PROGRAMMING,
            location=Location(cabinet=3, rack=2, row=5),
            signal_strength=-45.2,
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            status=BookStatus.PRESENT,
        )

    @pytest.fixture
    def weak_signal_book(self) -> Book:
        """Create a book with weak RFID signal."""
        return Book(
            book_id="B002",
            title="History of Rome",
            author="Jane Doe",
            description="A detailed examination of ancient Rome focusing on political and cultural developments.",
            category=Category.HISTORY,
            location=Location(cabinet=1, rack=1, row=1),
            signal_strength=-60.0,
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            status=BookStatus.PRESENT,
        )

    @pytest.fixture
    def checked_out_book(self) -> Book:
        """Create a checked out book."""
        return Book(
            book_id="B003",
            title="Science Basics",
            author="Bob Wilson",
            description="An introduction to fundamental scientific concepts and the scientific method.",
            category=Category.SCIENCE,
            location=Location(cabinet=2, rack=3, row=4),
            signal_strength=-50.0,
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            status=BookStatus.CHECKED_OUT,
        )

    def test_book_creation(self, sample_book: Book) -> None:
        """Test creating a book."""
        assert sample_book.book_id == "B001"
        assert sample_book.title == "Python Programming"
        assert sample_book.author == "John Smith"
        assert sample_book.category == Category.PROGRAMMING
        assert sample_book.location.cabinet == 3
        assert sample_book.signal_strength == -45.2
        assert sample_book.status == BookStatus.PRESENT

    def test_has_weak_signal_false(self, sample_book: Book) -> None:
        """Test has_weak_signal returns False for strong signal."""
        assert sample_book.has_weak_signal is False

    def test_has_weak_signal_true(self, weak_signal_book: Book) -> None:
        """Test has_weak_signal returns True for weak signal (<-55 dBm)."""
        assert weak_signal_book.has_weak_signal is True

    def test_has_weak_signal_boundary(self) -> None:
        """Test has_weak_signal at boundary value (-55 dBm)."""
        book = Book(
            book_id="B099",
            title="Test Book",
            author="Test Author",
            description="A test book for boundary testing of weak signal detection.",
            category=Category.FICTION,
            location=Location(cabinet=1, rack=1, row=1),
            signal_strength=-55.0,  # Exactly at threshold
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            status=BookStatus.PRESENT,
        )
        # At exactly -55, should NOT be weak (< -55 is weak)
        assert book.has_weak_signal is False

        # Just below threshold
        book_weak = Book(
            book_id="B098",
            title="Test Book 2",
            author="Test Author",
            description="Another test book for weak signal boundary condition testing.",
            category=Category.FICTION,
            location=Location(cabinet=1, rack=1, row=1),
            signal_strength=-55.1,
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            status=BookStatus.PRESENT,
        )
        assert book_weak.has_weak_signal is True

    def test_is_available_present(self, sample_book: Book) -> None:
        """Test is_available returns True for Present books."""
        assert sample_book.is_available is True

    def test_is_available_checked_out(self, checked_out_book: Book) -> None:
        """Test is_available returns False for Checked Out books."""
        assert checked_out_book.is_available is False

    def test_is_available_missing(self) -> None:
        """Test is_available returns False for Missing books."""
        missing_book = Book(
            book_id="B004",
            title="Missing Book",
            author="Unknown",
            description="A book that has gone missing from the library shelves.",
            category=Category.THRILLER,
            location=Location(cabinet=1, rack=1, row=1),
            signal_strength=-70.0,
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            status=BookStatus.MISSING,
        )
        assert missing_book.is_available is False

    def test_to_dict(self, sample_book: Book) -> None:
        """Test converting book to dictionary."""
        # Test default (without description for token efficiency)
        book_dict = sample_book.to_dict()

        assert book_dict["book_id"] == "B001"
        assert book_dict["title"] == "Python Programming"
        assert book_dict["author"] == "John Smith"
        assert "description" not in book_dict  # Not included by default
        assert book_dict["category"] == "Programming"
        assert book_dict["cabinet"] == 3
        assert book_dict["rack"] == 2
        assert book_dict["row"] == 5
        assert book_dict["signal_strength"] == -45.2
        assert book_dict["timestamp"] == "2025-01-15T10:30:00"
        assert book_dict["status"] == "Present"

        # Test with description included
        book_dict_with_desc = sample_book.to_dict(include_description=True)
        assert (
            book_dict_with_desc["description"]
            == "A comprehensive guide to Python programming covering best practices and design patterns."
        )

    def test_book_equality(self, sample_book: Book) -> None:
        """Test book equality based on all fields."""
        book2 = Book(
            book_id="B001",
            title="Python Programming",
            author="John Smith",
            description="A comprehensive guide to Python programming covering best practices and design patterns.",
            category=Category.PROGRAMMING,
            location=Location(cabinet=3, rack=2, row=5),
            signal_strength=-45.2,
            timestamp=datetime(2025, 1, 15, 10, 30, 0),
            status=BookStatus.PRESENT,
        )
        assert sample_book == book2

    def test_from_row(self) -> None:
        """Test creating book from database row tuple."""
        row = (
            "B001",
            "Python Programming",
            "John Smith",
            "A comprehensive guide to Python programming covering best practices and design patterns.",
            "Programming",
            3,
            2,
            5,
            -45.2,
            datetime(2025, 1, 15, 10, 30, 0),
            "Present",
        )
        book = Book.from_row(row)
        assert book.book_id == "B001"
        assert book.title == "Python Programming"
        assert (
            book.description
            == "A comprehensive guide to Python programming covering best practices and design patterns."
        )
        assert book.category == Category.PROGRAMMING
        assert book.status == BookStatus.PRESENT
