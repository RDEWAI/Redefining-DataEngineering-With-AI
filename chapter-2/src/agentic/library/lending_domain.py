"""Lending domain classes - re-exported from MCP package.

This module re-exports lending domain classes from the MCP package to avoid
code duplication. The canonical implementation lives in src/mcp/lending_domain.py.

Usage:
    from src.agentic.library.lending_domain import Loan, PatronSegment, Region, Channel
"""

# Re-export all lending domain classes from MCP package
from src.mcp.lending_domain import (
    Channel,
    Loan,
    PatronSegment,
    PaymentMethod,
    Region,
)

__all__ = [
    "Loan",
    "PatronSegment",
    "Region",
    "Channel",
    "PaymentMethod",
]
