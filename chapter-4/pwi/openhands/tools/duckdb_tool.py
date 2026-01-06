"""DuckDB tools for PWI OpenHands agents.

This module provides tools for interacting with DuckDB databases:
- duckdb_query: Execute SQL queries
- duckdb_schema: Get table schema information
- duckdb_validate: Validate SQL syntax
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pwi.openhands.tools.base import create_tool, register_tool
from pwi.utils.logging import get_logger

logger = get_logger("openhands.tools.duckdb")

# Default database path (relative to chapter-4/)
DEFAULT_DB_PATH = "../data/duckdb/raw.db"


# =============================================================================
# Tool Definitions
# =============================================================================

DuckDBQueryTool = create_tool(
    name="duckdb_query",
    description="Execute a SQL query against DuckDB database and return results",
    parameters={
        "query": {
            "type": "string",
            "description": "SQL query to execute",
        },
        "database_path": {
            "type": "string",
            "description": f"Path to DuckDB database file (default: {DEFAULT_DB_PATH})",
        },
        "limit": {
            "type": "integer",
            "description": "Maximum rows to return (default: 100)",
        },
    },
    required=["query"],
)

DuckDBSchemaTool = create_tool(
    name="duckdb_schema",
    description="Get schema information for a DuckDB table including columns, types, and constraints",
    parameters={
        "table_name": {
            "type": "string",
            "description": "Table name (e.g., 'synthea.patients' or just 'patients')",
        },
        "database_path": {
            "type": "string",
            "description": f"Path to DuckDB database file (default: {DEFAULT_DB_PATH})",
        },
    },
    required=["table_name"],
)

DuckDBValidateTool = create_tool(
    name="duckdb_validate",
    description="Validate SQL syntax without executing the query",
    parameters={
        "query": {
            "type": "string",
            "description": "SQL query to validate",
        },
        "database_path": {
            "type": "string",
            "description": f"Path to DuckDB database file (default: {DEFAULT_DB_PATH})",
        },
    },
    required=["query"],
)

DuckDBTablesTool = create_tool(
    name="duckdb_tables",
    description="List all tables in the DuckDB database",
    parameters={
        "database_path": {
            "type": "string",
            "description": f"Path to DuckDB database file (default: {DEFAULT_DB_PATH})",
        },
        "schema_name": {
            "type": "string",
            "description": "Schema name to filter (e.g., 'synthea')",
        },
    },
    required=[],
)


# =============================================================================
# Tool Executors
# =============================================================================

def _get_connection(database_path: str | None = None) -> Any:
    """Get a DuckDB connection.

    Args:
        database_path: Path to database file.

    Returns:
        DuckDB connection.
    """
    import duckdb

    db_path = database_path or DEFAULT_DB_PATH
    if not Path(db_path).exists():
        logger.warning(f"Database file not found: {db_path}")
        # Return in-memory connection for validation
        return duckdb.connect(":memory:")
    return duckdb.connect(db_path, read_only=True)


def execute_duckdb_query(
    query: str,
    database_path: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Execute a SQL query against DuckDB.

    Args:
        query: SQL query to execute.
        database_path: Path to database file.
        limit: Maximum rows to return.

    Returns:
        Dictionary with columns and rows.
    """
    try:
        conn = _get_connection(database_path)

        # Add LIMIT if not present
        query_lower = query.lower().strip()
        if "limit" not in query_lower and not query_lower.startswith(("create", "insert", "update", "delete", "drop")):
            query = f"{query.rstrip(';')} LIMIT {limit}"

        result = conn.execute(query)
        columns = [desc[0] for desc in result.description] if result.description else []
        rows = result.fetchall()

        logger.info(f"Query executed: {len(rows)} rows returned")

        return {
            "success": True,
            "columns": columns,
            "rows": [list(row) for row in rows],
            "row_count": len(rows),
        }

    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "columns": [],
            "rows": [],
            "row_count": 0,
        }


