"""Unit tests for PWI session management."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from pwi.workflow.session import (
    Session,
    SessionArtifact,
    SessionManager,
    SessionReview,
    TokenUsage,
)
from pwi.workflow.states import WorkflowState


class TestSession:
    """Tests for Session model."""

    def test_create_session(self) -> None:
        """Test creating a new session."""
        session = Session(
            project_name="test-project",
            request_path="/test/request.md",
            request_content="Test content",
        )

        assert session.session_id is not None
        assert len(session.session_id) == 8
        assert session.project_name == "test-project"
        assert session.current_state == WorkflowState.INITIALIZED.value
        assert session.artifacts == {}
        assert session.reviews == []

    def test_get_state(self) -> None:
        """Test getting state as enum."""
        session = Session()
        session.current_state = WorkflowState.DATA_ANALYST_RUNNING.value

        state = session.get_state()

        assert state == WorkflowState.DATA_ANALYST_RUNNING

    def test_set_state(self) -> None:
        """Test setting state updates timestamp."""
        session = Session()
        original_time = session.updated_at

        session.set_state(WorkflowState.DATA_ARCHITECT_REVIEW)

        assert session.current_state == WorkflowState.DATA_ARCHITECT_REVIEW.value
        assert session.updated_at >= original_time

    def test_add_artifact(self) -> None:
        """Test adding an artifact."""
        session = Session()

        artifact = session.add_artifact(
            artifact_type="drd",
            content="# DRD Content",
            format="markdown",
            agent="data_analyst",
        )

        assert "drd" in session.artifacts
        assert artifact.type == "drd"
        assert artifact.content == "# DRD Content"
        assert artifact.format == "markdown"
        assert artifact.agent == "data_analyst"
        assert artifact.version == 1

    def test_add_artifact_increments_version(self) -> None:
        """Test that re-adding artifact increments version."""
        session = Session()

        session.add_artifact("drd", "Content v1", "markdown", "data_analyst")
        artifact = session.add_artifact("drd", "Content v2", "markdown", "data_analyst")

        assert artifact.version == 2
        assert session.artifacts["drd"].content == "Content v2"

    def test_add_review(self) -> None:
        """Test recording a review decision."""
        session = Session()

        review = session.add_review(
            agent="data_analyst",
            approved=True,
            feedback="Looks good!",
        )

        assert len(session.reviews) == 1
        assert review.agent == "data_analyst"
        assert review.approved is True
        assert review.feedback == "Looks good!"

    def test_add_token_usage(self) -> None:
        """Test recording token usage."""
        session = Session()

        usage = session.add_token_usage(
            agent="data_analyst",
            prompt_tokens=100,
            completion_tokens=50,
            model="test/model",
        )

        assert len(session.token_usage) == 1
        assert usage.agent == "data_analyst"
        assert usage.total_tokens == 150

    def test_get_total_tokens(self) -> None:
        """Test calculating total token usage."""
        session = Session()
        session.add_token_usage("agent1", 100, 50, "model1")
        session.add_token_usage("agent2", 200, 100, "model2")

        total = session.get_total_tokens()

        assert total == 450

    def test_get_artifact(self) -> None:
        """Test retrieving an artifact."""
        session = Session()
        session.add_artifact("drd", "Content", "markdown", "analyst")

        artifact = session.get_artifact("drd")
        missing = session.get_artifact("nonexistent")

        assert artifact is not None
        assert artifact.content == "Content"
        assert missing is None

    def test_is_complete(self) -> None:
        """Test checking if session is complete."""
        session = Session()
        assert not session.is_complete()

        session.current_state = WorkflowState.COMPLETED.value
        assert session.is_complete()

    def test_is_failed(self) -> None:
        """Test checking if session is failed."""
        session = Session()
        assert not session.is_failed()

        session.current_state = WorkflowState.FAILED.value
        assert session.is_failed()

    def test_is_terminal(self) -> None:
        """Test checking if session is in terminal state."""
        session = Session()
        assert not session.is_terminal()

        session.current_state = WorkflowState.COMPLETED.value
        assert session.is_terminal()

        session.current_state = WorkflowState.FAILED.value
        assert session.is_terminal()


class TestSessionManager:
    """Tests for SessionManager."""

    def test_create_session(self, temp_session_dir: Path) -> None:
        """Test creating a session through manager."""
        manager = SessionManager(temp_session_dir)

        session = manager.create(
            project_name="test",
            request_path="/test.md",
            request_content="Content",
        )

        assert session.session_id is not None
        assert manager.exists(session.session_id)

    def test_save_and_load(self, temp_session_dir: Path) -> None:
        """Test saving and loading a session."""
        manager = SessionManager(temp_session_dir)
        session = manager.create("test", "/test.md", "Content")

        # Modify session
        session.add_artifact("drd", "DRD content", "markdown", "analyst")
        manager.save(session)

        # Load and verify
        loaded = manager.load(session.session_id)
        assert loaded.session_id == session.session_id
        assert "drd" in loaded.artifacts

    def test_exists(self, temp_session_dir: Path) -> None:
        """Test checking session existence."""
        manager = SessionManager(temp_session_dir)
        session = manager.create("test", "/test.md", "Content")

        assert manager.exists(session.session_id)
        assert not manager.exists("nonexistent")

    def test_delete(self, temp_session_dir: Path) -> None:
        """Test deleting a session."""
        manager = SessionManager(temp_session_dir)
        session = manager.create("test", "/test.md", "Content")

        result = manager.delete(session.session_id)

        assert result is True
        assert not manager.exists(session.session_id)

    def test_delete_nonexistent(self, temp_session_dir: Path) -> None:
        """Test deleting a nonexistent session."""
        manager = SessionManager(temp_session_dir)

        result = manager.delete("nonexistent")

        assert result is False

    def test_list_sessions(self, temp_session_dir: Path) -> None:
        """Test listing all sessions."""
        manager = SessionManager(temp_session_dir)
        manager.create("project1", "/test1.md", "Content 1")
        manager.create("project2", "/test2.md", "Content 2")
        manager.create("project3", "/test3.md", "Content 3")

        sessions = manager.list_sessions()

        assert len(sessions) == 3

    def test_list_sessions_sorted_by_date(self, temp_session_dir: Path) -> None:
        """Test that sessions are sorted by creation date (newest first)."""
        manager = SessionManager(temp_session_dir)
        s1 = manager.create("project1", "/test1.md", "Content 1")
        s2 = manager.create("project2", "/test2.md", "Content 2")
        s3 = manager.create("project3", "/test3.md", "Content 3")

        sessions = manager.list_sessions()

        # Newest should be first
        assert sessions[0].session_id == s3.session_id

    def test_get_recent_sessions(self, temp_session_dir: Path) -> None:
        """Test getting recent sessions with limit."""
        manager = SessionManager(temp_session_dir)
        for i in range(5):
            manager.create(f"project{i}", f"/test{i}.md", f"Content {i}")

        recent = manager.get_recent_sessions(limit=3)

        assert len(recent) == 3

    def test_load_nonexistent_raises(self, temp_session_dir: Path) -> None:
        """Test that loading nonexistent session raises error."""
        manager = SessionManager(temp_session_dir)

        with pytest.raises(FileNotFoundError):
            manager.load("nonexistent")


class TestSessionArtifact:
    """Tests for SessionArtifact model."""

    def test_create_artifact(self) -> None:
        """Test creating an artifact."""
        artifact = SessionArtifact(
            type="drd",
            content="# DRD",
            format="markdown",
            agent="data_analyst",
        )

        assert artifact.type == "drd"
        assert artifact.version == 1
        assert artifact.created_at is not None


class TestSessionReview:
    """Tests for SessionReview model."""

    def test_create_review(self) -> None:
        """Test creating a review."""
        review = SessionReview(
            agent="data_analyst",
            approved=True,
            feedback="Great work!",
        )

        assert review.agent == "data_analyst"
        assert review.approved is True
        assert review.reviewed_at is not None


class TestTokenUsage:
    """Tests for TokenUsage model."""

    def test_create_usage(self) -> None:
        """Test creating token usage record."""
        usage = TokenUsage(
            agent="data_analyst",
            prompt_tokens=100,
            completion_tokens=50,
            model="test/model",
        )

        assert usage.total_tokens == 0  # Not auto-calculated
        assert usage.prompt_tokens == 100
