"""Custom PWI events for OpenHands workflow.

This module defines PWI-specific events that flow through the EventStream:
- Agent lifecycle events (start, complete, error)
- Review gate events (pending, approved, rejected)
- Artifact events (generated, validated, saved)
- Workflow events (started, paused, resumed, completed)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class PWIEventType(str, Enum):
    """Types of PWI events."""

    # Workflow lifecycle
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_PAUSED = "workflow_paused"
    WORKFLOW_RESUMED = "workflow_resumed"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"

    # Agent lifecycle
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"
    AGENT_TOOL_CALL = "agent_tool_call"
    AGENT_TOOL_RESULT = "agent_tool_result"

    # Review gates
    REVIEW_PENDING = "review_pending"
    REVIEW_APPROVED = "review_approved"
    REVIEW_REJECTED = "review_rejected"
    REVIEW_TIMEOUT = "review_timeout"

    # Artifacts
    ARTIFACT_GENERATED = "artifact_generated"
    ARTIFACT_VALIDATED = "artifact_validated"
    ARTIFACT_SAVED = "artifact_saved"

    # User interaction
    USER_INPUT = "user_input"
    USER_FEEDBACK = "user_feedback"


class PWIEvent(BaseModel):
    """Base class for all PWI events.

    Events are immutable records that flow through the EventStream
    and can be persisted for replay and audit.
    """

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(default_factory=lambda: f"evt_{_utcnow().strftime('%Y%m%d%H%M%S%f')}")
    event_type: PWIEventType
    timestamp: datetime = Field(default_factory=_utcnow)
    session_id: str
    agent_name: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class WorkflowStartedEvent(PWIEvent):
    """Event when workflow starts."""

    event_type: PWIEventType = PWIEventType.WORKFLOW_STARTED


class WorkflowPausedEvent(PWIEvent):
    """Event when workflow is paused (e.g., for review)."""

    event_type: PWIEventType = PWIEventType.WORKFLOW_PAUSED
    pause_reason: str = "review_pending"
    resume_from: str | None = None


class WorkflowResumedEvent(PWIEvent):
    """Event when workflow resumes."""

    event_type: PWIEventType = PWIEventType.WORKFLOW_RESUMED
    resumed_from: str | None = None


class WorkflowCompletedEvent(PWIEvent):
    """Event when workflow completes successfully."""

    event_type: PWIEventType = PWIEventType.WORKFLOW_COMPLETED
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    artifact_count: int = 0


class WorkflowFailedEvent(PWIEvent):
    """Event when workflow fails."""

    event_type: PWIEventType = PWIEventType.WORKFLOW_FAILED
    error_message: str = ""
    failed_at_agent: str | None = None


class AgentStartedEvent(PWIEvent):
    """Event when an agent starts execution."""

    event_type: PWIEventType = PWIEventType.AGENT_STARTED
    agent_name: str
    model: str = ""
    tool_count: int = 0


class AgentCompletedEvent(PWIEvent):
    """Event when an agent completes successfully."""

    event_type: PWIEventType = PWIEventType.AGENT_COMPLETED
    agent_name: str
    artifact_type: str = ""
    artifact_format: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    tool_calls_count: int = 0


class AgentFailedEvent(PWIEvent):
    """Event when an agent fails."""

    event_type: PWIEventType = PWIEventType.AGENT_FAILED
    agent_name: str
    error_message: str = ""


class AgentToolCallEvent(PWIEvent):
    """Event when an agent makes a tool call."""

    event_type: PWIEventType = PWIEventType.AGENT_TOOL_CALL
    agent_name: str
    tool_name: str = ""
    arguments: dict[str, Any] = Field(default_factory=dict)


class AgentToolResultEvent(PWIEvent):
    """Event when a tool returns a result."""

    event_type: PWIEventType = PWIEventType.AGENT_TOOL_RESULT
    agent_name: str
    tool_name: str = ""
    success: bool = True
    result: dict[str, Any] = Field(default_factory=dict)


class ReviewPendingEvent(PWIEvent):
    """Event when review is pending for an agent output."""

    event_type: PWIEventType = PWIEventType.REVIEW_PENDING
    agent_name: str
    artifact_type: str = ""
    review_mode: str = "cli"  # cli, file, dashboard


class ReviewApprovedEvent(PWIEvent):
    """Event when review is approved."""

    event_type: PWIEventType = PWIEventType.REVIEW_APPROVED
    agent_name: str
    feedback: str = ""
    was_edited: bool = False


class ReviewRejectedEvent(PWIEvent):
    """Event when review is rejected."""

    event_type: PWIEventType = PWIEventType.REVIEW_REJECTED
    agent_name: str
    feedback: str = ""
    rejection_reason: str = ""


class ReviewTimeoutEvent(PWIEvent):
    """Event when review times out."""

    event_type: PWIEventType = PWIEventType.REVIEW_TIMEOUT
    agent_name: str
    timeout_minutes: int = 0


class ArtifactGeneratedEvent(PWIEvent):
    """Event when an artifact is generated."""

    event_type: PWIEventType = PWIEventType.ARTIFACT_GENERATED
    agent_name: str
    artifact_type: str = ""
    artifact_format: str = ""
    size_bytes: int = 0


class ArtifactValidatedEvent(PWIEvent):
    """Event when an artifact is validated."""

    event_type: PWIEventType = PWIEventType.ARTIFACT_VALIDATED
    artifact_type: str = ""
    is_valid: bool = True
    issues: list[str] = Field(default_factory=list)


class ArtifactSavedEvent(PWIEvent):
    """Event when an artifact is saved to disk."""

    event_type: PWIEventType = PWIEventType.ARTIFACT_SAVED
    artifact_type: str = ""
    file_path: str = ""


class UserInputEvent(PWIEvent):
    """Event for user input (e.g., business request)."""

    event_type: PWIEventType = PWIEventType.USER_INPUT
    input_type: str = "business_request"
    content: str = ""


class UserFeedbackEvent(PWIEvent):
    """Event for user feedback during review."""

    event_type: PWIEventType = PWIEventType.USER_FEEDBACK
    agent_name: str
    feedback: str = ""


class EventStream:
    """In-memory event stream for PWI workflow.

    This class manages a stream of events that can be:
    - Appended to as events occur
    - Persisted to storage
    - Replayed to reconstruct state
    """

    def __init__(self, session_id: str) -> None:
        """Initialize the event stream.

        Args:
            session_id: Session identifier for this stream.
        """
        self.session_id = session_id
        self._events: list[PWIEvent] = []
        self._subscribers: list[callable] = []

    def append(self, event: PWIEvent) -> None:
        """Append an event to the stream.

        Args:
            event: Event to append.
        """
        self._events.append(event)
        # Notify subscribers
        for subscriber in self._subscribers:
            subscriber(event)

    def subscribe(self, callback: callable) -> None:
        """Subscribe to new events.

        Args:
            callback: Function to call with each new event.
        """
        self._subscribers.append(callback)

    def unsubscribe(self, callback: callable) -> None:
        """Unsubscribe from events.

        Args:
            callback: Function to remove from subscribers.
        """
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def get_events(
        self,
        event_type: PWIEventType | None = None,
        agent_name: str | None = None,
    ) -> list[PWIEvent]:
        """Get events with optional filtering.

        Args:
            event_type: Filter by event type.
            agent_name: Filter by agent name.

        Returns:
            List of matching events.
        """
        events = self._events

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        if agent_name:
            events = [e for e in events if e.agent_name == agent_name]

        return events

    def get_last_event(self, event_type: PWIEventType | None = None) -> PWIEvent | None:
        """Get the most recent event.

        Args:
            event_type: Optional filter by event type.

        Returns:
            Most recent matching event or None.
        """
        events = self.get_events(event_type=event_type)
        return events[-1] if events else None

    def to_dict(self) -> list[dict[str, Any]]:
        """Convert stream to list of dictionaries for serialization.

        Returns:
            List of event dictionaries.
        """
        return [e.model_dump() for e in self._events]

    @classmethod
    def from_dict(cls, session_id: str, events_data: list[dict[str, Any]]) -> EventStream:
        """Create stream from serialized data.

        Args:
            session_id: Session identifier.
            events_data: List of event dictionaries.

        Returns:
            Reconstructed EventStream.
        """
        stream = cls(session_id)

        # Map event types to classes
        event_classes = {
            PWIEventType.WORKFLOW_STARTED: WorkflowStartedEvent,
            PWIEventType.WORKFLOW_PAUSED: WorkflowPausedEvent,
            PWIEventType.WORKFLOW_RESUMED: WorkflowResumedEvent,
            PWIEventType.WORKFLOW_COMPLETED: WorkflowCompletedEvent,
            PWIEventType.WORKFLOW_FAILED: WorkflowFailedEvent,
            PWIEventType.AGENT_STARTED: AgentStartedEvent,
            PWIEventType.AGENT_COMPLETED: AgentCompletedEvent,
            PWIEventType.AGENT_FAILED: AgentFailedEvent,
            PWIEventType.AGENT_TOOL_CALL: AgentToolCallEvent,
            PWIEventType.AGENT_TOOL_RESULT: AgentToolResultEvent,
            PWIEventType.REVIEW_PENDING: ReviewPendingEvent,
            PWIEventType.REVIEW_APPROVED: ReviewApprovedEvent,
            PWIEventType.REVIEW_REJECTED: ReviewRejectedEvent,
            PWIEventType.REVIEW_TIMEOUT: ReviewTimeoutEvent,
            PWIEventType.ARTIFACT_GENERATED: ArtifactGeneratedEvent,
            PWIEventType.ARTIFACT_VALIDATED: ArtifactValidatedEvent,
            PWIEventType.ARTIFACT_SAVED: ArtifactSavedEvent,
            PWIEventType.USER_INPUT: UserInputEvent,
            PWIEventType.USER_FEEDBACK: UserFeedbackEvent,
        }

        for event_data in events_data:
            event_type = PWIEventType(event_data.get("event_type"))
            event_class = event_classes.get(event_type, PWIEvent)
            event = event_class(**event_data)
            stream._events.append(event)

        return stream

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self):
        return iter(self._events)
