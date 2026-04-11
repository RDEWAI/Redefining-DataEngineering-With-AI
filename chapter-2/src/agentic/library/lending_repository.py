"""Lending repository - re-exported from MCP package.

This module re-exports the LendingRepository class from the MCP package to avoid
code duplication. The canonical implementation lives in src/mcp/lending_repository.py.

Usage:
    from src.agentic.library.lending_repository import LendingRepository, get_lending_repository
"""

# Re-export all lending repository classes from MCP package
from src.mcp.lending_repository import (
    LendingRepository,
    get_lending_repository,
)

__all__ = [
    "LendingRepository",
    "get_lending_repository",
]
