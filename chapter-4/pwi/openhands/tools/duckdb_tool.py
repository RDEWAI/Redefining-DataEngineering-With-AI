"""DuckDB tools for PWI OpenHands agents using official SDK pattern.

This module provides tools for interacting with DuckDB databases:
- DuckDBQueryTool: Execute SQL queries
- DuckDBSchemaTool: Get table schema information
- DuckDBValidateTool: Validate SQL syntax
- DuckDBTablesTool: List all tables
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import Field
from rich.text import Text

from openhands.sdk.tool import (
    Action,
    Observation,
    ToolAnnotations,
    ToolDefinition,
    ToolExecutor,
    register_tool,
)

if TYPE_CHECKING:
    from openhands.sdk.conversation.state import ConversationState

from pwi.utils.logging import get_logger

logger = get_logger("openhands.tools.duckdb")

# Default database path (relative to chapter-4/)
DEFAULT_DB_PATH = "../data/duckdb/raw.db"


# =============================================================================
# DuckDB Query Tool
# =============================================================================


class DuckDBQueryAction(Action):
    """Schema for DuckDB query execution."""

    query: str = Field(description="SQL query to execute against the DuckDB database")
    database_path: str | None = Field(
        default=None,
        description=f"Path to DuckDB database file (default: {DEFAULT_DB_PATH})",
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum number of rows to return (default: 100)",
    )

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation."""
        content = Text()
        content.append("SQL> ", style="bold cyan")
        content.append(self.query[:100], style="white")
        if len(self.query) > 100:
            content.append("...", style="dim")
        if self.limit != 100:
            content.append(f" [limit: {self.limit}]", style="yellow")
        return content


class DuckDBQueryObservation(Observation):
    """Result of DuckDB query execution."""

    success: bool = Field(description="Whether the query executed successfully")
    columns: list[str] = Field(default_factory=list, description="Column names")
    rows: list[list[Any]] = Field(default_factory=list, description="Result rows")
    row_count: int = Field(default=0, description="Number of rows returned")
    error: str | None = Field(default=None, description="Error message if failed")

    @property
    def visualize(self) -> Text:
        """Return Rich Text representation."""
        text = Text()
        if self.success:
            text.append("", style="green")
            text.append(f" Query returned {self.row_count} rows\n", style="green")
            if self.columns:
                text.append(" | ".join(self.columns), style="bold")
        else:
            text.append("", style="red")
            text.append(f" Error: {self.error}", style="red")
        return text


class DuckDBQueryExecutor(ToolExecutor[DuckDBQueryAction, DuckDBQueryObservation]):
    """Executor for DuckDB query tool."""

    def __init__(self, default_db_path: str = DEFAULT_DB_PATH):
        self.default_db_path = default_db_path

    def _get_connection(self, database_path: str | None = None) -> Any:
        """Get a DuckDB connection."""
        import duckdb

        db_path = database_path or self.default_db_path
        if not Path(db_path).exists():
            logger.warning(f"Database file not found: {db_path}")
            return duckdb.connect(":memory:")
        return duckdb.connect(db_path, read_only=True)

    def __call__(
        self, action: DuckDBQueryAction, conversation: Any = None
    ) -> DuckDBQueryObservation:
        """Execute the SQL query."""
        try:
            conn = self._get_connection(action.database_path)
            query = action.query

            # Add LIMIT if not present
            query_lower = query.lower().strip()
            if "limit" not in query_lower and not query_lower.startswith(
                ("create", "insert", "update", "delete", "drop")
            ):
                query = f"{query.rstrip(';')} LIMIT {action.limit}"

            result = conn.execute(query)
            columns = [desc[0] for desc in result.description] if result.description else []
            rows = result.fetchall()

            logger.info(f"Query executed: {len(rows)} rows returned")

            return DuckDBQueryObservation(
                success=True,
                columns=columns,
                rows=[list(row) for row in rows],
                row_count=len(rows),
            )

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return DuckDBQueryObservation(
                success=False,
                error=str(e),
            )


