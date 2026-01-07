"""PWI Agent Factory using OpenHands SDK.

This module provides factory functions to create PWI agents using the
official OpenHands SDK pattern with proper tool configuration.

Usage:
    from pwi.openhands.agents.factory import create_pwi_agent, create_pwi_conversation

    # Create an agent for data analysis
    agent = create_pwi_agent("data_analyst", llm_config)

    # Create a conversation with the agent
    conversation = create_pwi_conversation(agent, workspace_path)
    conversation.send_message("Analyze the healthcare data")
    conversation.run()
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import SecretStr

from openhands.sdk import LLM, Agent, Conversation
from openhands.sdk.context import AgentContext, KeywordTrigger, Skill
from openhands.sdk.tool import Tool
from openhands.sdk.tool.registry import list_registered_tools

# Import SDK built-in tools to register them with the global registry
from openhands.tools.file_editor import FileEditorTool  # noqa: F401
from openhands.tools.task_tracker import TaskTrackerTool  # noqa: F401
from openhands.tools.terminal import TerminalTool  # noqa: F401

# Import our domain tools to register them (auto-registration on import)
from pwi.openhands.tools.duckdb_tool import (  # noqa: F401
    DuckDBQueryTool,
    DuckDBSchemaTool,
    DuckDBTablesTool,
    DuckDBValidateTool,
)
from pwi.openhands.tools.csv_tool import (  # noqa: F401
    AnalyzeCSVTool,
    CSVSampleTool,
    CSVStatsTool,
)
from pwi.openhands.tools.metadata_tool import (  # noqa: F401
    GetLineageTool,
    GetTagsTool,
    QueryMetadataCatalogTool,
)
from pwi.openhands.tools.artifact_tool import (  # noqa: F401
    GenerateArtifactTool,
    ListArtifactTypesTool,
    SaveArtifactTool,
    ValidateArtifactTool,
)

from pwi.openhands.tools import AGENT_TOOL_MAP, get_tools_for_agent
from pwi.utils.logging import get_logger

if TYPE_CHECKING:
    from openhands.sdk.conversation.state import ConversationState

logger = get_logger("openhands.agents.factory")


# =============================================================================
# Microagent Configuration
# =============================================================================

# Path to microagent directory (relative to chapter-4 root)
MICROAGENTS_DIR = Path(__file__).parent.parent.parent.parent / ".openhands" / "microagents"


@dataclass
class MicroagentInfo:
    """Information about a discovered microagent.

    Attributes:
        name: Agent name (from frontmatter 'name' field).
        filename: Markdown filename.
        type: Microagent type ('repo', 'knowledge', etc.).
        version: Version string from frontmatter.
        triggers: List of trigger keywords.
        tools: Optional list of tool names from frontmatter.
        agent: Agent type (e.g., 'CodeActAgent') from frontmatter.
    """

    name: str
    filename: str
    type: str = "knowledge"
    version: str = "1.0.0"
    triggers: list[str] = field(default_factory=list)
    tools: list[str] | None = None
    agent: str = "CodeActAgent"


# Cache for discovered microagents
_discovered_microagents: dict[str, MicroagentInfo] | None = None


def discover_microagents(
    microagents_dir: Path | None = None,
    force_refresh: bool = False,
) -> dict[str, MicroagentInfo]:
    """Auto-discover microagent files from the microagents directory.

    Scans the .openhands/microagents/ directory and builds a mapping of
    agent names to their metadata. New microagents are automatically
    discovered without code changes.

    Args:
        microagents_dir: Custom directory to scan (defaults to MICROAGENTS_DIR).
        force_refresh: Force re-scan even if already cached.

    Returns:
        Dictionary mapping agent name to MicroagentInfo.

    Example:
        >>> microagents = discover_microagents()
        >>> print(microagents.keys())
        dict_keys(['data_analyst', 'data_architect', ...])
    """
    global _discovered_microagents

    # Return cached result if available
    if _discovered_microagents is not None and not force_refresh:
        return _discovered_microagents

    base_dir = microagents_dir or MICROAGENTS_DIR
    discovered: dict[str, MicroagentInfo] = {}

    if not base_dir.exists():
        logger.warning(f"Microagents directory not found: {base_dir}")
        _discovered_microagents = discovered
        return discovered

    # Scan all .md files in the directory
    for md_file in base_dir.glob("*.md"):
        try:
            frontmatter, _ = parse_microagent_file(md_file)

            # Get the agent name - prefer 'name' field, fall back to filename
            name = frontmatter.get("name")
            if not name:
                # Use filename without extension as fallback
                name = md_file.stem
                logger.warning(
                    f"Microagent {md_file.name} missing 'name' field, using '{name}'"
                )

            # Skip repo.md - it's a repository-wide config, not an agent
            if name == "pwi_conventions" or frontmatter.get("type") == "repo":
                logger.debug(f"Skipping repo microagent: {md_file.name}")
                continue

            # Create MicroagentInfo
            info = MicroagentInfo(
                name=name,
                filename=md_file.name,
                type=frontmatter.get("type", "knowledge"),
                version=frontmatter.get("version", "1.0.0"),
                triggers=frontmatter.get("triggers", []),
                tools=frontmatter.get("tools"),  # Optional tools list in frontmatter
                agent=frontmatter.get("agent", "CodeActAgent"),
            )

            discovered[name] = info
            logger.debug(f"Discovered microagent: {name} ({md_file.name})")

        except (ValueError, FileNotFoundError) as e:
            logger.warning(f"Failed to parse microagent {md_file.name}: {e}")
            continue

    logger.info(f"Discovered {len(discovered)} microagents from {base_dir}")
    _discovered_microagents = discovered
    return discovered


def get_microagent_info(agent_type: str) -> MicroagentInfo | None:
    """Get metadata for a specific microagent.

    Args:
        agent_type: Name of the agent.

    Returns:
        MicroagentInfo if found, None otherwise.
    """
    microagents = discover_microagents()
    return microagents.get(agent_type)


# Build AGENT_MICROAGENT_MAP dynamically from discovered microagents
def _build_agent_microagent_map() -> dict[str, str]:
    """Build agent-to-filename mapping from discovered microagents."""
    microagents = discover_microagents()
    return {name: info.filename for name, info in microagents.items()}


# Legacy compatibility - this is now built dynamically
# Access via discover_microagents() for full metadata
AGENT_MICROAGENT_MAP: dict[str, str] = {}  # Populated on first access


def _ensure_microagent_map_populated():
    """Ensure AGENT_MICROAGENT_MAP is populated (lazy initialization)."""
    global AGENT_MICROAGENT_MAP
    if not AGENT_MICROAGENT_MAP:
        AGENT_MICROAGENT_MAP.update(_build_agent_microagent_map())


# =============================================================================
# Skills Configuration (Knowledge Injections)
# =============================================================================

# Path to skills directory (separate from microagents)
SKILLS_DIR = Path(__file__).parent.parent.parent.parent / ".openhands" / "skills"


@dataclass
class SkillInfo:
    """Information about a discovered skill.

    Skills are knowledge injections that are triggered by keywords in user messages.
    Unlike microagents (which are full agent definitions), skills add contextual
    knowledge to enhance agent responses.

    Attributes:
        name: Skill name (from frontmatter 'name' field).
        filename: Markdown filename.
        triggers: List of trigger keywords (skill activates when these appear).
        content: The skill's knowledge content (markdown after frontmatter).
    """

    name: str
    filename: str
    triggers: list[str] = field(default_factory=list)
    content: str = ""


# Cache for discovered skills
_discovered_skills: dict[str, SkillInfo] | None = None


def discover_skills(
    skills_dir: Path | None = None,
    force_refresh: bool = False,
) -> dict[str, SkillInfo]:
    """Auto-discover skill files from the skills directory.

    Scans the .openhands/skills/ directory and builds a mapping of
    skill names to their metadata. New skills are automatically
    discovered without code changes.

    Args:
        skills_dir: Custom directory to scan (defaults to SKILLS_DIR).
        force_refresh: Force re-scan even if already cached.

    Returns:
        Dictionary mapping skill name to SkillInfo.

    Example:
        >>> skills = discover_skills()
        >>> print(skills.keys())
        dict_keys(['duckdb', 'synthea', ...])
    """
    global _discovered_skills

    # Return cached result if available
    if _discovered_skills is not None and not force_refresh:
        return _discovered_skills

    base_dir = skills_dir or SKILLS_DIR
    discovered: dict[str, SkillInfo] = {}

    if not base_dir.exists():
        logger.debug(f"Skills directory not found: {base_dir} (this is OK if no skills defined)")
        _discovered_skills = discovered
        return discovered

    # Scan all .md files in the directory
    for md_file in base_dir.glob("*.md"):
        try:
            frontmatter, content = parse_microagent_file(md_file)

            # Get the skill name - prefer 'name' field, fall back to filename
            name = frontmatter.get("name")
            if not name:
                # Use filename without extension as fallback
                name = md_file.stem
                logger.warning(
                    f"Skill {md_file.name} missing 'name' field, using '{name}'"
                )

            # Create SkillInfo
            info = SkillInfo(
                name=name,
                filename=md_file.name,
                triggers=frontmatter.get("triggers", []),
                content=content,
            )

            discovered[name] = info
            logger.debug(
                f"Discovered skill: {name} ({md_file.name})",
                extra={"triggers": info.triggers},
            )

        except (ValueError, FileNotFoundError) as e:
            logger.warning(f"Failed to parse skill {md_file.name}: {e}")
            continue

    logger.info(f"Discovered {len(discovered)} skills from {base_dir}")
    _discovered_skills = discovered
    return discovered


def get_skill_info(skill_name: str) -> SkillInfo | None:
    """Get metadata for a specific skill.

    Args:
        skill_name: Name of the skill.

    Returns:
        SkillInfo if found, None otherwise.
    """
    skills = discover_skills()
    return skills.get(skill_name)


def build_agent_context(skills_dir: Path | None = None) -> AgentContext:
    """Build AgentContext with all discovered skills.

    This loads skills from .openhands/skills/ and converts them to SDK Skill
    objects with keyword triggers. Skills provide contextual knowledge that
    helps agents use tools more effectively.

    Args:
        skills_dir: Custom directory for skills (defaults to SKILLS_DIR).

    Returns:
        AgentContext with all skills loaded.

    Example:
        >>> context = build_agent_context()
        >>> agent = Agent(llm=llm, tools=tools, agent_context=context)
    """
    discovered_skills = discover_skills(skills_dir)

    sdk_skills: list[Skill] = []
    for skill_info in discovered_skills.values():
        # Create trigger from keywords if present
        trigger = None
        if skill_info.triggers:
            trigger = KeywordTrigger(keywords=skill_info.triggers)

        # Create SDK Skill object
        sdk_skill = Skill(
            name=skill_info.name,
            content=skill_info.content,
            trigger=trigger,
        )
        sdk_skills.append(sdk_skill)

    logger.info(f"Built AgentContext with {len(sdk_skills)} skills")
    return AgentContext(skills=sdk_skills)


def parse_microagent_file(file_path: Path) -> tuple[dict[str, Any], str]:
    """Parse a microagent markdown file, extracting YAML frontmatter and content.

    Args:
        file_path: Path to the microagent markdown file.

    Returns:
        Tuple of (frontmatter_dict, markdown_content).

    Raises:
        ValueError: If file format is invalid (missing frontmatter).
        FileNotFoundError: If file does not exist.
    """
    import yaml

    if not file_path.exists():
        raise FileNotFoundError(f"Microagent file not found: {file_path}")

    content = file_path.read_text(encoding="utf-8")

    # Check for frontmatter
    if not content.startswith("---"):
        raise ValueError(
            f"Invalid microagent file format: {file_path} (missing YAML frontmatter)"
        )

    # Split on --- delimiters
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError(
            f"Invalid microagent file format: {file_path} (malformed frontmatter)"
        )

    # Parse YAML frontmatter
    frontmatter = yaml.safe_load(parts[1])

    # Extract markdown content (after second ---)
    markdown_content = parts[2].strip()

    return frontmatter, markdown_content


def load_microagent_prompt(
    agent_type: str,
    microagents_dir: Path | None = None,
) -> str:
    """Load system prompt from a microagent markdown file.

    Uses auto-discovery to find microagent files. New agents are automatically
    available when their markdown file is added to .openhands/microagents/.

    Args:
        agent_type: Type of agent (e.g., 'data_analyst').
        microagents_dir: Optional custom directory for microagent files.

    Returns:
        The markdown content as the system prompt.

    Raises:
        ValueError: If agent_type is unknown or file format is invalid.
        FileNotFoundError: If microagent file is not found.
    """
    base_dir = microagents_dir or MICROAGENTS_DIR

    # Use auto-discovery to find the microagent
    microagents = discover_microagents(microagents_dir)

    if agent_type not in microagents:
        # Provide helpful error with list of available agents
        available = list(microagents.keys())
        raise ValueError(
            f"Unknown agent type: '{agent_type}'. "
            f"Available agents: {available}. "
            f"To add a new agent, create {base_dir}/{agent_type}.md with YAML frontmatter."
        )

    info = microagents[agent_type]
    file_path = base_dir / info.filename

    # Parse the file
    frontmatter, prompt_content = parse_microagent_file(file_path)

    logger.debug(
        f"Loaded prompt for {agent_type} from {info.filename}",
        extra={"version": info.version, "triggers": info.triggers},
    )

    return prompt_content


# =============================================================================
# AGENT_PROMPTS - REMOVED
# =============================================================================
# Agent prompts are now loaded dynamically from .openhands/microagents/*.md files
# using load_microagent_prompt(agent_type). See AGENT_MICROAGENT_MAP for mapping.
#
# To add a new agent:
#   1. Create .openhands/microagents/{agent_type}.md with YAML frontmatter
#   2. Add entry to AGENT_MICROAGENT_MAP above
#   3. Add entry to AGENT_TOOL_MAP in pwi/openhands/tools/__init__.py


# =============================================================================
# LLM Configuration from Environment
# =============================================================================

# Default model - readers can override via LLM_MODEL env var
DEFAULT_MODEL = "openai/gpt-4o-mini"


def get_llm_config_from_env() -> dict[str, Any]:
    """Get LLM configuration from environment variables.

    Reads from .env file or environment:
    - LLM_API_KEY: API key (required)
    - LLM_BASE_URL: Base URL for API (e.g., https://openrouter.ai/api/v1)
    - LLM_MODEL: Model identifier (e.g., openai/gpt-4o-mini)

    Returns:
        Dictionary with LLM configuration.

    Raises:
        ValueError: If LLM_API_KEY is not set.
    """
    api_key = os.getenv("LLM_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "API key required. Set LLM_API_KEY in .env file or environment."
        )

    config: dict[str, Any] = {
        "api_key": api_key,
        "model": os.getenv("LLM_MODEL", DEFAULT_MODEL),
    }

    # Add base_url if provided (required for OpenRouter, etc.)
    base_url = os.getenv("LLM_BASE_URL")
    if base_url:
        config["base_url"] = base_url

    return config


def create_llm(
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> LLM:
    """Create an LLM instance for agent use.

    Configuration is read from environment variables by default:
    - LLM_API_KEY: API key (required)
    - LLM_BASE_URL: Base URL for API (e.g., https://openrouter.ai/api/v1)
    - LLM_MODEL: Model identifier (e.g., openai/gpt-4o-mini)

    Args:
        model: Model identifier (defaults to LLM_MODEL env var).
        api_key: API key (defaults to LLM_API_KEY env var).
        base_url: Base URL for API (defaults to LLM_BASE_URL env var).
        temperature: Sampling temperature.
        max_tokens: Maximum tokens for response.

    Returns:
        Configured LLM instance.

    Raises:
        ValueError: If API key is not provided or found in environment.
    """
    # Get defaults from environment
    env_config = get_llm_config_from_env()

    # Use provided values or fall back to environment
    final_model = model or env_config.get("model", DEFAULT_MODEL)
    final_api_key = api_key or env_config.get("api_key")
    final_base_url = base_url or env_config.get("base_url")

    if not final_api_key:
        raise ValueError(
            "API key required. Set LLM_API_KEY in .env file or pass api_key parameter."
        )

    llm_kwargs: dict[str, Any] = {
        "model": final_model,
        "api_key": SecretStr(final_api_key),
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }

    if final_base_url:
        llm_kwargs["base_url"] = final_base_url

    logger.info(
        f"Creating LLM with model={final_model}, base_url={final_base_url or 'default'}"
    )

    return LLM(**llm_kwargs)


# =============================================================================
# Agent Factory
# =============================================================================


# Default tools for agents without explicit tool mapping
DEFAULT_AGENT_TOOLS = [
    "terminal",
    "file_editor",
    "task_tracker",
    "duckdb_query",
    "duckdb_schema",
    "duckdb_tables",
]


def create_pwi_agent(
    agent_type: str,
    llm: LLM | None = None,
    llm_config: dict[str, Any] | None = None,
    custom_prompt: str | None = None,
    additional_tools: list[str] | None = None,
    microagents_dir: Path | None = None,
) -> Agent:
    """Create a PWI agent with appropriate tools.

    Tools are resolved in priority order:
    1. Tools specified in microagent frontmatter ('tools' field)
    2. Tools from AGENT_TOOL_MAP (explicit mapping)
    3. DEFAULT_AGENT_TOOLS (fallback for new agents)

    This allows new agents to be added by just creating a microagent file
    with an optional 'tools' list in the frontmatter.

    Args:
        agent_type: Type of agent (e.g., 'data_analyst', 'data_architect').
        llm: Pre-configured LLM instance (optional).
        llm_config: LLM configuration dict (used if llm not provided).
        custom_prompt: Custom system prompt (overrides microagent file).
        additional_tools: Additional tool names to include.
        microagents_dir: Custom directory for microagent files (for testing).

    Returns:
        Configured Agent instance.

    Raises:
        ValueError: If agent_type is unknown or LLM configuration missing.
        FileNotFoundError: If microagent file is not found.
    """
    # Use auto-discovery to validate agent type
    microagents = discover_microagents(microagents_dir)

    if agent_type not in microagents:
        available = list(microagents.keys())
        raise ValueError(
            f"Unknown agent type: '{agent_type}'. "
            f"Available agents: {available}. "
            f"To add a new agent, create .openhands/microagents/{agent_type}.md"
        )

    microagent_info = microagents[agent_type]

    # Create LLM if not provided
    if llm is None:
        if llm_config:
            llm = create_llm(**llm_config)
        else:
            llm = create_llm()  # Use defaults

    # Resolve tools - priority: frontmatter > AGENT_TOOL_MAP > defaults
    if microagent_info.tools:
        # Use tools specified in microagent frontmatter
        all_tool_names = microagent_info.tools.copy()
        logger.debug(f"Using tools from microagent frontmatter for {agent_type}")
    elif agent_type in AGENT_TOOL_MAP:
        # Use explicit mapping
        all_tool_names = get_tools_for_agent(agent_type)
        logger.debug(f"Using tools from AGENT_TOOL_MAP for {agent_type}")
    else:
        # Use default tools for new agents
        all_tool_names = DEFAULT_AGENT_TOOLS.copy()
        logger.info(
            f"Using default tools for new agent '{agent_type}'. "
            "Add 'tools' to frontmatter or AGENT_TOOL_MAP for custom tools."
        )

    # Add any additional tools
    if additional_tools:
        all_tool_names = list(set(all_tool_names + additional_tools))

    # Filter to only use tools that are registered with the SDK
    registered = set(list_registered_tools())
    tool_names = [t for t in all_tool_names if t in registered]

    # Log any unregistered tools (for debugging)
    unregistered = [t for t in all_tool_names if t not in registered]
    if unregistered:
        logger.warning(
            f"Skipping unregistered tools for {agent_type}: {unregistered}. "
            "These tools need to be migrated to SDK pattern."
        )

    # Create Tool specifications
    tools = [Tool(name=name) for name in tool_names]

    # Get system prompt - priority: custom_prompt > microagent file
    if custom_prompt:
        system_prompt = custom_prompt
    else:
        system_prompt = load_microagent_prompt(agent_type, microagents_dir)

    # Build AgentContext with skills for contextual knowledge
    agent_context = build_agent_context()

    logger.info(
        f"Creating {agent_type} agent with {len(tools)} tools and "
        f"{len(agent_context.skills)} skills",
        extra={"agent_type": agent_type, "tools": tool_names},
    )

    return Agent(
        llm=llm,
        tools=tools,
        system_prompt=system_prompt,
        agent_context=agent_context,
    )


def create_pwi_conversation(
    agent: Agent,
    workspace: str | Path,
    callbacks: list | None = None,
    max_iteration_per_run: int = 50,
) -> Conversation:
    """Create a conversation with a PWI agent.

    Args:
        agent: Configured Agent instance.
        workspace: Workspace directory path.
        callbacks: Optional list of callback functions.
        max_iteration_per_run: Maximum number of agent iterations per run (default: 100).
            This prevents runaway agents that get stuck in loops.

    Returns:
        Configured Conversation instance.
    """
    workspace_path = str(workspace) if isinstance(workspace, Path) else workspace

    conv_kwargs: dict[str, Any] = {
        "agent": agent,
        "workspace": workspace_path,
        "max_iteration_per_run": max_iteration_per_run,
    }

    if callbacks:
        conv_kwargs["callbacks"] = callbacks

    logger.info(
        f"Creating conversation in workspace: {workspace_path} "
        f"(max_iterations={max_iteration_per_run})"
    )

    return Conversation(**conv_kwargs)


# =============================================================================
# Convenience Functions
# =============================================================================


def _clean_artifact_content(content: str) -> str:
    """Clean artifact content by removing code fence wrappers.

    Args:
        content: Raw content from the agent.

    Returns:
        Cleaned content without code fence wrappers.
    """
    content = content.strip()

    # Remove markdown code fence wrapper
    if content.startswith("```markdown"):
        content = content[11:]
    elif content.startswith("```yaml"):
        content = content[7:]
    elif content.startswith("```csv"):
        content = content[6:]
    elif content.startswith("```"):
        content = content[3:]

    if content.endswith("```"):
        content = content[:-3]

    return content.strip()


def run_agent_task(
    agent_type: str,
    message: str,
    workspace: str | Path,
    llm_config: dict[str, Any] | None = None,
    context: dict[str, str] | None = None,
) -> str:
    """Run a complete agent task and return the result.

    Args:
        agent_type: Type of agent to use.
        message: Task message/prompt.
        workspace: Workspace directory.
        llm_config: Optional LLM configuration.
        context: Optional context (artifacts from previous agents).

    Returns:
        Agent's response content (cleaned of code fence wrappers).
    """
    from openhands.sdk.conversation import get_agent_final_response

    agent = create_pwi_agent(agent_type, llm_config=llm_config)
    conversation = create_pwi_conversation(agent, workspace)

    # Build message with context
    full_message = message
    if context:
        context_str = "\n\n".join(
            f"## {key.upper()}\n{value}" for key, value in context.items()
        )
        full_message = f"{message}\n\n## Context from Previous Agents:\n{context_str}"

    conversation.send_message(full_message)
    conversation.run()

    # Extract result from conversation events using SDK utility
    events = list(conversation.state.events)
    response = get_agent_final_response(events)

    if not response:
        logger.warning("No final response found in conversation events")
        return "Task completed but no response extracted"

    # Clean the response - remove code fence wrapping if present
    cleaned = _clean_artifact_content(response)

    logger.info(
        f"Extracted artifact from {agent_type}",
        extra={"content_length": len(cleaned)},
    )

    return cleaned


def get_available_agent_types() -> list[str]:
    """Get list of available agent types.

    Uses auto-discovery to find all available microagent-based agents.

    Returns:
        List of agent type names (sorted alphabetically).
    """
    microagents = discover_microagents()
    return sorted(microagents.keys())


__all__ = [
    # Configuration
    "MICROAGENTS_DIR",
    "SKILLS_DIR",
    "AGENT_MICROAGENT_MAP",
    "DEFAULT_MODEL",
    "DEFAULT_AGENT_TOOLS",
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
    # Re-exports from tools
    "AGENT_TOOL_MAP",
]


# Legacy placeholder for backward compatibility during transition
# This will be removed in a future version
AGENT_PROMPTS: dict[str, str] = {}  # Use load_microagent_prompt() instead
