"""OpenHands SDK integration for PWI.

This module provides the OpenHands SDK integration layer for the
Planning with Intent (PWI) framework, enabling tool-use capabilities
and external system integration.

Phase 8 of PWI development - OpenHands SDK Migration.

Usage:
    # Agents
    from pwi.openhands.agents import (
        DataAnalystAgent,
        get_agent,
        AGENT_SEQUENCE,
    )

    # Tools
    from pwi.openhands.tools import (
        get_all_tools,
        get_tools_for_agent,
    )

    # Workflow
    from pwi.openhands.workflow import (
        PWIWorkflowController,
        EventStream,
    )

    # Configuration
    from pwi.openhands.config import OpenHandsConfig
"""

from pwi.openhands.config import OpenHandsConfig

# Re-export from submodules for convenience
# These are imported lazily to avoid circular imports
__all__ = [
    # Configuration
    "OpenHandsConfig",
    # Submodule access
    "agents",
    "tools",
    "workflow",
]


def __getattr__(name: str):
    """Lazy import of submodules to avoid circular imports."""
    if name == "agents":
        from pwi.openhands import agents
        return agents
    elif name == "tools":
        from pwi.openhands import tools
        return tools
    elif name == "workflow":
        from pwi.openhands import workflow
        return workflow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
