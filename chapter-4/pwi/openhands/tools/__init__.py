"""Custom tools for PWI OpenHands agents.

This module provides custom tool definitions for external system integration:
- DuckDB tools: Query execution, schema inspection, SQL validation
- CSV tools: File analysis, data sampling, statistics
- Metadata tools: External catalog API integration
- Artifact tools: Structured artifact generation helpers

Usage:
    from pwi.openhands.tools import get_registry, get_all_tools

    # Get all registered tools
    tools = get_all_tools()

    # Get specific tools for an agent
    registry = get_registry()
    duckdb_tools = registry.get_tools(["duckdb_query", "duckdb_schema"])
"""

from pwi.openhands.tools.base import (
    ToolRegistry,
    create_tool,
    get_registry,
    register_tool,
)

# Import tools to trigger auto-registration
from pwi.openhands.tools.duckdb_tool import (
    DuckDBQueryTool,
    DuckDBSchemaTool,
    DuckDBTablesTool,
    DuckDBValidateTool,
)
from pwi.openhands.tools.csv_tool import (
    AnalyzeCSVTool,
    CSVSampleTool,
    CSVStatsTool,
)
from pwi.openhands.tools.metadata_tool import (
    GetLineageTool,
    GetTagsTool,
    QueryMetadataCatalogTool,
)
from pwi.openhands.tools.artifact_tool import (
    GenerateArtifactTool,
    ListArtifactTypesTool,
    SaveArtifactTool,
    ValidateArtifactTool,
)


def get_all_tools() -> list:
    """Get all registered PWI tools.

    Returns:
        List of all tool definitions.
    """
    return get_registry().get_tools()


def get_tools_for_agent(agent_name: str) -> list:
    """Get tools appropriate for a specific agent.

    Args:
        agent_name: Name of the agent (e.g., 'data_analyst').

    Returns:
        List of tool definitions for the agent.
    """
    # Define which tools each agent should have access to
    agent_tools = {
        "data_analyst": [
            "duckdb_query",
            "duckdb_schema",
            "duckdb_tables",
            "analyze_csv",
            "csv_stats",
        ],
        "data_architect": [
            "duckdb_schema",
            "duckdb_tables",
            "duckdb_query",
        ],
        "mapping_engineer": [
            "duckdb_schema",
            "duckdb_tables",
            "analyze_csv",
            "csv_sample",
            "query_metadata_catalog",
        ],
        "dq_engineer": [
            "duckdb_query",
            "duckdb_schema",
            "duckdb_validate",
            "analyze_csv",
        ],
        "story_writer": [
            "generate_artifact",
            "validate_artifact",
            "list_artifact_types",
        ],
        "sync_agent": [
            "generate_artifact",
            "save_artifact",
            "validate_artifact",
            "list_artifact_types",
        ],
    }

    tool_names = agent_tools.get(agent_name, [])
    return get_registry().get_tools(tool_names)


__all__ = [
    # Base
    "ToolRegistry",
    "create_tool",
    "get_registry",
    "register_tool",
    # Functions
    "get_all_tools",
    "get_tools_for_agent",
    # DuckDB Tools
    "DuckDBQueryTool",
    "DuckDBSchemaTool",
    "DuckDBTablesTool",
    "DuckDBValidateTool",
    # CSV Tools
    "AnalyzeCSVTool",
    "CSVSampleTool",
    "CSVStatsTool",
    # Metadata Tools
    "QueryMetadataCatalogTool",
    "GetLineageTool",
    "GetTagsTool",
    # Artifact Tools
    "GenerateArtifactTool",
    "SaveArtifactTool",
    "ValidateArtifactTool",
    "ListArtifactTypesTool",
]
