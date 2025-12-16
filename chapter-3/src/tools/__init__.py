"""Tool registry and dynamic tool discovery.

This package provides components for tool management:
- ToolRegistry: Register and manage tool handlers
- ToolSearch: Find tools by name or semantic similarity
- Capability: Tool capability categories

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
"""

from src.tools.tool_registry import (
    Capability,
    ToolMetadata,
    ToolRegistry,
    create_library_tool_registry,
)
from src.tools.tool_search import ToolSearch, create_tool_search

__all__ = [
    "ToolRegistry",
    "ToolMetadata",
    "Capability",
    "ToolSearch",
    "create_library_tool_registry",
    "create_tool_search",
]
