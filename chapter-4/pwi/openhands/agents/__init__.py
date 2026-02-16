"""OpenHands-based PWI agents.

This module provides the PWI (Planning with Intent) agent system using
the OpenHands SDK. Agents are created from microagent markdown files
located in .openhands/microagents/.

Available agents:
- data_analyst: Generates Data Requirements Documents (DRD)
- data_architect: Generates Pipeline Architecture Documents (PAD)
- mapping_engineer: Generates Data Mapping Documents (DMD)
- dq_engineer: Generates Data Quality Specifications (DQS)
- story_writer: Generates User Stories
- sync_agent: Consolidates all artifacts into a package
- validator_agent: Validates artifact format and content

Usage:
    from pwi.openhands.agents import (
        create_pwi_agent,
        create_pwi_conversation,
        load_microagent_prompt,
    )

    # Create an agent using SDK pattern
    agent = create_pwi_agent(
        "data_analyst",
        llm_config={"model": "anthropic/claude-sonnet-4-5-20250929"}
    )
    conversation = create_pwi_conversation(agent, workspace="/path/to/workspace")
    conversation.send_message("Analyze the healthcare data")
    conversation.run()

    # Or load just the prompt from microagent file
    prompt = load_microagent_prompt("data_analyst")
"""

# SDK Factory Functions
from pwi.openhands.agents.factory import (
    # Configuration
    MICROAGENTS_DIR,
    SKILLS_DIR,
    AGENT_MICROAGENT_MAP,
    DEFAULT_MODEL,
    DEFAULT_AGENT_TOOLS,
    # Auto-discovery (Microagents)
    MicroagentInfo,
    discover_microagents,
    get_microagent_info,
    # Auto-discovery (Skills)
    SkillInfo,
    discover_skills,
    get_skill_info,
    build_agent_context,
    # SDK Context re-exports
    AgentContext,
    Skill,
    KeywordTrigger,
    # Microagent loading
    parse_microagent_file,
    load_microagent_prompt,
    # LLM
    create_llm,
    get_llm_config_from_env,
    # Agent factory
    create_pwi_agent,
    create_pwi_conversation,
    run_agent_task,
    get_available_agent_types,
    # Legacy placeholder (empty dict for backward compatibility)
    AGENT_PROMPTS,
    # Re-exports from tools
    AGENT_TOOL_MAP,
)


# Default workflow sequence
AGENT_SEQUENCE = [
    "data_analyst",
    "data_architect",
    "mapping_engineer",
    "dq_engineer",
    "story_writer",
    "sync_agent",
]


def get_agent_sequence() -> list[str]:
    """Get the default agent execution sequence.

    Returns:
        List of agent names in execution order.
    """
    return AGENT_SEQUENCE.copy()


__all__ = [
    # Configuration
    "MICROAGENTS_DIR",
    "SKILLS_DIR",
    "AGENT_MICROAGENT_MAP",
    "DEFAULT_MODEL",
    "DEFAULT_AGENT_TOOLS",
    "AGENT_SEQUENCE",
    # Auto-discovery (Microagents)
    "MicroagentInfo",
    "discover_microagents",
    "get_microagent_info",
    # Auto-discovery (Skills)
    "SkillInfo",
    "discover_skills",
    "get_skill_info",
    "build_agent_context",
    # SDK Context re-exports
    "AgentContext",
    "Skill",
    "KeywordTrigger",
    # Microagent loading
    "parse_microagent_file",
    "load_microagent_prompt",
    # LLM
    "create_llm",
    "get_llm_config_from_env",
    # Agent factory
    "create_pwi_agent",
    "create_pwi_conversation",
    "run_agent_task",
    "get_available_agent_types",
    "get_agent_sequence",
    # Tool configuration
    "AGENT_TOOL_MAP",
    # Legacy placeholder (deprecated - use load_microagent_prompt instead)
    "AGENT_PROMPTS",
]
