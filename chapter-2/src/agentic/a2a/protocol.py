"""A2A message protocol for agent communication.

This module defines the core data structures for inter-agent communication:
- QueryType: Enum classifying the type of user query
- AgentMessage: Dataclass representing a message between agents

The protocol is designed to be simple and educational, demonstrating
multi-agent coordination without the complexity of HTTP-based A2A.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class QueryType(Enum):
    """Classification of user queries for routing decisions.

    The orchestrator uses this classification to determine which
    specialized agent(s) should handle a query.

    Attributes:
        SEARCH: Book discovery and lookup queries
        ANALYTICS: Statistics, aggregations, and reporting queries
        RECOMMENDATION: Book suggestions with quality filters
        MULTI_STEP: Complex queries requiring multiple agents
    """

    SEARCH = "search"
    ANALYTICS = "analytics"
    RECOMMENDATION = "recommendation"
    MULTI_STEP = "multi_step"

    def __str__(self) -> str:
        """Return human-readable name."""
        return self.value.replace("_", " ").title()


class AgentStatus(Enum):
    """Status of an agent message or response.

    Attributes:
        PENDING: Message created but not yet processed
        IN_PROGRESS: Agent is currently processing
        COMPLETED: Agent successfully completed processing
        FAILED: Agent encountered an error
        PARTIAL: Some results available but incomplete
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class AgentMessage:
    """Standardized message format for agent communication.

    This dataclass represents a message passed between agents in the
    multi-agent system. It includes metadata for tracking and routing,
    as well as the actual content and context.

    Attributes:
        id: Unique identifier for this message
        sender: Name of the sending agent
        recipient: Name of the receiving agent
        query_type: Classification of the query
        content: The actual message content (query string, results, etc.)
        context: Additional context passed between agents
        status: Current status of the message/response
        timestamp: When the message was created
        parent_id: ID of the parent message (for response chains)
        error: Error message if status is FAILED

    Example:
        >>> msg = AgentMessage.create(
        ...     sender="orchestrator",
        ...     recipient="search_agent",
        ...     query_type=QueryType.SEARCH,
        ...     content="Find Python books"
        ... )
        >>> print(msg.sender, "->", msg.recipient)
        orchestrator -> search_agent
    """

    id: str
    sender: str
    recipient: str
    query_type: QueryType
    content: Any
    context: dict[str, Any] = field(default_factory=dict)
    status: AgentStatus = AgentStatus.PENDING
    timestamp: datetime = field(default_factory=datetime.now)
    parent_id: str | None = None
    error: str | None = None

    @classmethod
    def create(
        cls,
        sender: str,
        recipient: str,
        query_type: QueryType,
        content: Any,
        context: dict[str, Any] | None = None,
        parent_id: str | None = None,
    ) -> "AgentMessage":
        """Factory method to create a new message with auto-generated ID.

        Args:
            sender: Name of the sending agent
            recipient: Name of the receiving agent
            query_type: Classification of the query
            content: The message content
            context: Optional context dictionary
            parent_id: Optional parent message ID

        Returns:
            A new AgentMessage instance
        """
        return cls(
            id=str(uuid.uuid4()),
            sender=sender,
            recipient=recipient,
            query_type=query_type,
            content=content,
            context=context or {},
            parent_id=parent_id,
        )

    def create_response(
        self,
        sender: str,
        content: Any,
        status: AgentStatus = AgentStatus.COMPLETED,
        error: str | None = None,
    ) -> "AgentMessage":
        """Create a response message to this message.

        Args:
            sender: Name of the responding agent
            content: Response content (results, etc.)
            status: Status of the response
            error: Error message if failed

        Returns:
            A new AgentMessage as a response
        """
        return AgentMessage(
            id=str(uuid.uuid4()),
            sender=sender,
            recipient=self.sender,
            query_type=self.query_type,
            content=content,
            context=self.context.copy(),
            status=status,
            parent_id=self.id,
            error=error,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation of the message
        """
        return {
            "id": self.id,
            "sender": self.sender,
            "recipient": self.recipient,
            "query_type": self.query_type.value,
            "content": self.content,
            "context": self.context,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "parent_id": self.parent_id,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentMessage":
        """Create from dictionary.

        Args:
            data: Dictionary with message data

        Returns:
            AgentMessage instance
        """
        return cls(
            id=data["id"],
            sender=data["sender"],
            recipient=data["recipient"],
            query_type=QueryType(data["query_type"]),
            content=data["content"],
            context=data.get("context", {}),
            status=AgentStatus(data.get("status", "pending")),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            parent_id=data.get("parent_id"),
            error=data.get("error"),
        )

    def __repr__(self) -> str:
        """Return detailed string representation."""
        return (
            f"AgentMessage(id={self.id[:8]}..., "
            f"{self.sender} -> {self.recipient}, "
            f"type={self.query_type.value}, "
            f"status={self.status.value})"
        )
