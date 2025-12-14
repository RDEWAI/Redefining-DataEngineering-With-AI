"""Integration tests for MCP server with in-memory transport.

Tests verify end-to-end MCP server functionality using FastMCP's
Client with direct FastMCP server transport.
"""

import json
import sys
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from fastmcp import Client


@pytest.fixture
def test_db_path(tmp_path):
    """Create a temporary test database."""
    db_path = tmp_path / "test_library.db"

    # Create test database with sample data
    import duckdb

    conn = duckdb.connect(str(db_path))

    # Create schema
    conn.execute("CREATE SCHEMA IF NOT EXISTS library")

    # Create table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS library.books (
            book_id VARCHAR PRIMARY KEY,
            title VARCHAR NOT NULL,
            author VARCHAR NOT NULL,
            category VARCHAR NOT NULL,
            cabinet INTEGER NOT NULL,
            rack INTEGER NOT NULL,
            row INTEGER NOT NULL,
            signal_strength FLOAT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            status VARCHAR NOT NULL
        )
    """)

    # Insert test data
    test_books = [
        ("B001", "Python Programming", "John Smith", "Programming", 1, 1, 1, -45.2, "2025-01-15 10:30:00", "Present"),
        ("B002", "Advanced Python", "Jane Doe", "Programming", 1, 1, 2, -60.5, "2025-01-15 10:31:00", "Present"),
        ("B003", "World History", "Bob Johnson", "History", 2, 1, 1, -50.0, "2025-01-15 09:00:00", "Checked Out"),
        ("B004", "Science 101", "Alice Brown", "Science", 3, 2, 5, -70.0, "2025-01-14 08:00:00", "Missing"),
    ]

    for book in test_books:
        conn.execute("""
            INSERT INTO library.books VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, book)

    conn.close()
    return str(db_path)


@pytest.fixture
def mcp_server(test_db_path, monkeypatch):
    """Create an MCP server instance with test database."""
    # Set database path in environment
    monkeypatch.setenv('DB_PATH', test_db_path)

    # Import server (will use test DB path)
    from src.mcp_servers import library_server

    # Reinitialize the repository with the test database
    from src.mcp_servers.library_server import BookRepository
    library_server.repository = BookRepository(test_db_path)

    # Return the FastMCP instance
    return library_server.mcp


def parse_tool_result(result):
    """Parse CallToolResult to extract the actual data.

    FastMCP's CallToolResult has:
    - is_error: bool
    - content: List of TextContent objects with .text attribute
    - structured_content: Dict with 'result' key containing parsed data
    """
    if result.is_error:
        error_text = result.content[0].text if result.content else "Unknown error"
        raise Exception(error_text)

    # Parse from content[0].text which contains the JSON string
    if result.content and hasattr(result.content[0], 'text'):
        return json.loads(result.content[0].text)

    return None


