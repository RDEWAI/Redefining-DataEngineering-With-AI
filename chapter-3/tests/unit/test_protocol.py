"""Unit tests for A2A protocol module.

Tests the QueryType enum, AgentMessage dataclass, and AgentStatus enum
to ensure proper message creation, serialization, and status tracking.
"""

import uuid
from datetime import datetime

import pytest

from src.a2a.protocol import AgentMessage, AgentStatus, QueryType


class TestQueryType:
    """Tests for QueryType enum."""

    def test_all_query_types_exist(self) -> None:
        """Verify all expected query types are defined."""
        assert QueryType.SEARCH.value == "search"
        assert QueryType.ANALYTICS.value == "analytics"
        assert QueryType.RECOMMENDATION.value == "recommendation"
        assert QueryType.MULTI_STEP.value == "multi_step"

    def test_query_type_string_representation(self) -> None:
        """Test human-readable string conversion."""
        assert str(QueryType.SEARCH) == "Search"
        assert str(QueryType.ANALYTICS) == "Analytics"
        assert str(QueryType.RECOMMENDATION) == "Recommendation"
        assert str(QueryType.MULTI_STEP) == "Multi Step"

    def test_query_type_from_value(self) -> None:
        """Test creating QueryType from string value."""
        assert QueryType("search") == QueryType.SEARCH
        assert QueryType("analytics") == QueryType.ANALYTICS
        assert QueryType("recommendation") == QueryType.RECOMMENDATION
        assert QueryType("multi_step") == QueryType.MULTI_STEP

    def test_invalid_query_type_raises(self) -> None:
        """Test that invalid query type raises ValueError."""
        with pytest.raises(ValueError):
            QueryType("invalid")


class TestAgentStatus:
    """Tests for AgentStatus enum."""

    def test_all_statuses_exist(self) -> None:
        """Verify all expected statuses are defined."""
        assert AgentStatus.PENDING.value == "pending"
        assert AgentStatus.IN_PROGRESS.value == "in_progress"
        assert AgentStatus.COMPLETED.value == "completed"
        assert AgentStatus.FAILED.value == "failed"
        assert AgentStatus.PARTIAL.value == "partial"

    def test_status_from_value(self) -> None:
        """Test creating AgentStatus from string value."""
        assert AgentStatus("pending") == AgentStatus.PENDING
        assert AgentStatus("completed") == AgentStatus.COMPLETED
        assert AgentStatus("failed") == AgentStatus.FAILED


