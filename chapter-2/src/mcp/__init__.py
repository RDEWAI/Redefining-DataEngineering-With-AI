"""MCP (Model Context Protocol) Package.

This package provides MCP server and client implementations for the Library
Management System, demonstrating how to expose tools to AI applications.

The package includes:
- library_server: FastMCP server exposing library and lending tools, resources, and prompts
- client: Unified MCP client with configuration and assistant integration
- lending_domain: Lending domain classes (Loan, PatronSegment, Region, Channel)
- lending_repository: Lending database repository for DuckDB operations

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
# For lending: from src.mcp.lending_repository import LendingRepository

__all__ = ["library_server", "client", "lending_domain", "lending_repository"]
