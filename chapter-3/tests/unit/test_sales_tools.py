"""Unit tests for sales tool definitions and output validation.

These tests ensure that sales tools return data with the correct keys,
particularly validating that total_revenue (not total_amount) is used
for aggregated revenue values.
"""

import pytest

from src.agentic.library.tools import (
    get_top_selling_books,
    get_sales_stats,
    get_book_sales,
    search_sales,
)


class TestGetTopSellingBooks:
    """Test get_top_selling_books output structure."""

    def test_returns_success_key(self) -> None:
        """Test that result includes success key."""
        result = get_top_selling_books(limit=5)
        assert "success" in result
        assert result["success"] is True

    def test_returns_books_list(self) -> None:
        """Test that result includes books list."""
        result = get_top_selling_books(limit=5)
        assert "books" in result
        assert isinstance(result["books"], list)

    def test_book_has_total_revenue_key(self) -> None:
        """Test that each book has total_revenue (NOT total_amount)."""
        result = get_top_selling_books(limit=5)

        if result["books"]:
            book = result["books"][0]
            # This is the critical test - should be total_revenue, NOT total_amount
            assert "total_revenue" in book, "Book should have 'total_revenue' key"
            assert "total_amount" not in book, "Book should NOT have 'total_amount' key"
            assert isinstance(book["total_revenue"], (int, float)), "total_revenue should be numeric"

    def test_book_has_required_fields(self) -> None:
        """Test that each book has all required fields."""
        result = get_top_selling_books(limit=5)

        if result["books"]:
            book = result["books"][0]
            required_fields = ["book_id", "title", "author", "category", "total_quantity", "total_revenue", "sale_count"]
            for field in required_fields:
                assert field in book, f"Book should have '{field}' field"

    def test_total_revenue_is_positive(self) -> None:
        """Test that total_revenue values are positive (if sales exist)."""
        result = get_top_selling_books(limit=5)

        if result["books"]:
            for book in result["books"]:
                assert book["total_revenue"] >= 0, "total_revenue should be non-negative"
                # If there are sales, revenue should be positive
                if book["total_quantity"] > 0:
                    assert book["total_revenue"] > 0, "total_revenue should be positive when quantity > 0"


class TestGetSalesStats:
    """Test get_sales_stats output structure."""

    def test_returns_success_key(self) -> None:
        """Test that result includes success key."""
        result = get_sales_stats()
        assert "success" in result
        assert result["success"] is True

    def test_returns_stats_dict(self) -> None:
        """Test that result includes stats dictionary."""
        result = get_sales_stats()
        assert "stats" in result
        assert isinstance(result["stats"], dict)

    def test_stats_has_total_revenue_key(self) -> None:
        """Test that stats has total_revenue (NOT total_amount)."""
        result = get_sales_stats()

        if result["stats"]:
            # This is the critical test
            assert "total_revenue" in result["stats"], "Stats should have 'total_revenue' key"

    def test_stats_has_required_fields(self) -> None:
        """Test that stats has all required fields."""
        result = get_sales_stats()

        if result["stats"]:
            required_fields = ["total_sales", "total_revenue", "total_units", "by_segment", "by_region", "by_channel"]
            for field in required_fields:
                assert field in result["stats"], f"Stats should have '{field}' field"


class TestGetBookSales:
    """Test get_book_sales output structure."""

    def test_returns_success_key(self) -> None:
        """Test that result includes success key for valid book."""
        result = get_book_sales("B001")
        assert "success" in result

    def test_returns_total_revenue_key(self) -> None:
        """Test that result has total_revenue (NOT total_amount)."""
        result = get_book_sales("B001")

        if result["success"]:
            assert "total_revenue" in result, "Result should have 'total_revenue' key"

    def test_returns_sales_list(self) -> None:
        """Test that result includes sales list."""
        result = get_book_sales("B001")

        if result["success"]:
            assert "sales" in result
            assert isinstance(result["sales"], list)


class TestSearchSales:
    """Test search_sales output structure."""

    def test_returns_success_key(self) -> None:
        """Test that result includes success key."""
        result = search_sales(limit=5)
        assert "success" in result
        assert result["success"] is True

    def test_returns_sales_list(self) -> None:
        """Test that result includes sales list."""
        result = search_sales(limit=5)
        assert "sales" in result
        assert isinstance(result["sales"], list)

    def test_sale_has_total_amount_key(self) -> None:
        """Test that individual sales have total_amount (correct for individual sale)."""
        result = search_sales(limit=5)

        if result["sales"]:
            sale = result["sales"][0]
            # Individual sales SHOULD have total_amount (the sale amount)
            # Only aggregated results should have total_revenue
            assert "total_amount" in sale, "Individual sale should have 'total_amount' key"
