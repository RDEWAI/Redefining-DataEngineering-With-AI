"""State machine for PWI workflow orchestration.

This module implements the workflow state machine using the
transitions library, managing the progression through agents.

Note: The transitions library dynamically adds trigger methods and the
`state` attribute to the model class. Type checkers can't see these,
so we use `# type: ignore` comments where needed.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from transitions import EventData, Machine

from pwi.workflow.session import Session
from pwi.workflow.states import (
    AGENT_ORDER,
    WorkflowState,
)

if TYPE_CHECKING:
    from pwi.workflow.session import SessionManager


class PWIWorkflow:
    """State machine for PWI workflow orchestration.

    This class manages the workflow state transitions as agents
    execute and reviews are processed.

    Note: The transitions library dynamically adds the following attributes:
    - self.state: Current state string
    - Trigger methods for each transition (e.g., self.start(), self.analyst_complete())
    """

    # Dynamically added by transitions library
    state: str

    # Trigger methods added dynamically by transitions library
    # These are declared here for type checking purposes
    start: Callable[[], bool]
    analyst_complete: Callable[[], bool]
    analyst_approved: Callable[[], bool]
    analyst_rejected: Callable[[], bool]
    architect_complete: Callable[[], bool]
    architect_approved: Callable[[], bool]
    architect_rejected: Callable[[], bool]
    mapping_complete: Callable[[], bool]
    mapping_approved: Callable[[], bool]
    mapping_rejected: Callable[[], bool]
    dq_complete: Callable[[], bool]
    dq_approved: Callable[[], bool]
    dq_rejected: Callable[[], bool]
    stories_complete: Callable[[], bool]
    stories_approved: Callable[[], bool]
    stories_rejected: Callable[[], bool]
    sync_complete: Callable[[], bool]
    pause: Callable[[], bool]
    fail: Callable[[], bool]
    cancel: Callable[[], bool]

    # All possible states
    states = [state.value for state in WorkflowState]

    # State transitions
    transitions = [
        # Start workflow
        {
            "trigger": "start",
            "source": WorkflowState.INITIALIZED.value,
            "dest": WorkflowState.DATA_ANALYST_RUNNING.value,
        },
        # Data Analyst flow
        {
            "trigger": "analyst_complete",
            "source": WorkflowState.DATA_ANALYST_RUNNING.value,
            "dest": WorkflowState.DATA_ANALYST_REVIEW.value,
        },
        {
            "trigger": "analyst_approved",
            "source": WorkflowState.DATA_ANALYST_REVIEW.value,
            "dest": WorkflowState.DATA_ARCHITECT_RUNNING.value,
        },
        {
            "trigger": "analyst_rejected",
            "source": WorkflowState.DATA_ANALYST_REVIEW.value,
            "dest": WorkflowState.DATA_ANALYST_RUNNING.value,
        },
        # Data Architect flow
        {
            "trigger": "architect_complete",
            "source": WorkflowState.DATA_ARCHITECT_RUNNING.value,
            "dest": WorkflowState.DATA_ARCHITECT_REVIEW.value,
        },
        {
            "trigger": "architect_approved",
            "source": WorkflowState.DATA_ARCHITECT_REVIEW.value,
            "dest": WorkflowState.MAPPING_ENGINEER_RUNNING.value,
        },
        {
            "trigger": "architect_rejected",
            "source": WorkflowState.DATA_ARCHITECT_REVIEW.value,
            "dest": WorkflowState.DATA_ARCHITECT_RUNNING.value,
        },
        # Mapping Engineer flow
        {
            "trigger": "mapping_complete",
            "source": WorkflowState.MAPPING_ENGINEER_RUNNING.value,
            "dest": WorkflowState.MAPPING_ENGINEER_REVIEW.value,
        },
        {
            "trigger": "mapping_approved",
            "source": WorkflowState.MAPPING_ENGINEER_REVIEW.value,
            "dest": WorkflowState.DQ_ENGINEER_RUNNING.value,
        },
        {
            "trigger": "mapping_rejected",
            "source": WorkflowState.MAPPING_ENGINEER_REVIEW.value,
            "dest": WorkflowState.MAPPING_ENGINEER_RUNNING.value,
        },
        # DQ Engineer flow
        {
            "trigger": "dq_complete",
            "source": WorkflowState.DQ_ENGINEER_RUNNING.value,
            "dest": WorkflowState.DQ_ENGINEER_REVIEW.value,
        },
        {
            "trigger": "dq_approved",
            "source": WorkflowState.DQ_ENGINEER_REVIEW.value,
            "dest": WorkflowState.STORY_WRITER_RUNNING.value,
        },
        {
            "trigger": "dq_rejected",
            "source": WorkflowState.DQ_ENGINEER_REVIEW.value,
            "dest": WorkflowState.DQ_ENGINEER_RUNNING.value,
        },
        # Story Writer flow
        {
            "trigger": "stories_complete",
            "source": WorkflowState.STORY_WRITER_RUNNING.value,
            "dest": WorkflowState.STORY_WRITER_REVIEW.value,
        },
        {
            "trigger": "stories_approved",
            "source": WorkflowState.STORY_WRITER_REVIEW.value,
            "dest": WorkflowState.SYNC_AGENT_RUNNING.value,
        },
        {
            "trigger": "stories_rejected",
            "source": WorkflowState.STORY_WRITER_REVIEW.value,
            "dest": WorkflowState.STORY_WRITER_RUNNING.value,
        },
        # Sync Agent (final - no review)
        {
            "trigger": "sync_complete",
            "source": WorkflowState.SYNC_AGENT_RUNNING.value,
            "dest": WorkflowState.COMPLETED.value,
        },
        # Pause from any non-terminal state
        {
            "trigger": "pause",
            "source": "*",
            "dest": WorkflowState.PAUSED.value,
            "conditions": "_can_pause",
        },
        # Fail from any non-terminal state
        {
            "trigger": "fail",
            "source": "*",
            "dest": WorkflowState.FAILED.value,
            "conditions": "_can_fail",
        },
        # Cancel from any non-terminal state
        {
            "trigger": "cancel",
            "source": "*",
            "dest": WorkflowState.CANCELLED.value,
            "conditions": "_can_cancel",
        },
    ]

    def __init__(
        self,
        session: Session,
        session_manager: SessionManager | None = None,
        on_state_change: Callable[[str, str], None] | None = None,
    ) -> None:
        """Initialize the workflow state machine.

        Args:
            session: Session to track state for.
            session_manager: Optional manager for persisting session.
            on_state_change: Optional callback for state changes.
        """
        self.session = session
        self.session_manager = session_manager
        self.on_state_change_callback = on_state_change

        # Initialize the state machine
        self.machine = Machine(
            model=self,
            states=self.states,
            transitions=self.transitions,
            initial=session.current_state,
            auto_transitions=False,
            send_event=True,
            after_state_change="_after_state_change",
        )

    def _after_state_change(self, event: EventData) -> None:
        """Callback after any state change.

        Updates the session and persists if manager is available.
        """
        self.session.set_state(WorkflowState(self.state))

        if self.session_manager:
            self.session_manager.save(self.session)

        if self.on_state_change_callback:
            self.on_state_change_callback(event.transition.source, self.state)  # type: ignore[union-attr]

    def _can_pause(self, event: EventData) -> bool:
        """Check if workflow can be paused from current state."""
        current = WorkflowState(self.state)
        return not WorkflowState.is_terminal(current)

    def _can_fail(self, event: EventData) -> bool:
        """Check if workflow can fail from current state."""
        current = WorkflowState(self.state)
        return not WorkflowState.is_terminal(current)

    def _can_cancel(self, event: EventData) -> bool:
        """Check if workflow can be cancelled from current state."""
        current = WorkflowState(self.state)
        return not WorkflowState.is_terminal(current)

    def get_current_agent(self) -> str | None:
        """Get the name of the current agent based on state."""
        return WorkflowState.get_agent_name(WorkflowState(self.state))

    def is_in_review(self) -> bool:
        """Check if workflow is waiting for review."""
        return WorkflowState.is_review(WorkflowState(self.state))

    def is_running_agent(self) -> bool:
        """Check if an agent is currently running."""
        return WorkflowState.is_running(WorkflowState(self.state))

    def is_complete(self) -> bool:
        """Check if workflow has completed."""
        return self.state == WorkflowState.COMPLETED.value

    def is_terminal(self) -> bool:
        """Check if workflow is in a terminal state."""
        return WorkflowState.is_terminal(WorkflowState(self.state))

    def agent_completed(self) -> None:
        """Signal that the current agent has completed.

        Automatically calls the appropriate trigger based on current state.
        """
        agent = self.get_current_agent()
        if not agent:
            return

        # Map agent to completion trigger
        trigger_map = {
            "data_analyst": self.analyst_complete,
            "data_architect": self.architect_complete,
            "mapping_engineer": self.mapping_complete,
            "dq_engineer": self.dq_complete,
            "story_writer": self.stories_complete,
            "sync_agent": self.sync_complete,
        }

        trigger = trigger_map.get(agent)
        if trigger:
            trigger()

    def review_approved(self) -> None:
        """Signal that the current review was approved.

        Automatically calls the appropriate trigger based on current state.
        """
        agent = self.get_current_agent()
        if not agent:
            return

        # Map agent to approval trigger
        trigger_map = {
            "data_analyst": self.analyst_approved,
            "data_architect": self.architect_approved,
            "mapping_engineer": self.mapping_approved,
            "dq_engineer": self.dq_approved,
            "story_writer": self.stories_approved,
        }

        trigger = trigger_map.get(agent)
        if trigger:
            trigger()

    def review_rejected(self) -> None:
        """Signal that the current review was rejected.

        Automatically calls the appropriate trigger based on current state.
        """
        agent = self.get_current_agent()
        if not agent:
            return

        # Map agent to rejection trigger
        trigger_map = {
            "data_analyst": self.analyst_rejected,
            "data_architect": self.architect_rejected,
            "mapping_engineer": self.mapping_rejected,
            "dq_engineer": self.dq_rejected,
            "story_writer": self.stories_rejected,
        }

        trigger = trigger_map.get(agent)
        if trigger:
            trigger()

    def get_progress(self) -> tuple[int, int]:
        """Get the current progress through the workflow.

        Returns:
            Tuple of (completed_agents, total_agents).
        """
        current_state = WorkflowState(self.state)

        if current_state == WorkflowState.INITIALIZED:
            return (0, len(AGENT_ORDER))

        if current_state == WorkflowState.COMPLETED:
            return (len(AGENT_ORDER), len(AGENT_ORDER))

        if current_state in {
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
            WorkflowState.PAUSED,
        }:
            # Return progress at time of interruption
            agent = self.get_current_agent()
            if agent:
                idx = AGENT_ORDER.index(agent)
                return (idx, len(AGENT_ORDER))
            return (0, len(AGENT_ORDER))

        # Count completed agents
        agent = self.get_current_agent()
        if agent:
            idx = AGENT_ORDER.index(agent)
            return (idx, len(AGENT_ORDER))

        return (0, len(AGENT_ORDER))
