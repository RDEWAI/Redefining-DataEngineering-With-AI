"""Tool registry for dynamic tool discovery and execution.

This module provides the ToolRegistry class for registering, discovering,
and executing tools. It supports capability-based filtering and generates
OpenAI-compatible tool schemas for LLM integration.

Example:
    >>> from src.tools.tool_registry import ToolRegistry, Capability
    >>> registry = ToolRegistry()
    >>> @registry.register(
    ...     description="Search books",
    ...     input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
    ...     capabilities=[Capability.SEARCH],
    ... )
    ... def search_books(query: str) -> list:
    ...     return [{"title": "Python Book"}]
    >>> result = registry.execute_tool("search_books", query="Python")
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any


class Capability(Enum):
    """Tool capability categories for filtering.

    Attributes:
        SEARCH: Tools that search or find information
        ANALYTICS: Tools that compute statistics or aggregations
        MONITORING: Tools that monitor status or health
        RAG: Tools that use semantic/vector search
        CODE_EXECUTION: Tools that execute generated code
    """

    SEARCH = "search"
    ANALYTICS = "analytics"
    MONITORING = "monitoring"
    RAG = "rag"
    CODE_EXECUTION = "code_execution"


@dataclass
class ToolMetadata:
    """Metadata for a registered tool.

    Attributes:
        name: Unique tool name (typically function name)
        description: Human-readable description for LLM
        input_schema: JSON Schema for tool parameters
        capabilities: List of capability tags
        handler: Callable that executes the tool
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    capabilities: list[str] = field(default_factory=list)
    handler: Callable[..., Any] = field(default=lambda: None)


