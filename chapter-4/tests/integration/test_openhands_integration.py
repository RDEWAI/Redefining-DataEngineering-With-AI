"""Integration tests for OpenHands SDK migration.

These tests validate the full OpenHands integration including:
- SDK Agent creation and Conversation
- Microagent prompt loading
- Tool registration and execution
- Event stream functionality
- Workflow state management
- Runtime configuration
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# SDK imports
from pwi.openhands.agents import (
    # Configuration
    MICROAGENTS_DIR,
    SKILLS_DIR,
    AGENT_SEQUENCE,
    # Auto-discovery (Microagents)
    discover_microagents,
    MicroagentInfo,
    # Auto-discovery (Skills)
    discover_skills,
    SkillInfo,
    # Microagent loading
    parse_microagent_file,
    load_microagent_prompt,
    # SDK Factory Functions
    create_pwi_agent,
    create_pwi_conversation,
    create_llm,
    get_available_agent_types,
    get_agent_sequence,
    # Tool configuration
    AGENT_TOOL_MAP,
)
from pwi.openhands.tools import (
    # SDK Tool Mapping
    get_tools_for_agent,
    get_domain_tool_names,
    # SDK DuckDB Tools
    DuckDBQueryTool,
    DuckDBSchemaTool,
    DuckDBTablesTool,
    DuckDBValidateTool,
)
from pwi.openhands.config import OpenHandsConfig, RuntimeType
from pwi.openhands.runtime import PWIRuntime, create_runtime
from pwi.openhands.workflow.events import (
    EventStream,
    PWIEventType,
    WorkflowStartedEvent,
    WorkflowCompletedEvent,
    AgentStartedEvent,
    AgentCompletedEvent,
)
from pwi.openhands.workflow.review_handler import (
    get_review_handler,
    AutoApproveHandler,
    SkipReviewHandler,
)


# =============================================================================
# Microagent Prompt Loading Tests
# =============================================================================


class TestMicroagentPromptLoading:
    """Test microagent prompt loading from markdown files."""

    def test_microagents_dir_exists(self):
        """Verify MICROAGENTS_DIR points to existing directory."""
        assert MICROAGENTS_DIR.exists()
        assert MICROAGENTS_DIR.is_dir()

    def test_agent_microagent_map_complete(self):
        """Verify all expected agents are discovered via discover_microagents()."""
        microagents = discover_microagents()
        expected_agents = [
            "data_analyst",
            "data_architect",
            "mapping_engineer",
            "dq_engineer",
            "story_writer",
            "sync_agent",
            "validator_agent",
        ]
        for agent in expected_agents:
            assert agent in microagents, f"Missing microagent: {agent}"
            assert isinstance(microagents[agent], MicroagentInfo)

    def test_load_data_analyst_prompt(self):
        """Test loading data_analyst prompt from microagent file."""
        prompt = load_microagent_prompt("data_analyst")
        assert len(prompt) > 100
        # Check for expected content
        assert "Data Analyst" in prompt or "DRD" in prompt

    def test_load_all_agent_prompts(self):
        """Test all agents have loadable prompts."""
        microagents = discover_microagents()
        for agent_type in microagents:
            prompt = load_microagent_prompt(agent_type)
            assert len(prompt) > 0, f"Empty prompt for {agent_type}"

    def test_load_unknown_agent_raises(self):
        """Test that unknown agent type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown agent type"):
            load_microagent_prompt("unknown_agent")

    def test_parse_microagent_frontmatter(self):
        """Test parsing YAML frontmatter from microagent file."""
        frontmatter, content = parse_microagent_file(
            MICROAGENTS_DIR / "data_analyst.md"
        )
        assert frontmatter["name"] == "data_analyst"
        assert frontmatter["type"] == "knowledge"
        assert "version" in frontmatter
        assert len(content) > 0

    def test_parse_microagent_with_triggers(self):
        """Test microagent files have triggers defined."""
        frontmatter, _ = parse_microagent_file(
            MICROAGENTS_DIR / "data_analyst.md"
        )
        assert "triggers" in frontmatter
        assert isinstance(frontmatter["triggers"], list)
        assert len(frontmatter["triggers"]) > 0


