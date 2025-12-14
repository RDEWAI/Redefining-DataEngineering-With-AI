"""Library domain classes.

This module defines the core domain objects for the library management system:
- BookStatus: Availability status enum
- Category: Book category enum
- Location: Physical location dataclass
- Book: Main book entity dataclass

All domain objects are immutable and support JSON serialization.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class BookStatus(Enum):
    """Book availability status.

    Attributes:
        PRESENT: Book is on shelf and detectable by RFID
        MISSING: Book cannot be located or not seen for >30 minutes
        CHECKED_OUT: Book is borrowed by a patron
    """

    PRESENT = "Present"
    MISSING = "Missing"
    CHECKED_OUT = "Checked Out"


class Category(Enum):
    """Book category classification.

    Attributes:
        PROGRAMMING: Technical programming books
        HISTORY: Historical books
        SCIENCE: Science-related books
        FICTION: Fiction novels
        THRILLER: Thriller novels
    """

    PROGRAMMING = "Programming"
    HISTORY = "History"
    SCIENCE = "Science"
    FICTION = "Fiction"
    THRILLER = "Thriller"


@dataclass(frozen=True)
class Location:
    """Physical location of a book in the library.

    Attributes:
        cabinet: Cabinet number (1-based)
        rack: Rack number within cabinet (1-based)
        row: Row number within rack (1-based)
    """

    cabinet: int
    rack: int
    row: int

    def __str__(self) -> str:
        """Return human-readable location string."""
        return f"Cabinet {self.cabinet}, Rack {self.rack}, Row {self.row}"


@dataclass(frozen=True)
class Book:
    """Library book entity with RFID tracking data.

    Attributes:
        book_id: Unique identifier (e.g., "B001")
        title: Book title
        author: Author name
        category: Book category
        location: Physical location in library
        signal_strength: RFID signal strength in dBm (typically -30 to -90)
        timestamp: Last RFID scan timestamp
        status: Current availability status
    """

    book_id: str
    title: str
    author: str
    category: Category
    location: Location
    signal_strength: float
    timestamp: datetime
    status: BookStatus

    @property
    def has_weak_signal(self) -> bool:
        """Check if RFID signal is weak.

        Weak signal is defined as below -55 dBm, which may indicate
        the book needs RFID maintenance or relocation.

        Returns:
            True if signal strength is below -55 dBm
        """
        return self.signal_strength < -55

    @property
    def is_available(self) -> bool:
        """Check if book is available for checkout.

        A book is available only if it has Present status.

        Returns:
            True if book status is Present
        """
        return self.status == BookStatus.PRESENT

    def to_dict(self) -> dict[str, Any]:
        """Convert book to dictionary for JSON serialization.

        Returns:
            Dictionary with all book fields, with enum values as strings
            and timestamp as ISO format string.
        """
        return {
            "book_id": self.book_id,
            "title": self.title,
            "author": self.author,
            "category": self.category.value,
            "cabinet": self.location.cabinet,
            "rack": self.location.rack,
            "row": self.location.row,
            "signal_strength": self.signal_strength,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
        }

    @classmethod
    def from_row(cls, row: tuple) -> "Book":
        """Create Book instance from database row tuple.

        Args:
            row: Tuple with values in order: (book_id, title, author,
                category, cabinet, rack, row, signal_strength, timestamp, status)

        Returns:
            Book instance

        Example:
            >>> row = ("B001", "Python Book", "John", "Programming", 1, 2, 3,
            ...        -45.0, datetime.now(), "Present")
            >>> book = Book.from_row(row)
        """
        (
            book_id,
            title,
            author,
            category_str,
            cabinet,
            rack,
            row_num,
            signal_strength,
            timestamp,
            status_str,
        ) = row

        return cls(
            book_id=book_id,
            title=title,
            author=author,
            category=Category(category_str),
            location=Location(cabinet=cabinet, rack=rack, row=row_num),
            signal_strength=signal_strength,
            timestamp=timestamp
            if isinstance(timestamp, datetime)
            else datetime.fromisoformat(str(timestamp)),
            status=BookStatus(status_str),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Book":
        """Create Book instance from dictionary.

        Args:
            data: Dictionary with book fields. Category and status can be
                either enum instances or string values.

        Returns:
            Book instance
        """
        category = data["category"]
        if isinstance(category, str):
            category = Category(category)

        status = data["status"]
        if isinstance(status, str):
            status = BookStatus(status)

        timestamp = data["timestamp"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        return cls(
            book_id=data["book_id"],
            title=data["title"],
            author=data["author"],
            category=category,
            location=Location(
                cabinet=data["cabinet"],
                rack=data["rack"],
                row=data["row"],
            ),
            signal_strength=data["signal_strength"],
            timestamp=timestamp,
            status=status,
        )
