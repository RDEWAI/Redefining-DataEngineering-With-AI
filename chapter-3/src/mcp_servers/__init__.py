"""MCP servers package for library operations.

This package contains FastMCP server implementations exposing library
tools, resources, and prompts following the Model Context Protocol.
"""

from .library_server import mcp

__all__ = ['mcp']
