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


def _generate_session_id() -> str:
    """Generate timestamp-based session ID.

    Format: YYYY-MM-DD_HH-MM-SS_xxxx
    Example: 2024-01-15_10-30-45_a7b3

    Benefits:
    - Human readable ISO-like date/time
    - Chronological sorting in filesystem
    - 4-char suffix prevents collisions
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    suffix = str(uuid.uuid4())[:4]
    return f"{timestamp}_{suffix}"


class SessionArtifact(BaseModel):
    """An artifact produced by an agent.

    Artifacts can be stored either:
    - Inline (legacy): content stored directly in the JSON
    - File-based (new): content stored in separate files within session directory
    """

    type: str  # drd, pad, dmd, dqs, stories, package
    content: str = ""  # Legacy inline content (empty when file-based)
    format: str  # markdown, csv, yaml, json
    created_at: datetime = Field(default_factory=datetime.utcnow)
    agent: str
    version: int = 1
    filename: str | None = None  # File name when stored separately (e.g., "drd.md")

    @property
    def is_file_based(self) -> bool:
        """Check if artifact is stored in a separate file."""
        return self.filename is not None

    def get_file_extension(self) -> str:
        """Get file extension for this artifact format."""
        extensions = {
            "markdown": ".md",
            "csv": ".csv",
            "yaml": ".yaml",
            "json": ".json",
        }
        return extensions.get(self.format, ".txt")


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

    session_id: str = Field(default_factory=_generate_session_id)
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
        file_based: bool = True,
    ) -> SessionArtifact:
        """Add or update an artifact.

        If an artifact of this type already exists, increment the version.

        Args:
            artifact_type: Type of artifact (drd, pad, dmd, etc.).
            content: Artifact content (stored inline if not file_based).
            format: Format of the artifact (markdown, csv, yaml, json).
            agent: Name of the agent that produced the artifact.
            file_based: If True, content is stored in a separate file.

        Returns:
            The created SessionArtifact.
        """
        version = 1
        if artifact_type in self.artifacts:
            version = self.artifacts[artifact_type].version + 1

        # Determine filename for file-based storage
        extensions = {
            "markdown": ".md",
            "csv": ".csv",
            "yaml": ".yaml",
            "json": ".json",
        }
        ext = extensions.get(format, ".txt")
        filename = f"{artifact_type}{ext}" if file_based else None

        artifact = SessionArtifact(
            type=artifact_type,
            content="" if file_based else content,  # Empty if file-based
            format=format,
            agent=agent,
            version=version,
            filename=filename,
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

    def get_session_dir(self, base_dir: Path) -> Path:
        """Get session directory path for file-based storage.

        Args:
            base_dir: Base sessions directory.

        Returns:
            Path to this session's directory.
        """
        return base_dir / self.session_id

    def get_artifact_path(self, base_dir: Path, artifact_type: str) -> Path | None:
        """Get file path for an artifact.

        Args:
            base_dir: Base sessions directory.
            artifact_type: Type of artifact (drd, pad, etc.).

        Returns:
            Path to artifact file, or None if artifact doesn't exist.
        """
        if artifact_type not in self.artifacts:
            return None
        artifact = self.artifacts[artifact_type]
        if artifact.filename:
            return self.get_session_dir(base_dir) / artifact.filename
        return None

    def read_artifact_content(self, base_dir: Path, artifact_type: str) -> str | None:
        """Read artifact content, supporting both inline and file-based storage.

        Args:
            base_dir: Base sessions directory.
            artifact_type: Type of artifact to read.

        Returns:
            Artifact content string, or None if not found.
        """
        artifact = self.artifacts.get(artifact_type)
        if not artifact:
            return None

        # If file-based, read from file
        if artifact.is_file_based:
            path = self.get_artifact_path(base_dir, artifact_type)
            if path and path.exists():
                return path.read_text(encoding="utf-8")
            return None

        # Otherwise return inline content
        return artifact.content if artifact.content else None

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

    Sessions can be stored in two formats:
    - Legacy: Single JSON file per session (<session_id>.json)
    - File-based: Directory per session with session.json + artifact files

    The manager automatically detects which format a session uses.
    New sessions use the file-based format.
    """

    def __init__(self, session_dir: Path, use_file_based: bool = True) -> None:
        """Initialize the session manager.

        Args:
            session_dir: Directory where sessions are stored.
            use_file_based: If True, new sessions use directory-based storage.
        """
        self.session_dir = session_dir
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.use_file_based = use_file_based

    def _session_dir_path(self, session_id: str) -> Path:
        """Get session directory path (for file-based storage)."""
        return self.session_dir / session_id

    def _session_json_path(self, session_id: str) -> Path:
        """Get session.json path within session directory (file-based)."""
        return self._session_dir_path(session_id) / "session.json"

    def _legacy_session_path(self, session_id: str) -> Path:
        """Get legacy session file path (<session_id>.json)."""
        return self.session_dir / f"{session_id}.json"

    def _is_file_based_session(self, session_id: str) -> bool:
        """Check if session uses file-based storage."""
        return self._session_dir_path(session_id).is_dir()

    def _session_path(self, session_id: str) -> Path:
        """Get the path to a session file (auto-detect format)."""
        # Check file-based first (directory exists)
        if self._is_file_based_session(session_id):
            return self._session_json_path(session_id)
        # Fall back to legacy
        return self._legacy_session_path(session_id)

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

        # Create session directory for file-based storage
        if self.use_file_based:
            session_dir = self._session_dir_path(session.session_id)
            session_dir.mkdir(parents=True, exist_ok=True)

        self.save(session)
        return session

    def save(self, session: Session) -> None:
        """Save a session to disk.

        Args:
            session: Session to save.
        """
        # Determine storage format
        if self._is_file_based_session(session.session_id) or (
            self.use_file_based and not self._legacy_session_path(session.session_id).exists()
        ):
            # File-based: ensure directory exists
            session_dir = self._session_dir_path(session.session_id)
            session_dir.mkdir(parents=True, exist_ok=True)
            path = self._session_json_path(session.session_id)
        else:
            # Legacy: single JSON file
            path = self._legacy_session_path(session.session_id)

        with open(path, "w", encoding="utf-8") as f:
            f.write(session.model_dump_json(indent=2))

    def save_artifact(
        self,
        session: Session,
        artifact_type: str,
        content: str,
    ) -> Path:
        """Save artifact content to a separate file.

        Args:
            session: Session containing the artifact.
            artifact_type: Type of artifact (drd, pad, etc.).
            content: Artifact content to save.

        Returns:
            Path to the saved artifact file.

        Raises:
            ValueError: If artifact not found in session.
        """
        artifact = session.artifacts.get(artifact_type)
        if not artifact:
            raise ValueError(f"Artifact '{artifact_type}' not found in session")

        if not artifact.filename:
            raise ValueError(f"Artifact '{artifact_type}' has no filename set")

        # Ensure session directory exists
        session_dir = self._session_dir_path(session.session_id)
        session_dir.mkdir(parents=True, exist_ok=True)

        # Write artifact content to file
        artifact_path = session_dir / artifact.filename
        artifact_path.write_text(content, encoding="utf-8")

        return artifact_path

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

    def load_artifact_content(
        self,
        session_id: str,
        artifact_type: str,
    ) -> str | None:
        """Load artifact content from file.

        Args:
            session_id: ID of the session.
            artifact_type: Type of artifact to load.

        Returns:
            Artifact content, or None if not found.
        """
        session = self.load(session_id)
        return session.read_artifact_content(self.session_dir, artifact_type)

    def exists(self, session_id: str) -> bool:
        """Check if a session exists.

        Args:
            session_id: ID of the session to check.

        Returns:
            True if the session exists, False otherwise.
        """
        # Check both file-based and legacy formats
        return (
            self._session_json_path(session_id).exists()
            or self._legacy_session_path(session_id).exists()
        )

    def delete(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: ID of the session to delete.

        Returns:
            True if deleted, False if didn't exist.
        """
        import shutil

        # Try file-based first
        session_dir = self._session_dir_path(session_id)
        if session_dir.is_dir():
            shutil.rmtree(session_dir)
            return True

        # Try legacy
        legacy_path = self._legacy_session_path(session_id)
        if legacy_path.exists():
            legacy_path.unlink()
            return True

        return False

    def list_sessions(self) -> list[Session]:
        """List all sessions.

        Returns:
            List of all sessions, sorted by creation date (newest first).
        """
        sessions = []
        seen_ids: set[str] = set()

        # Find file-based sessions (directories with session.json)
        for path in self.session_dir.iterdir():
            if path.is_dir() and (path / "session.json").exists():
                try:
                    session = self.load(path.name)
                    sessions.append(session)
                    seen_ids.add(path.name)
                except Exception:
                    continue

        # Find legacy sessions (*.json files)
        for path in self.session_dir.glob("*.json"):
            if path.stem not in seen_ids:
                try:
                    session = self.load(path.stem)
                    sessions.append(session)
                except Exception:
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
