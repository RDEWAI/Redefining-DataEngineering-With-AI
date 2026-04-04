"""Replenish repository for MCP package DuckDB database operations.

This module provides the ReplenishRepository class for all database operations
related to replenishment. It implements search, filtering, and analytics queries.
"""

import logging
from datetime import date
from pathlib import Path
from typing import Any

import duckdb

from .replenish_domain import (
    BookCondition,
    FundingSource,
    Priority,
    Replenishment,
    ReplenishType,
    Supplier,
)

logger = logging.getLogger("mcp.replenish_repository")


class ReplenishRepository:
    """Repository for replenishment database operations.

    This class encapsulates all DuckDB queries for the library.replenish table.
    It provides methods for searching, filtering, and aggregating replenish data.

    Args:
        db_path: Path to DuckDB database file
        connection: Existing DuckDB connection (alternative to db_path)
        read_only: If True, open database in read-only mode

    Example:
        >>> repo = ReplenishRepository(db_path="data/duckdb/chapter2.db")
        >>> records = repo.search_replenish(supplier="Ingram")
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

    def _row_to_replenishment(self, row: tuple) -> Replenishment:
        """Convert database row to Replenishment instance."""
        return Replenishment.from_row(row)

    def _execute_query(
        self, query: str, params: tuple[object, ...] | None = None
    ) -> list[tuple[object, ...]]:
        """Execute query and return all results."""
        if params:
            result = self.conn.execute(query, params)
        else:
            result = self.conn.execute(query)
        return list(result.fetchall())

    def get_by_id(self, replenish_id: str) -> Replenishment | None:
        """Get a replenishment by its ID."""
        sql = """
            SELECT replenish_id, book_id, replenish_date, quantity, unit_cost, total_cost,
                   discount_pct, supplier, replenish_type, condition, funding_source, priority
            FROM library.replenish
            WHERE replenish_id = ?
        """
        rows = self._execute_query(sql, (replenish_id,))
        if rows:
            return self._row_to_replenishment(rows[0])
        return None

    def get_replenish_for_book(self, book_id: str) -> list[Replenishment]:
        """Get all replenishments for a specific book."""
        sql = """
            SELECT replenish_id, book_id, replenish_date, quantity, unit_cost, total_cost,
                   discount_pct, supplier, replenish_type, condition, funding_source, priority
            FROM library.replenish
            WHERE book_id = ?
            ORDER BY replenish_date DESC
        """
        rows = self._execute_query(sql, (book_id,))
        return [self._row_to_replenishment(row) for row in rows]

    def search_replenish(
        self,
        book_id: str | None = None,
        supplier: Supplier | str | None = None,
        replenish_type: ReplenishType | str | None = None,
        condition: BookCondition | str | None = None,
        funding_source: FundingSource | str | None = None,
        priority: Priority | str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
    ) -> list[Replenishment]:
        """Search replenishment records with optional filters."""
        sql = """
            SELECT replenish_id, book_id, replenish_date, quantity, unit_cost, total_cost,
                   discount_pct, supplier, replenish_type, condition, funding_source, priority
            FROM library.replenish
            WHERE 1=1
        """
        params: list[Any] = []

        if book_id is not None:
            sql += " AND book_id = ?"
            params.append(book_id)

        if supplier is not None:
            supplier_val = supplier.value if isinstance(supplier, Supplier) else supplier
            sql += " AND supplier = ?"
            params.append(supplier_val)

        if replenish_type is not None:
            type_val = (
                replenish_type.value
                if isinstance(replenish_type, ReplenishType)
                else replenish_type
            )
            sql += " AND replenish_type = ?"
            params.append(type_val)

        if condition is not None:
            cond_val = condition.value if isinstance(condition, BookCondition) else condition
            sql += " AND condition = ?"
            params.append(cond_val)

        if funding_source is not None:
            fund_val = (
                funding_source.value
                if isinstance(funding_source, FundingSource)
                else funding_source
            )
            sql += " AND funding_source = ?"
            params.append(fund_val)

        if priority is not None:
            prio_val = priority.value if isinstance(priority, Priority) else priority
            sql += " AND priority = ?"
            params.append(prio_val)

        if date_from is not None:
            sql += " AND replenish_date >= ?"
            params.append(date_from.isoformat())

        if date_to is not None:
            sql += " AND replenish_date <= ?"
            params.append(date_to.isoformat())

        sql += " ORDER BY replenish_date DESC LIMIT ?"
        params.append(limit)

        rows = self._execute_query(sql, tuple(params))
        return [self._row_to_replenishment(row) for row in rows]

    def get_replenish_stats(self) -> dict[str, Any]:
        """Get aggregate statistics about replenishment."""
        # Get totals
        totals_result = self._execute_query("""
            SELECT
                COUNT(*) as total_records,
                SUM(total_cost) as total_cost,
                SUM(quantity) as total_units,
                AVG(total_cost) as avg_cost,
                COUNT(DISTINCT book_id) as unique_books
            FROM library.replenish
        """)
        totals = totals_result[0]

        # By supplier
        supplier_result = self._execute_query("""
            SELECT supplier, SUM(total_cost) as cost, COUNT(*) as count
            FROM library.replenish
            GROUP BY supplier
        """)
        by_supplier = {
            row[0]: {"cost": float(row[1]) if row[1] is not None else 0.0, "count": row[2]}  # type: ignore[arg-type]
            for row in supplier_result
        }

        # By type
        type_result = self._execute_query("""
            SELECT replenish_type, SUM(total_cost) as cost, COUNT(*) as count
            FROM library.replenish
            GROUP BY replenish_type
        """)
        by_type = {
            row[0]: {"cost": float(row[1]) if row[1] is not None else 0.0, "count": row[2]}  # type: ignore[arg-type]
            for row in type_result
        }

        # By funding source
        funding_result = self._execute_query("""
            SELECT funding_source, SUM(total_cost) as cost, COUNT(*) as count
            FROM library.replenish
            GROUP BY funding_source
        """)
        by_funding = {
            row[0]: {"cost": float(row[1]) if row[1] is not None else 0.0, "count": row[2]}  # type: ignore[arg-type]
            for row in funding_result
        }

        # By condition
        condition_result = self._execute_query("""
            SELECT condition, SUM(total_cost) as cost, COUNT(*) as count
            FROM library.replenish
            GROUP BY condition
        """)
        by_condition = {
            row[0]: {"cost": float(row[1]) if row[1] is not None else 0.0, "count": row[2]}  # type: ignore[arg-type]
            for row in condition_result
        }

        return {
            "total_records": totals[0],
            "total_cost": float(totals[1]) if totals[1] else 0.0,  # type: ignore[arg-type]
            "total_units": totals[2] if totals[2] else 0,
            "avg_cost": float(totals[3]) if totals[3] else 0.0,  # type: ignore[arg-type]
            "unique_books": totals[4] if totals[4] else 0,
            "by_supplier": by_supplier,
            "by_type": by_type,
            "by_funding": by_funding,
            "by_condition": by_condition,
        }

    def get_most_replenished_books(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get most replenished books ranked by total quantity added."""
        sql = """
            SELECT
                r.book_id,
                b.title,
                b.author,
                b.category,
                SUM(r.quantity) as total_quantity,
                SUM(r.total_cost) as total_cost,
                COUNT(r.replenish_id) as replenish_count
            FROM library.replenish r
            JOIN library.books b ON r.book_id = b.book_id
            GROUP BY r.book_id, b.title, b.author, b.category
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
                "total_cost": float(row[5]),  # type: ignore[arg-type]
                "replenish_count": row[6],
            }
            for row in rows
        ]

    def get_replenish_by_month(self) -> list[dict[str, Any]]:
        """Get replenishments aggregated by month."""
        sql = """
            SELECT
                strftime(replenish_date, '%Y-%m') as month,
                COUNT(*) as total_records,
                SUM(total_cost) as total_cost,
                SUM(quantity) as total_units
            FROM library.replenish
            GROUP BY strftime(replenish_date, '%Y-%m')
            ORDER BY month
        """
        rows = self._execute_query(sql)
        return [
            {
                "month": row[0],
                "total_records": row[1],
                "total_cost": float(row[2]),  # type: ignore[arg-type]
                "total_units": row[3],
            }
            for row in rows
        ]


def get_replenish_repository(
    db_path: str | None = None, read_only: bool = True
) -> ReplenishRepository:
    """Get a ReplenishRepository instance.

    Factory function that creates a repository with default database path
    if not specified.
    """
    if db_path is None:
        default_path = Path(__file__).parent.parent.parent / "data" / "duckdb" / "chapter2.db"
        db_path = str(default_path)

    return ReplenishRepository(db_path=db_path, read_only=read_only)
