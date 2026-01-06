"""Pytest fixtures for PWI tests.

This module provides shared fixtures for unit, integration,
and contract tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pwi.config.schema import (
    AgentConfig,
    LLMConfig,
    LoggingConfig,
    ProjectConfig,
    PWIConfig,
    ReviewConfig,
)
from pwi.llm.client import CompletionResponse, LLMClient
from pwi.workflow.session import Session, SessionManager
from pwi.workflow.states import WorkflowState


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for tests."""
    return tmp_path


@pytest.fixture
def temp_session_dir(tmp_path: Path) -> Path:
    """Provide a temporary session directory."""
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()
    return session_dir


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Provide a temporary output directory."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def mock_config(temp_session_dir: Path, temp_output_dir: Path) -> PWIConfig:
    """Provide a test configuration."""
    return PWIConfig(
        version="1.0",
        project=ProjectConfig(
            name="test-project",
            type="data_engineering",
            output_dir=temp_output_dir,
            session_dir=temp_session_dir,
        ),
        llm=LLMConfig(
            provider="openrouter",
            api_key="test-api-key",
            base_url="https://test.api/v1",
            default_model="test/model",
            models={
                "fast": "test/fast-model",
                "balanced": "test/balanced-model",
                "powerful": "test/powerful-model",
            },
        ),
        agents={
            "data_analyst": AgentConfig(model="balanced", temperature=0.7),
            "data_architect": AgentConfig(model="powerful", temperature=0.5),
            "mapping_engineer": AgentConfig(model="balanced", temperature=0.3),
            "dq_engineer": AgentConfig(model="balanced", temperature=0.3),
            "story_writer": AgentConfig(model="balanced", temperature=0.8),
            "sync_agent": AgentConfig(model="fast", temperature=0.2),
        },
        review=ReviewConfig(default_mode="cli", timeout_minutes=60),
        logging=LoggingConfig(level="DEBUG", format="text"),
    )


@pytest.fixture
def mock_completion_response() -> CompletionResponse:
    """Provide a mock LLM completion response."""
    return CompletionResponse(
        content="This is a test response from the LLM.",
        model="test/model",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        finish_reason="stop",
    )


@pytest.fixture
def mock_llm_client(mock_completion_response: CompletionResponse) -> MagicMock:
    """Provide a mock LLM client."""
    client = MagicMock(spec=LLMClient)
    client.complete = MagicMock(return_value=mock_completion_response)
    client.acomplete = AsyncMock(return_value=mock_completion_response)
    client.acomplete_with_retry = AsyncMock(return_value=mock_completion_response)
    client.close = MagicMock()
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def session_manager(temp_session_dir: Path) -> SessionManager:
    """Provide a session manager with temporary storage."""
    return SessionManager(temp_session_dir)


@pytest.fixture
def sample_request() -> str:
    """Provide a sample business request."""
    return """# Customer Analytics Pipeline

## Business Context

We need to build a customer analytics pipeline that integrates data from
multiple sources to create a unified view of customer behavior.

## Data Sources

1. **Salesforce CRM**
   - Customer accounts and contacts
   - Opportunity and deal data

2. **Web Analytics**
   - Page views and sessions
   - User journeys

## Requirements

- Daily batch processing
- Data quality checks
- SCD Type 2 for customer dimension
"""


@pytest.fixture
def sample_session(session_manager: SessionManager, sample_request: str) -> Session:
    """Provide a sample session."""
    return session_manager.create(
        project_name="test-project",
        request_path="/test/request.md",
        request_content=sample_request,
    )


@pytest.fixture
def sample_session_with_artifacts(sample_session: Session) -> Session:
    """Provide a session with some artifacts already created."""
    sample_session.add_artifact(
        artifact_type="drd",
        content="# Data Requirements Document\n\nTest DRD content...",
        format="markdown",
        agent="data_analyst",
    )
    sample_session.add_artifact(
        artifact_type="pad",
        content="# Pipeline Architecture Document\n\nTest PAD content...",
        format="markdown",
        agent="data_architect",
    )
    return sample_session


@pytest.fixture
def session_at_review(
    session_manager: SessionManager,
    sample_request: str,
) -> Session:
    """Provide a session in a review state."""
    session = session_manager.create(
        project_name="test-project",
        request_path="/test/request.md",
        request_content=sample_request,
    )
    session.set_state(WorkflowState.DATA_ANALYST_REVIEW)
    session.add_artifact(
        artifact_type="drd",
        content="# Data Requirements Document\n\nTest content...",
        format="markdown",
        agent="data_analyst",
    )
    session_manager.save(session)
    return session


@pytest.fixture
def mock_agent_config() -> AgentConfig:
    """Provide a mock agent configuration."""
    return AgentConfig(
        model="test/model",
        temperature=0.7,
        max_tokens=4096,
    )


# Helpers for test assertions


def assert_session_state(session: Session, expected_state: WorkflowState) -> None:
    """Assert that a session is in the expected state."""
    actual = session.get_state()
    assert actual == expected_state, f"Expected {expected_state}, got {actual}"


def assert_has_artifact(session: Session, artifact_type: str) -> None:
    """Assert that a session has a specific artifact."""
    assert artifact_type in session.artifacts, f"Missing artifact: {artifact_type}"


def assert_artifact_content_contains(
    session: Session,
    artifact_type: str,
    expected_content: str,
) -> None:
    """Assert that an artifact contains expected content."""
    assert artifact_type in session.artifacts
    content = session.artifacts[artifact_type].content
    assert expected_content in content, f"Expected '{expected_content}' in artifact"