def execute_duckdb_schema(
    table_name: str,
    database_path: str | None = None,
) -> dict[str, Any]:
    """Get schema information for a table.

    Args:
        table_name: Table name (with optional schema prefix).
        database_path: Path to database file.

    Returns:
        Dictionary with table schema information.
    """
    try:
        conn = _get_connection(database_path)

        # Parse schema and table
        if "." in table_name:
            schema, table = table_name.split(".", 1)
        else:
            schema = None
            table = table_name

        # Get column information using PRAGMA
        if schema:
            query = f"PRAGMA table_info('{schema}.{table}')"
        else:
            query = f"PRAGMA table_info('{table}')"

        result = conn.execute(query)
        columns_info = result.fetchall()

        if not columns_info:
            # Try without schema
            result = conn.execute(f"PRAGMA table_info('{table}')")
            columns_info = result.fetchall()

        columns = []
        for col in columns_info:
            columns.append({
                "name": col[1],
                "type": col[2],
                "nullable": col[3] == 0,  # notnull is 0 when nullable
                "default": col[4],
                "primary_key": col[5] == 1,
            })

        # Get row count
        count_query = f"SELECT COUNT(*) FROM {table_name}" if schema else f"SELECT COUNT(*) FROM {table}"
        try:
            count_result = conn.execute(count_query if "." in table_name else f"SELECT COUNT(*) FROM {table}")
            row_count = count_result.fetchone()[0]
        except Exception:
            row_count = None

        logger.info(f"Schema retrieved for {table_name}: {len(columns)} columns")

        return {
            "success": True,
            "table_name": table_name,
            "schema": schema,
            "columns": columns,
            "column_count": len(columns),
            "row_count": row_count,
        }

    except Exception as e:
        logger.error(f"Schema retrieval failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "table_name": table_name,
            "columns": [],
        }


def execute_duckdb_validate(
    query: str,
    database_path: str | None = None,
) -> dict[str, Any]:
    """Validate SQL syntax without executing.

    Args:
        query: SQL query to validate.
        database_path: Path to database file.

    Returns:
        Dictionary with validation result.
    """
    try:
        conn = _get_connection(database_path)

        # Use EXPLAIN to validate without executing
        explain_query = f"EXPLAIN {query}"
        conn.execute(explain_query)

        logger.info("Query validation successful")

        return {
            "success": True,
            "valid": True,
            "message": "SQL syntax is valid",
        }

    except Exception as e:
        error_msg = str(e)
        logger.warning(f"Query validation failed: {error_msg}")

        return {
            "success": True,  # Validation completed, but query is invalid
            "valid": False,
            "message": f"SQL syntax error: {error_msg}",
        }


def execute_duckdb_tables(
    database_path: str | None = None,
    schema_name: str | None = None,
) -> dict[str, Any]:
    """List all tables in the database.

    Args:
        database_path: Path to database file.
        schema_name: Optional schema filter.

    Returns:
        Dictionary with table list.
    """
    try:
        conn = _get_connection(database_path)

        if schema_name:
            query = f"""
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema = '{schema_name}'
                ORDER BY table_name
            """
        else:
            query = """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
                ORDER BY table_schema, table_name
            """

        result = conn.execute(query)
        tables = result.fetchall()

        table_list = [
            {"schema": row[0], "table": row[1], "full_name": f"{row[0]}.{row[1]}"}
            for row in tables
        ]

        logger.info(f"Found {len(table_list)} tables")

        return {
            "success": True,
            "tables": table_list,
            "count": len(table_list),
        }

    except Exception as e:
        logger.error(f"Table listing failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "tables": [],
            "count": 0,
        }


# =============================================================================
# Register Tools
# =============================================================================

def register_duckdb_tools() -> None:
    """Register all DuckDB tools with the global registry."""
    register_tool(DuckDBQueryTool, execute_duckdb_query)
    register_tool(DuckDBSchemaTool, execute_duckdb_schema)
    register_tool(DuckDBValidateTool, execute_duckdb_validate)
    register_tool(DuckDBTablesTool, execute_duckdb_tables)
    logger.info("DuckDB tools registered")


# Auto-register on import
register_duckdb_tools()