class DuckDBQueryTool(ToolDefinition[DuckDBQueryAction, DuckDBQueryObservation]):
    """Tool for executing SQL queries against DuckDB."""

    name = "duckdb_query"

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState",
        db_path: str | None = None,
        executor: ToolExecutor | None = None,
    ) -> Sequence["DuckDBQueryTool"]:
        """Create DuckDB query tool instance."""
        if executor is None:
            executor = DuckDBQueryExecutor(default_db_path=db_path or DEFAULT_DB_PATH)

        return [
            cls(
                action_type=DuckDBQueryAction,
                observation_type=DuckDBQueryObservation,
                description="Execute a SQL query against DuckDB database and return results. "
                "The query will automatically have a LIMIT clause added if not present.",
                annotations=ToolAnnotations(
                    title="DuckDB Query",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
                executor=executor,
            )
        ]


# =============================================================================
# DuckDB Schema Tool
# =============================================================================


class DuckDBSchemaAction(Action):
    """Schema for DuckDB schema retrieval."""

    table_name: str = Field(
        description="Table name (e.g., 'synthea.patients' or just 'patients')"
    )
    database_path: str | None = Field(
        default=None,
        description=f"Path to DuckDB database file (default: {DEFAULT_DB_PATH})",
    )

    @property
    def visualize(self) -> Text:
        content = Text()
        content.append("SCHEMA> ", style="bold magenta")
        content.append(self.table_name, style="white")
        return content


class DuckDBSchemaObservation(Observation):
    """Result of DuckDB schema retrieval."""

    success: bool = Field(description="Whether schema retrieval succeeded")
    table_name: str = Field(description="Full table name")
    schema_name: str | None = Field(default=None, description="Schema name if present")
    columns: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Column information (name, type, nullable, default, primary_key)",
    )
    column_count: int = Field(default=0, description="Number of columns")
    row_count: int | None = Field(default=None, description="Number of rows in table")
    error: str | None = Field(default=None, description="Error message if failed")

    @property
    def visualize(self) -> Text:
        text = Text()
        if self.success:
            text.append("", style="green")
            text.append(f" Table {self.table_name}: ", style="green")
            text.append(f"{self.column_count} columns", style="bold")
            if self.row_count is not None:
                text.append(f", {self.row_count} rows", style="dim")
        else:
            text.append("", style="red")
            text.append(f" Error: {self.error}", style="red")
        return text


class DuckDBSchemaExecutor(ToolExecutor[DuckDBSchemaAction, DuckDBSchemaObservation]):
    """Executor for DuckDB schema tool."""

    def __init__(self, default_db_path: str = DEFAULT_DB_PATH):
        self.default_db_path = default_db_path

    def _get_connection(self, database_path: str | None = None) -> Any:
        import duckdb

        db_path = database_path or self.default_db_path
        if not Path(db_path).exists():
            return duckdb.connect(":memory:")
        return duckdb.connect(db_path, read_only=True)

    def __call__(
        self, action: DuckDBSchemaAction, conversation: Any = None
    ) -> DuckDBSchemaObservation:
        """Get schema information for a table."""
        try:
            conn = self._get_connection(action.database_path)

            # Parse schema and table
            if "." in action.table_name:
                schema, table = action.table_name.split(".", 1)
            else:
                schema = None
                table = action.table_name

            # Get column information using PRAGMA
            query = f"PRAGMA table_info('{action.table_name}')"
            result = conn.execute(query)
            columns_info = result.fetchall()

            if not columns_info and not schema:
                result = conn.execute(f"PRAGMA table_info('{table}')")
                columns_info = result.fetchall()

            columns = []
            for col in columns_info:
                columns.append({
                    "name": col[1],
                    "type": col[2],
                    "nullable": col[3] == 0,
                    "default": col[4],
                    "primary_key": col[5] == 1,
                })

            # Get row count
            row_count = None
            try:
                count_result = conn.execute(f"SELECT COUNT(*) FROM {action.table_name}")
                row_count = count_result.fetchone()[0]
            except Exception:
                pass

            logger.info(f"Schema retrieved for {action.table_name}: {len(columns)} columns")

            return DuckDBSchemaObservation(
                success=True,
                table_name=action.table_name,
                schema_name=schema,
                columns=columns,
                column_count=len(columns),
                row_count=row_count,
            )

        except Exception as e:
            logger.error(f"Schema retrieval failed: {e}")
            return DuckDBSchemaObservation(
                success=False,
                table_name=action.table_name,
                error=str(e),
            )


