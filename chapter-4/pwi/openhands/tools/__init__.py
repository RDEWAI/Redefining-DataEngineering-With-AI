"""Custom tools for PWI OpenHands agents using official SDK pattern.

This module provides custom tool definitions for external system integration:
- DuckDB tools: Query execution, schema inspection, SQL validation
- CSV tools: File analysis, data sampling, statistics
- Metadata tools: External catalog API integration
- Artifact tools: Structured artifact generation helpers

All tools use the OpenHands SDK ToolDefinition pattern and are auto-registered
when this module is imported.

Usage:
    from openhands.sdk.tool import Tool
    from pwi.openhands.tools import AGENT_TOOL_MAP

    # Get tool names for an agent
    tool_names = AGENT_TOOL_MAP["data_analyst"]

    # Create Tool specifications for SDK Agent
    tools = [Tool(name=name) for name in tool_names]
"""

from typing import TYPE_CHECKING

# Re-export SDK tool utilities
from openhands.sdk.tool import (
    Action,
    Observation,
    Tool,
    ToolAnnotations,
    ToolDefinition,
    ToolExecutor,
    register_tool,
)

if TYPE_CHECKING:
    pass

# Import DuckDB tools (SDK pattern) - auto-registers on import
from pwi.openhands.tools.duckdb_tool import (
    DuckDBQueryAction,
    DuckDBQueryObservation,
    DuckDBQueryTool,
    DuckDBSchemaAction,
    DuckDBSchemaObservation,
    DuckDBSchemaTool,
    DuckDBTablesAction,
    DuckDBTablesObservation,
    DuckDBTablesTool,
    DuckDBValidateAction,
    DuckDBValidateObservation,
    DuckDBValidateTool,
)

# Import CSV tools (SDK pattern) - auto-registers on import
from pwi.openhands.tools.csv_tool import (
    AnalyzeCSVAction,
    AnalyzeCSVObservation,
    AnalyzeCSVTool,
    CSVSampleAction,
    CSVSampleObservation,
    CSVSampleTool,
    CSVStatsAction,
    CSVStatsObservation,
    CSVStatsTool,
)

# Import Metadata tools (SDK pattern) - auto-registers on import
from pwi.openhands.tools.metadata_tool import (
    GetLineageAction,
    GetLineageObservation,
    GetLineageTool,
    GetTagsAction,
    GetTagsObservation,
    GetTagsTool,
    QueryMetadataCatalogAction,
    QueryMetadataCatalogObservation,
    QueryMetadataCatalogTool,
)

# Import Artifact tools (SDK pattern) - auto-registers on import
from pwi.openhands.tools.artifact_tool import (
    ARTIFACT_TYPES,
    GenerateArtifactAction,
    GenerateArtifactObservation,
    GenerateArtifactTool,
    ListArtifactTypesAction,
    ListArtifactTypesObservation,
    ListArtifactTypesTool,
    SaveArtifactAction,
    SaveArtifactObservation,
    SaveArtifactTool,
    ValidateArtifactAction,
    ValidateArtifactObservation,
    ValidateArtifactTool,
)

# Import Discovery tools (SDK pattern) - auto-registers on import
from pwi.openhands.tools.discovery_tool import (
    DataDiscoveryAction,
    DataDiscoveryObservation,
    DataDiscoveryTool,
)

# Legacy imports for backward compatibility during migration
# Keep base.py available but deprecated
try:
    from pwi.openhands.tools.base import (
        ToolRegistry,
        create_tool,
        get_registry,
        register_tool as legacy_register_tool,
    )

    LEGACY_TOOLS_AVAILABLE = True
except ImportError:
    LEGACY_TOOLS_AVAILABLE = False


# =============================================================================
# Agent Tool Mapping (SDK Pattern)
# =============================================================================