# =============================================================================
# SDK Integration Tests
# =============================================================================


class TestSDKAgentFactory:
    """Test SDK Agent creation using factory functions."""

    def test_get_available_agent_types(self):
        """Verify all agent types are available."""
        types = get_available_agent_types()
        assert "data_analyst" in types
        assert "data_architect" in types
        assert "mapping_engineer" in types
        assert "dq_engineer" in types
        assert "story_writer" in types
        assert "sync_agent" in types

    @patch("pwi.openhands.agents.factory.LLM")
    @patch("pwi.openhands.agents.factory.Agent")
    def test_create_pwi_agent(self, mock_agent, mock_llm):
        """Test creating a PWI agent using SDK factory."""
        mock_llm_instance = MagicMock()
        mock_llm.return_value = mock_llm_instance

        agent = create_pwi_agent(
            "data_analyst",
            llm_config={"model": "test-model", "api_key": "test-key"},
        )

        # Verify LLM was created with config
        mock_llm.assert_called_once()

        # Verify Agent was created with tools
        mock_agent.assert_called_once()
        call_kwargs = mock_agent.call_args.kwargs
        assert "tools" in call_kwargs
        assert "system_prompt" in call_kwargs
        # System prompt should be loaded from microagent
        assert len(call_kwargs["system_prompt"]) > 100

    @patch("pwi.openhands.agents.factory.LLM")
    @patch("pwi.openhands.agents.factory.Agent")
    def test_create_pwi_agent_custom_prompt(self, mock_agent, mock_llm):
        """Test custom_prompt overrides microagent file."""
        custom = "Custom system prompt for testing"
        agent = create_pwi_agent(
            "data_analyst",
            llm_config={"model": "test-model", "api_key": "test-key"},
            custom_prompt=custom,
        )

        call_kwargs = mock_agent.call_args.kwargs
        assert call_kwargs["system_prompt"] == custom

    def test_create_pwi_agent_unknown_type(self):
        """Test that unknown agent type raises error."""
        with pytest.raises(ValueError, match="Unknown agent type"):
            create_pwi_agent("unknown_agent")


class TestSDKToolMapping:
    """Test SDK tool mapping for agents."""

    def test_agent_tool_map_exists(self):
        """Verify AGENT_TOOL_MAP is defined."""
        assert len(AGENT_TOOL_MAP) >= 6

    def test_data_analyst_tools(self):
        """Verify data analyst has correct SDK tools."""
        tools = AGENT_TOOL_MAP["data_analyst"]
        # Check for data exploration tools
        assert "duckdb_query" in tools or "duckdb_tables" in tools

    def test_get_domain_tool_names(self):
        """Test getting domain-specific tool names."""
        domain_tools = get_domain_tool_names()
        assert "duckdb_query" in domain_tools
        assert "duckdb_schema" in domain_tools
        # SDK built-ins should be excluded
        assert "terminal" not in domain_tools
        assert "file_editor" not in domain_tools


class TestSDKDuckDBTools:
    """Test SDK DuckDB tool definitions."""

    def test_duckdb_query_tool_defined(self):
        """Verify DuckDB query tool is defined."""
        assert DuckDBQueryTool.name == "duckdb_query"

    def test_duckdb_schema_tool_defined(self):
        """Verify DuckDB schema tool is defined."""
        assert DuckDBSchemaTool.name == "duckdb_schema"

    def test_duckdb_tables_tool_defined(self):
        """Verify DuckDB tables tool is defined."""
        assert DuckDBTablesTool.name == "duckdb_tables"

    def test_duckdb_validate_tool_defined(self):
        """Verify DuckDB validate tool is defined."""
        assert DuckDBValidateTool.name == "duckdb_validate"


