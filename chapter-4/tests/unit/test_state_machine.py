"""Unit tests for the PWI workflow state machine."""

from __future__ import annotations

import pytest

from pwi.workflow.session import Session, SessionManager
from pwi.workflow.state_machine import PWIWorkflow
from pwi.workflow.states import (
    AGENT_ORDER,
    AGENT_RUNNING_STATES,
    WorkflowState,
    get_next_agent,
)


class TestWorkflowState:
    """Tests for WorkflowState enum."""

    def test_is_terminal_completed(self) -> None:
        """Test that COMPLETED is a terminal state."""
        assert WorkflowState.is_terminal(WorkflowState.COMPLETED)

    def test_is_terminal_failed(self) -> None:
        """Test that FAILED is a terminal state."""
        assert WorkflowState.is_terminal(WorkflowState.FAILED)

    def test_is_terminal_cancelled(self) -> None:
        """Test that CANCELLED is a terminal state."""
        assert WorkflowState.is_terminal(WorkflowState.CANCELLED)

    def test_is_not_terminal_running(self) -> None:
        """Test that running states are not terminal."""
        assert not WorkflowState.is_terminal(WorkflowState.DATA_ANALYST_RUNNING)
        assert not WorkflowState.is_terminal(WorkflowState.MAPPING_ENGINEER_RUNNING)

    def test_is_running(self) -> None:
        """Test is_running detection."""
        assert WorkflowState.is_running(WorkflowState.DATA_ANALYST_RUNNING)
        assert WorkflowState.is_running(WorkflowState.DATA_ARCHITECT_RUNNING)
        assert not WorkflowState.is_running(WorkflowState.DATA_ANALYST_REVIEW)

    def test_is_review(self) -> None:
        """Test is_review detection."""
        assert WorkflowState.is_review(WorkflowState.DATA_ANALYST_REVIEW)
        assert WorkflowState.is_review(WorkflowState.MAPPING_ENGINEER_REVIEW)
        assert not WorkflowState.is_review(WorkflowState.DATA_ANALYST_RUNNING)

    def test_get_agent_name_running(self) -> None:
        """Test extracting agent name from running state."""
        assert WorkflowState.get_agent_name(WorkflowState.DATA_ANALYST_RUNNING) == "data_analyst"
        assert WorkflowState.get_agent_name(WorkflowState.MAPPING_ENGINEER_RUNNING) == "mapping_engineer"

    def test_get_agent_name_review(self) -> None:
        """Test extracting agent name from review state."""
        assert WorkflowState.get_agent_name(WorkflowState.DATA_ANALYST_REVIEW) == "data_analyst"
        assert WorkflowState.get_agent_name(WorkflowState.DQ_ENGINEER_REVIEW) == "dq_engineer"

    def test_get_agent_name_terminal(self) -> None:
        """Test that terminal states return None."""
        assert WorkflowState.get_agent_name(WorkflowState.COMPLETED) is None
        assert WorkflowState.get_agent_name(WorkflowState.FAILED) is None


class TestGetNextAgent:
    """Tests for get_next_agent function."""

    def test_first_to_second(self) -> None:
        """Test transition from first to second agent."""
        assert get_next_agent("data_analyst") == "data_architect"

    def test_middle_agents(self) -> None:
        """Test transitions between middle agents."""
        assert get_next_agent("data_architect") == "mapping_engineer"
        assert get_next_agent("mapping_engineer") == "dq_engineer"
        assert get_next_agent("dq_engineer") == "story_writer"

    def test_last_agent_returns_none(self) -> None:
        """Test that last agent has no next."""
        assert get_next_agent("sync_agent") is None

    def test_invalid_agent_returns_none(self) -> None:
        """Test that invalid agent name returns None."""
        assert get_next_agent("invalid_agent") is None


