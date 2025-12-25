"""MCP (Model Context Protocol) Package.

This package provides MCP server and client implementations for the Library
Management System, demonstrating how to expose tools to AI applications.

The package includes:
- library_server: FastMCP server exposing library tools, resources, and prompts
- client: Interactive client for exploring MCP capabilities

Usage:
    # Start MCP server (for Claude Desktop)
    make mcp-server

    # Interactive client to explore tools
    make mcp-client

    # Development mode with MCP Inspector
    make mcp-dev
"""

from .library_server import mcp, repository

__all__ = ["mcp", "repository"]
