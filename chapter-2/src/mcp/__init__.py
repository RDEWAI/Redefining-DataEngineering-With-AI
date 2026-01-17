"""MCP (Model Context Protocol) Package.

This package provides MCP server and client implementations for the Library
Management System, demonstrating how to expose tools to AI applications.

The package includes:
- library_server: FastMCP server exposing library and sales tools, resources, and prompts
- client: Unified MCP client with configuration and assistant integration
- sales_domain: Sales domain classes (Sale, CustomerSegment, Region, Channel)
- sales_repository: Sales database repository for DuckDB operations

Usage:
    # Start MCP server (for Claude Desktop)
    make mcp-server

    # Unified MCP client (interactive menu + assistant)
    make mcp-client

    # MCP client with specific configuration
    make mcp-client ARGS="--rag"
    make mcp-client ARGS="--mode traditional"

    # Development mode with MCP Inspector
    make mcp-dev
"""

# Note: Imports are intentionally not done at module level to avoid
# circular import issues with the external 'mcp' package.
# Use direct imports: from src.mcp.library_server import mcp, repository
# For client config: from src.mcp.client import MCPClient, MCPClientConfig
# For sales: from src.mcp.sales_repository import SalesRepository

__all__ = ["library_server", "client", "sales_domain", "sales_repository"]