class TestRuntimeConfiguration:
    """Test runtime configuration and factory."""

    def test_runtime_type_literal(self):
        """Verify RuntimeType is defined."""
        # Just verify the type exists
        assert "sdk" in RuntimeType.__args__
        assert "local" in RuntimeType.__args__
        assert "docker" in RuntimeType.__args__

    def test_config_from_env(self):
        """Test creating config from environment."""
        with patch.dict("os.environ", {"OPENHANDS_RUNTIME": "sdk"}):
            config = OpenHandsConfig.from_env()
            assert config.runtime.runtime_type == "sdk"

    def test_config_default_sdk_runtime(self):
        """Verify SDK is the default runtime type."""
        config = OpenHandsConfig()
        assert config.runtime.runtime_type == "sdk"

    def test_create_runtime_factory(self):
        """Test runtime factory function."""
        runtime = create_runtime(runtime_type="local")
        assert isinstance(runtime, PWIRuntime)
        assert runtime._runtime_type == "local"

    def test_create_runtime_invalid_type(self):
        """Test that invalid runtime type raises error."""
        with pytest.raises(ValueError, match="Invalid runtime_type"):
            create_runtime(runtime_type="invalid")


# =============================================================================
# Agent Sequence Tests
# =============================================================================


class TestAgentSequence:
    """Test agent sequence and workflow configuration."""

    def test_agent_sequence_defined(self):
        """Verify AGENT_SEQUENCE is defined."""
        assert len(AGENT_SEQUENCE) == 6

    def test_agent_sequence_order(self):
        """Verify agent sequence is in correct order."""
        sequence = get_agent_sequence()
        assert sequence == [
            "data_analyst",
            "data_architect",
            "mapping_engineer",
            "dq_engineer",
            "story_writer",
            "sync_agent",
        ]

    def test_get_agent_sequence_returns_copy(self):
        """Verify get_agent_sequence returns a copy."""
        seq1 = get_agent_sequence()
        seq2 = get_agent_sequence()
        assert seq1 == seq2
        seq1.append("test")
        assert seq1 != seq2


# =============================================================================
# Event Stream Tests
# =============================================================================


class TestEventStream:
    """Test event stream functionality."""

    def test_create_event_stream(self):
        """Test creating event stream."""
        stream = EventStream("test-session")
        assert len(stream) == 0

    def test_append_events(self):
        """Test appending events to stream."""
        stream = EventStream("test-session")

        start_event = WorkflowStartedEvent(session_id="test-session")
        stream.append(start_event)

        assert len(stream) == 1
        assert stream.get_last_event().event_type == PWIEventType.WORKFLOW_STARTED

    def test_filter_events(self):
        """Test filtering events by type."""
        stream = EventStream("test-session")

        stream.append(WorkflowStartedEvent(session_id="test-session"))
        stream.append(AgentStartedEvent(session_id="test-session", agent_name="data_analyst"))
        stream.append(AgentCompletedEvent(session_id="test-session", agent_name="data_analyst"))

        agent_events = stream.get_events(event_type=PWIEventType.AGENT_STARTED)
        assert len(agent_events) == 1
        assert agent_events[0].agent_name == "data_analyst"

    def test_event_subscription(self):
        """Test event subscription."""
        stream = EventStream("test-session")
        received_events = []

        def callback(event):
            received_events.append(event)

        stream.subscribe(callback)
        stream.append(WorkflowStartedEvent(session_id="test-session"))

        assert len(received_events) == 1

    def test_serialize_deserialize_stream(self):
        """Test stream serialization."""
        stream = EventStream("test-session")
        stream.append(WorkflowStartedEvent(session_id="test-session"))
        stream.append(AgentStartedEvent(session_id="test-session", agent_name="data_analyst"))

        # Serialize
        data = stream.to_dict()
        assert len(data) == 2

        # Deserialize
        restored = EventStream.from_dict("test-session", data)
        assert len(restored) == 2


# =============================================================================
# Review Handler Tests
# =============================================================================


class TestReviewHandlers:
    """Test review handler functionality."""

    def test_get_auto_handler(self):
        """Test getting auto-approve handler."""
        handler = get_review_handler("auto")
        assert isinstance(handler, AutoApproveHandler)

    def test_get_skip_handler(self):
        """Test getting skip handler."""
        handler = get_review_handler("skip")
        assert isinstance(handler, SkipReviewHandler)

    def test_invalid_handler_mode(self):
        """Test invalid handler mode raises error."""
        with pytest.raises(ValueError):
            get_review_handler("invalid_mode")