class TestMCPToolExecution:
    """Test executing MCP tools end-to-end."""

    @pytest.mark.asyncio
    async def test_search_books_tool(self, mcp_server):
        """Test search_books tool execution."""
        async with Client(mcp_server) as client:
            # Call the search_books tool
            result = await client.call_tool("search_books", {"query": "Python"})
            data = parse_tool_result(result)

            assert data is not None
            assert isinstance(data, list)
            assert len(data) >= 2  # Should find both Python books

            # Verify structure
            assert all('book_id' in book for book in data)
            assert all('title' in book for book in data)
            assert any('Python' in book['title'] for book in data)

    @pytest.mark.asyncio
    async def test_get_book_details_tool(self, mcp_server):
        """Test get_book_details tool execution."""
        async with Client(mcp_server) as client:
            result = await client.call_tool("get_book_details", {"book_id": "B001"})
            data = parse_tool_result(result)

            assert data is not None
            assert data['book_id'] == "B001"
            assert data['title'] == "Python Programming"
            assert data['author'] == "John Smith"
            # Location is stored as flat keys
            assert 'cabinet' in data
            assert 'rack' in data
            assert 'row' in data
            assert 'status' in data

    @pytest.mark.asyncio
    async def test_check_availability_tool(self, mcp_server):
        """Test check_availability tool execution."""
        async with Client(mcp_server) as client:
            # Test available book
            result = await client.call_tool("check_availability", {"book_id": "B001"})
            data = parse_tool_result(result)

            assert data is not None
            assert data['available'] is True
            assert data['status'] == "Present"

            # Test checked out book
            result = await client.call_tool("check_availability", {"book_id": "B003"})
            data = parse_tool_result(result)
            assert data['available'] is False
            assert data['status'] == "Checked Out"

    @pytest.mark.asyncio
    async def test_list_by_category_tool(self, mcp_server):
        """Test list_by_category tool execution."""
        async with Client(mcp_server) as client:
            result = await client.call_tool("list_by_category", {"category": "Programming"})
            data = parse_tool_result(result)

            assert data is not None
            assert isinstance(data, list)
            assert len(data) == 2  # Two programming books
            assert all(book['category'] == "Programming" for book in data)

    @pytest.mark.asyncio
    async def test_list_by_status_tool(self, mcp_server):
        """Test list_by_status tool execution."""
        async with Client(mcp_server) as client:
            result = await client.call_tool("list_by_status", {"status": "Present"})
            data = parse_tool_result(result)

            assert data is not None
            assert isinstance(data, list)
            assert all(book['status'] == "Present" for book in data)

    @pytest.mark.asyncio
    async def test_locate_book_tool(self, mcp_server):
        """Test locate_book tool execution."""
        async with Client(mcp_server) as client:
            result = await client.call_tool("locate_book", {"book_id": "B001"})
            data = parse_tool_result(result)

            assert data is not None
            assert 'cabinet' in data
            assert 'rack' in data
            assert 'row' in data
            assert data['cabinet'] == 1
            assert data['rack'] == 1
            assert data['row'] == 1

    @pytest.mark.asyncio
    async def test_find_books_in_cabinet_tool(self, mcp_server):
        """Test find_books_in_cabinet tool execution."""
        async with Client(mcp_server) as client:
            result = await client.call_tool("find_books_in_cabinet", {"cabinet": 1})
            data = parse_tool_result(result)

            assert data is not None
            assert isinstance(data, list)
            # Books in cabinet 1 should have cabinet field equal to 1
            for book in data:
                assert book['cabinet'] == 1

    @pytest.mark.asyncio
    async def test_get_weak_signal_books_tool(self, mcp_server):
        """Test get_weak_signal_books tool execution."""
        async with Client(mcp_server) as client:
            result = await client.call_tool("get_weak_signal_books", {"threshold": -55})
            data = parse_tool_result(result)

            assert data is not None
            assert isinstance(data, list)
            # Should include B002 (-60.5) and B004 (-70.0)
            book_ids = [book['book_id'] for book in data]
            assert "B002" in book_ids
            assert "B004" in book_ids


class TestMCPResources:
    """Test MCP resource access."""

    @pytest.mark.asyncio
    async def test_library_stats_resource(self, mcp_server):
        """Test library://stats resource."""
        async with Client(mcp_server) as client:
            # read_resource returns a list of TextResourceContents
            result = await client.read_resource("library://stats")

            assert result is not None
            assert len(result) > 0
            # Get the text from first result
            text = result[0].text
            data = json.loads(text)
            assert 'by_category' in data
            assert 'by_status' in data
            assert 'total_books' in data

    @pytest.mark.asyncio
    async def test_missing_books_resource(self, mcp_server):
        """Test library://missing_books resource."""
        async with Client(mcp_server) as client:
            result = await client.read_resource("library://missing_books")

            assert result is not None
            assert len(result) > 0
            text = result[0].text
            data = json.loads(text)
            assert isinstance(data, list)
            # Should have B004 which is marked as Missing
            assert any(book['book_id'] == "B004" for book in data)

    @pytest.mark.asyncio
    async def test_location_map_resource(self, mcp_server):
        """Test library://location_map resource."""
        async with Client(mcp_server) as client:
            result = await client.read_resource("library://location_map")

            assert result is not None
            assert len(result) > 0
            text = result[0].text
            data = json.loads(text)
            assert isinstance(data, list)
            assert all('cabinet' in loc for loc in data)
            assert all('book_count' in loc for loc in data)


