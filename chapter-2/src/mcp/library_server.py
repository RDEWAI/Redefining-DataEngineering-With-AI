"""Library MCP Server using FastMCP.

Exposes library operations as MCP tools, resources, and prompts for
integration with Claude Desktop and other MCP clients.

Usage:
    # Production mode
    make mcp-server

    # Development mode with MCP Inspector
    make mcp-dev
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, cast

from fastmcp import Context, FastMCP

# Add chapter-2 directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agentic.library.domain import BookStatus, Category
from src.agentic.library.repository import BookRepository

from .lending_repository import LendingRepository
from .replenish_repository import ReplenishRepository

# Initialize FastMCP server
mcp = FastMCP("LibraryServer")

# Initialize repository with database path from environment
DB_PATH = os.getenv(
    "DB_PATH", str(Path(__file__).parent.parent.parent / "data" / "duckdb" / "chapter2.db")
)
# Use read_only=True to allow concurrent access from multiple MCP connections
repository = BookRepository(DB_PATH, read_only=True)
lending_repository = LendingRepository(db_path=DB_PATH, read_only=True)
replenish_repository = ReplenishRepository(db_path=DB_PATH, read_only=True)


# ============================================================================
# Tools - 8 library operations
# ============================================================================


@mcp.tool()
def search_books(
    query: str, category: str | None = None, limit: int = 10
) -> list[dict[str, Any]] | dict[str, str]:
    """Search books by title, author, or keyword.

    Args:
        query: Search query to match against title or author
        category: Optional category filter (Programming, History, Science, Fiction, Thriller)
        limit: Maximum number of results to return (1-50, default: 10)

    Returns:
        List of matching books with availability status
    """
    try:
        # Validate category if provided
        if category:
            try:
                cat_enum = Category[category.upper().replace(" ", "_")]
            except KeyError:
                return {
                    "error": f"Invalid category '{category}'. Valid options: Programming, History, Science, Fiction, Thriller"
                }
        else:
            cat_enum = None

        # Validate limit
        if limit < 1 or limit > 50:
            return {"error": "Limit must be between 1 and 50"}

        # Search books
        books = repository.search_books(query, cat_enum)

        # Limit results
        books = books[:limit]

        # Convert to dict format
        return [book.to_dict() for book in books]

    except Exception as e:
        return {"error": f"Search failed: {str(e)}. Please check your query and try again."}


@mcp.tool()
def get_book_details(book_id: str) -> dict[str, Any]:
    """Get complete details for a specific book including location and status.

    Args:
        book_id: Book ID (e.g., 'B001')

    Returns:
        Book details with location and status
    """
    try:
        book = repository.get_book_by_id(book_id)

        if book is None:
            return {
                "error": f"Book with ID '{book_id}' not found. Please check the book ID and try again."
            }

        return cast(dict[str, Any], book.to_dict())

    except Exception as e:
        return {"error": f"Failed to get book details: {str(e)}"}


@mcp.tool()
def check_availability(book_id: str) -> dict[str, Any]:
    """Check if a book is available and get its current location.

    Args:
        book_id: Book ID to check

    Returns:
        Availability status and location
    """
    try:
        book = repository.get_book_by_id(book_id)

        if book is None:
            return {"error": f"Book with ID '{book_id}' not found."}

        return {
            "book_id": book.book_id,
            "title": book.title,
            "available": book.is_available,
            "status": book.status.value,
            "location": str(book.location),
            "signal_strength": book.signal_strength,
        }

    except Exception as e:
        return {"error": f"Failed to check availability: {str(e)}"}


@mcp.tool()
def list_by_category(
    category: str, status: str | None = None
) -> list[dict[str, Any]] | dict[str, str]:
    """List all books in a specific category.

    Args:
        category: Category to filter by (Programming, History, Science, Fiction, Thriller)
        status: Optional status filter (Present, Missing, Checked Out)

    Returns:
        List of books in the specified category
    """
    try:
        # Validate category
        try:
            cat_enum = Category[category.upper().replace(" ", "_")]
        except KeyError:
            return {
                "error": f"Invalid category '{category}'. Valid options: Programming, History, Science, Fiction, Thriller"
            }

        # Validate status if provided
        status_enum = None
        if status:
            try:
                status_enum = BookStatus(status)
            except ValueError:
                return {
                    "error": f"Invalid status '{status}'. Valid options: Present, Missing, Checked Out"
                }

        books = repository.list_by_category(cat_enum, status_enum)
        return [book.to_dict() for book in books]

    except Exception as e:
        return {"error": f"Failed to list books by category: {str(e)}"}


@mcp.tool()
def list_by_status(
    status: str, category: str | None = None
) -> list[dict[str, Any]] | dict[str, str]:
    """List all books with a specific availability status.

    Args:
        status: Status to filter by (Present, Missing, Checked Out)
        category: Optional category filter

    Returns:
        List of books with the specified status
    """
    try:
        # Validate status
        try:
            status_enum = BookStatus(status)
        except ValueError:
            return {
                "error": f"Invalid status '{status}'. Valid options: Present, Missing, Checked Out"
            }

        # Validate category if provided
        cat_enum = None
        if category:
            try:
                cat_enum = Category[category.upper().replace(" ", "_")]
            except KeyError:
                return {
                    "error": f"Invalid category '{category}'. Valid options: Programming, History, Science, Fiction, Thriller"
                }

        books = repository.list_by_status(status_enum, cat_enum)
        return [book.to_dict() for book in books]

    except Exception as e:
        return {"error": f"Failed to list books by status: {str(e)}"}


@mcp.tool()
def locate_book(book_id: str) -> dict[str, Any]:
    """Get the physical location of a book (Cabinet, Rack, Row).

    Args:
        book_id: Book ID to locate

    Returns:
        Book location details
    """
    try:
        book = repository.get_book_by_id(book_id)

        if book is None:
            return {"error": f"Book with ID '{book_id}' not found."}

        return {
            "book_id": book.book_id,
            "title": book.title,
            "cabinet": book.location.cabinet,
            "rack": book.location.rack,
            "row": book.location.row,
            "location_description": str(book.location),
        }

    except Exception as e:
        return {"error": f"Failed to locate book: {str(e)}"}


@mcp.tool()
def find_books_in_cabinet(
    cabinet: int, rack: int | None = None
) -> list[dict[str, Any]] | dict[str, str]:
    """List all books in a specific cabinet location.

    Args:
        cabinet: Cabinet number
        rack: Optional rack number within cabinet

    Returns:
        List of books in the specified location
    """
    try:
        if cabinet < 1:
            return {"error": "Cabinet number must be 1 or greater."}

        if rack is not None and rack < 1:
            return {"error": "Rack number must be 1 or greater."}

        books = repository.find_books_in_cabinet(cabinet, rack)
        return [book.to_dict() for book in books]

    except Exception as e:
        return {"error": f"Failed to find books in cabinet: {str(e)}"}


@mcp.tool()
def get_weak_signal_books(threshold: float = -55.0) -> list[dict[str, Any]] | dict[str, str]:
    """Get books with weak RFID signal strength that may need maintenance.

    Args:
        threshold: Signal strength threshold in dBm (default: -55)

    Returns:
        List of books with weak signals
    """
    try:
        books = repository.get_weak_signal_books(threshold)
        return [
            {**book.to_dict(), "needs_maintenance": True, "signal_quality": "Weak"}
            for book in books
        ]

    except Exception as e:
        return {"error": f"Failed to get weak signal books: {str(e)}"}


# ============================================================================
# Lending Tools - 5 lending operations
# ============================================================================


@mcp.tool()
def search_lending(
    book_id: str | None = None,
    patron_segment: str | None = None,
    region: str | None = None,
    channel: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]] | dict[str, str]:
    """Search lending records with optional filters.

    Args:
        book_id: Filter by book ID (e.g., 'B001')
        patron_segment: Filter by segment (Individual, Corporate, Educational, Government)
        region: Filter by region (Northeast, Southeast, Midwest, West, International)
        channel: Filter by channel (In-Store, Online, Phone Order, Partner)
        limit: Maximum number of results (1-100, default: 20)

    Returns:
        List of matching lending records
    """
    try:
        # Validate limit
        if limit < 1 or limit > 100:
            return {"error": "Limit must be between 1 and 100"}

        loans = lending_repository.search_lending(
            book_id=book_id,
            patron_segment=patron_segment,
            region=region,
            channel=channel,
            limit=limit,
        )

        return [loan.to_dict() for loan in loans]

    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}


@mcp.tool()
def get_book_lending(book_id: str) -> dict[str, Any]:
    """Get all loans for a specific book with summary statistics.

    Args:
        book_id: Book ID (e.g., 'B001')

    Returns:
        Lending records with total units and fees
    """
    try:
        book = repository.get_book_by_id(book_id)
        if not book:
            return {"error": f"No book found with ID '{book_id}'"}

        loans = lending_repository.get_lending_for_book(book_id)
        loans_list = [loan.to_dict() for loan in loans]

        total_fees = sum(float(loan.total_fees) for loan in loans)
        total_units = sum(loan.quantity for loan in loans)

        return {
            "book_id": book_id,
            "book_title": book.title,
            "book_author": book.author,
            "loan_count": len(loans),
            "total_units": total_units,
            "total_fees": round(total_fees, 2),
            "loans": loans_list,
        }

    except Exception as e:
        return {"error": f"Failed to get book lending: {str(e)}"}


@mcp.tool()
def get_lending_stats() -> dict[str, Any]:
    """Get aggregate statistics about all lending.

    Returns:
        Statistics including total loans, fees, units, and breakdowns
    """
    try:
        stats = lending_repository.get_lending_stats()
        return {
            "total_loans": stats["total_loans"],
            "total_fees": round(stats["total_fees"], 2),
            "total_units": stats["total_units"],
            "avg_loan_fees": round(stats["avg_loan_fees"], 2),
            "unique_patrons": stats["unique_patrons"],
            "by_segment": stats["by_segment"],
            "by_region": stats["by_region"],
            "by_channel": stats["by_channel"],
        }

    except Exception as e:
        return {"error": f"Failed to get lending stats: {str(e)}"}


@mcp.tool()
def get_most_lent_books(limit: int = 10) -> list[dict[str, Any]] | dict[str, str]:
    """Get most lent books ranked by total quantity lent.

    Args:
        limit: Maximum number of results (1-50, default: 10)

    Returns:
        List of most lent books with lending statistics
    """
    try:
        if limit < 1 or limit > 50:
            return {"error": "Limit must be between 1 and 50"}

        top_books = lending_repository.get_most_lent_books(limit=limit)
        return top_books

    except Exception as e:
        return {"error": f"Failed to get most lent books: {str(e)}"}


@mcp.tool()
def get_lending_by_month() -> list[dict[str, Any]] | dict[str, str]:
    """Get lending aggregated by month for trend analysis.

    Returns:
        List of monthly lending with totals and fees
    """
    try:
        monthly_lending = lending_repository.get_lending_by_month()
        return monthly_lending

    except Exception as e:
        return {"error": f"Failed to get lending by month: {str(e)}"}


# ============================================================================
# Replenish Tools - 5 replenish operations
# ============================================================================


@mcp.tool()
def search_replenish(
    book_id: str | None = None,
    supplier: str | None = None,
    replenish_type: str | None = None,
    condition: str | None = None,
    funding_source: str | None = None,
    priority: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]] | dict[str, str]:
    """Search replenishment records with optional filters.

    Args:
        book_id: Filter by book ID (e.g., 'B001')
        supplier: Filter by supplier (Ingram, Baker & Taylor, Brodart, Direct Publisher, Amazon Business)
        replenish_type: Filter by type (New Acquisition, Replacement, Restock, Donation, Return Processing)
        condition: Filter by condition (New, Refurbished, Used - Good, Used - Fair)
        funding_source: Filter by funding (Operating Budget, Grant, Donation Fund, Special Collection, Emergency Fund)
        priority: Filter by priority (Urgent, High, Normal, Low)
        limit: Maximum number of results (1-100, default: 20)

    Returns:
        List of matching replenishment records
    """
    try:
        if limit < 1 or limit > 100:
            return {"error": "Limit must be between 1 and 100"}

        records = replenish_repository.search_replenish(
            book_id=book_id,
            supplier=supplier,
            replenish_type=replenish_type,
            condition=condition,
            funding_source=funding_source,
            priority=priority,
            limit=limit,
        )

        return [rec.to_dict() for rec in records]

    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}


@mcp.tool()
def get_book_replenish(book_id: str) -> dict[str, Any]:
    """Get all replenishments for a specific book with summary statistics.

    Args:
        book_id: Book ID (e.g., 'B001')

    Returns:
        Replenishment records with total units and cost
    """
    try:
        book = repository.get_book_by_id(book_id)
        if not book:
            return {"error": f"No book found with ID '{book_id}'"}

        records = replenish_repository.get_replenish_for_book(book_id)
        records_list = [rec.to_dict() for rec in records]

        total_cost = sum(float(rec.total_cost) for rec in records)
        total_units = sum(rec.quantity for rec in records)

        return {
            "book_id": book_id,
            "book_title": book.title,
            "book_author": book.author,
            "replenish_count": len(records),
            "total_units": total_units,
            "total_cost": round(total_cost, 2),
            "replenishments": records_list,
        }

    except Exception as e:
        return {"error": f"Failed to get book replenishments: {str(e)}"}


@mcp.tool()
def get_replenish_stats() -> dict[str, Any]:
    """Get aggregate statistics about all replenishments.

    Returns:
        Statistics including total records, cost, units, and breakdowns
    """
    try:
        stats = replenish_repository.get_replenish_stats()
        return {
            "total_records": stats["total_records"],
            "total_cost": round(stats["total_cost"], 2),
            "total_units": stats["total_units"],
            "avg_cost": round(stats["avg_cost"], 2),
            "unique_books": stats["unique_books"],
            "by_supplier": stats["by_supplier"],
            "by_type": stats["by_type"],
            "by_funding": stats["by_funding"],
            "by_condition": stats["by_condition"],
        }

    except Exception as e:
        return {"error": f"Failed to get replenish stats: {str(e)}"}


@mcp.tool()
def get_most_replenished_books(limit: int = 10) -> list[dict[str, Any]] | dict[str, str]:
    """Get most replenished books ranked by total quantity added.

    Args:
        limit: Maximum number of results (1-50, default: 10)

    Returns:
        List of most replenished books with statistics
    """
    try:
        if limit < 1 or limit > 50:
            return {"error": "Limit must be between 1 and 50"}

        top_books = replenish_repository.get_most_replenished_books(limit=limit)
        return top_books

    except Exception as e:
        return {"error": f"Failed to get most replenished books: {str(e)}"}


@mcp.tool()
def get_replenish_by_month() -> list[dict[str, Any]] | dict[str, str]:
    """Get replenishments aggregated by month for trend analysis.

    Returns:
        List of monthly replenishments with totals and costs
    """
    try:
        monthly = replenish_repository.get_replenish_by_month()
        return monthly

    except Exception as e:
        return {"error": f"Failed to get replenish by month: {str(e)}"}


# ============================================================================
# Resources - 4 library data resources
# ============================================================================


@mcp.resource("library://stats")
def get_library_stats() -> str:
    """Get aggregate library statistics.

    Returns:
        JSON with book counts by category and status
    """
    try:
        stats = repository.get_library_stats()
        return json.dumps(stats, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Failed to get library stats: {str(e)}"})


@mcp.resource("library://missing_books")
def get_missing_books() -> str:
    """Get list of all missing books.

    Returns:
        JSON list of missing books, ordered by last seen timestamp
    """
    try:
        books = repository.list_by_status(BookStatus.MISSING)
        # Sort by timestamp (oldest first)
        books_sorted = sorted(books, key=lambda b: b.timestamp)
        return json.dumps([book.to_dict() for book in books_sorted], indent=2)

    except Exception as e:
        return json.dumps({"error": f"Failed to get missing books: {str(e)}"})


@mcp.resource("library://location_map")
def get_location_map() -> str:
    """Get location map with book counts.

    Returns:
        JSON list of distinct Cabinet/Rack/Row combinations with book counts
    """
    try:
        # Query to get location counts
        conn = repository.conn
        result = conn.execute("""
            SELECT
                cabinet,
                rack,
                row,
                COUNT(*) as book_count,
                STRING_AGG(book_id, ', ') as book_ids
            FROM library.books
            GROUP BY cabinet, rack, row
            ORDER BY cabinet, rack, row
        """).fetchall()

        locations = [
            {
                "cabinet": row[0],
                "rack": row[1],
                "row": row[2],
                "book_count": row[3],
                "book_ids": row[4],
            }
            for row in result
        ]

        return json.dumps(locations, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Failed to get location map: {str(e)}"})


@mcp.resource("library://lending_stats")
def get_lending_stats_resource() -> str:
    """Get aggregate lending statistics.

    Returns:
        JSON with lending totals and breakdowns by segment, region, channel
    """
    try:
        stats = lending_repository.get_lending_stats()
        return json.dumps(stats, indent=2, default=float)

    except Exception as e:
        return json.dumps({"error": f"Failed to get lending stats: {str(e)}"})


@mcp.resource("library://replenish_stats")
def get_replenish_stats_resource() -> str:
    """Get aggregate replenishment statistics.

    Returns:
        JSON with replenish totals and breakdowns by supplier, type, funding, condition
    """
    try:
        stats = replenish_repository.get_replenish_stats()
        return json.dumps(stats, indent=2, default=float)

    except Exception as e:
        return json.dumps({"error": f"Failed to get replenish stats: {str(e)}"})


# ============================================================================
# Prompts - 2 prompt templates
# ============================================================================


@mcp.prompt()
def book_search(query: str) -> str:
    """Generate a natural language book search query.

    Args:
        query: What the user is looking for

    Returns:
        Formatted search prompt
    """
    return f"""Please search the library catalog for books matching: "{query}"