# =============================================================================
# Microagent Files Tests
# =============================================================================


class TestMicroagentFiles:
    """Test Skills/Microagents files exist and are valid."""

    def test_microagents_exist(self):
        """Verify all microagent files exist."""
        expected_files = [
            "repo.md",
            "data_analyst.md",
            "data_architect.md",
            "mapping_engineer.md",
            "dq_engineer.md",
            "story_writer.md",
            "sync_agent.md",
            "validator_agent.md",
        ]
        for filename in expected_files:
            filepath = MICROAGENTS_DIR / filename
            assert filepath.exists(), f"Missing microagent: {filename}"

    def test_microagent_frontmatter_valid(self):
        """Verify microagents have valid YAML frontmatter."""
        import yaml

        for filepath in MICROAGENTS_DIR.glob("*.md"):
            content = filepath.read_text()

            # Check for frontmatter
            assert content.startswith("---"), f"{filepath.name} missing frontmatter"

            # Extract frontmatter
            parts = content.split("---", 2)
            assert len(parts) >= 3, f"{filepath.name} invalid frontmatter format"

            # Parse YAML
            frontmatter = yaml.safe_load(parts[1])
            assert "name" in frontmatter, f"{filepath.name} missing 'name' in frontmatter"
            assert "type" in frontmatter, f"{filepath.name} missing 'type' in frontmatter"

    def test_microagent_has_content(self):
        """Verify microagents have actual content after frontmatter."""
        for filepath in MICROAGENTS_DIR.glob("*.md"):
            content = filepath.read_text()
            parts = content.split("---", 2)
            if len(parts) >= 3:
                markdown_content = parts[2].strip()
                assert len(markdown_content) > 50, f"{filepath.name} has insufficient content"


# =============================================================================
# Skills Tests
# =============================================================================


class TestSkillsDiscovery:
    """Test skills discovery and loading."""

    def test_skills_dir_exists(self):
        """Verify SKILLS_DIR points to existing directory."""
        assert SKILLS_DIR.exists()
        assert SKILLS_DIR.is_dir()

    def test_discover_skills_returns_dict(self):
        """Verify discover_skills returns a dictionary."""
        skills = discover_skills()
        assert isinstance(skills, dict)

    def test_duckdb_skill_exists(self):
        """Verify duckdb skill is discovered."""
        skills = discover_skills()
        assert "duckdb" in skills
        assert isinstance(skills["duckdb"], SkillInfo)

    def test_duckdb_skill_has_triggers(self):
        """Verify duckdb skill has trigger keywords."""
        skills = discover_skills()
        duckdb_skill = skills.get("duckdb")
        assert duckdb_skill is not None
        assert len(duckdb_skill.triggers) > 0
        assert "duckdb" in duckdb_skill.triggers

    def test_duckdb_skill_has_content(self):
        """Verify duckdb skill has content."""
        skills = discover_skills()
        duckdb_skill = skills.get("duckdb")
        assert duckdb_skill is not None
        assert len(duckdb_skill.content) > 100
        assert "DuckDB" in duckdb_skill.content

    def test_skill_frontmatter_valid(self):
        """Verify skills have valid YAML frontmatter."""
        import yaml

        for filepath in SKILLS_DIR.glob("*.md"):
            content = filepath.read_text()

            # Check for frontmatter
            assert content.startswith("---"), f"{filepath.name} missing frontmatter"

            # Extract frontmatter
            parts = content.split("---", 2)
            assert len(parts) >= 3, f"{filepath.name} invalid frontmatter format"

            # Parse YAML
            frontmatter = yaml.safe_load(parts[1])
            assert "name" in frontmatter, f"{filepath.name} missing 'name' in frontmatter"
            assert "triggers" in frontmatter, f"{filepath.name} missing 'triggers' in frontmatter"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
