"""Unit tests for tool registry.

Tests the ToolRegistry class for tool registration, lookup, and filtering.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest


class TestToolMetadata:
    """Tests for ToolMetadata dataclass."""

    def test_tool_metadata_creation(self) -> None:
        """Test creating tool metadata."""
        from src.tools.tool_registry import ToolMetadata

        metadata = ToolMetadata(
            name="search_books",
            description="Search books by title or author",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            capabilities=["search"],
            handler=lambda x: x,
        )

        assert metadata.name == "search_books"
        assert metadata.description == "Search books by title or author"
        assert "query" in metadata.input_schema["properties"]
        assert "search" in metadata.capabilities
        assert callable(metadata.handler)

    def test_tool_metadata_multiple_capabilities(self) -> None:
        """Test tool with multiple capabilities."""
        from src.tools.tool_registry import ToolMetadata

        metadata = ToolMetadata(
            name="get_library_stats",
            description="Get library statistics",
            input_schema={"type": "object", "properties": {}},
            capabilities=["analytics", "monitoring"],
            handler=lambda: {},
        )

        assert "analytics" in metadata.capabilities
        assert "monitoring" in metadata.capabilities
        assert len(metadata.capabilities) == 2


class TestToolRegistry:
    """Tests for ToolRegistry class."""

    def test_register_tool(self) -> None:
        """Test registering a tool."""
        from src.tools.tool_registry import ToolMetadata, ToolRegistry

        registry = ToolRegistry()

        metadata = ToolMetadata(
            name="search_books",
            description="Search books",
            input_schema={"type": "object"},
            capabilities=["search"],
            handler=lambda x: x,
        )

        registry.register_tool(metadata)

        assert "search_books" in registry.list_tool_names()

    def test_register_duplicate_tool_raises_error(self) -> None:
        """Test that registering duplicate tool raises error."""
        from src.tools.tool_registry import ToolMetadata, ToolRegistry

        registry = ToolRegistry()

        metadata = ToolMetadata(
            name="search_books",
            description="Search books",
            input_schema={"type": "object"},
            capabilities=["search"],
            handler=lambda x: x,
        )

        registry.register_tool(metadata)

        with pytest.raises(ValueError, match="already registered"):
            registry.register_tool(metadata)

    def test_get_tool_by_name(self) -> None:
        """Test getting tool by name."""
        from src.tools.tool_registry import ToolMetadata, ToolRegistry

        registry = ToolRegistry()

        handler = MagicMock(return_value={"result": "ok"})
        metadata = ToolMetadata(
            name="search_books",
            description="Search books",
            input_schema={"type": "object"},
            capabilities=["search"],
            handler=handler,
        )

        registry.register_tool(metadata)
        retrieved = registry.get_tool("search_books")

        assert retrieved is not None
        assert retrieved.name == "search_books"
        assert retrieved.handler == handler

    def test_get_nonexistent_tool_returns_none(self) -> None:
        """Test that getting nonexistent tool returns None."""
        from src.tools.tool_registry import ToolRegistry

        registry = ToolRegistry()
        result = registry.get_tool("nonexistent")

        assert result is None

    def test_list_tools_by_capability(self) -> None:
        """Test listing tools by capability."""
        from src.tools.tool_registry import ToolMetadata, ToolRegistry

        registry = ToolRegistry()

        # Register search tool
        registry.register_tool(
            ToolMetadata(
                name="search_books",
                description="Search books",
                input_schema={"type": "object"},
                capabilities=["search"],
                handler=lambda: None,
            )
        )

        # Register analytics tool
        registry.register_tool(
            ToolMetadata(
                name="get_stats",
                description="Get statistics",
                input_schema={"type": "object"},
                capabilities=["analytics"],
                handler=lambda: None,
            )
        )

        # Register tool with multiple capabilities
        registry.register_tool(
            ToolMetadata(
                name="semantic_search",
                description="Semantic search",
                input_schema={"type": "object"},
                capabilities=["search", "rag"],
                handler=lambda: None,
            )
        )

        search_tools = registry.list_tools(capability="search")
        analytics_tools = registry.list_tools(capability="analytics")

        assert len(search_tools) == 2
        assert any(t.name == "search_books" for t in search_tools)
        assert any(t.name == "semantic_search" for t in search_tools)
        assert len(analytics_tools) == 1
        assert analytics_tools[0].name == "get_stats"

    def test_list_all_tools(self) -> None:
        """Test listing all tools without filter."""
        from src.tools.tool_registry import ToolMetadata, ToolRegistry

        registry = ToolRegistry()

        for i in range(3):
            registry.register_tool(
                ToolMetadata(
                    name=f"tool_{i}",
                    description=f"Tool {i}",
                    input_schema={"type": "object"},
                    capabilities=["test"],
                    handler=lambda: None,
                )
            )

        all_tools = registry.list_tools()

        assert len(all_tools) == 3

    def test_list_tool_names(self) -> None:
        """Test listing tool names."""
        from src.tools.tool_registry import ToolMetadata, ToolRegistry

        registry = ToolRegistry()

        registry.register_tool(
            ToolMetadata(
                name="tool_a",
                description="Tool A",
                input_schema={"type": "object"},
                capabilities=["test"],
                handler=lambda: None,
            )
        )
        registry.register_tool(
            ToolMetadata(
                name="tool_b",
                description="Tool B",
                input_schema={"type": "object"},
                capabilities=["test"],
                handler=lambda: None,
            )
        )

        names = registry.list_tool_names()

        assert "tool_a" in names
        assert "tool_b" in names
        assert len(names) == 2

    def test_execute_tool(self) -> None:
        """Test executing a registered tool."""
        from src.tools.tool_registry import ToolMetadata, ToolRegistry

        registry = ToolRegistry()

        def handler(query: str) -> dict[str, Any]:
            return {"result": f"Found: {query}"}

        registry.register_tool(
            ToolMetadata(
                name="search",
                description="Search",
                input_schema={"type": "object"},
                capabilities=["search"],
                handler=handler,
            )
        )

        result = registry.execute_tool("search", query="Python")

        assert result == {"result": "Found: Python"}

    def test_execute_nonexistent_tool_raises_error(self) -> None:
        """Test that executing nonexistent tool raises error."""
        from src.tools.tool_registry import ToolRegistry

        registry = ToolRegistry()

        with pytest.raises(ValueError, match="not found"):
            registry.execute_tool("nonexistent")

    def test_get_tool_schema(self) -> None:
        """Test getting tool schema for LLM."""
        from src.tools.tool_registry import ToolMetadata, ToolRegistry

        registry = ToolRegistry()

        schema = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }

        registry.register_tool(
            ToolMetadata(
                name="search",
                description="Search function",
                input_schema=schema,
                capabilities=["search"],
                handler=lambda: None,
            )
        )

        tool_schema = registry.get_tool_schema("search")

        assert tool_schema["type"] == "function"
        assert tool_schema["function"]["name"] == "search"
        assert tool_schema["function"]["description"] == "Search function"
        assert tool_schema["function"]["parameters"] == schema

    def test_get_all_schemas(self) -> None:
        """Test getting all tool schemas for LLM."""
        from src.tools.tool_registry import ToolMetadata, ToolRegistry

        registry = ToolRegistry()

        for name in ["tool_a", "tool_b"]:
            registry.register_tool(
                ToolMetadata(
                    name=name,
                    description=f"Description for {name}",
                    input_schema={"type": "object"},
                    capabilities=["test"],
                    handler=lambda: None,
                )
            )

        schemas = registry.get_all_schemas()

        assert len(schemas) == 2
        assert all(s["type"] == "function" for s in schemas)


class TestToolRegistryDecorator:
    """Tests for tool registration decorator."""

    def test_register_decorator(self) -> None:
        """Test using decorator to register tools."""
        from src.tools.tool_registry import ToolRegistry

        registry = ToolRegistry()

        @registry.register(
            description="Search books by query",
            input_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            capabilities=["search"],
        )
        def search_books(query: str) -> list[dict]:
            return [{"title": f"Found: {query}"}]

        assert "search_books" in registry.list_tool_names()

        result = registry.execute_tool("search_books", query="Python")
        assert result == [{"title": "Found: Python"}]

    def test_register_decorator_uses_function_name(self) -> None:
        """Test that decorator uses function name as tool name."""
        from src.tools.tool_registry import ToolRegistry

        registry = ToolRegistry()

        @registry.register(
            description="Custom tool",
            input_schema={"type": "object"},
            capabilities=["test"],
        )
        def my_custom_tool() -> str:
            return "result"

        assert "my_custom_tool" in registry.list_tool_names()


class TestCapabilities:
    """Tests for capability constants."""

    def test_capability_constants_exist(self) -> None:
        """Test that capability constants are defined."""
        from src.tools.tool_registry import Capability

        assert hasattr(Capability, "SEARCH")
        assert hasattr(Capability, "ANALYTICS")
        assert hasattr(Capability, "MONITORING")
        assert hasattr(Capability, "RAG")
        assert hasattr(Capability, "CODE_EXECUTION")

    def test_capability_values(self) -> None:
        """Test capability enum values."""
        from src.tools.tool_registry import Capability

        assert Capability.SEARCH.value == "search"
        assert Capability.ANALYTICS.value == "analytics"
        assert Capability.MONITORING.value == "monitoring"
        assert Capability.RAG.value == "rag"
        assert Capability.CODE_EXECUTION.value == "code_execution"
