"""OpenHands SDK integration for PWI.

This module provides the OpenHands SDK integration layer for the
Planning with Intent (PWI) framework, enabling tool-use capabilities
and external system integration.

Phase 8 of PWI development - OpenHands SDK Migration.

Usage (SDK Pattern - Recommended):
    from openhands.sdk import LLM, Agent, Conversation, Tool
    from pwi.openhands.agents import create_pwi_agent, create_pwi_conversation
    from pwi.openhands.tools import AGENT_TOOL_MAP

    # Create an agent with SDK pattern
    agent = create_pwi_agent("data_analyst")
    conversation = create_pwi_conversation(agent, workspace="/path/to/workspace")
    conversation.send_message("Analyze the healthcare data")
    conversation.run()

Legacy Usage:
    from pwi.openhands.agents import get_agent, PWIAgentConfig
    from pwi.openhands.tools import get_tools_for_agent
"""

# SDK imports
from openhands.sdk import LLM, Agent, Conversation
from openhands.sdk.tool import Tool

from pwi.openhands.config import OpenHandsConfig, RuntimeType
from pwi.openhands.runtime import PWIRuntime, create_runtime

# Re-export from submodules for convenience
# These are imported lazily to avoid circular imports
__all__ = [
    # SDK Classes
    "LLM",
    "Agent",
    "Conversation",
    "Tool",
    # Configuration
    "OpenHandsConfig",
    "RuntimeType",
    # Runtime
    "PWIRuntime",
    "create_runtime",
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