class ToolRegistry:
    """Registry for tool registration, discovery, and execution.

    Provides methods for:
    - Registering tools with metadata
    - Looking up tools by name or capability
    - Generating LLM-compatible schemas
    - Executing registered tools

    Example:
        >>> registry = ToolRegistry()
        >>> registry.register_tool(ToolMetadata(
        ...     name="search",
        ...     description="Search books",
        ...     input_schema={"type": "object"},
        ...     capabilities=["search"],
        ...     handler=search_func,
        ... ))
        >>> tool = registry.get_tool("search")
    """

    def __init__(self) -> None:
        """Initialize empty tool registry."""
        self._tools: dict[str, ToolMetadata] = {}

    def register_tool(self, metadata: ToolMetadata) -> None:
        """Register a tool with the registry.

        Args:
            metadata: Tool metadata including handler

        Raises:
            ValueError: If tool name is already registered
        """
        if metadata.name in self._tools:
            raise ValueError(f"Tool '{metadata.name}' is already registered")

        self._tools[metadata.name] = metadata

    def get_tool(self, name: str) -> ToolMetadata | None:
        """Get tool metadata by name.

        Args:
            name: Tool name to look up

        Returns:
            ToolMetadata if found, None otherwise
        """
        return self._tools.get(name)

    def list_tools(self, capability: str | None = None) -> list[ToolMetadata]:
        """List all tools, optionally filtered by capability.

        Args:
            capability: If provided, only return tools with this capability

        Returns:
            List of ToolMetadata objects
        """
        tools = list(self._tools.values())

        if capability is not None:
            tools = [t for t in tools if capability in t.capabilities]

        return tools

    def list_tool_names(self) -> list[str]:
        """Get list of all registered tool names.

        Returns:
            List of tool name strings
        """
        return list(self._tools.keys())

    def execute_tool(self, name: str, **kwargs: Any) -> Any:
        """Execute a registered tool by name.

        Args:
            name: Tool name to execute
            **kwargs: Arguments to pass to tool handler

        Returns:
            Result from tool handler

        Raises:
            ValueError: If tool is not found
        """
        tool = self.get_tool(name)
        if tool is None:
            raise ValueError(f"Tool '{name}' not found in registry")

        return tool.handler(**kwargs)

    def get_tool_schema(self, name: str) -> dict[str, Any]:
        """Get OpenAI-compatible tool schema for a tool.

        Args:
            name: Tool name

        Returns:
            Dict in OpenAI function calling format

        Raises:
            ValueError: If tool is not found
        """
        tool = self.get_tool(name)
        if tool is None:
            raise ValueError(f"Tool '{name}' not found in registry")

        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            },
        }

    def get_all_schemas(self) -> list[dict[str, Any]]:
        """Get all tool schemas for LLM.

        Returns:
            List of OpenAI-compatible tool schema dicts
        """
        return [self.get_tool_schema(name) for name in self._tools]

    def register(
        self,
        description: str,
        input_schema: dict[str, Any],
        capabilities: list[str | Capability] | None = None,
        name: str | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator for registering functions as tools.

        Args:
            description: Tool description for LLM
            input_schema: JSON Schema for parameters
            capabilities: List of capability tags
            name: Optional custom name (defaults to function name)

        Returns:
            Decorator function

        Example:
            >>> @registry.register(
            ...     description="Search books",
            ...     input_schema={"type": "object"},
            ...     capabilities=[Capability.SEARCH],
            ... )
            ... def search_books(query: str):
            ...     return []
        """
        # Convert Capability enums to strings
        cap_list: list[str] = []
        if capabilities:
            for cap in capabilities:
                if isinstance(cap, Capability):
                    cap_list.append(cap.value)
                else:
                    cap_list.append(cap)

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            tool_name = name if name else func.__name__

            metadata = ToolMetadata(
                name=tool_name,
                description=description,
                input_schema=input_schema,
                capabilities=cap_list,
                handler=func,
            )

            self.register_tool(metadata)

            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                return func(*args, **kwargs)

            return wrapper

        return decorator


def create_library_tool_registry() -> ToolRegistry:
    """Create a registry with all library tools pre-registered.

    Returns:
        ToolRegistry with library tools registered
    """
    from src.library.tools import (
        check_availability,
        find_books_in_cabinet,
        get_book_details,
        get_library_stats,
        get_weak_signal_books,
        list_by_category,
        list_by_status,
        search_books,
    )

    registry = ToolRegistry()

    # Search tools
    registry.register_tool(
        ToolMetadata(
            name="search_books",
            description="Search books by title, author, or keyword. Returns matching books with availability status and location.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to match against title or author",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["Programming", "History", "Science", "Fiction", "Thriller"],
                        "description": "Optional category filter",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 10,
                        "description": "Maximum number of results",
                    },
                },
                "required": ["query"],
            },
            capabilities=[Capability.SEARCH.value],
            handler=search_books,
        )
    )

    registry.register_tool(
        ToolMetadata(
            name="get_book_details",
            description="Get complete details for a specific book including physical location, RFID signal strength, and availability status.",
            input_schema={
                "type": "object",
                "properties": {
                    "book_id": {
                        "type": "string",
                        "description": "Book ID (e.g., 'B001')",
                    },
                },
                "required": ["book_id"],
            },
            capabilities=[Capability.SEARCH.value],
            handler=get_book_details,
        )
    )

    registry.register_tool(
        ToolMetadata(
            name="check_availability",
            description="Check if a book is available for checkout and get its current shelf location.",
            input_schema={
                "type": "object",
                "properties": {
                    "book_id": {
                        "type": "string",
                        "description": "Book ID to check",
                    },
                },
                "required": ["book_id"],
            },
            capabilities=[Capability.SEARCH.value],
            handler=check_availability,
        )
    )

    # Analytics tools
    registry.register_tool(
        ToolMetadata(
            name="list_by_category",
            description="List all books in a specific category with optional status filter.",
            input_schema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["Programming", "History", "Science", "Fiction", "Thriller"],
                        "description": "Category to filter by",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["Present", "Missing", "Checked Out"],
                        "description": "Optional status filter",
                    },
                },
                "required": ["category"],
            },
            capabilities=[Capability.ANALYTICS.value],
            handler=list_by_category,
        )
    )

    registry.register_tool(
        ToolMetadata(
            name="list_by_status",
            description="List all books with a specific availability status.",
            input_schema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["Present", "Missing", "Checked Out"],
                        "description": "Status to filter by",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["Programming", "History", "Science", "Fiction", "Thriller"],
                        "description": "Optional category filter",
                    },
                },
                "required": ["status"],
            },
            capabilities=[Capability.ANALYTICS.value],
            handler=list_by_status,
        )
    )

    registry.register_tool(
        ToolMetadata(
            name="get_library_stats",
            description="Get aggregate statistics about the library: total books, counts by category, counts by status.",
            input_schema={
                "type": "object",
                "properties": {},
                "required": [],
            },
            capabilities=[Capability.ANALYTICS.value, Capability.MONITORING.value],
            handler=get_library_stats,
        )
    )

    # Monitoring tools
    registry.register_tool(
        ToolMetadata(
            name="get_weak_signal_books",
            description="Get books with weak RFID signal strength that may need maintenance or relocation.",
            input_schema={
                "type": "object",
                "properties": {
                    "threshold": {
                        "type": "number",
                        "default": -55,
                        "description": "Signal strength threshold in dBm (default: -55)",
                    },
                },
                "required": [],
            },
            capabilities=[Capability.MONITORING.value],
            handler=get_weak_signal_books,
        )
    )

    registry.register_tool(
        ToolMetadata(
            name="find_books_in_cabinet",
            description="List all books in a specific cabinet, optionally filtered by rack.",
            input_schema={
                "type": "object",
                "properties": {
                    "cabinet": {
                        "type": "integer",
                        "description": "Cabinet number",
                    },
                    "rack": {
                        "type": "integer",
                        "description": "Optional rack number within cabinet",
                    },
                },
                "required": ["cabinet"],
            },
            capabilities=[Capability.SEARCH.value],
            handler=find_books_in_cabinet,
        )
    )

    return registry
