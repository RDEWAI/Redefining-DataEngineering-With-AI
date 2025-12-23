"""Unit tests for MCP tool registration and validation.

Tests verify that FastMCP decorators properly register tools, resources,
and prompts for the library server.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


class TestMCPToolRegistration:
    """Test that MCP tools are properly registered."""

    @pytest.mark.asyncio
    async def test_all_tools_registered(self):
        """Test that all 8 library tools are registered."""
        with patch("library.repository.BookRepository"):
            from src.agentic.mcp_servers import library_server

            tools = await library_server.mcp.get_tools()
            # get_tools() returns a dict of {name: tool_object}
            tool_names = list(tools.keys())

            # Verify all 8 tools are registered
            expected_tools = [
                "search_books",
                "get_book_details",
                "check_availability",
                "list_by_category",
                "list_by_status",
                "locate_book",
                "find_books_in_cabinet",
                "get_weak_signal_books",
            ]

            for tool_name in expected_tools:
                assert tool_name in tool_names, f"Tool '{tool_name}' not registered"

    @pytest.mark.asyncio
    async def test_tool_has_description(self):
        """Test that tools have descriptions."""
        with patch("library.repository.BookRepository"):
            from src.agentic.mcp_servers import library_server

            search_tool = await library_server.mcp.get_tool("search_books")
            assert search_tool is not None
            assert hasattr(search_tool, "description")
            assert len(search_tool.description) > 0


class TestMCPResources:
    """Test that MCP resources are properly registered."""

    @pytest.mark.asyncio
    async def test_all_resources_registered(self):
        """Test that all 3 resources are registered."""
        with patch("library.repository.BookRepository"):
            from src.agentic.mcp_servers import library_server

            resources = await library_server.mcp.get_resources()
            # get_resources() returns a dict of {uri: resource_object}
            resource_uris = list(resources.keys())

            # Verify all 3 resources are registered
            expected_resources = [
                "library://stats",
                "library://missing_books",
                "library://location_map",
            ]

            for resource_uri in expected_resources:
                assert resource_uri in resource_uris, f"Resource '{resource_uri}' not registered"


class TestMCPPrompts:
    """Test that MCP prompts are properly registered."""

    @pytest.mark.asyncio
    async def test_all_prompts_registered(self):
        """Test that both prompts are registered."""
        with patch("library.repository.BookRepository"):
            from src.agentic.mcp_servers import library_server

            prompts = await library_server.mcp.get_prompts()
            # get_prompts() returns a dict of {name: prompt_object}
            prompt_names = list(prompts.keys())

            # Verify both prompts are registered
            expected_prompts = ["book_search", "library_status_report"]

            for prompt_name in expected_prompts:
                assert prompt_name in prompt_names, f"Prompt '{prompt_name}' not registered"


class TestServerInitialization:
    """Test MCP server initialization."""

    def test_server_name(self):
        """Test server has correct name."""
        with patch("library.repository.BookRepository"):
            from src.agentic.mcp_servers import library_server

            assert library_server.mcp.name == "LibraryServer"

    def test_server_has_repository(self):
        """Test server initializes with repository."""
        with patch("library.repository.BookRepository"):
            from src.agentic.mcp_servers import library_server

            assert hasattr(library_server, "repository")
