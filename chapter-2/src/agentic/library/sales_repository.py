"""Sales repository - re-exported from MCP package.

This module re-exports the SalesRepository class from the MCP package to avoid
code duplication. The canonical implementation lives in src/mcp/sales_repository.py.

Usage:
    from src.agentic.library.sales_repository import SalesRepository, get_sales_repository
"""

# Re-export all sales repository classes from MCP package
from src.mcp.sales_repository import (
    SalesRepository,
    get_sales_repository,
)

__all__ = [
    "SalesRepository",
    "get_sales_repository",
]