Use the search_books tool to find relevant books. Consider:
- Title matches
- Author matches
- Related categories
- Availability status

After finding results, you can use get_book_details to get more information
about specific books, or check_availability to verify if a book is available
for checkout."""


@mcp.prompt()
def library_status_report(focus: str | None = None) -> str:
    """Generate a status report for the library.

    Args:
        focus: Area to focus on (availability, maintenance, categories)

    Returns:
        Formatted status report prompt
    """
    base_prompt = """Please generate a comprehensive library status report.

Use the following resources and tools:
1. library://stats - Get overall statistics
2. library://missing_books - List missing books
3. get_weak_signal_books - Check for maintenance needs

"""

    if focus == "availability":
        base_prompt += """Focus on:
- Books available for checkout
- Checked out books
- Missing books that need to be located
"""
    elif focus == "maintenance":
        base_prompt += """Focus on:
- Books with weak RFID signals
- Missing books
- Books that may need attention
"""
    elif focus == "categories":
        base_prompt += """Focus on:
- Distribution of books across categories
- Category-specific availability
- Popular categories
"""
    else:
        base_prompt += """Provide a balanced overview covering availability, maintenance, and category distribution."""

    return base_prompt


# ============================================================================
# Context and Logging Support
# ============================================================================


@mcp.tool()
async def search_books_with_logging(
    query: str, category: str | None = None, limit: int = 10, ctx: Context | None = None
) -> list[dict[str, Any]] | dict[str, str]:
    """Search books with progress logging (example of Context usage).

    This is a demonstration of how to use FastMCP's Context for logging.
    """
    if ctx:
        await ctx.info(f"Searching for books matching: {query}")

        if category:
            await ctx.info(f"Filtering by category: {category}")

    result: list[dict[str, Any]] | dict[str, str] = search_books(query, category, limit)  # type: ignore[operator]  # FastMCP decorated function

    if ctx:
        if isinstance(result, list):
            await ctx.info(f"Found {len(result)} matching books")
        else:
            await ctx.error("Search failed")

    return result


# ============================================================================
# Server Entry Point
# ============================================================================

if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
