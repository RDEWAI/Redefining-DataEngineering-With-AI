"""Session adapter for OpenHands-based PWI workflow.

This module bridges the existing PWI Session model with the
OpenHands EventStream, providing:
- Event-based session state updates
- Session persistence with event replay
- Backward compatibility with existing session storage
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pwi.workflow.states import WorkflowState
from pwi.openhands.workflow.events import (
    AgentCompletedEvent,
    ArtifactGeneratedEvent,
    ArtifactSavedEvent,
    EventStream,
    PWIEvent,
    PWIEventType,
    ReviewApprovedEvent,
    ReviewRejectedEvent,
    UserInputEvent,
    WorkflowCompletedEvent,
    WorkflowFailedEvent,
    WorkflowPausedEvent,
    WorkflowStartedEvent,
)
from pwi.utils.logging import get_logger

if TYPE_CHECKING:
    from pwi.workflow.session import Session, SessionManager

logger = get_logger("openhands.workflow.session_adapter")


class SessionEventAdapter:
    """Adapter that syncs PWI Session with EventStream.

    This adapter:
    - Listens to events and updates the Session accordingly
    - Provides methods to emit events from Session changes
    - Handles session persistence with event history
    """

    def __init__(
        self,
        session: Session,
        session_manager: SessionManager,
        event_stream: EventStream | None = None,
    ) -> None:
        """Initialize the session adapter.

        Args:
            session: PWI session to adapt.
            session_manager: Session persistence manager.
            event_stream: Optional existing event stream.
        """
        self.session = session
        self.session_manager = session_manager
        self.event_stream = event_stream or EventStream(session.session_id)

        # Subscribe to events for session updates
        self.event_stream.subscribe(self._handle_event)

    def _handle_event(self, event: PWIEvent) -> None:
        """Handle incoming events and update session.

        Args:
            event: Event to process.
        """
        handlers = {
            PWIEventType.WORKFLOW_STARTED: self._handle_workflow_started,
            PWIEventType.WORKFLOW_COMPLETED: self._handle_workflow_completed,
            PWIEventType.WORKFLOW_FAILED: self._handle_workflow_failed,
            PWIEventType.WORKFLOW_PAUSED: self._handle_workflow_paused,
            PWIEventType.AGENT_COMPLETED: self._handle_agent_completed,
            PWIEventType.REVIEW_APPROVED: self._handle_review_approved,
            PWIEventType.REVIEW_REJECTED: self._handle_review_rejected,
            PWIEventType.ARTIFACT_GENERATED: self._handle_artifact_generated,
            PWIEventType.USER_INPUT: self._handle_user_input,
        }

        handler = handlers.get(event.event_type)
        if handler:
            handler(event)

    def _handle_workflow_started(self, event: WorkflowStartedEvent) -> None:
        """Handle workflow started event."""
        # Use set_state which updates current_state and updated_at
        self.session.set_state(WorkflowState.DATA_ANALYST_RUNNING)
        self._save()

    def _handle_workflow_completed(self, event: WorkflowCompletedEvent) -> None:
        """Handle workflow completed event."""
        self.session.set_state(WorkflowState.COMPLETED)
        self._save()

    def _handle_workflow_failed(self, event: WorkflowFailedEvent) -> None:
        """Handle workflow failed event."""
        self.session.set_state(WorkflowState.FAILED)
        self.session.error_message = event.error_message
        self._save()

    def _handle_workflow_paused(self, event: WorkflowPausedEvent) -> None:
        """Handle workflow paused event."""
        self.session.set_state(WorkflowState.PAUSED)
        self._save()

    def _handle_agent_completed(self, event: AgentCompletedEvent) -> None:
        """Handle agent completed event."""
        # Record token usage
        if event.total_tokens > 0:
            self.session.add_token_usage(
                agent=event.agent_name,
                prompt_tokens=event.prompt_tokens,
                completion_tokens=event.completion_tokens,
                model=event.data.get("model", ""),
            )
            self._save()

    def _handle_review_approved(self, event: ReviewApprovedEvent) -> None:
        """Handle review approved event."""
        self.session.add_review(
            agent=event.agent_name,
            approved=True,
            feedback=event.feedback,
        )
        self._save()

    def _handle_review_rejected(self, event: ReviewRejectedEvent) -> None:
        """Handle review rejected event."""
        self.session.add_review(
            agent=event.agent_name,
            approved=False,
            feedback=event.feedback,
        )
        self._save()

    def _handle_artifact_generated(self, event: ArtifactGeneratedEvent) -> None:
        """Handle artifact generated event."""
        # Artifact content is typically added separately
        logger.debug(f"Artifact generated: {event.artifact_type}")

    def _handle_user_input(self, event: UserInputEvent) -> None:
        """Handle user input event."""
        if event.input_type == "business_request":
            self.session.request_content = event.content
            self._save()

    def _save(self) -> None:
        """Save session state."""
        self.session_manager.save(self.session)

    # Event emission methods

    def emit_workflow_started(self) -> None:
        """Emit workflow started event."""
        event = WorkflowStartedEvent(session_id=self.session.session_id)
        self.event_stream.append(event)

    def emit_workflow_completed(
        self,
        total_tokens: int = 0,
        total_cost_usd: float = 0.0,
    ) -> None:
        """Emit workflow completed event."""
        event = WorkflowCompletedEvent(
            session_id=self.session.session_id,
            total_tokens=total_tokens,
            total_cost_usd=total_cost_usd,
            artifact_count=len(self.session.artifacts),
        )
        self.event_stream.append(event)

    def emit_workflow_failed(
        self,
        error_message: str,
        failed_at_agent: str | None = None,
    ) -> None:
        """Emit workflow failed event."""
        event = WorkflowFailedEvent(
            session_id=self.session.session_id,
            error_message=error_message,
            failed_at_agent=failed_at_agent,
        )
        self.event_stream.append(event)

    def emit_workflow_paused(
        self,
        pause_reason: str = "review_pending",
        resume_from: str | None = None,
    ) -> None:
        """Emit workflow paused event."""
        event = WorkflowPausedEvent(
            session_id=self.session.session_id,
            pause_reason=pause_reason,
            resume_from=resume_from,
        )
        self.event_stream.append(event)

    def emit_agent_completed(
        self,
        agent_name: str,
        artifact_type: str,
        artifact_format: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        tool_calls_count: int = 0,
        model: str = "",
    ) -> None:
        """Emit agent completed event."""
        event = AgentCompletedEvent(
            session_id=self.session.session_id,
            agent_name=agent_name,
            artifact_type=artifact_type,
            artifact_format=artifact_format,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            tool_calls_count=tool_calls_count,
            data={"model": model},
        )
        self.event_stream.append(event)

    def emit_artifact_generated(
        self,
        agent_name: str,
        artifact_type: str,
        artifact_format: str,
        content: str,
    ) -> None:
        """Emit artifact generated event and add to session."""
        # Add artifact to session
        self.session.add_artifact(
            artifact_type=artifact_type,
            content=content,
            format=artifact_format,
            agent=agent_name,
        )
        self._save()

        # Emit event
        event = ArtifactGeneratedEvent(
            session_id=self.session.session_id,
            agent_name=agent_name,
            artifact_type=artifact_type,
            artifact_format=artifact_format,
            size_bytes=len(content.encode("utf-8")),
        )
        self.event_stream.append(event)

    def emit_artifact_saved(
        self,
        artifact_type: str,
        file_path: str,
    ) -> None:
        """Emit artifact saved event."""
        event = ArtifactSavedEvent(
            session_id=self.session.session_id,
            artifact_type=artifact_type,
            file_path=file_path,
        )
        self.event_stream.append(event)

    def emit_review_approved(
        self,
        agent_name: str,
        feedback: str = "",
        was_edited: bool = False,
    ) -> None:
        """Emit review approved event."""
        event = ReviewApprovedEvent(
            session_id=self.session.session_id,
            agent_name=agent_name,
            feedback=feedback,
            was_edited=was_edited,
        )
        self.event_stream.append(event)

    def emit_review_rejected(
        self,
        agent_name: str,
        feedback: str = "",
        rejection_reason: str = "",
    ) -> None:
        """Emit review rejected event."""
        event = ReviewRejectedEvent(
            session_id=self.session.session_id,
            agent_name=agent_name,
            feedback=feedback,
            rejection_reason=rejection_reason,
        )
        self.event_stream.append(event)

    def emit_user_input(
        self,
        content: str,
        input_type: str = "business_request",
    ) -> None:
        """Emit user input event."""
        event = UserInputEvent(
            session_id=self.session.session_id,
            input_type=input_type,
            content=content,
        )
        self.event_stream.append(event)

    def get_event_history(self) -> list[dict[str, Any]]:
        """Get event history for serialization.

        Returns:
            List of event dictionaries.
        """
        return self.event_stream.to_dict()

    def get_completed_agents(self) -> list[str]:
        """Get list of agents that have completed.

        Returns:
            List of completed agent names.
        """
        completed_events = self.event_stream.get_events(
            event_type=PWIEventType.AGENT_COMPLETED
        )
        return [e.agent_name for e in completed_events if e.agent_name]

    def get_pending_review_agent(self) -> str | None:
        """Get agent name waiting for review.

        Returns:
            Agent name or None if no review pending.
        """
        # Find most recent pause event
        pause_event = self.event_stream.get_last_event(PWIEventType.WORKFLOW_PAUSED)
        if pause_event and isinstance(pause_event, WorkflowPausedEvent):
            return pause_event.resume_from
        return None
