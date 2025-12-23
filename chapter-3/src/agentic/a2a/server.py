"""In-process message routing for A2A communication.

This module provides the MessageRouter class that handles routing
messages between agents in the multi-agent system. Unlike a full
A2A HTTP implementation, this uses in-process function calls for
simplicity and educational clarity.

The router maintains a registry of agents and their capabilities,
routing messages to the appropriate agent based on the recipient field.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from .protocol import AgentMessage, AgentStatus, QueryType


class AgentProtocol(Protocol):
    """Protocol defining the interface for agents.

    Any class implementing this protocol can be registered with
    the MessageRouter and receive messages.
    """

    name: str
    capabilities: list[QueryType]

    def can_handle(self, query_type: QueryType) -> bool:
        """Check if the agent can handle a query type."""
        ...

    def process(self, message: AgentMessage) -> AgentMessage:
        """Process a message and return a response."""
        ...


@dataclass
class AgentInfo:
    """Information about a registered agent.

    Attributes:
        name: Unique name of the agent
        capabilities: Query types this agent can handle
        handler: The agent instance or callable
        description: Human-readable description
    """

    name: str
    capabilities: list[QueryType]
    handler: AgentProtocol | Callable[[AgentMessage], AgentMessage]
    description: str = ""


class MessageRouter:
    """In-process message router for agent communication.

    The router maintains a registry of agents and routes messages
    to the appropriate handler based on the recipient field.

    Attributes:
        agents: Dictionary of registered agents by name
        message_log: Optional log of all routed messages

    Example:
        >>> router = MessageRouter()
        >>> router.register_agent(search_agent)
        >>> router.register_agent(analytics_agent)
        >>>
        >>> msg = AgentMessage.create(
        ...     sender="orchestrator",
        ...     recipient="search_agent",
        ...     query_type=QueryType.SEARCH,
        ...     content="Find Python books"
        ... )
        >>> response = router.route(msg)
    """

    def __init__(self, enable_logging: bool = False) -> None:
        """Initialize the message router.

        Args:
            enable_logging: Whether to log all routed messages
        """
        self._agents: dict[str, AgentInfo] = {}
        self._enable_logging = enable_logging
        self._message_log: list[AgentMessage] = []

    def register_agent(
        self,
        agent: AgentProtocol,
        description: str = "",
    ) -> None:
        """Register an agent with the router.

        Args:
            agent: Agent instance implementing AgentProtocol
            description: Optional description of the agent

        Raises:
            ValueError: If an agent with the same name is already registered
        """
        if agent.name in self._agents:
            raise ValueError(f"Agent '{agent.name}' is already registered")

        self._agents[agent.name] = AgentInfo(
            name=agent.name,
            capabilities=agent.capabilities,
            handler=agent,
            description=description or f"Agent: {agent.name}",
        )

    def register_handler(
        self,
        name: str,
        capabilities: list[QueryType],
        handler: Callable[[AgentMessage], AgentMessage],
        description: str = "",
    ) -> None:
        """Register a callable handler as an agent.

        This is useful for simple agents that don't need a full class.

        Args:
            name: Unique name for the handler
            capabilities: Query types the handler can process
            handler: Callable that processes messages
            description: Optional description

        Raises:
            ValueError: If a handler with the same name is already registered
        """
        if name in self._agents:
            raise ValueError(f"Handler '{name}' is already registered")

        self._agents[name] = AgentInfo(
            name=name,
            capabilities=capabilities,
            handler=handler,
            description=description,
        )

    def unregister_agent(self, name: str) -> None:
        """Remove an agent from the registry.

        Args:
            name: Name of the agent to remove

        Raises:
            KeyError: If the agent is not registered
        """
        if name not in self._agents:
            raise KeyError(f"Agent '{name}' is not registered")
        del self._agents[name]

    def get_agent(self, name: str) -> AgentInfo | None:
        """Get agent info by name.

        Args:
            name: Name of the agent

        Returns:
            AgentInfo if found, None otherwise
        """
        return self._agents.get(name)

    def list_agents(self) -> list[AgentInfo]:
        """Get list of all registered agents.

        Returns:
            List of AgentInfo for all registered agents
        """
        return list(self._agents.values())

    def find_agents_for_query(self, query_type: QueryType) -> list[AgentInfo]:
        """Find agents that can handle a query type.

        Args:
            query_type: The type of query to handle

        Returns:
            List of AgentInfo for agents that can handle this query type
        """
        return [agent for agent in self._agents.values() if query_type in agent.capabilities]

    def route(self, message: AgentMessage) -> AgentMessage:
        """Route a message to its recipient agent.

        Args:
            message: The message to route

        Returns:
            Response message from the recipient agent

        Raises:
            ValueError: If the recipient agent is not registered
        """
        if self._enable_logging:
            self._message_log.append(message)

        # Find the recipient agent
        agent_info = self._agents.get(message.recipient)
        if agent_info is None:
            # Return error response
            return message.create_response(
                sender="router",
                content=None,
                status=AgentStatus.FAILED,
                error=f"Agent '{message.recipient}' is not registered. "
                f"Available agents: {list(self._agents.keys())}",
            )

        # Process the message
        try:
            handler = agent_info.handler
            if hasattr(handler, "process"):
                # It's an agent with process method
                response = handler.process(message)
            else:
                # It's a callable
                response = handler(message)

            if self._enable_logging:
                self._message_log.append(response)

            return response

        except Exception as e:
            error_response = message.create_response(
                sender=message.recipient,
                content=None,
                status=AgentStatus.FAILED,
                error=f"Error processing message: {str(e)}",
            )
            if self._enable_logging:
                self._message_log.append(error_response)
            return error_response

    def broadcast(
        self,
        message: AgentMessage,
        query_type: QueryType | None = None,
    ) -> list[AgentMessage]:
        """Broadcast a message to all capable agents.

        Args:
            message: The message to broadcast
            query_type: Optional filter for agent capabilities

        Returns:
            List of responses from all agents that processed the message
        """
        responses = []
        target_agents = (
            self.find_agents_for_query(query_type) if query_type else list(self._agents.values())
        )

        for agent_info in target_agents:
            # Create a copy of the message with specific recipient
            agent_message = AgentMessage.create(
                sender=message.sender,
                recipient=agent_info.name,
                query_type=message.query_type,
                content=message.content,
                context=message.context.copy(),
                parent_id=message.id,
            )
            response = self.route(agent_message)
            responses.append(response)

        return responses

    def get_message_log(self) -> list[AgentMessage]:
        """Get the message log.

        Returns:
            List of all logged messages (empty if logging disabled)
        """
        return self._message_log.copy()

    def clear_log(self) -> None:
        """Clear the message log."""
        self._message_log.clear()

    def get_routing_stats(self) -> dict[str, Any]:
        """Get statistics about message routing.

        Returns:
            Dictionary with routing statistics
        """
        if not self._enable_logging:
            return {"logging_enabled": False}

        total = len(self._message_log)
        by_status: dict[str, int] = {}
        by_query_type: dict[str, int] = {}
        by_agent: dict[str, int] = {}

        for msg in self._message_log:
            # Count by status
            status = msg.status.value
            by_status[status] = by_status.get(status, 0) + 1

            # Count by query type
            qt = msg.query_type.value
            by_query_type[qt] = by_query_type.get(qt, 0) + 1

            # Count by recipient
            by_agent[msg.recipient] = by_agent.get(msg.recipient, 0) + 1

        return {
            "logging_enabled": True,
            "total_messages": total,
            "by_status": by_status,
            "by_query_type": by_query_type,
            "by_agent": by_agent,
        }
