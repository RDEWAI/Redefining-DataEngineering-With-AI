"""Lending repository for MCP package DuckDB database operations.

This module provides the LendingRepository class for all database operations
related to lending. It implements search, filtering, and analytics queries.
"""

import logging
from datetime import date
from pathlib import Path
from typing import Any

import duckdb

from .lending_domain import Channel, Loan, PatronSegment, Region

logger = logging.getLogger("mcp.lending_repository")


class LendingRepository:
    """Repository for lending database operations.

    This class encapsulates all DuckDB queries for the library.lending table.
    It provides methods for searching, filtering, and aggregating lending data.

    Args:
        db_path: Path to DuckDB database file
        connection: Existing DuckDB connection (alternative to db_path)
        read_only: If True, open database in read-only mode

    Example:
        >>> repo = LendingRepository(db_path="data/duckdb/chapter2.db")
        >>> loans = repo.search_lending(patron_segment="Corporate")
        >>> repo.close()
    """

    def __init__(
        self,
        db_path: str | None = None,
        connection: duckdb.DuckDBPyConnection | None = None,
        read_only: bool = False,
    ) -> None:
        """Initialize repository with database connection."""
        if connection is not None:
            self.conn = connection
            self._owns_connection = False
        elif db_path is not None:
            self.conn = duckdb.connect(db_path, read_only=read_only)
            self._owns_connection = True
        else:
            raise ValueError("Either db_path or connection must be provided")

    def close(self) -> None:
        """Close the database connection if owned by this repository."""
        if self._owns_connection and self.conn is not None:
            self.conn.close()
            self.conn = None  # type: ignore[assignment]

    def reopen(self, db_path: str, read_only: bool = False) -> None:
        """Reopen the database connection after it was closed."""
        if self.conn is None:
            self.conn = duckdb.connect(db_path, read_only=read_only)
            self._owns_connection = True

    def is_open(self) -> bool:
        """Check if the database connection is open."""
        return self.conn is not None

    def _row_to_loan(self, row: tuple) -> Loan:
        """Convert database row to Loan instance."""
        return Loan.from_row(row)

    def _execute_query(
        self, query: str, params: tuple[object, ...] | None = None
    ) -> list[tuple[object, ...]]:
        """Execute query and return all results."""
        if params:
            result = self.conn.execute(query, params)
        else:
            result = self.conn.execute(query)
        return list(result.fetchall())

    def get_loan_by_id(self, loan_id: str) -> Loan | None:
        """Get a loan by its ID."""
        sql = """
            SELECT loan_id, book_id, loan_date, quantity, lending_fee, total_fees,
                   fee_waiver, payment_method, patron_id, patron_segment, region, channel
            FROM library.lending
            WHERE loan_id = ?
        """
        rows = self._execute_query(sql, (loan_id,))
        if rows:
            return self._row_to_loan(rows[0])
        return None

    def get_lending_for_book(self, book_id: str) -> list[Loan]:
        """Get all loans for a specific book."""
        sql = """
            SELECT loan_id, book_id, loan_date, quantity, lending_fee, total_fees,
                   fee_waiver, payment_method, patron_id, patron_segment, region, channel
            FROM library.lending
            WHERE book_id = ?
            ORDER BY loan_date DESC
        """
        rows = self._execute_query(sql, (book_id,))
        return [self._row_to_loan(row) for row in rows]

    def search_lending(
        self,
        book_id: str | None = None,
        patron_segment: PatronSegment | str | None = None,
        region: Region | str | None = None,
        channel: Channel | str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
    ) -> list[Loan]:
        """Search lending records with optional filters."""
        sql = """
            SELECT loan_id, book_id, loan_date, quantity, lending_fee, total_fees,
                   fee_waiver, payment_method, patron_id, patron_segment, region, channel
            FROM library.lending
            WHERE 1=1
        """
        params: list[Any] = []

        if book_id is not None:
            sql += " AND book_id = ?"
            params.append(book_id)

        if patron_segment is not None:
            segment_val = (
                patron_segment.value
                if isinstance(patron_segment, PatronSegment)
                else patron_segment
            )
            sql += " AND patron_segment = ?"
            params.append(segment_val)

        if region is not None:
            region_val = region.value if isinstance(region, Region) else region
            sql += " AND region = ?"
            params.append(region_val)

        if channel is not None:
            channel_val = channel.value if isinstance(channel, Channel) else channel
            sql += " AND channel = ?"
            params.append(channel_val)

        if date_from is not None:
            sql += " AND loan_date >= ?"
            params.append(date_from.isoformat())

        if date_to is not None:
            sql += " AND loan_date <= ?"
            params.append(date_to.isoformat())

        sql += " ORDER BY loan_date DESC LIMIT ?"
        params.append(limit)

        rows = self._execute_query(sql, tuple(params))
        return [self._row_to_loan(row) for row in rows]

    def get_lending_stats(self) -> dict[str, Any]:
        """Get aggregate statistics about lending."""
        # Get totals
        totals_result = self._execute_query("""
            SELECT
                COUNT(*) as total_loans,
                SUM(total_fees) as total_fees,
                SUM(quantity) as total_units,
                AVG(total_fees) as avg_loan_fees,
                COUNT(DISTINCT patron_id) as unique_patrons
            FROM library.lending
        """)
        totals = totals_result[0]

        # Fees by segment
        segment_result = self._execute_query("""
            SELECT patron_segment, SUM(total_fees) as fees, COUNT(*) as count
            FROM library.lending
            GROUP BY patron_segment
        """)
        by_segment = {row[0]: {"fees": float(row[1]), "count": row[2]} for row in segment_result}  # type: ignore[arg-type]

        # Fees by region
        region_result = self._execute_query("""
            SELECT region, SUM(total_fees) as fees, COUNT(*) as count
            FROM library.lending
            GROUP BY region
        """)
        by_region = {row[0]: {"fees": float(row[1]), "count": row[2]} for row in region_result}  # type: ignore[arg-type]

        # Fees by channel
        channel_result = self._execute_query("""
            SELECT channel, SUM(total_fees) as fees, COUNT(*) as count
            FROM library.lending
            GROUP BY channel
        """)
        by_channel = {row[0]: {"fees": float(row[1]), "count": row[2]} for row in channel_result}  # type: ignore[arg-type]

        return {
            "total_loans": totals[0],
            "total_fees": float(totals[1]) if totals[1] else 0.0,  # type: ignore[arg-type]
            "total_units": totals[2] if totals[2] else 0,
            "avg_loan_fees": float(totals[3]) if totals[3] else 0.0,  # type: ignore[arg-type]
            "unique_patrons": totals[4] if totals[4] else 0,
            "by_segment": by_segment,
            "by_region": by_region,
            "by_channel": by_channel,
        }

    def get_most_lent_books(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get most lent books ranked by total quantity lent."""
        sql = """
            SELECT
                l.book_id,
                b.title,
                b.author,
                b.category,
                SUM(l.quantity) as total_quantity,
                SUM(l.total_fees) as total_fees,
                COUNT(l.loan_id) as loan_count
            FROM library.lending l
            JOIN library.books b ON l.book_id = b.book_id
            GROUP BY l.book_id, b.title, b.author, b.category
            ORDER BY total_quantity DESC
            LIMIT ?
        """
        rows = self._execute_query(sql, (limit,))
        return [
            {
                "book_id": row[0],
                "title": row[1],
                "author": row[2],
                "category": row[3],
                "total_quantity": row[4],
                "total_fees": float(row[5]),  # type: ignore[arg-type]
                "loan_count": row[6],
            }
            for row in rows
        ]

    def get_lending_by_month(self) -> list[dict[str, Any]]:
        """Get lending aggregated by month."""
        sql = """
            SELECT
                strftime(loan_date, '%Y-%m') as month,
                COUNT(*) as total_loans,
                SUM(total_fees) as total_fees,
                SUM(quantity) as total_units
            FROM library.lending
            GROUP BY strftime(loan_date, '%Y-%m')
            ORDER BY month
        """
        rows = self._execute_query(sql)
        return [
            {
                "month": row[0],
                "total_loans": row[1],
                "total_fees": float(row[2]),  # type: ignore[arg-type]
                "total_units": row[3],
            }
            for row in rows
        ]

    def get_bulk_loans(self, min_quantity: int = 3, limit: int = 50) -> list[Loan]:
        """Get bulk loan records."""
        sql = """
            SELECT loan_id, book_id, loan_date, quantity, lending_fee, total_fees,
                   fee_waiver, payment_method, patron_id, patron_segment, region, channel
            FROM library.lending
            WHERE quantity >= ?
            ORDER BY quantity DESC, loan_date DESC
            LIMIT ?
        """
        rows = self._execute_query(sql, (min_quantity, limit))
        return [self._row_to_loan(row) for row in rows]


def get_lending_repository(db_path: str | None = None, read_only: bool = True) -> LendingRepository:
    """Get a LendingRepository instance.

    Factory function that creates a repository with default database path
    if not specified.
    """
    if db_path is None:
        default_path = Path(__file__).parent.parent.parent / "data" / "duckdb" / "chapter2.db"
        db_path = str(default_path)

    return LendingRepository(db_path=db_path, read_only=read_only)
