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

from .sales_repository import SalesRepository

# Initialize FastMCP server
mcp = FastMCP("LibraryServer")

# Initialize repository with database path from environment
DB_PATH = os.getenv(
    "DB_PATH", str(Path(__file__).parent.parent.parent / "data" / "duckdb" / "chapter2.db")
)
# Use read_only=True to allow concurrent access from multiple MCP connections
repository = BookRepository(DB_PATH, read_only=True)
sales_repository = SalesRepository(db_path=DB_PATH, read_only=True)


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
# Sales Tools - 5 sales operations
# ============================================================================


@mcp.tool()
def search_sales(
    book_id: str | None = None,
    customer_segment: str | None = None,
    region: str | None = None,
    channel: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]] | dict[str, str]:
    """Search sales records with optional filters.

    Args:
        book_id: Filter by book ID (e.g., 'B001')
        customer_segment: Filter by segment (Individual, Corporate, Educational, Government)
        region: Filter by region (Northeast, Southeast, Midwest, West, International)
        channel: Filter by channel (In-Store, Online, Phone Order, Partner)
        limit: Maximum number of results (1-100, default: 20)

    Returns:
        List of matching sales records
    """
    try:
        # Validate limit
        if limit < 1 or limit > 100:
            return {"error": "Limit must be between 1 and 100"}

        sales = sales_repository.search_sales(
            book_id=book_id,
            customer_segment=customer_segment,
            region=region,
            channel=channel,
            limit=limit,
        )

        return [sale.to_dict() for sale in sales]

    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}


@mcp.tool()
def get_book_sales(book_id: str) -> dict[str, Any]:
    """Get all sales for a specific book with summary statistics.

    Args:
        book_id: Book ID (e.g., 'B001')

    Returns:
        Sales records with total units and revenue
    """
    try:
        book = repository.get_book_by_id(book_id)
        if not book:
            return {"error": f"No book found with ID '{book_id}'"}

        sales = sales_repository.get_sales_for_book(book_id)
        sales_list = [sale.to_dict() for sale in sales]

        total_revenue = sum(float(sale.total_amount) for sale in sales)
        total_units = sum(sale.quantity for sale in sales)

        return {
            "book_id": book_id,
            "book_title": book.title,
            "book_author": book.author,
            "sales_count": len(sales),
            "total_units": total_units,
            "total_revenue": round(total_revenue, 2),
            "sales": sales_list,
        }

    except Exception as e:
        return {"error": f"Failed to get book sales: {str(e)}"}


@mcp.tool()
def get_sales_stats() -> dict[str, Any]:
    """Get aggregate statistics about all sales.

    Returns:
        Statistics including total sales, revenue, units, and breakdowns
    """
    try:
        stats = sales_repository.get_sales_stats()
        return {
            "total_sales": stats["total_sales"],
            "total_revenue": round(stats["total_revenue"], 2),
            "total_units": stats["total_units"],
            "avg_order_value": round(stats["avg_order_value"], 2),
            "unique_customers": stats["unique_customers"],
            "by_segment": stats["by_segment"],
            "by_region": stats["by_region"],
            "by_channel": stats["by_channel"],
        }

    except Exception as e:
        return {"error": f"Failed to get sales stats: {str(e)}"}


@mcp.tool()
def get_top_selling_books(limit: int = 10) -> list[dict[str, Any]] | dict[str, str]:
    """Get best-selling books ranked by total quantity sold.

    Args:
        limit: Maximum number of results (1-50, default: 10)

    Returns:
        List of top-selling books with sales statistics
    """
    try:
        if limit < 1 or limit > 50:
            return {"error": "Limit must be between 1 and 50"}

        top_books = sales_repository.get_top_selling_books(limit=limit)
        return top_books

    except Exception as e:
        return {"error": f"Failed to get top selling books: {str(e)}"}


@mcp.tool()
def get_sales_by_month() -> list[dict[str, Any]] | dict[str, str]:
    """Get sales aggregated by month for trend analysis.

    Returns:
        List of monthly sales with totals and revenue
    """
    try:
        monthly_sales = sales_repository.get_sales_by_month()
        return monthly_sales

    except Exception as e:
        return {"error": f"Failed to get sales by month: {str(e)}"}


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


@mcp.resource("library://sales_stats")
def get_sales_stats_resource() -> str:
    """Get aggregate sales statistics.

    Returns:
        JSON with sales totals and breakdowns by segment, region, channel
    """
    try:
        stats = sales_repository.get_sales_stats()
        return json.dumps(stats, indent=2, default=float)

    except Exception as e:
        return json.dumps({"error": f"Failed to get sales stats: {str(e)}"})


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
