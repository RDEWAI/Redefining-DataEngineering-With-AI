"""Sales repository for MCP package DuckDB database operations.

This module provides the SalesRepository class for all database operations
related to sales. It implements search, filtering, and analytics queries.
"""

import logging
from datetime import date
from pathlib import Path
from typing import Any

import duckdb

from .sales_domain import Channel, CustomerSegment, Region, Sale

logger = logging.getLogger("mcp.sales_repository")


class SalesRepository:
    """Repository for sales database operations.

    This class encapsulates all DuckDB queries for the library.sales table.
    It provides methods for searching, filtering, and aggregating sales data.

    Args:
        db_path: Path to DuckDB database file
        connection: Existing DuckDB connection (alternative to db_path)
        read_only: If True, open database in read-only mode

    Example:
        >>> repo = SalesRepository(db_path="data/duckdb/chapter3.db")
        >>> sales = repo.search_sales(customer_segment="Corporate")
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

    def _row_to_sale(self, row: tuple) -> Sale:
        """Convert database row to Sale instance."""
        return Sale.from_row(row)

    def _execute_query(
        self, query: str, params: tuple[object, ...] | None = None
    ) -> list[tuple[object, ...]]:
        """Execute query and return all results."""
        if params:
            result = self.conn.execute(query, params)
        else:
            result = self.conn.execute(query)
        return list(result.fetchall())

    def get_sale_by_id(self, sale_id: str) -> Sale | None:
        """Get a sale by its ID."""
        sql = """
            SELECT sale_id, book_id, sale_date, quantity, unit_price, total_amount,
                   discount, payment_method, customer_id, customer_segment, region, channel
            FROM library.sales
            WHERE sale_id = ?
        """
        rows = self._execute_query(sql, (sale_id,))
        if rows:
            return self._row_to_sale(rows[0])
        return None

    def get_sales_for_book(self, book_id: str) -> list[Sale]:
        """Get all sales for a specific book."""
        sql = """
            SELECT sale_id, book_id, sale_date, quantity, unit_price, total_amount,
                   discount, payment_method, customer_id, customer_segment, region, channel
            FROM library.sales
            WHERE book_id = ?
            ORDER BY sale_date DESC
        """
        rows = self._execute_query(sql, (book_id,))
        return [self._row_to_sale(row) for row in rows]

    def search_sales(
        self,
        book_id: str | None = None,
        customer_segment: CustomerSegment | str | None = None,
        region: Region | str | None = None,
        channel: Channel | str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
    ) -> list[Sale]:
        """Search sales with optional filters."""
        sql = """
            SELECT sale_id, book_id, sale_date, quantity, unit_price, total_amount,
                   discount, payment_method, customer_id, customer_segment, region, channel
            FROM library.sales
            WHERE 1=1
        """
        params: list[Any] = []

        if book_id is not None:
            sql += " AND book_id = ?"
            params.append(book_id)

        if customer_segment is not None:
            segment_val = (
                customer_segment.value
                if isinstance(customer_segment, CustomerSegment)
                else customer_segment
            )
            sql += " AND customer_segment = ?"
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
            sql += " AND sale_date >= ?"
            params.append(date_from.isoformat())

        if date_to is not None:
            sql += " AND sale_date <= ?"
            params.append(date_to.isoformat())

        sql += " ORDER BY sale_date DESC LIMIT ?"
        params.append(limit)

        rows = self._execute_query(sql, tuple(params))
        return [self._row_to_sale(row) for row in rows]

    def get_sales_stats(self) -> dict[str, Any]:
        """Get aggregate statistics about sales."""
        # Get totals
        totals_result = self._execute_query("""
            SELECT
                COUNT(*) as total_sales,
                SUM(total_amount) as total_revenue,
                SUM(quantity) as total_units,
                AVG(total_amount) as avg_order_value,
                COUNT(DISTINCT customer_id) as unique_customers
            FROM library.sales
        """)
        totals = totals_result[0]

        # Revenue by segment
        segment_result = self._execute_query("""
            SELECT customer_segment, SUM(total_amount) as revenue, COUNT(*) as count
            FROM library.sales
            GROUP BY customer_segment
        """)
        by_segment = {row[0]: {"revenue": float(row[1]), "count": row[2]} for row in segment_result}

        # Revenue by region
        region_result = self._execute_query("""
            SELECT region, SUM(total_amount) as revenue, COUNT(*) as count
            FROM library.sales
            GROUP BY region
        """)
        by_region = {row[0]: {"revenue": float(row[1]), "count": row[2]} for row in region_result}

        # Revenue by channel
        channel_result = self._execute_query("""
            SELECT channel, SUM(total_amount) as revenue, COUNT(*) as count
            FROM library.sales
            GROUP BY channel
        """)
        by_channel = {row[0]: {"revenue": float(row[1]), "count": row[2]} for row in channel_result}

        return {
            "total_sales": totals[0],
            "total_revenue": float(totals[1]) if totals[1] else 0.0,
            "total_units": totals[2] if totals[2] else 0,
            "avg_order_value": float(totals[3]) if totals[3] else 0.0,
            "unique_customers": totals[4] if totals[4] else 0,
            "by_segment": by_segment,
            "by_region": by_region,
            "by_channel": by_channel,
        }

    def get_top_selling_books(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get best-selling books ranked by total quantity sold."""
        sql = """
            SELECT
                s.book_id,
                b.title,
                b.author,
                b.category,
                SUM(s.quantity) as total_quantity,
                SUM(s.total_amount) as total_revenue,
                COUNT(s.sale_id) as sale_count
            FROM library.sales s
            JOIN library.books b ON s.book_id = b.book_id
            GROUP BY s.book_id, b.title, b.author, b.category
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
                "total_revenue": float(row[5]),
                "sale_count": row[6],
            }
            for row in rows
        ]

    def get_sales_by_month(self) -> list[dict[str, Any]]:
        """Get sales aggregated by month."""
        sql = """
            SELECT
                strftime('%Y-%m', sale_date) as month,
                COUNT(*) as total_sales,
                SUM(total_amount) as total_revenue,
                SUM(quantity) as total_units
            FROM library.sales
            GROUP BY strftime('%Y-%m', sale_date)
            ORDER BY month
        """
        rows = self._execute_query(sql)
        return [
            {
                "month": row[0],
                "total_sales": row[1],
                "total_revenue": float(row[2]),
                "total_units": row[3],
            }
            for row in rows
        ]

    def get_bulk_purchases(self, min_quantity: int = 3, limit: int = 50) -> list[Sale]:
        """Get bulk purchase sales."""
        sql = """
            SELECT sale_id, book_id, sale_date, quantity, unit_price, total_amount,
                   discount, payment_method, customer_id, customer_segment, region, channel
            FROM library.sales
            WHERE quantity >= ?
            ORDER BY quantity DESC, sale_date DESC
            LIMIT ?
        """
        rows = self._execute_query(sql, (min_quantity, limit))
        return [self._row_to_sale(row) for row in rows]


def get_sales_repository(db_path: str | None = None, read_only: bool = True) -> SalesRepository:
    """Get a SalesRepository instance.

    Factory function that creates a repository with default database path
    if not specified.
    """
    if db_path is None:
        default_path = Path(__file__).parent.parent.parent / "data" / "duckdb" / "chapter3.db"
        db_path = str(default_path)

    return SalesRepository(db_path=db_path, read_only=read_only)