class DuckDBSchemaTool(ToolDefinition[DuckDBSchemaAction, DuckDBSchemaObservation]):
    """Tool for retrieving DuckDB table schema information."""

    name = "duckdb_schema"

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState",
        db_path: str | None = None,
        executor: ToolExecutor | None = None,
    ) -> Sequence["DuckDBSchemaTool"]:
        """Create DuckDB schema tool instance."""
        if executor is None:
            executor = DuckDBSchemaExecutor(default_db_path=db_path or DEFAULT_DB_PATH)

        return [
            cls(
                action_type=DuckDBSchemaAction,
                observation_type=DuckDBSchemaObservation,
                description="Get schema information for a DuckDB table including "
                "columns, types, nullability, defaults, and row count.",
                annotations=ToolAnnotations(
                    title="DuckDB Schema",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
                executor=executor,
            )
        ]


# =============================================================================
# DuckDB Validate Tool
# =============================================================================


class DuckDBValidateAction(Action):
    """Schema for DuckDB query validation."""

    query: str = Field(description="SQL query to validate")
    database_path: str | None = Field(
        default=None,
        description=f"Path to DuckDB database file (default: {DEFAULT_DB_PATH})",
    )

    @property
    def visualize(self) -> Text:
        content = Text()
        content.append("VALIDATE> ", style="bold yellow")
        content.append(self.query[:80], style="white")
        if len(self.query) > 80:
            content.append("...", style="dim")
        return content


class DuckDBValidateObservation(Observation):
    """Result of DuckDB query validation."""

    success: bool = Field(description="Whether validation completed")
    valid: bool = Field(default=False, description="Whether the SQL is valid")
    message: str = Field(description="Validation result message")

    @property
    def visualize(self) -> Text:
        text = Text()
        if self.valid:
            text.append(" SQL syntax is valid", style="green")
        else:
            text.append(f" {self.message}", style="red")
        return text


class DuckDBValidateExecutor(ToolExecutor[DuckDBValidateAction, DuckDBValidateObservation]):
    """Executor for DuckDB validate tool."""

    def __init__(self, default_db_path: str = DEFAULT_DB_PATH):
        self.default_db_path = default_db_path

    def _get_connection(self, database_path: str | None = None) -> Any:
        import duckdb

        db_path = database_path or self.default_db_path
        if not Path(db_path).exists():
            return duckdb.connect(":memory:")
        return duckdb.connect(db_path, read_only=True)

    def __call__(
        self, action: DuckDBValidateAction, conversation: Any = None
    ) -> DuckDBValidateObservation:
        """Validate SQL syntax without executing."""
        try:
            conn = self._get_connection(action.database_path)
            explain_query = f"EXPLAIN {action.query}"
            conn.execute(explain_query)

            logger.info("Query validation successful")
            return DuckDBValidateObservation(
                success=True,
                valid=True,
                message="SQL syntax is valid",
            )

        except Exception as e:
            error_msg = str(e)
            logger.warning(f"Query validation failed: {error_msg}")
            return DuckDBValidateObservation(
                success=True,
                valid=False,
                message=f"SQL syntax error: {error_msg}",
            )


class DuckDBValidateTool(ToolDefinition[DuckDBValidateAction, DuckDBValidateObservation]):
    """Tool for validating SQL syntax without executing."""

    name = "duckdb_validate"

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState",
        db_path: str | None = None,
        executor: ToolExecutor | None = None,
    ) -> Sequence["DuckDBValidateTool"]:
        """Create DuckDB validate tool instance."""
        if executor is None:
            executor = DuckDBValidateExecutor(default_db_path=db_path or DEFAULT_DB_PATH)

        return [
            cls(
                action_type=DuckDBValidateAction,
                observation_type=DuckDBValidateObservation,
                description="Validate SQL syntax without executing the query. "
                "Uses EXPLAIN to check if the query is syntactically correct.",
                annotations=ToolAnnotations(
                    title="DuckDB Validate",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
                executor=executor,
            )
        ]


# =============================================================================
# DuckDB Tables Tool
# =============================================================================


class DuckDBTablesAction(Action):
    """Schema for listing DuckDB tables."""

    database_path: str | None = Field(
        default=None,
        description=f"Path to DuckDB database file (default: {DEFAULT_DB_PATH})",
    )
    schema_name: str | None = Field(
        default=None,
        description="Schema name to filter (e.g., 'synthea')",
    )

    @property
    def visualize(self) -> Text:
        content = Text()
        content.append("TABLES> ", style="bold blue")
        if self.schema_name:
            content.append(f"schema={self.schema_name}", style="white")
        else:
            content.append("all schemas", style="dim")
        return content


class DuckDBTablesObservation(Observation):
    """Result of listing DuckDB tables."""

    success: bool = Field(description="Whether table listing succeeded")
    tables: list[dict[str, str]] = Field(
        default_factory=list,
        description="List of tables with schema, table, and full_name",
    )
    count: int = Field(default=0, description="Number of tables found")
    error: str | None = Field(default=None, description="Error message if failed")

    @property
    def visualize(self) -> Text:
        text = Text()
        if self.success:
            text.append("", style="green")
            text.append(f" Found {self.count} tables\n", style="green")
            for t in self.tables[:10]:
                text.append(f"  {t['full_name']}\n", style="white")
            if self.count > 10:
                text.append(f"  ... and {self.count - 10} more", style="dim")
        else:
            text.append("", style="red")
            text.append(f" Error: {self.error}", style="red")
        return text


class DuckDBTablesExecutor(ToolExecutor[DuckDBTablesAction, DuckDBTablesObservation]):
    """Executor for DuckDB tables tool."""

    def __init__(self, default_db_path: str = DEFAULT_DB_PATH):
        self.default_db_path = default_db_path

    def _get_connection(self, database_path: str | None = None) -> Any:
        import duckdb

        db_path = database_path or self.default_db_path
        if not Path(db_path).exists():
            return duckdb.connect(":memory:")
        return duckdb.connect(db_path, read_only=True)

    def __call__(
        self, action: DuckDBTablesAction, conversation: Any = None
    ) -> DuckDBTablesObservation:
        """List all tables in the database."""
        try:
            conn = self._get_connection(action.database_path)

            if action.schema_name:
                query = f"""
                    SELECT table_schema, table_name
                    FROM information_schema.tables
                    WHERE table_schema = '{action.schema_name}'
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

            return DuckDBTablesObservation(
                success=True,
                tables=table_list,
                count=len(table_list),
            )

        except Exception as e:
            logger.error(f"Table listing failed: {e}")
            return DuckDBTablesObservation(
                success=False,
                error=str(e),
            )


class DuckDBTablesTool(ToolDefinition[DuckDBTablesAction, DuckDBTablesObservation]):
    """Tool for listing all tables in DuckDB database."""

    name = "duckdb_tables"

    @classmethod
    def create(
        cls,
        conv_state: "ConversationState",
        db_path: str | None = None,
        executor: ToolExecutor | None = None,
    ) -> Sequence["DuckDBTablesTool"]:
        """Create DuckDB tables tool instance."""
        if executor is None:
            executor = DuckDBTablesExecutor(default_db_path=db_path or DEFAULT_DB_PATH)

        return [
            cls(
                action_type=DuckDBTablesAction,
                observation_type=DuckDBTablesObservation,
                description="List all tables in the DuckDB database. "
                "Optionally filter by schema name.",
                annotations=ToolAnnotations(
                    title="DuckDB Tables",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
                executor=executor,
            )
        ]


# =============================================================================
# Tool Registration
# =============================================================================

# Register all DuckDB tools with the SDK
register_tool(DuckDBQueryTool.name, DuckDBQueryTool)
register_tool(DuckDBSchemaTool.name, DuckDBSchemaTool)
register_tool(DuckDBValidateTool.name, DuckDBValidateTool)
register_tool(DuckDBTablesTool.name, DuckDBTablesTool)

logger.info("DuckDB tools registered with OpenHands SDK")


# =============================================================================
# Convenience Exports
# =============================================================================

__all__ = [
    # Query Tool
    "DuckDBQueryTool",
    "DuckDBQueryAction",
    "DuckDBQueryObservation",
    "DuckDBQueryExecutor",
    # Schema Tool
    "DuckDBSchemaTool",
    "DuckDBSchemaAction",
    "DuckDBSchemaObservation",
    "DuckDBSchemaExecutor",
    # Validate Tool
    "DuckDBValidateTool",
    "DuckDBValidateAction",
    "DuckDBValidateObservation",
    "DuckDBValidateExecutor",
    # Tables Tool
    "DuckDBTablesTool",
    "DuckDBTablesAction",
    "DuckDBTablesObservation",
    "DuckDBTablesExecutor",
]
