"""Integration tests for MCP server with in-memory transport.

Tests verify end-to-end MCP server functionality using FastMCP's
test transport for simulating client-server interactions.
"""
import pytest
import asyncio
from pathlib import Path
import sys
import tempfile
import json

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


@pytest.fixture
def test_db_path(tmp_path):
    """Create a temporary test database."""
    db_path = tmp_path / "test_library.db"

    # Create test database with sample data
    import duckdb
    from src.library.domain import BookStatus, Category

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

    # Return the FastMCP instance
    return library_server.mcp


class TestMCPToolExecution:
    """Test executing MCP tools end-to-end."""

    @pytest.mark.asyncio
    async def test_search_books_tool(self, mcp_server):
        """Test search_books tool execution."""
        # Use FastMCP's test client
        async with mcp_server.test_client() as client:
            # Call the search_books tool
            result = await client.call_tool("search_books", {"query": "Python"})

            assert result is not None
            assert isinstance(result, list)
            assert len(result) >= 2  # Should find both Python books

            # Verify structure
            assert all('book_id' in book for book in result)
            assert all('title' in book for book in result)
            assert any('Python' in book['title'] for book in result)

    @pytest.mark.asyncio
    async def test_get_book_details_tool(self, mcp_server):
        """Test get_book_details tool execution."""
        async with mcp_server.test_client() as client:
            result = await client.call_tool("get_book_details", {"book_id": "B001"})

            assert result is not None
            assert result['book_id'] == "B001"
            assert result['title'] == "Python Programming"
            assert result['author'] == "John Smith"
            assert 'location' in result
            assert 'status' in result

    @pytest.mark.asyncio
    async def test_check_availability_tool(self, mcp_server):
        """Test check_availability tool execution."""
        async with mcp_server.test_client() as client:
            # Test available book
            result = await client.call_tool("check_availability", {"book_id": "B001"})

            assert result is not None
            assert result['available'] is True
            assert result['status'] == "Present"

            # Test checked out book
            result = await client.call_tool("check_availability", {"book_id": "B003"})
            assert result['available'] is False
            assert result['status'] == "Checked Out"

    @pytest.mark.asyncio
    async def test_list_by_category_tool(self, mcp_server):
        """Test list_by_category tool execution."""
        async with mcp_server.test_client() as client:
            result = await client.call_tool("list_by_category", {"category": "Programming"})

            assert result is not None
            assert isinstance(result, list)
            assert len(result) == 2  # Two programming books
            assert all(book['category'] == "Programming" for book in result)

    @pytest.mark.asyncio
    async def test_list_by_status_tool(self, mcp_server):
        """Test list_by_status tool execution."""
        async with mcp_server.test_client() as client:
            result = await client.call_tool("list_by_status", {"status": "Present"})

            assert result is not None
            assert isinstance(result, list)
            assert all(book['status'] == "Present" for book in result)

    @pytest.mark.asyncio
    async def test_locate_book_tool(self, mcp_server):
        """Test locate_book tool execution."""
        async with mcp_server.test_client() as client:
            result = await client.call_tool("locate_book", {"book_id": "B001"})

            assert result is not None
            assert 'cabinet' in result
            assert 'rack' in result
            assert 'row' in result
            assert result['cabinet'] == 1
            assert result['rack'] == 1
            assert result['row'] == 1

    @pytest.mark.asyncio
    async def test_find_books_in_cabinet_tool(self, mcp_server):
        """Test find_books_in_cabinet tool execution."""
        async with mcp_server.test_client() as client:
            result = await client.call_tool("find_books_in_cabinet", {"cabinet": 1})

            assert result is not None
            assert isinstance(result, list)
            assert all(book['cabinet'] == 1 for book in result)

    @pytest.mark.asyncio
    async def test_get_weak_signal_books_tool(self, mcp_server):
        """Test get_weak_signal_books tool execution."""
        async with mcp_server.test_client() as client:
            result = await client.call_tool("get_weak_signal_books", {"threshold": -55})

            assert result is not None
            assert isinstance(result, list)
            # Should include B002 (-60.5) and B004 (-70.0)
            assert any(book['book_id'] == "B002" for book in result)
            assert any(book['book_id'] == "B004" for book in result)


