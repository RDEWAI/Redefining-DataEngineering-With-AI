"""Tool registration module for OpenHands GUI integration.

This module provides a standalone entry point for registering all PWI tools
with the OpenHands SDK. It is designed to be called from Docker entrypoints
or server startup scripts.

Usage:
    # From Python
    from pwi.openhands.tools.registration import register_all_tools
    tools = register_all_tools()

    # From command line
    python -m pwi.openhands.tools.registration

Example:
    $ python -m pwi.openhands.tools.registration
    Registered 14 tools: ['analyze_csv', 'csv_sample', 'csv_stats', ...]
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def register_all_tools() -> list[str]:
    """Register all PWI tools with OpenHands SDK.

    This function imports all tool modules, which triggers their auto-registration
    with the OpenHands SDK via the @register_tool decorator.

    Returns:
        List of registered tool names.

    Example:
        >>> tools = register_all_tools()
        >>> print(f"Registered {len(tools)} tools")
        Registered 14 tools
    """
    # Import all PWI tools - this triggers auto-registration via register_tool()
    # DuckDB Tools
    from pwi.openhands.tools.duckdb_tool import (  # noqa: F401
        DuckDBQueryTool,
        DuckDBSchemaTool,
        DuckDBTablesTool,
        DuckDBValidateTool,
    )

    # CSV Tools
    from pwi.openhands.tools.csv_tool import (  # noqa: F401
        AnalyzeCSVTool,
        CSVSampleTool,
        CSVStatsTool,
    )

    # Metadata Tools
    from pwi.openhands.tools.metadata_tool import (  # noqa: F401
        GetLineageTool,
        GetTagsTool,
        QueryMetadataCatalogTool,
    )

    # Artifact Tools
    from pwi.openhands.tools.artifact_tool import (  # noqa: F401
        GenerateArtifactTool,
        ListArtifactTypesTool,
        SaveArtifactTool,
        ValidateArtifactTool,
    )

    # Discovery Tools
    from pwi.openhands.tools.discovery_tool import (  # noqa: F401
        DataDiscoveryTool,
    )

    # Get list of registered tools from SDK
    from openhands.sdk.tool.registry import list_registered_tools

    return list_registered_tools()


def register_all_microagents() -> dict[str, str]:
    """Discover and return all PWI microagents.

    Returns:
        Dictionary mapping agent name to filename.
    """
    from pwi.openhands.agents.factory import discover_microagents

    microagents = discover_microagents()
    return {name: info.filename for name, info in microagents.items()}


def register_all_skills() -> dict[str, list[str]]:
    """Discover and return all PWI skills.

    Returns:
        Dictionary mapping skill name to trigger keywords.
    """
    from pwi.openhands.agents.factory import discover_skills

    skills = discover_skills()
    return {name: info.triggers for name, info in skills.items()}


def verify_registration() -> dict[str, int]:
    """Verify all PWI components are registered.

    Returns:
        Dictionary with counts of tools, microagents, and skills.
    """
    tools = register_all_tools()
    microagents = register_all_microagents()
    skills = register_all_skills()

    return {
        "tools": len(tools),
        "microagents": len(microagents),
        "skills": len(skills),
    }


def main() -> int:
    """Main entry point for command-line usage."""
    print("PWI Tool Registration")
    print("=" * 40)
    print()

    # Register tools
    print("Registering tools...")
    tools = register_all_tools()
    print(f"  Registered {len(tools)} tools:")
    for tool in sorted(tools):
        print(f"    - {tool}")
    print()

    # Discover microagents
    print("Discovering microagents...")
    try:
        microagents = register_all_microagents()
        print(f"  Found {len(microagents)} microagents:")
        for name in sorted(microagents.keys()):
            print(f"    - {name}")
    except Exception as e:
        print(f"  Warning: Could not discover microagents: {e}")
    print()

    # Discover skills
    print("Discovering skills...")
    try:
        skills = register_all_skills()
        print(f"  Found {len(skills)} skills:")
        for name in sorted(skills.keys()):
            print(f"    - {name}")
    except Exception as e:
        print(f"  Warning: Could not discover skills: {e}")
    print()

    print("=" * 40)
    print("Registration complete!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
