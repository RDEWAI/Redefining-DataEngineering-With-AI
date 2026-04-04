"""Replenish repository - re-exported from MCP package.

This module re-exports the ReplenishRepository class from the MCP package to avoid
code duplication. The canonical implementation lives in src/mcp/replenish_repository.py.

Usage:
    from src.agentic.library.replenish_repository import ReplenishRepository, get_replenish_repository
"""

# Re-export all replenish repository classes from MCP package
from src.mcp.replenish_repository import (
    ReplenishRepository,
    get_replenish_repository,
)

__all__ = [
    "ReplenishRepository",
    "get_replenish_repository",
]
