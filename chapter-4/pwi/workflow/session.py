"""Session management for Planning with Intent.

This module provides session persistence and management,
allowing workflows to be paused, resumed, and tracked.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from pwi.workflow.states import WorkflowState


class SessionArtifact(BaseModel):
    """An artifact produced by an agent."""

    type: str  # drd, pad, dmd, dqs, stories, package
    content: str
    format: str  # markdown, csv, yaml, json
    created_at: datetime = Field(default_factory=datetime.utcnow)
    agent: str
    version: int = 1


class SessionReview(BaseModel):
    """A review decision for an artifact."""

    agent: str
    approved: bool
    feedback: str | None = None
    reviewed_at: datetime = Field(default_factory=datetime.utcnow)


class TokenUsage(BaseModel):
    """Token usage tracking for an agent execution."""

    agent: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    cost_usd: str = "0.00"  # Stored as string for JSON serialization


class Session(BaseModel):
    """A PWI workflow session.

    Sessions track the state of a workflow execution, including:
    - Current state in the state machine
    - Generated artifacts
    - Review decisions
    - Token usage for cost tracking
    """

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    project_name: str = ""
    request_path: str = ""
    request_content: str = ""
    current_state: str = WorkflowState.INITIALIZED.value
    artifacts: dict[str, SessionArtifact] = Field(default_factory=dict)
    reviews: list[SessionReview] = Field(default_factory=list)
    token_usage: list[TokenUsage] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None

    def get_state(self) -> WorkflowState:
        """Get the current state as a WorkflowState enum."""
        return WorkflowState(self.current_state)

    def set_state(self, state: WorkflowState) -> None:
        """Set the current state and update timestamp."""
        self.current_state = state.value
        self.updated_at = datetime.utcnow()

    def add_artifact(
        self,
        artifact_type: str,
        content: str,
        format: str,
        agent: str,
    ) -> SessionArtifact:
        """Add or update an artifact.

        If an artifact of this type already exists, increment the version.
        """
        version = 1
        if artifact_type in self.artifacts:
            version = self.artifacts[artifact_type].version + 1

        artifact = SessionArtifact(
            type=artifact_type,
            content=content,
            format=format,
            agent=agent,
            version=version,
        )
        self.artifacts[artifact_type] = artifact
        self.updated_at = datetime.utcnow()
        return artifact

    def add_review(
        self,
        agent: str,
        approved: bool,
        feedback: str | None = None,
    ) -> SessionReview:
        """Record a review decision."""
        review = SessionReview(
            agent=agent,
            approved=approved,
            feedback=feedback,
        )
        self.reviews.append(review)
        self.updated_at = datetime.utcnow()
        return review

    def add_token_usage(
        self,
        agent: str,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
    ) -> TokenUsage:
        """Record token usage for an agent."""
        from pwi.llm.models import calculate_cost

        cost = calculate_cost(model, prompt_tokens, completion_tokens)
        usage = TokenUsage(
            agent=agent,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model=model,
            cost_usd=str(cost),
        )
        self.token_usage.append(usage)
        return usage

    def get_total_tokens(self) -> int:
        """Get total tokens used across all agents."""
        return sum(u.total_tokens for u in self.token_usage)

    def get_total_cost(self) -> Decimal:
        """Get total cost in USD across all agents."""
        return sum(
            (Decimal(u.cost_usd) for u in self.token_usage),
            start=Decimal("0"),
        )

    def get_formatted_cost(self) -> str:
        """Get total cost formatted for display."""
        from pwi.llm.models import format_cost

        return format_cost(self.get_total_cost())

    def get_artifact(self, artifact_type: str) -> SessionArtifact | None:
        """Get an artifact by type."""
        return self.artifacts.get(artifact_type)

    def is_complete(self) -> bool:
        """Check if the session has completed successfully."""
        return self.current_state == WorkflowState.COMPLETED.value

    def is_failed(self) -> bool:
        """Check if the session has failed."""
        return self.current_state == WorkflowState.FAILED.value

    def is_terminal(self) -> bool:
        """Check if the session is in a terminal state."""
        return WorkflowState.is_terminal(self.get_state())


class SessionManager:
    """Manages session persistence to the filesystem.

    Sessions are stored as JSON files in the session directory,
    with the filename being the session ID.
    """

    def __init__(self, session_dir: Path) -> None:
        """Initialize the session manager.

        Args:
            session_dir: Directory where sessions are stored.
        """
        self.session_dir = session_dir
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        """Get the path to a session file."""
        return self.session_dir / f"{session_id}.json"

    def create(
        self,
        project_name: str,
        request_path: str,
        request_content: str,
    ) -> Session:
        """Create a new session.

        Args:
            project_name: Name of the project.
            request_path: Path to the request file.
            request_content: Content of the request.

        Returns:
            New Session object.
        """
        session = Session(
            project_name=project_name,
            request_path=request_path,
            request_content=request_content,
        )
        self.save(session)
        return session

    def save(self, session: Session) -> None:
        """Save a session to disk.

        Args:
            session: Session to save.
        """
        path = self._session_path(session.session_id)
        with open(path, "w", encoding="utf-8") as f:
            f.write(session.model_dump_json(indent=2))

    def load(self, session_id: str) -> Session:
        """Load a session from disk.

        Args:
            session_id: ID of the session to load.

        Returns:
            Loaded Session object.

        Raises:
            FileNotFoundError: If the session doesn't exist.
        """
        path = self._session_path(session_id)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return Session.model_validate(data)

    def exists(self, session_id: str) -> bool:
        """Check if a session exists.

        Args:
            session_id: ID of the session to check.

        Returns:
            True if the session exists, False otherwise.
        """
        return self._session_path(session_id).exists()

    def delete(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: ID of the session to delete.

        Returns:
            True if deleted, False if didn't exist.
        """
        path = self._session_path(session_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_sessions(self) -> list[Session]:
        """List all sessions.

        Returns:
            List of all sessions, sorted by creation date (newest first).
        """
        sessions = []
        for path in self.session_dir.glob("*.json"):
            try:
                session = self.load(path.stem)
                sessions.append(session)
            except Exception:
                # Skip invalid session files
                continue

        # Sort by creation date, newest first
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return sessions

    def get_recent_sessions(self, limit: int = 10) -> list[Session]:
        """Get the most recent sessions.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            List of recent sessions.
        """
        return self.list_sessions()[:limit]