AGENT_TOOL_MAP: dict[str, list[str]] = {
    "data_analyst": [
        # SDK built-in tools
        "terminal",
        "file_editor",
        "task_tracker",
        # Discovery tool - CALL FIRST to determine which data tools to use
        "discover_data",
        # Domain tools (DuckDB)
        "duckdb_query",
        "duckdb_schema",
        "duckdb_tables",
        # Domain tools (CSV)
        "analyze_csv",
        "csv_stats",
    ],
    "data_architect": [
        # No exploration tools - data_architect generates PAD from DRD context
        # Adding exploration tools causes stuck detection (repeated duckdb_tables calls)
        "file_editor",
        "task_tracker",
    ],
    "mapping_engineer": [
        "terminal",
        "file_editor",
        "task_tracker",
        # Discovery tool - CALL FIRST to determine which data tools to use
        "discover_data",
        "duckdb_schema",
        "duckdb_tables",
        "analyze_csv",
        "csv_sample",
        "query_metadata_catalog",
        "get_lineage",
        "get_tags",
    ],
    "dq_engineer": [
        # NO TOOLS - DQ engineer must output DQS YAML directly as text
        # Using tools causes stuck detection loops
    ],
    "story_writer": [
        # No terminal - story_writer generates stories from all prior artifacts
        "file_editor",
        "task_tracker",
    ],
    "sync_agent": [
        # NO TOOLS - sync_agent must output Package directly as text
        # Using tools causes stuck detection loops
    ],
    "validator_agent": [
        # Validation tools
        "validate_artifact",
        "list_artifact_types",
        # Discovery tool - CALL FIRST to determine which data tools to use
        "discover_data",
        # Schema tools for cross-reference validation
        "duckdb_schema",
        "duckdb_tables",
        "analyze_csv",
        # No file editing - validator is read-only
    ],
}


def get_tools_for_agent(agent_name: str) -> list[str]:
    """Get tool names appropriate for a specific agent.

    Args:
        agent_name: Name of the agent (e.g., 'data_analyst').

    Returns:
        List of tool names for the agent.
    """
    return AGENT_TOOL_MAP.get(agent_name, [])


def get_domain_tool_names() -> list[str]:
    """Get all domain-specific tool names (non-SDK built-in).

    Returns:
        List of domain tool names.
    """
    sdk_builtins = {"terminal", "file_editor", "task_tracker"}
    all_tools = set()
    for tools in AGENT_TOOL_MAP.values():
        all_tools.update(tools)
    return sorted(all_tools - sdk_builtins)


# Legacy compatibility function
def get_all_tools():
    """Get all registered PWI tools (legacy compatibility).

    Returns:
        List of all tool definitions.
    """
    if LEGACY_TOOLS_AVAILABLE:
        return get_registry().get_tools()
    return []


__all__ = [
    # SDK Tool Classes
    "Action",
    "Observation",
    "Tool",
    "ToolAnnotations",
    "ToolDefinition",
    "ToolExecutor",
    "register_tool",
    # Agent Tool Mapping
    "AGENT_TOOL_MAP",
    "get_tools_for_agent",
    "get_domain_tool_names",
    # DuckDB Tools
    "DuckDBQueryTool",
    "DuckDBQueryAction",
    "DuckDBQueryObservation",
    "DuckDBSchemaTool",
    "DuckDBSchemaAction",
    "DuckDBSchemaObservation",
    "DuckDBTablesTool",
    "DuckDBTablesAction",
    "DuckDBTablesObservation",
    "DuckDBValidateTool",
    "DuckDBValidateAction",
    "DuckDBValidateObservation",
    # CSV Tools
    "AnalyzeCSVTool",
    "AnalyzeCSVAction",
    "AnalyzeCSVObservation",
    "CSVStatsTool",
    "CSVStatsAction",
    "CSVStatsObservation",
    "CSVSampleTool",
    "CSVSampleAction",
    "CSVSampleObservation",
    # Metadata Tools
    "QueryMetadataCatalogTool",
    "QueryMetadataCatalogAction",
    "QueryMetadataCatalogObservation",
    "GetLineageTool",
    "GetLineageAction",
    "GetLineageObservation",
    "GetTagsTool",
    "GetTagsAction",
    "GetTagsObservation",
    # Artifact Tools
    "ARTIFACT_TYPES",
    "GenerateArtifactTool",
    "GenerateArtifactAction",
    "GenerateArtifactObservation",
    "SaveArtifactTool",
    "SaveArtifactAction",
    "SaveArtifactObservation",
    "ValidateArtifactTool",
    "ValidateArtifactAction",
    "ValidateArtifactObservation",
    "ListArtifactTypesTool",
    "ListArtifactTypesAction",
    "ListArtifactTypesObservation",
    # Discovery Tools
    "DataDiscoveryTool",
    "DataDiscoveryAction",
    "DataDiscoveryObservation",
    # Legacy Compatibility
    "get_all_tools",
    "LEGACY_TOOLS_AVAILABLE",
]

# Add legacy exports if available
if LEGACY_TOOLS_AVAILABLE:
    __all__.extend(
        [
            "ToolRegistry",
            "create_tool",
            "get_registry",
        ]
    )