class TestMCPPrompts:
    """Test MCP prompt generation."""

    @pytest.mark.asyncio
    async def test_book_search_prompt(self, mcp_server):
        """Test book_search prompt."""
        async with Client(mcp_server) as client:
            result = await client.get_prompt("book_search", {"query": "Python books"})

            assert result is not None
            # Get the prompt message content
            assert len(result.messages) > 0
            content = result.messages[0].content
            # Content could be a string or a TextContent object
            text = content.text if hasattr(content, 'text') else str(content)
            assert "Python books" in text
            assert len(text) > 0

    @pytest.mark.asyncio
    async def test_library_status_report_prompt(self, mcp_server):
        """Test library_status_report prompt."""
        async with Client(mcp_server) as client:
            result = await client.get_prompt("library_status_report", {"focus": "availability"})

            assert result is not None
            assert len(result.messages) > 0
            content = result.messages[0].content
            text = content.text if hasattr(content, 'text') else str(content)
            assert len(text) > 0


class TestErrorHandling:
    """Test error handling in MCP tools."""

    @pytest.mark.asyncio
    async def test_invalid_book_id(self, mcp_server):
        """Test user-friendly error for invalid book ID."""
        async with Client(mcp_server) as client:
            result = await client.call_tool("get_book_details", {"book_id": "INVALID"})
            data = parse_tool_result(result)

            # Tool returns error dict instead of raising
            assert "error" in data
            error_msg = data["error"].lower()
            assert "not found" in error_msg

    @pytest.mark.asyncio
    async def test_missing_required_parameter(self, mcp_server):
        """Test error when required parameter is missing."""
        async with Client(mcp_server) as client:
            # The tool should handle missing query gracefully or FastMCP will error
            try:
                result = await client.call_tool("search_books", {})  # Missing 'query'
                # If it doesn't raise, check for error in result
                data = parse_tool_result(result)
                assert "error" in data or len(data) == 0
            except Exception as exc_info:
                # Should indicate missing parameter
                error_msg = str(exc_info).lower()
                assert "query" in error_msg or "required" in error_msg or "missing" in error_msg

    @pytest.mark.asyncio
    async def test_invalid_category(self, mcp_server):
        """Test error for invalid category value."""
        from fastmcp.exceptions import ToolError

        async with Client(mcp_server) as client:
            # FastMCP raises ToolError because tool returns dict but expects list
            with pytest.raises(ToolError) as exc_info:
                await client.call_tool("list_by_category", {"category": "InvalidCategory"})

            # Error should mention invalid category
            error_msg = str(exc_info.value).lower()
            assert "invalid" in error_msg or "category" in error_msg or "validation" in error_msg


class TestMultiToolWorkflow:
    """Test workflows involving multiple tool calls."""

    @pytest.mark.asyncio
    async def test_search_then_details_workflow(self, mcp_server):
        """Test searching for books then getting details."""
        async with Client(mcp_server) as client:
            # Step 1: Search for Python books
            search_result = await client.call_tool("search_books", {"query": "Python"})
            search_results = parse_tool_result(search_result)
            assert len(search_results) > 0

            # Step 2: Get details for first result
            first_book_id = search_results[0]['book_id']
            details_result = await client.call_tool("get_book_details", {"book_id": first_book_id})
            details = parse_tool_result(details_result)

            assert details['book_id'] == first_book_id
            assert "Python" in details['title']

    @pytest.mark.asyncio
    async def test_category_to_location_workflow(self, mcp_server):
        """Test listing books by category then finding locations."""
        async with Client(mcp_server) as client:
            # Step 1: List programming books
            cat_result = await client.call_tool("list_by_category", {"category": "Programming"})
            prog_books = parse_tool_result(cat_result)
            assert len(prog_books) > 0

            # Step 2: Get location for each book
            for book in prog_books:
                loc_result = await client.call_tool("locate_book", {"book_id": book['book_id']})
                location = parse_tool_result(loc_result)
                assert 'cabinet' in location
                assert location['cabinet'] >= 1
