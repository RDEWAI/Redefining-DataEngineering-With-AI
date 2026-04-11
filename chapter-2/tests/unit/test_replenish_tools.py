"""Unit tests for replenish tool definitions and output validation.

These tests ensure that replenish tools return data with the correct keys,
particularly validating that total_cost (not total_amount) is used
for aggregated cost values.
"""

from src.agentic.library.tools import (
    get_book_replenish,
    get_most_replenished_books,
    get_replenish_stats,
    search_replenish,
)


class TestGetMostReplenishedBooks:
    """Test get_most_replenished_books output structure."""

    def test_returns_success_key(self) -> None:
        result = get_most_replenished_books(limit=5)
        assert "success" in result
        assert result["success"] is True

    def test_returns_books_list(self) -> None:
        result = get_most_replenished_books(limit=5)
        assert "books" in result
        assert isinstance(result["books"], list)

    def test_book_has_total_cost_key(self) -> None:
        """Test that each book has total_cost (NOT total_amount)."""
        result = get_most_replenished_books(limit=5)
        assert len(result["books"]) > 0, "Expected non-empty books list"

        book = result["books"][0]
        assert "total_cost" in book, "Book should have 'total_cost' key"
        assert "total_amount" not in book, "Book should NOT have 'total_amount' key"
        assert isinstance(book["total_cost"], int | float), "total_cost should be numeric"

    def test_book_has_required_fields(self) -> None:
        result = get_most_replenished_books(limit=5)
        assert len(result["books"]) > 0, "Expected non-empty books list"

        book = result["books"][0]
        required_fields = [
            "book_id",
            "title",
            "author",
            "category",
            "total_quantity",
            "total_cost",
            "replenish_count",
        ]
        for field in required_fields:
            assert field in book, f"Book should have '{field}' field"


class TestGetReplenishStats:
    """Test get_replenish_stats output structure."""

    def test_returns_success_key(self) -> None:
        result = get_replenish_stats()
        assert "success" in result
        assert result["success"] is True

    def test_returns_stats_dict(self) -> None:
        result = get_replenish_stats()
        assert "stats" in result
        assert isinstance(result["stats"], dict)

    def test_stats_has_total_cost_key(self) -> None:
        result = get_replenish_stats()
        assert result["stats"] is not None, "Expected non-None stats"
        assert "total_cost" in result["stats"], "Stats should have 'total_cost' key"

    def test_stats_has_required_fields(self) -> None:
        result = get_replenish_stats()
        assert result["stats"] is not None, "Expected non-None stats"

        required_fields = [
            "total_records",
            "total_cost",
            "total_units",
            "by_supplier",
            "by_type",
            "by_funding",
            "by_condition",
        ]
        for field in required_fields:
            assert field in result["stats"], f"Stats should have '{field}' field"


class TestGetBookReplenish:
    """Test get_book_replenish output structure."""

    def test_returns_success_key(self) -> None:
        result = get_book_replenish("B001")
        assert "success" in result

    def test_returns_total_cost_key(self) -> None:
        result = get_book_replenish("B001")
        assert result["success"], f"Expected success, got: {result['message']}"
        assert "total_cost" in result, "Result should have 'total_cost' key"

    def test_returns_replenishments_list(self) -> None:
        result = get_book_replenish("B001")
        assert result["success"], f"Expected success, got: {result['message']}"
        assert "replenishments" in result
        assert isinstance(result["replenishments"], list)


class TestSearchReplenish:
    """Test search_replenish output structure."""

    def test_returns_success_key(self) -> None:
        result = search_replenish(limit=5)
        assert "success" in result
        assert result["success"] is True

    def test_returns_replenishments_list(self) -> None:
        result = search_replenish(limit=5)
        assert "replenishments" in result
        assert isinstance(result["replenishments"], list)

    def test_replenishment_has_total_cost_key(self) -> None:
        result = search_replenish(limit=5)
        assert len(result["replenishments"]) > 0, "Expected non-empty replenishments list"

        rec = result["replenishments"][0]
        assert "total_cost" in rec, "Individual replenishment should have 'total_cost' key"