class TestPWIWorkflow:
    """Tests for PWIWorkflow state machine."""

    def test_initial_state(self, sample_session: Session) -> None:
        """Test workflow starts in INITIALIZED state."""
        workflow = PWIWorkflow(sample_session)
        assert workflow.state == WorkflowState.INITIALIZED.value

    def test_start_transition(self, sample_session: Session) -> None:
        """Test start trigger moves to DATA_ANALYST_RUNNING."""
        workflow = PWIWorkflow(sample_session)
        workflow.start()
        assert workflow.state == WorkflowState.DATA_ANALYST_RUNNING.value

    def test_analyst_complete_to_review(
        self,
        session_manager: SessionManager,
        sample_request: str,
    ) -> None:
        """Test analyst completion moves to review state."""
        session = session_manager.create("test", "/test.md", sample_request)
        session.current_state = WorkflowState.DATA_ANALYST_RUNNING.value
        workflow = PWIWorkflow(session)

        workflow.analyst_complete()

        assert workflow.state == WorkflowState.DATA_ANALYST_REVIEW.value

    def test_analyst_approved_to_architect(
        self,
        session_manager: SessionManager,
        sample_request: str,
    ) -> None:
        """Test analyst approval moves to architect running."""
        session = session_manager.create("test", "/test.md", sample_request)
        session.current_state = WorkflowState.DATA_ANALYST_REVIEW.value
        workflow = PWIWorkflow(session)

        workflow.analyst_approved()

        assert workflow.state == WorkflowState.DATA_ARCHITECT_RUNNING.value

    def test_analyst_rejected_reruns(
        self,
        session_manager: SessionManager,
        sample_request: str,
    ) -> None:
        """Test analyst rejection returns to running state."""
        session = session_manager.create("test", "/test.md", sample_request)
        session.current_state = WorkflowState.DATA_ANALYST_REVIEW.value
        workflow = PWIWorkflow(session)

        workflow.analyst_rejected()

        assert workflow.state == WorkflowState.DATA_ANALYST_RUNNING.value

    def test_full_workflow_happy_path(
        self,
        session_manager: SessionManager,
        sample_request: str,
    ) -> None:
        """Test complete workflow from start to finish."""
        session = session_manager.create("test", "/test.md", sample_request)
        workflow = PWIWorkflow(session)

        # Start
        workflow.start()
        assert workflow.state == WorkflowState.DATA_ANALYST_RUNNING.value

        # Data Analyst
        workflow.analyst_complete()
        workflow.analyst_approved()
        assert workflow.state == WorkflowState.DATA_ARCHITECT_RUNNING.value

        # Data Architect
        workflow.architect_complete()
        workflow.architect_approved()
        assert workflow.state == WorkflowState.MAPPING_ENGINEER_RUNNING.value

        # Mapping Engineer
        workflow.mapping_complete()
        workflow.mapping_approved()
        assert workflow.state == WorkflowState.DQ_ENGINEER_RUNNING.value

        # DQ Engineer
        workflow.dq_complete()
        workflow.dq_approved()
        assert workflow.state == WorkflowState.STORY_WRITER_RUNNING.value

        # Story Writer
        workflow.stories_complete()
        workflow.stories_approved()
        assert workflow.state == WorkflowState.SYNC_AGENT_RUNNING.value

        # Sync Agent
        workflow.sync_complete()
        assert workflow.state == WorkflowState.COMPLETED.value

    def test_fail_from_running_state(
        self,
        session_manager: SessionManager,
        sample_request: str,
    ) -> None:
        """Test fail trigger works from running state."""
        session = session_manager.create("test", "/test.md", sample_request)
        session.current_state = WorkflowState.DATA_ARCHITECT_RUNNING.value
        workflow = PWIWorkflow(session)

        workflow.fail()

        assert workflow.state == WorkflowState.FAILED.value

    def test_pause_from_review_state(
        self,
        session_manager: SessionManager,
        sample_request: str,
    ) -> None:
        """Test pause trigger works from review state."""
        session = session_manager.create("test", "/test.md", sample_request)
        session.current_state = WorkflowState.MAPPING_ENGINEER_REVIEW.value
        workflow = PWIWorkflow(session)

        workflow.pause()

        assert workflow.state == WorkflowState.PAUSED.value

    def test_get_current_agent(
        self,
        session_manager: SessionManager,
        sample_request: str,
    ) -> None:
        """Test getting current agent name."""
        session = session_manager.create("test", "/test.md", sample_request)
        session.current_state = WorkflowState.DQ_ENGINEER_RUNNING.value
        workflow = PWIWorkflow(session)

        assert workflow.get_current_agent() == "dq_engineer"

    def test_is_in_review(
        self,
        session_manager: SessionManager,
        sample_request: str,
    ) -> None:
        """Test is_in_review detection."""
        session = session_manager.create("test", "/test.md", sample_request)
        session.current_state = WorkflowState.STORY_WRITER_REVIEW.value
        workflow = PWIWorkflow(session)

        assert workflow.is_in_review()

    def test_agent_completed_helper(
        self,
        session_manager: SessionManager,
        sample_request: str,
    ) -> None:
        """Test agent_completed helper method."""
        session = session_manager.create("test", "/test.md", sample_request)
        session.current_state = WorkflowState.MAPPING_ENGINEER_RUNNING.value
        workflow = PWIWorkflow(session)

        workflow.agent_completed()

        assert workflow.state == WorkflowState.MAPPING_ENGINEER_REVIEW.value

    def test_review_approved_helper(
        self,
        session_manager: SessionManager,
        sample_request: str,
    ) -> None:
        """Test review_approved helper method."""
        session = session_manager.create("test", "/test.md", sample_request)
        session.current_state = WorkflowState.DQ_ENGINEER_REVIEW.value
        workflow = PWIWorkflow(session)

        workflow.review_approved()

        assert workflow.state == WorkflowState.STORY_WRITER_RUNNING.value

    def test_get_progress_initial(self, sample_session: Session) -> None:
        """Test progress at initial state."""
        workflow = PWIWorkflow(sample_session)
        completed, total = workflow.get_progress()

        assert completed == 0
        assert total == len(AGENT_ORDER)

    def test_get_progress_midway(
        self,
        session_manager: SessionManager,
        sample_request: str,
    ) -> None:
        """Test progress midway through workflow."""
        session = session_manager.create("test", "/test.md", sample_request)
        session.current_state = WorkflowState.MAPPING_ENGINEER_RUNNING.value
        workflow = PWIWorkflow(session)

        completed, total = workflow.get_progress()

        assert completed == 2  # data_analyst and data_architect done
        assert total == len(AGENT_ORDER)

    def test_get_progress_complete(
        self,
        session_manager: SessionManager,
        sample_request: str,
    ) -> None:
        """Test progress at completion."""
        session = session_manager.create("test", "/test.md", sample_request)
        session.current_state = WorkflowState.COMPLETED.value
        workflow = PWIWorkflow(session)

        completed, total = workflow.get_progress()

        assert completed == total
