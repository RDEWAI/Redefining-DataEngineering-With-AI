"""Interactive MCP Client for Library Server.

Demonstrates MCP capabilities by connecting to the library server
and allowing users to explore tools, resources, and run queries.

Usage:
    python -m src.mcp.client
    # or
    make mcp-client
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# Add chapter-3 to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agentic.library.domain import BookStatus, Category
from src.agentic.library.repository import BookRepository

# Database path
DB_PATH = os.getenv(
    "DB_PATH",
    str(Path(__file__).parent.parent.parent / "data" / "duckdb" / "chapter3.db"),
)


class MCPClient:
    """Interactive client for MCP server capabilities."""

    def __init__(self):
        """Initialize the MCP client."""
        self.repository = BookRepository(DB_PATH, read_only=True)
        self.tools = self._define_tools()
        self.resources = self._define_resources()

    def _define_tools(self) -> dict[str, dict[str, Any]]:
        """Define available MCP tools with their metadata."""
        return {
            "search_books": {
                "description": "Search books by title, author, or keyword",
                "parameters": {
                    "query": "Search query (required)",
                    "category": "Optional: Programming, History, Science, Fiction, Thriller",
                    "limit": "Max results (1-50, default: 10)",
                },
                "example": 'search_books query="Python"',
            },
            "get_book_details": {
                "description": "Get complete details for a specific book",
                "parameters": {"book_id": "Book ID (e.g., 'B001')"},
                "example": "get_book_details book_id=B001",
            },
            "check_availability": {
                "description": "Check if a book is available",
                "parameters": {"book_id": "Book ID to check"},
                "example": "check_availability book_id=B001",
            },
            "list_by_category": {
                "description": "List all books in a category",
                "parameters": {
                    "category": "Category (required)",
                    "status": "Optional: Present, Missing, Checked Out",
                },
                "example": "list_by_category category=Programming",
            },
            "list_by_status": {
                "description": "List books by availability status",
                "parameters": {
                    "status": "Status: Present, Missing, Checked Out",
                    "category": "Optional category filter",
                },
                "example": "list_by_status status=Missing",
            },
            "locate_book": {
                "description": "Get physical location of a book",
                "parameters": {"book_id": "Book ID to locate"},
                "example": "locate_book book_id=B001",
            },
            "find_books_in_cabinet": {
                "description": "List books in a specific cabinet",
                "parameters": {
                    "cabinet": "Cabinet number (required)",
                    "rack": "Optional rack number",
                },
                "example": "find_books_in_cabinet cabinet=1",
            },
            "get_weak_signal_books": {
                "description": "Get books with weak RFID signals",
                "parameters": {"threshold": "Signal threshold in dBm (default: -55)"},
                "example": "get_weak_signal_books threshold=-50",
            },
        }

    def _define_resources(self) -> dict[str, dict[str, str]]:
        """Define available MCP resources."""
        return {
            "library://stats": {
                "description": "Aggregate library statistics",
                "example": "resource stats",
            },
            "library://missing_books": {
                "description": "List of all missing books",
                "example": "resource missing_books",
            },
            "library://location_map": {
                "description": "Location map with book counts",
                "example": "resource location_map",
            },
        }

    def show_status(self) -> None:
        """Display MCP server status and capabilities."""
        print("\n" + "=" * 60)
        print("MCP Library Server Status")
        print("=" * 60)

        # Check database connection
        try:
            stats = self.repository.get_library_stats()
            print(f"\n[OK] Database Connected: {DB_PATH}")
            print(f"[OK] Total Books: {stats['total_books']}")
            print(f"[OK] Categories: {len(stats['by_category'])}")
            print("\nBook Status Distribution:")
            for status, count in stats["by_status"].items():
                icon = "[P]" if status == "Present" else "[M]" if status == "Missing" else "[O]"
                print(f"   {icon} {status}: {count}")
        except Exception as e:
            print(f"\n[ERROR] Database Error: {e}")
            print("  Run 'make load-data' to initialize the database")
            return

        print(f"\nAvailable Tools: {len(self.tools)}")
        print(f"Available Resources: {len(self.resources)}")
        print("=" * 60)

    def show_tools(self) -> None:
        """Display all available MCP tools."""
        print("\n" + "=" * 60)
        print("Available MCP Tools")
        print("=" * 60)

        for name, info in self.tools.items():
            print(f"\n* {name}")
            print(f"   {info['description']}")
            print("   Parameters:")
            for param, desc in info["parameters"].items():
                print(f"      - {param}: {desc}")
            print(f"   Example: {info['example']}")

        print("\n" + "=" * 60)

    def show_resources(self) -> None:
        """Display all available MCP resources."""
        print("\n" + "=" * 60)
        print("Available MCP Resources")
        print("=" * 60)

        for uri, info in self.resources.items():
            print(f"\n* {uri}")
            print(f"   {info['description']}")
            print(f"   Usage: {info['example']}")

        print("\n" + "=" * 60)

    def execute_tool(self, tool_name: str, **kwargs: Any) -> dict[str, Any] | list[dict[str, Any]]:
        """Execute an MCP tool and return results."""
        if tool_name == "search_books":
            return self._search_books(**kwargs)
        elif tool_name == "get_book_details":
            return self._get_book_details(**kwargs)
        elif tool_name == "check_availability":
            return self._check_availability(**kwargs)
        elif tool_name == "list_by_category":
            return self._list_by_category(**kwargs)
        elif tool_name == "list_by_status":
            return self._list_by_status(**kwargs)
        elif tool_name == "locate_book":
            return self._locate_book(**kwargs)
        elif tool_name == "find_books_in_cabinet":
            return self._find_books_in_cabinet(**kwargs)
        elif tool_name == "get_weak_signal_books":
            return self._get_weak_signal_books(**kwargs)
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    def get_resource(self, resource_name: str) -> str:
        """Get an MCP resource."""
        if resource_name in ("stats", "library://stats"):
            return json.dumps(self.repository.get_library_stats(), indent=2)
        elif resource_name in ("missing_books", "library://missing_books"):
            books = self.repository.list_by_status(BookStatus.MISSING)
            return json.dumps([b.to_dict() for b in books], indent=2)
        elif resource_name in ("location_map", "library://location_map"):
            result = self.repository.conn.execute("""
                SELECT cabinet, rack, row, COUNT(*) as book_count
                FROM library.books
                GROUP BY cabinet, rack, row
                ORDER BY cabinet, rack, row
                LIMIT 20
            """).fetchall()
            locations = [
                {"cabinet": r[0], "rack": r[1], "row": r[2], "book_count": r[3]}
                for r in result
            ]
            return json.dumps(locations, indent=2)
        else:
            return json.dumps({"error": f"Unknown resource: {resource_name}"})

    # Tool implementations
    def _search_books(
        self, query: str, category: str | None = None, limit: int = 10
    ) -> list[dict[str, Any]] | dict[str, str]:
        try:
            cat_enum = None
            if category:
                cat_enum = Category[category.upper().replace(" ", "_")]
            books = self.repository.search_books(query, cat_enum)[:limit]
            return [b.to_dict() for b in books]
        except Exception as e:
            return {"error": str(e)}

    def _get_book_details(self, book_id: str) -> dict[str, Any]:
        book = self.repository.get_book_by_id(book_id)
        if book is None:
            return {"error": f"Book '{book_id}' not found"}
        return book.to_dict()

    def _check_availability(self, book_id: str) -> dict[str, Any]:
        book = self.repository.get_book_by_id(book_id)
        if book is None:
            return {"error": f"Book '{book_id}' not found"}
        return {
            "book_id": book.book_id,
            "title": book.title,
            "available": book.is_available,
            "status": book.status.value,
            "location": str(book.location),
        }

    def _list_by_category(
        self, category: str, status: str | None = None
    ) -> list[dict[str, Any]] | dict[str, str]:
        try:
            cat_enum = Category[category.upper().replace(" ", "_")]
            status_enum = BookStatus(status) if status else None
            books = self.repository.list_by_category(cat_enum, status_enum)
            return [b.to_dict() for b in books]
        except Exception as e:
            return {"error": str(e)}

    def _list_by_status(
        self, status: str, category: str | None = None
    ) -> list[dict[str, Any]] | dict[str, str]:
        try:
            status_enum = BookStatus(status)
            cat_enum = Category[category.upper().replace(" ", "_")] if category else None
            books = self.repository.list_by_status(status_enum, cat_enum)
            return [b.to_dict() for b in books]
        except Exception as e:
            return {"error": str(e)}

    def _locate_book(self, book_id: str) -> dict[str, Any]:
        book = self.repository.get_book_by_id(book_id)
        if book is None:
            return {"error": f"Book '{book_id}' not found"}
        return {
            "book_id": book.book_id,
            "title": book.title,
            "cabinet": book.location.cabinet,
            "rack": book.location.rack,
            "row": book.location.row,
            "location": str(book.location),
        }

    def _find_books_in_cabinet(
        self, cabinet: int, rack: int | None = None
    ) -> list[dict[str, Any]]:
        books = self.repository.find_books_in_cabinet(int(cabinet), int(rack) if rack else None)
        return [b.to_dict() for b in books]

    def _get_weak_signal_books(
        self, threshold: float = -55.0
    ) -> list[dict[str, Any]]:
        books = self.repository.get_weak_signal_books(float(threshold))
        return [b.to_dict() for b in books]

    def parse_command(self, cmd: str) -> tuple[str, dict[str, Any]]:
        """Parse a command string into tool name and parameters."""
        parts = cmd.strip().split(maxsplit=1)
        if not parts:
            return "", {}

        tool_name = parts[0]
        kwargs: dict[str, Any] = {}

        if len(parts) > 1:
            # Parse key=value pairs
            param_str = parts[1]
            # Handle quoted values
            matches = re.findall(r'(\w+)=(?:"([^"]+)"|(\S+))', param_str)
            for match in matches:
                key = match[0]
                value = match[1] if match[1] else match[2]
                # Try to convert to int/float if applicable
                try:
                    value = int(value)
                except ValueError:
                    try:
                        value = float(value)
                    except ValueError:
                        pass
                kwargs[key] = value

        return tool_name, kwargs

    def run_interactive(self) -> None:
        """Run interactive MCP client session."""
        print("\n" + "=" * 60)
        print("MCP Library Client - Interactive Mode")
        print("=" * 60)
        print("\nCommands:")
        print("  /status    - Show server status")
        print("  /tools     - List all available tools")
        print("  /resources - List all available resources")
        print("  /help      - Show this help message")
        print("  /quit      - Exit")
        print("\nTool Usage:")
        print('  search_books query="Python"')
        print("  get_book_details book_id=B001")
        print("  list_by_status status=Missing")
        print("\nResource Usage:")
        print("  resource stats")
        print("  resource missing_books")
        print("=" * 60)

        # Show initial status
        self.show_status()

        while True:
            try:
                user_input = input("\n> ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ("/quit", "/exit", "/q"):
                    print("\nGoodbye!")
                    break

                if user_input.lower() == "/status":
                    self.show_status()
                    continue

                if user_input.lower() == "/tools":
                    self.show_tools()
                    continue

                if user_input.lower() == "/resources":
                    self.show_resources()
                    continue

                if user_input.lower() == "/help":
                    print("\nCommands:")
                    print("  /status    - Show server status")
                    print("  /tools     - List all available tools")
                    print("  /resources - List all available resources")
                    print("  /quit      - Exit")
                    print("\nExample tool calls:")
                    print('  search_books query="Python" category=Programming')
                    print("  list_by_status status=Missing")
                    print("  get_book_details book_id=B001")
                    continue

                # Check for resource command
                if user_input.lower().startswith("resource "):
                    resource_name = user_input[9:].strip()
                    print(f"\nResource: {resource_name}")
                    print("-" * 40)
                    result = self.get_resource(resource_name)
                    print(result)
                    continue

                # Parse and execute tool command
                tool_name, kwargs = self.parse_command(user_input)

                if tool_name not in self.tools:
                    print(f"\n[ERROR] Unknown tool: {tool_name}")
                    print("   Use /tools to see available tools")
                    continue

                print(f"\nExecuting: {tool_name}")
                if kwargs:
                    print(f"   Parameters: {kwargs}")
                print("-" * 40)

                result = self.execute_tool(tool_name, **kwargs)

                if isinstance(result, dict) and "error" in result:
                    print(f"[ERROR] {result['error']}")
                elif isinstance(result, list):
                    print(f"Found {len(result)} results:")
                    for i, item in enumerate(result[:5], 1):
                        if "title" in item:
                            status_icon = (
                                "[P]"
                                if item.get("status") == "Present"
                                else "[M]" if item.get("status") == "Missing" else "[O]"
                            )
                            print(
                                f"  {i}. {status_icon} [{item.get('book_id', 'N/A')}] "
                                f"{item.get('title', 'N/A')} by {item.get('author', 'N/A')}"
                            )
                        else:
                            print(f"  {i}. {json.dumps(item)}")
                    if len(result) > 5:
                        print(f"  ... and {len(result) - 5} more")
                else:
                    print(json.dumps(result, indent=2))

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"\n[ERROR] {e}")


def main():
    """Entry point for MCP client."""
    client = MCPClient()
    client.run_interactive()


if __name__ == "__main__":
    main()
