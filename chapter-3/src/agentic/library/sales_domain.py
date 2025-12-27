"""Sales domain classes - re-exported from MCP package.

This module re-exports sales domain classes from the MCP package to avoid
code duplication. The canonical implementation lives in src/mcp/sales_domain.py.

Usage:
    from src.agentic.library.sales_domain import Sale, CustomerSegment, Region, Channel
"""

# Re-export all sales domain classes from MCP package
from src.mcp.sales_domain import (
    Channel,
    CustomerSegment,
    PaymentMethod,
    Region,
    Sale,
)

__all__ = [
    "Sale",
    "CustomerSegment",
    "Region",
    "Channel",
    "PaymentMethod",
]
