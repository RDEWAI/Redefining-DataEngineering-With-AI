"""Integration tests for OpenHands SDK migration.

These tests validate the full OpenHands integration including:
- Agent creation and configuration
- Tool registration and execution
- Event stream functionality
- Workflow state management
"""

import asyncio
import pytest
from pathlib import Path

from pwi.openhands.agents import (
    DataAnalystAgent,
    DataArchitectAgent,
    MappingEngineerAgent,
    DQEngineerAgent,
    StoryWriterAgent,
    SyncAgent,
    PWIAgentConfig,
    PWIAgentState,
    get_agent,
    get_agent_sequence,
    list_agents,
    AGENT_REGISTRY,
)
from pwi.openhands.tools import (
    get_registry,
    get_all_tools,
    get_tools_for_agent,
)
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


class TestToolRegistry:
    """Test tool registration and execution."""

    def test_registry_has_all_tools(self):
        """Verify all expected tools are registered."""
        registry = get_registry()
        expected_tools = [
            "duckdb_query",
            "duckdb_schema",
            "duckdb_validate",
            "duckdb_tables",
            "analyze_csv",
            "csv_stats",
            "csv_sample",
            "query_metadata_catalog",
            "get_lineage",
            "get_tags",
            "generate_artifact",
            "save_artifact",
            "validate_artifact",
            "list_artifact_types",
        ]
        for tool in expected_tools:
            assert tool in registry.tool_names, f"Missing tool: {tool}"

    def test_get_tools_for_data_analyst(self):
        """Verify data analyst gets correct tools."""
        tools = get_tools_for_agent("data_analyst")
        tool_names = [t["function"]["name"] for t in tools]
        assert "duckdb_query" in tool_names
        assert "duckdb_schema" in tool_names
        assert "analyze_csv" in tool_names

    def test_get_tools_for_sync_agent(self):
        """Verify sync agent gets artifact tools."""
        tools = get_tools_for_agent("sync_agent")
        tool_names = [t["function"]["name"] for t in tools]
        assert "generate_artifact" in tool_names
        assert "save_artifact" in tool_names

    def test_list_artifact_types_execution(self):
        """Test list_artifact_types tool execution."""
        registry = get_registry()
        result = registry.execute("list_artifact_types")
        assert result["success"] is True
        assert "drd" in result["artifact_types"]
        assert "pad" in result["artifact_types"]
        assert result["count"] == 6

    def test_validate_artifact_execution(self):
        """Test validate_artifact tool execution."""
        registry = get_registry()
        content = "# Data Requirements Document (DRD)\n\n## Summary\nTest"
        result = registry.execute("validate_artifact", artifact_type="drd", content=content)
        assert result["success"] is True
        assert result["artifact_type"] == "drd"


class TestAgents:
    """Test agent creation and configuration."""

    def test_all_agents_in_registry(self):
        """Verify all agents are registered."""
        expected_agents = [
            "data_analyst",
            "data_architect",
            "mapping_engineer",
            "dq_engineer",
            "story_writer",
            "sync_agent",
        ]
        for agent in expected_agents:
            assert agent in AGENT_REGISTRY, f"Missing agent: {agent}"

    def test_agent_sequence(self):
        """Verify agent sequence is correct."""
        sequence = get_agent_sequence()
        assert sequence == [
            "data_analyst",
            "data_architect",
            "mapping_engineer",
            "dq_engineer",
            "story_writer",
            "sync_agent",
        ]

    def test_create_data_analyst(self):
        """Test creating a data analyst agent."""
        config = PWIAgentConfig(name="data_analyst", model="gpt-4o")
        agent = DataAnalystAgent(config=config)
        assert agent.AGENT_NAME == "data_analyst"
        assert agent.ARTIFACT_TYPE == "drd"
        assert agent.ARTIFACT_FORMAT == "markdown"
        assert len(agent.tools) > 0

    def test_create_agent_via_factory(self):
        """Test creating agent via get_agent factory."""
        config = PWIAgentConfig(name="data_architect", model="gpt-4o")
        agent = get_agent("data_architect", config)
        assert isinstance(agent, DataArchitectAgent)

    def test_agent_required_inputs(self):
        """Test agent dependency declarations."""
        config = PWIAgentConfig(name="test", model="gpt-4o")

        # Data analyst has no dependencies
        analyst = DataAnalystAgent(config=config)
        assert analyst.get_required_inputs() == []

        # Data architect depends on DRD
        architect = DataArchitectAgent(config=config)
        assert "drd" in architect.get_required_inputs()

        # Sync agent depends on all artifacts
        sync = SyncAgent(config=config)
        required = sync.get_required_inputs()
        assert "drd" in required
        assert "pad" in required
        assert "dmd" in required
        assert "dqs" in required
        assert "stories" in required

    def test_list_agents(self):
        """Test list_agents function."""
        agents = list_agents()
        assert len(agents) == 6
        agent_names = [a["name"] for a in agents]
        assert "data_analyst" in agent_names


class TestAgentState:
    """Test agent state management."""

    def test_create_agent_state(self):
        """Test creating agent state."""
        state = PWIAgentState(
            session_id="test-123",
            business_request="Test business request",
        )
        assert state.session_id == "test-123"
        assert state.current_step == 0
        assert state.is_complete is False

    def test_state_with_artifacts(self):
        """Test state with existing artifacts."""
        state = PWIAgentState(
            session_id="test-123",
            business_request="Test request",
            artifacts={"drd": "# DRD Content"},
        )
        assert "drd" in state.artifacts

    def test_validate_inputs(self):
        """Test input validation."""
        config = PWIAgentConfig(name="data_architect", model="gpt-4o")
        agent = DataArchitectAgent(config=config)

        # State without required DRD
        state_no_drd = PWIAgentState(
            session_id="test",
            business_request="test",
        )
        is_valid, error = agent.validate_inputs(state_no_drd)
        assert is_valid is False
        assert "drd" in error

        # State with required DRD
        state_with_drd = PWIAgentState(
            session_id="test",
            business_request="test",
            artifacts={"drd": "# DRD Content"},
        )
        is_valid, error = agent.validate_inputs(state_with_drd)
        assert is_valid is True


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


class TestMicroagents:
    """Test Skills/Microagents files."""

    def test_microagents_exist(self):
        """Verify all microagent files exist."""
        base_path = Path(__file__).parent.parent.parent / ".openhands" / "microagents"
        expected_files = [
            "repo.md",
            "data_analyst.md",
            "data_architect.md",
            "mapping_engineer.md",
            "dq_engineer.md",
            "story_writer.md",
            "sync_agent.md",
        ]
        for filename in expected_files:
            filepath = base_path / filename
            assert filepath.exists(), f"Missing microagent: {filename}"

    def test_microagent_frontmatter(self):
        """Verify microagents have valid YAML frontmatter."""
        import yaml

        base_path = Path(__file__).parent.parent.parent / ".openhands" / "microagents"

        for filepath in base_path.glob("*.md"):
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
