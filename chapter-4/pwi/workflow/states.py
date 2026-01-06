"""Workflow state definitions for Planning with Intent.

This module defines all possible states in the PWI workflow,
following a state machine pattern for the agent pipeline.
"""

from collections.abc import Mapping
from enum import Enum


class WorkflowState(str, Enum):
    """Workflow states for the PWI Data Engineering pipeline.

    The workflow progresses through agents in sequence:
    1. Data Analyst → DRD (Data Requirements Document)
    2. Data Architect → PAD (Pipeline Architecture Document)
    3. Mapping Engineer → DMD (Data Mapping Document)
    4. DQ Engineer → DQS (Data Quality Specification)
    5. Story Writer → Epics & Stories
    6. Sync Agent → Final package

    Each agent has a RUNNING and REVIEW state, with the exception
    of Sync Agent which doesn't require review.
    """

    # Initial state
    INITIALIZED = "initialized"

    # Data Analyst states
    DATA_ANALYST_RUNNING = "data_analyst_running"
    DATA_ANALYST_REVIEW = "data_analyst_review"

    # Data Architect states
    DATA_ARCHITECT_RUNNING = "data_architect_running"
    DATA_ARCHITECT_REVIEW = "data_architect_review"

    # Mapping Engineer states
    MAPPING_ENGINEER_RUNNING = "mapping_engineer_running"
    MAPPING_ENGINEER_REVIEW = "mapping_engineer_review"

    # DQ Engineer states
    DQ_ENGINEER_RUNNING = "dq_engineer_running"
    DQ_ENGINEER_REVIEW = "dq_engineer_review"

    # Story Writer states
    STORY_WRITER_RUNNING = "story_writer_running"
    STORY_WRITER_REVIEW = "story_writer_review"

    # Sync Agent state (no review needed)
    SYNC_AGENT_RUNNING = "sync_agent_running"

    # Terminal states
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"

    @classmethod
    def is_terminal(cls, state: "WorkflowState") -> bool:
        """Check if a state is terminal (no transitions out)."""
        return state in {cls.COMPLETED, cls.FAILED, cls.CANCELLED}

    @classmethod
    def is_running(cls, state: "WorkflowState") -> bool:
        """Check if a state represents an agent running."""
        return state.value.endswith("_running")

    @classmethod
    def is_review(cls, state: "WorkflowState") -> bool:
        """Check if a state represents a review gate."""
        return state.value.endswith("_review")

    @classmethod
    def get_agent_name(cls, state: "WorkflowState") -> str | None:
        """Extract the agent name from a state.

        Args:
            state: A workflow state.

        Returns:
            Agent name (e.g., 'data_analyst') or None if not an agent state.
        """
        if state.value == "initialized":
            return None
        if cls.is_terminal(state) or state == cls.PAUSED:
            return None

        # Extract agent name by removing _running or _review suffix
        value: str = state.value
        if value.endswith("_running"):
            return str(value[:-8])  # Remove "_running"
        if value.endswith("_review"):
            return str(value[:-7])  # Remove "_review"
        return None


# Agent execution order
AGENT_ORDER = [
    "data_analyst",
    "data_architect",
    "mapping_engineer",
    "dq_engineer",
    "story_writer",
    "sync_agent",
]

# Maps agent name to the artifact type it produces
AGENT_ARTIFACTS = {
    "data_analyst": "drd",
    "data_architect": "pad",
    "mapping_engineer": "dmd",
    "dq_engineer": "dqs",
    "story_writer": "stories",
    "sync_agent": "package",
}

# Maps agent name to its running state
AGENT_RUNNING_STATES = {
    "data_analyst": WorkflowState.DATA_ANALYST_RUNNING,
    "data_architect": WorkflowState.DATA_ARCHITECT_RUNNING,
    "mapping_engineer": WorkflowState.MAPPING_ENGINEER_RUNNING,
    "dq_engineer": WorkflowState.DQ_ENGINEER_RUNNING,
    "story_writer": WorkflowState.STORY_WRITER_RUNNING,
    "sync_agent": WorkflowState.SYNC_AGENT_RUNNING,
}

# Maps agent name to its review state (sync_agent has no review)
AGENT_REVIEW_STATES = {
    "data_analyst": WorkflowState.DATA_ANALYST_REVIEW,
    "data_architect": WorkflowState.DATA_ARCHITECT_REVIEW,
    "mapping_engineer": WorkflowState.MAPPING_ENGINEER_REVIEW,
    "dq_engineer": WorkflowState.DQ_ENGINEER_REVIEW,
    "story_writer": WorkflowState.STORY_WRITER_REVIEW,
}


def get_next_agent(current_agent: str) -> str | None:
    """Get the next agent in the workflow sequence.

    Args:
        current_agent: Name of the current agent.

    Returns:
        Name of the next agent, or None if at the end.
    """
    try:
        idx = AGENT_ORDER.index(current_agent)
        if idx < len(AGENT_ORDER) - 1:
            return AGENT_ORDER[idx + 1]
        return None
    except ValueError:
        return None


def get_resume_agent(artifacts: Mapping[str, object]) -> str | None:
    """Determine which agent to resume from based on completed artifacts.

    Args:
        artifacts: Dictionary of completed artifacts (keyed by artifact type).

    Returns:
        Name of the next agent to run, or None if all complete.
    """
    # Map from artifact type to the agent that produces it
    artifact_to_agent = {v: k for k, v in AGENT_ARTIFACTS.items()}

    # Find completed agents based on artifacts
    completed_agents = set()
    for artifact_type in artifacts:
        agent = artifact_to_agent.get(artifact_type)
        if agent:
            completed_agents.add(agent)

    # Find first incomplete agent
    for agent in AGENT_ORDER:
        if agent not in completed_agents:
            return agent

    return None  # All agents complete
