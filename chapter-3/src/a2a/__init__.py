"""Agent-to-Agent (A2A) communication protocol.

This package implements an A2A-inspired in-process message passing protocol
for multi-agent orchestration. It provides:

- QueryType: Classification of user queries (search, analytics, recommendation, multi-step)
- AgentMessage: Standardized message format for agent communication
- MessageRouter: In-process routing of messages between agents

The protocol is inspired by Google's A2A but simplified for educational purposes,
using in-process communication rather than HTTP.

Example:
    >>> from src.a2a.protocol import QueryType, AgentMessage
    >>> from src.a2a.server import MessageRouter
    >>>
    >>> # Create a message
    >>> msg = AgentMessage.create(
    ...     sender="orchestrator",
    ...     recipient="search_agent",
    ...     query_type=QueryType.SEARCH,
    ...     content="Find Python programming books"
    ... )
    >>>
    >>> # Route through the router
    >>> router = MessageRouter()
    >>> router.register_agent("search_agent", search_agent)
    >>> response = router.route(msg)
"""

from .protocol import AgentMessage, QueryType
from .server import MessageRouter

__all__ = [
    "QueryType",
    "AgentMessage",
    "MessageRouter",
]
