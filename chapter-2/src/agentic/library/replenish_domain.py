"""Replenish domain classes - re-exported from MCP package.

This module re-exports replenish domain classes from the MCP package to avoid
code duplication. The canonical implementation lives in src/mcp/replenish_domain.py.

Usage:
    from src.agentic.library.replenish_domain import Replenishment, Supplier, ReplenishType
"""

# Re-export all replenish domain classes from MCP package
from src.mcp.replenish_domain import (
    BookCondition,
    FundingSource,
    Priority,
    Replenishment,
    ReplenishType,
    Supplier,
)

__all__ = [
    "Replenishment",
    "Supplier",
    "ReplenishType",
    "BookCondition",
    "FundingSource",
    "Priority",
]