class TestAgentMessage:
    """Tests for AgentMessage dataclass."""

    def test_create_message_factory(self) -> None:
        """Test creating message via factory method."""
        msg = AgentMessage.create(
            sender="orchestrator",
            recipient="search_agent",
            query_type=QueryType.SEARCH,
            content="Find Python books",
        )

        assert msg.sender == "orchestrator"
        assert msg.recipient == "search_agent"
        assert msg.query_type == QueryType.SEARCH
        assert msg.content == "Find Python books"
        assert msg.status == AgentStatus.PENDING
        assert msg.context == {}
        assert msg.parent_id is None
        assert msg.error is None

    def test_create_message_auto_generates_id(self) -> None:
        """Test that factory method generates unique IDs."""
        msg1 = AgentMessage.create(
            sender="a",
            recipient="b",
            query_type=QueryType.SEARCH,
            content="test",
        )
        msg2 = AgentMessage.create(
            sender="a",
            recipient="b",
            query_type=QueryType.SEARCH,
            content="test",
        )

        assert msg1.id != msg2.id
        # Verify it's a valid UUID format
        uuid.UUID(msg1.id)
        uuid.UUID(msg2.id)

    def test_create_message_with_context(self) -> None:
        """Test creating message with context dictionary."""
        context = {"user_id": "123", "session": "abc"}
        msg = AgentMessage.create(
            sender="orchestrator",
            recipient="search_agent",
            query_type=QueryType.SEARCH,
            content="test",
            context=context,
        )

        assert msg.context == context
        assert msg.context["user_id"] == "123"

    def test_create_message_with_parent_id(self) -> None:
        """Test creating message with parent ID for response chains."""
        parent_id = str(uuid.uuid4())
        msg = AgentMessage.create(
            sender="search_agent",
            recipient="orchestrator",
            query_type=QueryType.SEARCH,
            content="results",
            parent_id=parent_id,
        )

        assert msg.parent_id == parent_id

    def test_create_response_from_message(self) -> None:
        """Test creating a response to a message."""
        original = AgentMessage.create(
            sender="orchestrator",
            recipient="search_agent",
            query_type=QueryType.SEARCH,
            content="Find Python books",
            context={"key": "value"},
        )

        response = original.create_response(
            sender="search_agent",
            content=["book1", "book2"],
            status=AgentStatus.COMPLETED,
        )

        assert response.sender == "search_agent"
        assert response.recipient == "orchestrator"  # Swapped
        assert response.query_type == QueryType.SEARCH  # Preserved
        assert response.content == ["book1", "book2"]
        assert response.status == AgentStatus.COMPLETED
        assert response.parent_id == original.id
        assert response.context == {"key": "value"}  # Context copied
        assert response.error is None

    def test_create_error_response(self) -> None:
        """Test creating a failed response with error message."""
        original = AgentMessage.create(
            sender="orchestrator",
            recipient="search_agent",
            query_type=QueryType.SEARCH,
            content="test",
        )

        response = original.create_response(
            sender="search_agent",
            content=None,
            status=AgentStatus.FAILED,
            error="Database connection failed",
        )

        assert response.status == AgentStatus.FAILED
        assert response.error == "Database connection failed"
        assert response.content is None

    def test_to_dict_serialization(self) -> None:
        """Test converting message to dictionary."""
        msg = AgentMessage.create(
            sender="orchestrator",
            recipient="search_agent",
            query_type=QueryType.SEARCH,
            content="Find books",
            context={"test": True},
        )

        data = msg.to_dict()

        assert data["sender"] == "orchestrator"
        assert data["recipient"] == "search_agent"
        assert data["query_type"] == "search"  # Enum value, not object
        assert data["content"] == "Find books"
        assert data["status"] == "pending"  # Enum value
        assert data["context"] == {"test": True}
        assert "timestamp" in data
        assert data["parent_id"] is None
        assert data["error"] is None

    def test_from_dict_deserialization(self) -> None:
        """Test creating message from dictionary."""
        original = AgentMessage.create(
            sender="orchestrator",
            recipient="search_agent",
            query_type=QueryType.ANALYTICS,
            content={"query": "test"},
            context={"session": "123"},
        )

        data = original.to_dict()
        restored = AgentMessage.from_dict(data)

        assert restored.id == original.id
        assert restored.sender == original.sender
        assert restored.recipient == original.recipient
        assert restored.query_type == original.query_type
        assert restored.content == original.content
        assert restored.context == original.context
        assert restored.status == original.status

    def test_message_repr(self) -> None:
        """Test string representation of message."""
        msg = AgentMessage.create(
            sender="orchestrator",
            recipient="search_agent",
            query_type=QueryType.SEARCH,
            content="test",
        )

        repr_str = repr(msg)
        assert "orchestrator" in repr_str
        assert "search_agent" in repr_str
        assert "search" in repr_str
        assert "pending" in repr_str

    def test_message_timestamp_auto_generated(self) -> None:
        """Test that timestamp is automatically set."""
        before = datetime.now()
        msg = AgentMessage.create(
            sender="a",
            recipient="b",
            query_type=QueryType.SEARCH,
            content="test",
        )
        after = datetime.now()

        assert before <= msg.timestamp <= after

    def test_complex_content_types(self) -> None:
        """Test that various content types are supported."""
        # String content
        msg1 = AgentMessage.create(
            sender="a",
            recipient="b",
            query_type=QueryType.SEARCH,
            content="string content",
        )
        assert msg1.content == "string content"

        # List content
        msg2 = AgentMessage.create(
            sender="a",
            recipient="b",
            query_type=QueryType.SEARCH,
            content=["item1", "item2"],
        )
        assert msg2.content == ["item1", "item2"]

        # Dict content
        msg3 = AgentMessage.create(
            sender="a",
            recipient="b",
            query_type=QueryType.ANALYTICS,
            content={"books": 100, "missing": 5},
        )
        assert msg3.content["books"] == 100

        # Nested content
        msg4 = AgentMessage.create(
            sender="a",
            recipient="b",
            query_type=QueryType.MULTI_STEP,
            content={
                "steps": [
                    {"agent": "search", "query": "Python"},
                    {"agent": "recommendation", "filter": "available"},
                ]
            },
        )
        assert len(msg4.content["steps"]) == 2
