"""Book repository for DuckDB database operations.

This module provides the BookRepository class for all database operations
related to books. It implements search, filtering, and statistics queries.
"""

from pathlib import Path
from typing import Any

import duckdb

from .domain import Book, BookStatus, Category


class BookRepository:
    """Repository for book database operations.

    This class encapsulates all DuckDB queries for the library.books table.
    It provides methods for searching, filtering, and aggregating book data.

    Args:
        db_path: Path to DuckDB database file
        connection: Existing DuckDB connection (alternative to db_path)

    Example:
        >>> repo = BookRepository(db_path="data/duckdb/library.db")
        >>> books = repo.search_books("Python")
        >>> repo.close()
    """

    def __init__(
        self,
        db_path: str | None = None,
        connection: duckdb.DuckDBPyConnection | None = None,
    ) -> None:
        """Initialize repository with database connection.

        Args:
            db_path: Path to DuckDB database file. Used if connection not provided.
            connection: Existing DuckDB connection. Takes precedence over db_path.

        Raises:
            ValueError: If neither db_path nor connection is provided.
        """
        if connection is not None:
            self.conn = connection
            self._owns_connection = False
        elif db_path is not None:
            self.conn = duckdb.connect(db_path)
            self._owns_connection = True
        else:
            raise ValueError("Either db_path or connection must be provided")

    def close(self) -> None:
        """Close the database connection if owned by this repository."""
        if self._owns_connection and self.conn is not None:
            self.conn.close()

    def _row_to_book(self, row: tuple) -> Book:
        """Convert database row to Book instance."""
        return Book.from_row(row)

    def _execute_query(self, query: str, params: tuple | None = None) -> list[tuple]:
        """Execute query and return all results."""
        if params:
            result = self.conn.execute(query, params)
        else:
            result = self.conn.execute(query)
        return result.fetchall()

    def search_books(
        self,
        query: str,
        category: Category | None = None,
        limit: int = 10,
    ) -> list[Book]:
        """Search books by title or author.

        Performs case-insensitive search on title and author fields.

        Args:
            query: Search query string
            category: Optional category filter
            limit: Maximum number of results (default 10)

        Returns:
            List of matching Book instances

        Example:
            >>> books = repo.search_books("Python", category=Category.PROGRAMMING)
        """
        sql = """
            SELECT book_id, title, author, category, cabinet, rack, row,
                   signal_strength, timestamp, status
            FROM library.books
            WHERE (LOWER(title) LIKE LOWER('%' || ? || '%')
                   OR LOWER(author) LIKE LOWER('%' || ? || '%'))
        """
        params: list[Any] = [query, query]

        if category is not None:
            sql += " AND category = ?"
            params.append(category.value)

        sql += " ORDER BY title LIMIT ?"
        params.append(limit)

        rows = self._execute_query(sql, tuple(params))
        return [self._row_to_book(row) for row in rows]

    def get_book_by_id(self, book_id: str) -> Book | None:
        """Get a book by its ID.

        Args:
            book_id: Book ID (e.g., "B001")

        Returns:
            Book instance if found, None otherwise
        """
        sql = """
            SELECT book_id, title, author, category, cabinet, rack, row,
                   signal_strength, timestamp, status
            FROM library.books
            WHERE book_id = ?
        """
        rows = self._execute_query(sql, (book_id,))
        if rows:
            return self._row_to_book(rows[0])
        return None

    def list_by_category(
        self,
        category: Category,
        status: BookStatus | None = None,
    ) -> list[Book]:
        """List all books in a category.

        Args:
            category: Category to filter by
            status: Optional status filter

        Returns:
            List of Book instances in the category
        """
        sql = """
            SELECT book_id, title, author, category, cabinet, rack, row,
                   signal_strength, timestamp, status
            FROM library.books
            WHERE category = ?
        """
        params: list[Any] = [category.value]

        if status is not None:
            sql += " AND status = ?"
            params.append(status.value)

        sql += " ORDER BY title"
        rows = self._execute_query(sql, tuple(params))
        return [self._row_to_book(row) for row in rows]

    def list_by_status(
        self,
        status: BookStatus,
        category: Category | None = None,
    ) -> list[Book]:
        """List all books with a specific status.

        Args:
            status: Status to filter by
            category: Optional category filter

        Returns:
            List of Book instances with the status
        """
        sql = """
            SELECT book_id, title, author, category, cabinet, rack, row,
                   signal_strength, timestamp, status
            FROM library.books
            WHERE status = ?
        """
        params: list[Any] = [status.value]

        if category is not None:
            sql += " AND category = ?"
            params.append(category.value)

        sql += " ORDER BY title"
        rows = self._execute_query(sql, tuple(params))
        return [self._row_to_book(row) for row in rows]

    def get_weak_signal_books(self, threshold: float = -55.0) -> list[Book]:
        """Get books with weak RFID signal.

        Books with signal strength below the threshold may need
        RFID maintenance or relocation.

        Args:
            threshold: Signal strength threshold in dBm (default -55)

        Returns:
            List of Book instances with weak signal, ordered by signal strength
        """
        sql = """
            SELECT book_id, title, author, category, cabinet, rack, row,
                   signal_strength, timestamp, status
            FROM library.books
            WHERE signal_strength < ?
            ORDER BY signal_strength ASC
        """
        rows = self._execute_query(sql, (threshold,))
        return [self._row_to_book(row) for row in rows]

    def find_books_in_cabinet(
        self,
        cabinet: int,
        rack: int | None = None,
    ) -> list[Book]:
        """Find all books in a cabinet.

        Args:
            cabinet: Cabinet number
            rack: Optional rack number within cabinet

        Returns:
            List of Book instances in the cabinet
        """
        sql = """
            SELECT book_id, title, author, category, cabinet, rack, row,
                   signal_strength, timestamp, status
            FROM library.books
            WHERE cabinet = ?
        """
        params: list[Any] = [cabinet]

        if rack is not None:
            sql += " AND rack = ?"
            params.append(rack)

        sql += " ORDER BY rack, row"
        rows = self._execute_query(sql, tuple(params))
        return [self._row_to_book(row) for row in rows]

    def get_library_stats(self) -> dict[str, Any]:
        """Get aggregate statistics about the library.

        Returns:
            Dictionary with:
            - total_books: Total number of books
            - available_count: Number of available (Present) books
            - by_status: Dict of count per status
            - by_category: Dict of count per category
            - weak_signal_count: Books with signal < -55 dBm
        """
        # Get total and available count
        total_result = self._execute_query("SELECT COUNT(*) FROM library.books")
        total_books = total_result[0][0]

        available_result = self._execute_query(
            "SELECT COUNT(*) FROM library.books WHERE status = 'Present'"
        )
        available_count = available_result[0][0]

        # Get counts by status
        status_result = self._execute_query(
            "SELECT status, COUNT(*) FROM library.books GROUP BY status"
        )
        by_status = {row[0]: row[1] for row in status_result}

        # Get counts by category
        category_result = self._execute_query(
            "SELECT category, COUNT(*) FROM library.books GROUP BY category"
        )
        by_category = {row[0]: row[1] for row in category_result}

        # Get weak signal count
        weak_signal_result = self._execute_query(
            "SELECT COUNT(*) FROM library.books WHERE signal_strength < -55"
        )
        weak_signal_count = weak_signal_result[0][0]

        return {
            "total_books": total_books,
            "available_count": available_count,
            "by_status": by_status,
            "by_category": by_category,
            "weak_signal_count": weak_signal_count,
        }


def get_repository(db_path: str | None = None) -> BookRepository:
    """Get a BookRepository instance.

    Factory function that creates a repository with default database path
    if not specified.

    Args:
        db_path: Path to DuckDB database file. Defaults to
            chapter-3/data/duckdb/library.db relative to project root.

    Returns:
        BookRepository instance
    """
    if db_path is None:
        # Default path relative to chapter-3 directory
        default_path = Path(__file__).parent.parent.parent / "data" / "duckdb" / "chapter3.db"
        db_path = str(default_path)

    return BookRepository(db_path=db_path)
