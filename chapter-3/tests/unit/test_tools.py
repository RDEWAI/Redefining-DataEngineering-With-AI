"""Unit tests for JSON schema tool definitions.

Tests that tool definitions match the contract in contracts/llm-tools.json
and can be properly converted for LLM function calling.
"""

import pytest

# Import to be tested (will be created in library_assistant.py)
from src.agents.library_assistant import (
    TOOL_DEFINITIONS,
    get_tool_function,
    get_tools_for_llm,
)


class TestToolDefinitions:
    """Test that tool definitions match the contract specification."""

    def test_all_required_tools_defined(self) -> None:
        """Test that all 8 core tools are defined."""
        required_tools = [
            "search_books",
            "get_book_details",
            "check_availability",
            "list_by_category",
            "list_by_status",
            "locate_book",
            "find_books_in_cabinet",
            "get_weak_signal_books",
            "get_library_stats",
        ]

        tool_names = [tool.name for tool in TOOL_DEFINITIONS]

        for required in required_tools:
            assert required in tool_names, f"Missing required tool: {required}"

    def test_tool_definition_structure(self) -> None:
        """Test that each tool definition has required fields."""
        for tool in TOOL_DEFINITIONS:
            # Check duck typing instead of isinstance due to import path differences
            assert hasattr(tool, "name"), "Tool must have name attribute"
            assert hasattr(tool, "description"), "Tool must have description attribute"
            assert hasattr(tool, "parameters"), "Tool must have parameters attribute"
            assert tool.name, "Tool name must not be empty"
            assert tool.description, "Tool description must not be empty"
            assert isinstance(tool.parameters, dict), "Parameters must be a dict"
            assert "type" in tool.parameters, "Parameters must have a type field"
            assert tool.parameters["type"] == "object", "Parameters type must be 'object'"

    def test_search_books_schema(self) -> None:
        """Test search_books tool matches contract."""
        tool = next(t for t in TOOL_DEFINITIONS if t.name == "search_books")

        assert "query" in tool.parameters.get("properties", {})
        assert "category" in tool.parameters.get("properties", {})
        assert "limit" in tool.parameters.get("properties", {})
        assert "query" in tool.parameters.get("required", [])

    def test_get_book_details_schema(self) -> None:
        """Test get_book_details tool matches contract."""
        tool = next(t for t in TOOL_DEFINITIONS if t.name == "get_book_details")

        assert "book_id" in tool.parameters.get("properties", {})
        assert "book_id" in tool.parameters.get("required", [])

    def test_list_by_category_schema(self) -> None:
        """Test list_by_category tool matches contract."""
        tool = next(t for t in TOOL_DEFINITIONS if t.name == "list_by_category")

        props = tool.parameters.get("properties", {})
        assert "category" in props
        assert "enum" in props["category"], "category should have enum values"
        assert "status" in props

    def test_list_by_status_schema(self) -> None:
        """Test list_by_status tool matches contract."""
        tool = next(t for t in TOOL_DEFINITIONS if t.name == "list_by_status")

        props = tool.parameters.get("properties", {})
        assert "status" in props
        assert "enum" in props["status"], "status should have enum values"
        assert "category" in props

    def test_find_books_in_cabinet_schema(self) -> None:
        """Test find_books_in_cabinet tool matches contract."""
        tool = next(t for t in TOOL_DEFINITIONS if t.name == "find_books_in_cabinet")

        props = tool.parameters.get("properties", {})
        assert "cabinet" in props
        assert props["cabinet"]["type"] == "integer"
        assert "rack" in props
        assert "cabinet" in tool.parameters.get("required", [])

    def test_get_weak_signal_books_schema(self) -> None:
        """Test get_weak_signal_books tool matches contract."""
        tool = next(t for t in TOOL_DEFINITIONS if t.name == "get_weak_signal_books")

        props = tool.parameters.get("properties", {})
        assert "threshold" in props
        assert props["threshold"]["type"] == "number"
        # threshold should have a default value
        assert "default" in props["threshold"]


class TestToolConversion:
    """Test tool definition conversion for LLM APIs."""

    def test_to_openai_format(self) -> None:
        """Test conversion to OpenAI tool format."""
        tool = TOOL_DEFINITIONS[0]
        openai_format = tool.to_openai_format()

        assert openai_format["type"] == "function"
        assert "function" in openai_format
        assert openai_format["function"]["name"] == tool.name
        assert openai_format["function"]["description"] == tool.description
        assert openai_format["function"]["parameters"] == tool.parameters

    def test_get_tools_for_llm_returns_list(self) -> None:
        """Test get_tools_for_llm returns proper list format."""
        tools = get_tools_for_llm()

        assert isinstance(tools, list)
        assert len(tools) > 0
        for tool in tools:
            assert tool["type"] == "function"
            assert "function" in tool


class TestToolFunctionMapping:
    """Test tool function mapping and execution."""

    def test_get_tool_function_returns_callable(self) -> None:
        """Test that get_tool_function returns callable for known tools."""
        for tool in TOOL_DEFINITIONS:
            func = get_tool_function(tool.name)
            assert callable(func), f"Tool {tool.name} should return a callable"

    def test_get_tool_function_unknown_raises(self) -> None:
        """Test that get_tool_function raises for unknown tools."""
        with pytest.raises(ValueError, match="Unknown tool"):
            get_tool_function("unknown_tool_name")

    def test_search_books_function_mapping(self) -> None:
        """Test search_books is mapped correctly."""
        func = get_tool_function("search_books")
        assert func.__name__ == "search_books"

    def test_get_library_stats_function_mapping(self) -> None:
        """Test get_library_stats is mapped correctly."""
        func = get_tool_function("get_library_stats")
        assert func.__name__ == "get_library_stats"


class TestToolArgumentValidation:
    """Test tool argument validation."""

    def test_search_books_valid_args(self) -> None:
        """Test search_books with valid arguments."""
        func = get_tool_function("search_books")
        # This should not raise - function exists and can be called
        result = func(query="Python")
        assert "success" in result

    def test_search_books_with_category(self) -> None:
        """Test search_books with category filter."""
        func = get_tool_function("search_books")
        result = func(query="test", category="Programming")
        assert "success" in result

    def test_list_by_category_valid_args(self) -> None:
        """Test list_by_category with valid arguments."""
        func = get_tool_function("list_by_category")
        result = func(category="Programming")
        assert "success" in result

    def test_get_book_details_valid_args(self) -> None:
        """Test get_book_details with valid book_id."""
        func = get_tool_function("get_book_details")
        result = func(book_id="B001")
        assert "success" in result

    def test_find_books_in_cabinet_valid_args(self) -> None:
        """Test find_books_in_cabinet with valid cabinet number."""
        func = get_tool_function("find_books_in_cabinet")
        result = func(cabinet=1)
        assert "success" in result

    def test_get_weak_signal_books_default_threshold(self) -> None:
        """Test get_weak_signal_books with default threshold."""
        func = get_tool_function("get_weak_signal_books")
        result = func()
        assert "success" in result

    def test_get_library_stats_no_args(self) -> None:
        """Test get_library_stats requires no arguments."""
        func = get_tool_function("get_library_stats")
        result = func()
        assert "success" in result
