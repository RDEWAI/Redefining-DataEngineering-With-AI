"""Tool registry and dynamic tool discovery.

This package provides components for tool management:
- ToolRegistry: Register and manage tool handlers
- ToolSearch: Find tools by name or semantic similarity
- Capability: Tool capability categories
- Dummy Tools: 100 enterprise dummy tools for scale demonstration

Example:
    >>> from src.tools import ToolRegistry, Capability
    >>> registry = ToolRegistry()
    >>> @registry.register(
    ...     description="Search books",
    ...     input_schema={"type": "object"},
    ...     capabilities=[Capability.SEARCH],
    ... )
    ... def search_books(query: str):
    ...     return []

    >>> # Generate 100 enterprise dummy tools
    >>> from src.tools import generate_dummy_tools, EnterpriseDomain
    >>> tools = generate_dummy_tools()
    >>> len(tools)
    100
"""

from src.tools.dummy_tools import (
    DummyTool,
    EnterpriseDomain,
    generate_dummy_tool_definitions,
    generate_dummy_tools,
    get_domain_tool_count,
    get_dummy_tool_functions,
    get_total_tool_count,
)
from src.tools.tool_registry import (
    Capability,
    ToolMetadata,
    ToolRegistry,
    create_library_tool_registry,
)
from src.tools.tool_search import ToolSearch, create_tool_search

__all__ = [
    # Tool Registry
    "ToolRegistry",
    "ToolMetadata",
    "Capability",
    "ToolSearch",
    "create_library_tool_registry",
    "create_tool_search",
    # Dummy Tools (Phase 7.5)
    "EnterpriseDomain",
    "DummyTool",
    "generate_dummy_tools",
    "generate_dummy_tool_definitions",
    "get_dummy_tool_functions",
    "get_domain_tool_count",
    "get_total_tool_count",
]
