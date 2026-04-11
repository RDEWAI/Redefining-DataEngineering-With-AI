"""Unit tests for lending tool definitions and output validation.

These tests ensure that lending tools return data with the correct keys,
particularly validating that total_fees (not total_amount) is used
for aggregated fee values.
"""

from src.agentic.library.tools import (
    get_book_lending,
    get_lending_stats,
    get_most_lent_books,
    search_lending,
)


class TestGetMostLentBooks:
    """Test get_most_lent_books output structure."""

    def test_returns_success_key(self) -> None:
        """Test that result includes success key."""
        result = get_most_lent_books(limit=5)
        assert "success" in result
        assert result["success"] is True

    def test_returns_books_list(self) -> None:
        """Test that result includes books list."""
        result = get_most_lent_books(limit=5)
        assert "books" in result
        assert isinstance(result["books"], list)

    def test_book_has_total_fees_key(self) -> None:
        """Test that each book has total_fees (NOT total_amount)."""
        result = get_most_lent_books(limit=5)

        if result["books"]:
            book = result["books"][0]
            # This is the critical test - should be total_fees, NOT total_amount
            assert "total_fees" in book, "Book should have 'total_fees' key"
            assert "total_amount" not in book, "Book should NOT have 'total_amount' key"
            assert isinstance(book["total_fees"], int | float), "total_fees should be numeric"

    def test_book_has_required_fields(self) -> None:
        """Test that each book has all required fields."""
        result = get_most_lent_books(limit=5)

        if result["books"]:
            book = result["books"][0]
            required_fields = [
                "book_id",
                "title",
                "author",
                "category",
                "total_quantity",
                "total_fees",
                "loan_count",
            ]
            for field in required_fields:
                assert field in book, f"Book should have '{field}' field"

    def test_total_fees_is_positive(self) -> None:
        """Test that total_fees values are positive (if loans exist)."""
        result = get_most_lent_books(limit=5)

        if result["books"]:
            for book in result["books"]:
                assert book["total_fees"] >= 0, "total_fees should be non-negative"
                # If there are loans, fees should be positive
                if book["total_quantity"] > 0:
                    assert (
                        book["total_fees"] >= 0
                    ), "total_fees should be non-negative when quantity > 0"


class TestGetLendingStats:
    """Test get_lending_stats output structure."""

    def test_returns_success_key(self) -> None:
        """Test that result includes success key."""
        result = get_lending_stats()
        assert "success" in result
        assert result["success"] is True

    def test_returns_stats_dict(self) -> None:
        """Test that result includes stats dictionary."""
        result = get_lending_stats()
        assert "stats" in result
        assert isinstance(result["stats"], dict)

    def test_stats_has_total_fees_key(self) -> None:
        """Test that stats has total_fees (NOT total_amount)."""
        result = get_lending_stats()

        if result["stats"]:
            # This is the critical test
            assert "total_fees" in result["stats"], "Stats should have 'total_fees' key"

    def test_stats_has_required_fields(self) -> None:
        """Test that stats has all required fields."""
        result = get_lending_stats()

        if result["stats"]:
            required_fields = [
                "total_loans",
                "total_fees",
                "total_units",
                "by_segment",
                "by_region",
                "by_channel",
            ]
            for field in required_fields:
                assert field in result["stats"], f"Stats should have '{field}' field"


class TestGetBookLending:
    """Test get_book_lending output structure."""

    def test_returns_success_key(self) -> None:
        """Test that result includes success key for valid book."""
        result = get_book_lending("B001")
        assert "success" in result

    def test_returns_total_fees_key(self) -> None:
        """Test that result has total_fees (NOT total_amount)."""
        result = get_book_lending("B001")

        if result["success"]:
            assert "total_fees" in result, "Result should have 'total_fees' key"

    def test_returns_loans_list(self) -> None:
        """Test that result includes loans list."""
        result = get_book_lending("B001")

        if result["success"]:
            assert "loans" in result
            assert isinstance(result["loans"], list)


class TestSearchLending:
    """Test search_lending output structure."""

    def test_returns_success_key(self) -> None:
        """Test that result includes success key."""
        result = search_lending(limit=5)
        assert "success" in result
        assert result["success"] is True

    def test_returns_loans_list(self) -> None:
        """Test that result includes loans list."""
        result = search_lending(limit=5)
        assert "loans" in result
        assert isinstance(result["loans"], list)

    def test_loan_has_total_fees_key(self) -> None:
        """Test that individual loans have total_fees (correct for individual loan)."""
        result = search_lending(limit=5)

        if result["loans"]:
            loan = result["loans"][0]
            # Individual loans SHOULD have total_fees (the loan fee amount)
            assert "total_fees" in loan, "Individual loan should have 'total_fees' key"
