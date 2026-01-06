"""OpenHands-based PWI agents.

This module contains the OpenHands SDK implementations of the 6 PWI agents:
- DataAnalystAgent: Generates Data Requirements Documents (DRD)
- DataArchitectAgent: Generates Pipeline Architecture Documents (PAD)
- MappingEngineerAgent: Generates Data Mapping Documents (DMD)
- DQEngineerAgent: Generates Data Quality Specifications (DQS)
- StoryWriterAgent: Generates User Stories
- SyncAgent: Consolidates all artifacts into a package

Usage:
    from pwi.openhands.agents import (
        DataAnalystAgent,
        DataArchitectAgent,
        MappingEngineerAgent,
        DQEngineerAgent,
        StoryWriterAgent,
        SyncAgent,
        get_agent,
        get_agent_sequence,
    )

    # Create an agent
    config = PWIAgentConfig(name="data_analyst", model="gpt-4o")
    agent = DataAnalystAgent(config=config, llm_client=llm)

    # Or get agent by name
    agent = get_agent("data_analyst", config, llm)
"""

from typing import Any

from pwi.openhands.agents.base import (
    BasePWIAgent,
    PWIAgentConfig,
    PWIAgentResult,
    PWIAgentState,
)
from pwi.openhands.agents.data_analyst import DataAnalystAgent
from pwi.openhands.agents.data_architect import DataArchitectAgent
from pwi.openhands.agents.mapping_engineer import MappingEngineerAgent
from pwi.openhands.agents.dq_engineer import DQEngineerAgent
from pwi.openhands.agents.story_writer import StoryWriterAgent
from pwi.openhands.agents.sync_agent import SyncAgent


# Agent registry for dynamic instantiation
AGENT_REGISTRY: dict[str, type[BasePWIAgent]] = {
    "data_analyst": DataAnalystAgent,
    "data_architect": DataArchitectAgent,
    "mapping_engineer": MappingEngineerAgent,
    "dq_engineer": DQEngineerAgent,
    "story_writer": StoryWriterAgent,
    "sync_agent": SyncAgent,
}

# Default workflow sequence
AGENT_SEQUENCE = [
    "data_analyst",
    "data_architect",
    "mapping_engineer",
    "dq_engineer",
    "story_writer",
    "sync_agent",
]


def get_agent(
    agent_name: str,
    config: PWIAgentConfig,
    llm_client: Any = None,
) -> BasePWIAgent:
    """Get an agent instance by name.

    Args:
        agent_name: Name of the agent (e.g., 'data_analyst').
        config: Agent configuration.
        llm_client: LLM client for completions.

    Returns:
        Instantiated agent.

    Raises:
        ValueError: If agent name is not recognized.
    """
    agent_class = AGENT_REGISTRY.get(agent_name)
    if agent_class is None:
        valid_names = ", ".join(AGENT_REGISTRY.keys())
        raise ValueError(f"Unknown agent: {agent_name}. Valid agents: {valid_names}")

    return agent_class(config=config, llm_client=llm_client)


def get_agent_sequence() -> list[str]:
    """Get the default agent execution sequence.

    Returns:
        List of agent names in execution order.
    """
    return AGENT_SEQUENCE.copy()


def get_agent_info(agent_name: str) -> dict[str, Any]:
    """Get information about an agent.

    Args:
        agent_name: Name of the agent.

    Returns:
        Dictionary with agent information.

    Raises:
        ValueError: If agent name is not recognized.
    """
    agent_class = AGENT_REGISTRY.get(agent_name)
    if agent_class is None:
        raise ValueError(f"Unknown agent: {agent_name}")

    return {
        "name": agent_class.AGENT_NAME,
        "artifact_type": agent_class.ARTIFACT_TYPE,
        "artifact_format": agent_class.ARTIFACT_FORMAT,
        "version": agent_class.VERSION,
    }


def list_agents() -> list[dict[str, str]]:
    """List all available agents with their information.

    Returns:
        List of agent information dictionaries.
    """
    agents = []
    for name, agent_class in AGENT_REGISTRY.items():
        agents.append({
            "name": name,
            "artifact_type": agent_class.ARTIFACT_TYPE,
            "artifact_format": agent_class.ARTIFACT_FORMAT,
            "version": agent_class.VERSION,
        })
    return agents


__all__ = [
    # Base classes
    "BasePWIAgent",
    "PWIAgentConfig",
    "PWIAgentResult",
    "PWIAgentState",
    # Agent implementations
    "DataAnalystAgent",
    "DataArchitectAgent",
    "MappingEngineerAgent",
    "DQEngineerAgent",
    "StoryWriterAgent",
    "SyncAgent",
    # Registry and utilities
    "AGENT_REGISTRY",
    "AGENT_SEQUENCE",
    "get_agent",
    "get_agent_sequence",
    "get_agent_info",
    "list_agents",
]
