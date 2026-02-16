"""Data source discovery tool for PWI OpenHands agents.

This module provides a tool to automatically discover available data sources:
- discover_data: Auto-detect CSV files, DuckDB databases, and their contents

The discovery tool helps agents intelligently choose between CSV tools and DuckDB tools
based on what's actually available in the environment.

Usage:
    from pwi.openhands.tools.discovery_tool import DataDiscoveryTool
    # Tools are auto-registered on import
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import Field

from openhands.sdk import Action, Observation
from openhands.sdk.tool import ToolDefinition, ToolExecutor, register_tool

from pwi.utils.logging import get_logger

logger = get_logger("openhands.tools.discovery")


# Common paths to search for data
DEFAULT_CSV_PATHS = [
    "data/raw",
    "chapter-4/data/raw",
    "../data/raw",
    "data",
    ".",
]

DEFAULT_DUCKDB_PATHS = [
    "data/duckdb/raw.db",
    "chapter-4/data/duckdb/raw.db",
    "../data/duckdb/raw.db",
    "data/raw.db",
    "data/database.db",
    "data/analytics.db",
]


class DataDiscoveryAction(Action):
    """Schema for data discovery action."""

    csv_search_paths: list[str] | None = Field(
        default=None,
        description="Paths to search for CSV files (uses defaults if not specified)",
    )
    duckdb_search_paths: list[str] | None = Field(
        default=None,
        description="Paths to search for DuckDB databases (uses defaults if not specified)",
    )
    working_dir: str | None = Field(
        default=None,
        description="Working directory for relative paths (defaults to current dir)",
    )


class DataDiscoveryObservation(Observation):
    """Schema for data discovery result."""

    success: bool = Field(default=True)

    # CSV discovery results
    csv_found: bool = Field(default=False)
    csv_directory: str | None = Field(default=None)
    csv_files: list[dict[str, Any]] = Field(default_factory=list)
    csv_file_count: int = Field(default=0)

    # DuckDB discovery results
    duckdb_found: bool = Field(default=False)
    duckdb_path: str | None = Field(default=None)
    duckdb_schemas: list[str] = Field(default_factory=list)
    duckdb_tables: list[dict[str, str]] = Field(default_factory=list)
    duckdb_table_count: int = Field(default=0)

    # Recommendations
    recommended_approach: str = Field(default="")
    recommended_tools: list[str] = Field(default_factory=list)

    error: str | None = Field(default=None)


class DataDiscoveryExecutor(ToolExecutor[DataDiscoveryAction, DataDiscoveryObservation]):
    """Executor for data source discovery."""

    def _find_csv_directory(self, search_paths: list[str], working_dir: Path) -> tuple[Path | None, list[dict[str, Any]]]:
        """Find a directory containing CSV files."""
        for search_path in search_paths:
            if search_path.startswith("/"):
                path = Path(search_path)
            else:
                path = working_dir / search_path

            if path.exists() and path.is_dir():
                csv_files = list(path.glob("*.csv"))
                if csv_files:
                    file_info = []
                    for f in sorted(csv_files):
                        try:
                            size = f.stat().st_size
                            file_info.append({
                                "name": f.name,
                                "path": str(f),
                                "size_bytes": size,
                                "size_human": self._format_size(size),
                            })
                        except Exception:
                            file_info.append({
                                "name": f.name,
                                "path": str(f),
                                "size_bytes": 0,
                                "size_human": "unknown",
                            })
                    return path, file_info
        return None, []

    def _format_size(self, size_bytes: int) -> str:
        """Format bytes into human-readable string."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def _find_duckdb(self, search_paths: list[str], working_dir: Path) -> tuple[Path | None, list[str], list[dict[str, str]]]:
        """Find a DuckDB database and list its contents."""
        for search_path in search_paths:
            if search_path.startswith("/"):
                path = Path(search_path)
            else:
                path = working_dir / search_path

            if path.exists() and path.is_file():
                try:
                    import duckdb
                    conn = duckdb.connect(str(path), read_only=True)

                    # Get schemas
                    schemas_result = conn.execute(
                        "SELECT DISTINCT table_schema FROM information_schema.tables "
                        "WHERE table_schema NOT IN ('information_schema', 'pg_catalog')"
                    ).fetchall()
                    schemas = [row[0] for row in schemas_result]

                    # Get tables
                    tables_result = conn.execute(
                        "SELECT table_schema, table_name FROM information_schema.tables "
                        "WHERE table_schema NOT IN ('information_schema', 'pg_catalog') "
                        "ORDER BY table_schema, table_name"
                    ).fetchall()
                    tables = [{"schema": row[0], "table": row[1], "qualified_name": f"{row[0]}.{row[1]}"} for row in tables_result]

                    conn.close()
                    return path, schemas, tables
                except Exception as e:
                    logger.warning(f"Could not open DuckDB at {path}: {e}")
                    continue
        return None, [], []

    def __call__(
        self, action: DataDiscoveryAction, conversation: Any = None
    ) -> DataDiscoveryObservation:
        """Execute data source discovery."""
        try:
            working_dir = Path(action.working_dir) if action.working_dir else Path.cwd()

            # Search for CSV files
            csv_paths = action.csv_search_paths or DEFAULT_CSV_PATHS
            csv_dir, csv_files = self._find_csv_directory(csv_paths, working_dir)

            # Search for DuckDB database
            duckdb_paths = action.duckdb_search_paths or DEFAULT_DUCKDB_PATHS
            duckdb_path, duckdb_schemas, duckdb_tables = self._find_duckdb(duckdb_paths, working_dir)

            # Determine recommendations
            # Priority: CSV files first (raw source of truth), then DuckDB as derived/loaded data
            if csv_dir and csv_files:
                recommended_approach = "csv"
                recommended_tools = ["analyze_csv", "csv_stats", "csv_sample"]
                recommendation_reason = f"CSV files found at {csv_dir} ({len(csv_files)} files)"
            elif duckdb_path and duckdb_tables:
                recommended_approach = "duckdb"
                recommended_tools = ["duckdb_tables", "duckdb_schema", "duckdb_query"]
                recommendation_reason = f"DuckDB database found at {duckdb_path} with {len(duckdb_tables)} tables"
            else:
                recommended_approach = "none"
                recommended_tools = []
                recommendation_reason = "No data sources found - check paths in request document"

            logger.info(f"Data discovery complete: {recommendation_reason}")

            return DataDiscoveryObservation(
                success=True,
                csv_found=csv_dir is not None,
                csv_directory=str(csv_dir) if csv_dir else None,
                csv_files=csv_files,
                csv_file_count=len(csv_files),
                duckdb_found=duckdb_path is not None,
                duckdb_path=str(duckdb_path) if duckdb_path else None,
                duckdb_schemas=duckdb_schemas,
                duckdb_tables=duckdb_tables,
                duckdb_table_count=len(duckdb_tables),
                recommended_approach=recommended_approach,
                recommended_tools=recommended_tools,
            )

        except Exception as e:
            logger.error(f"Data discovery failed: {e}")
            return DataDiscoveryObservation(success=False, error=str(e))


class DataDiscoveryTool(ToolDefinition[DataDiscoveryAction, DataDiscoveryObservation]):
    """Tool definition for data source discovery."""

    name = "discover_data"

    @classmethod
    def create(cls, conv_state: Any = None, **kwargs: Any) -> list[ToolDefinition]:
        """Create the tool instance."""
        return [
            cls(
                action_type=DataDiscoveryAction,
                observation_type=DataDiscoveryObservation,
                description=(
                    "Discover available data sources (CSV files and DuckDB databases). "
                    "Call this FIRST to determine which tools to use for data exploration. "
                    "Returns paths to data and recommends appropriate tools."
                ),
                executor=DataDiscoveryExecutor(),
            )
        ]


# =============================================================================
# Register Tool with SDK
# =============================================================================


def _register_discovery_tools() -> None:
    """Register data discovery tool with the OpenHands SDK registry."""
    register_tool("discover_data", DataDiscoveryTool)
    logger.info("Data discovery tool registered with OpenHands SDK")


# Auto-register on import
_register_discovery_tools()


__all__ = [
    "DataDiscoveryAction",
    "DataDiscoveryObservation",
    "DataDiscoveryTool",
]