class TestMCPResources:
    """Test MCP resource access."""

    @pytest.mark.asyncio
    async def test_library_stats_resource(self, mcp_server):
        """Test library://stats resource."""
        async with mcp_server.test_client() as client:
            result = await client.read_resource("library://stats")

            assert result is not None
            data = json.loads(result)
            assert 'by_category' in data
            assert 'by_status' in data
            assert 'total_books' in data

    @pytest.mark.asyncio
    async def test_missing_books_resource(self, mcp_server):
        """Test library://missing_books resource."""
        async with mcp_server.test_client() as client:
            result = await client.read_resource("library://missing_books")

            assert result is not None
            data = json.loads(result)
            assert isinstance(data, list)
            # Should have B004 which is marked as Missing
            assert any(book['book_id'] == "B004" for book in data)

    @pytest.mark.asyncio
    async def test_location_map_resource(self, mcp_server):
        """Test library://location_map resource."""
        async with mcp_server.test_client() as client:
            result = await client.read_resource("library://location_map")

            assert result is not None
            data = json.loads(result)
            assert isinstance(data, list)
            assert all('cabinet' in loc for loc in data)
            assert all('book_count' in loc for loc in data)


class TestMCPPrompts:
    """Test MCP prompt generation."""

    @pytest.mark.asyncio
    async def test_book_search_prompt(self, mcp_server):
        """Test book_search prompt."""
        async with mcp_server.test_client() as client:
            result = await client.get_prompt("book_search", {"query": "Python books"})

            assert result is not None
            assert isinstance(result, str)
            assert "Python books" in result
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_library_status_report_prompt(self, mcp_server):
        """Test library_status_report prompt."""
        async with mcp_server.test_client() as client:
            result = await client.get_prompt("library_status_report", {"focus": "availability"})

            assert result is not None
            assert isinstance(result, str)
            assert len(result) > 0


class TestErrorHandling:
    """Test error handling in MCP tools."""

    @pytest.mark.asyncio
    async def test_invalid_book_id(self, mcp_server):
        """Test user-friendly error for invalid book ID."""
        async with mcp_server.test_client() as client:
            with pytest.raises(Exception) as exc_info:
                await client.call_tool("get_book_details", {"book_id": "INVALID"})

            # Error message should be user-friendly
            error_msg = str(exc_info.value).lower()
            assert "not found" in error_msg or "invalid" in error_msg

    @pytest.mark.asyncio
    async def test_missing_required_parameter(self, mcp_server):
        """Test error when required parameter is missing."""
        async with mcp_server.test_client() as client:
            with pytest.raises(Exception) as exc_info:
                await client.call_tool("search_books", {})  # Missing 'query'

            # Should indicate missing parameter
            error_msg = str(exc_info.value).lower()
            assert "query" in error_msg or "required" in error_msg

    @pytest.mark.asyncio
    async def test_invalid_category(self, mcp_server):
        """Test error for invalid category value."""
        async with mcp_server.test_client() as client:
            with pytest.raises(Exception) as exc_info:
                await client.call_tool("list_by_category", {"category": "InvalidCategory"})

            # Should indicate invalid category
            error_msg = str(exc_info.value).lower()
            assert "category" in error_msg or "invalid" in error_msg


class TestMultiToolWorkflow:
    """Test workflows involving multiple tool calls."""

    @pytest.mark.asyncio
    async def test_search_then_details_workflow(self, mcp_server):
        """Test searching for books then getting details."""
        async with mcp_server.test_client() as client:
            # Step 1: Search for Python books
            search_results = await client.call_tool("search_books", {"query": "Python"})
            assert len(search_results) > 0

            # Step 2: Get details for first result
            first_book_id = search_results[0]['book_id']
            details = await client.call_tool("get_book_details", {"book_id": first_book_id})

            assert details['book_id'] == first_book_id
            assert "Python" in details['title']

    @pytest.mark.asyncio
    async def test_category_to_location_workflow(self, mcp_server):
        """Test listing books by category then finding locations."""
        async with mcp_server.test_client() as client:
            # Step 1: List programming books
            prog_books = await client.call_tool("list_by_category", {"category": "Programming"})
            assert len(prog_books) > 0

            # Step 2: Get location for each book
            for book in prog_books:
                location = await client.call_tool("locate_book", {"book_id": book['book_id']})
                assert 'cabinet' in location
                assert location['cabinet'] >= 1
