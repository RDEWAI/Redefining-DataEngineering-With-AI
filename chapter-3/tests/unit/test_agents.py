"""Unit tests for multi-agent system components.

Tests the specialized agents (SearchAgent, AnalyticsAgent, RecommendationAgent)
and the MessageRouter for proper message handling and routing.
"""

import pytest

from src.a2a.protocol import AgentMessage, AgentStatus, QueryType
from src.a2a.server import AgentInfo, MessageRouter


class MockAgent:
    """Mock agent for testing the router."""

    def __init__(
        self,
        name: str,
        capabilities: list[QueryType],
        response_content: str = "mock response",
    ) -> None:
        self.name = name
        self.capabilities = capabilities
        self.response_content = response_content
        self.received_messages: list[AgentMessage] = []

    def can_handle(self, query_type: QueryType) -> bool:
        return query_type in self.capabilities

    def process(self, message: AgentMessage) -> AgentMessage:
        self.received_messages.append(message)
        return message.create_response(
            sender=self.name,
            content=self.response_content,
            status=AgentStatus.COMPLETED,
        )


class FailingAgent:
    """Agent that always fails for testing error handling."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.capabilities = [QueryType.SEARCH]

    def can_handle(self, query_type: QueryType) -> bool:
        return query_type in self.capabilities

    def process(self, message: AgentMessage) -> AgentMessage:
        raise RuntimeError("Simulated agent failure")


class TestMessageRouter:
    """Tests for MessageRouter class."""

    def test_register_agent(self) -> None:
        """Test registering an agent with the router."""
        router = MessageRouter()
        agent = MockAgent("search_agent", [QueryType.SEARCH])

        router.register_agent(agent, description="Search agent")

        assert router.get_agent("search_agent") is not None
        assert router.get_agent("search_agent").name == "search_agent"

    def test_register_duplicate_agent_raises(self) -> None:
        """Test that registering duplicate agent name raises error."""
        router = MessageRouter()
        agent = MockAgent("search_agent", [QueryType.SEARCH])

        router.register_agent(agent)

        with pytest.raises(ValueError, match="already registered"):
            router.register_agent(agent)

    def test_register_handler_callable(self) -> None:
        """Test registering a callable as a handler."""
        router = MessageRouter()

        def my_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response(
                sender="my_handler",
                content="handled",
                status=AgentStatus.COMPLETED,
            )

        router.register_handler(
            name="my_handler",
            capabilities=[QueryType.SEARCH],
            handler=my_handler,
        )

        assert router.get_agent("my_handler") is not None

    def test_unregister_agent(self) -> None:
        """Test removing an agent from the registry."""
        router = MessageRouter()
        agent = MockAgent("search_agent", [QueryType.SEARCH])

        router.register_agent(agent)
        assert router.get_agent("search_agent") is not None

        router.unregister_agent("search_agent")
        assert router.get_agent("search_agent") is None

    def test_unregister_nonexistent_agent_raises(self) -> None:
        """Test unregistering non-existent agent raises error."""
        router = MessageRouter()

        with pytest.raises(KeyError):
            router.unregister_agent("nonexistent")

    def test_list_agents(self) -> None:
        """Test listing all registered agents."""
        router = MessageRouter()
        router.register_agent(MockAgent("agent1", [QueryType.SEARCH]))
        router.register_agent(MockAgent("agent2", [QueryType.ANALYTICS]))
        router.register_agent(MockAgent("agent3", [QueryType.RECOMMENDATION]))

        agents = router.list_agents()

        assert len(agents) == 3
        names = [a.name for a in agents]
        assert "agent1" in names
        assert "agent2" in names
        assert "agent3" in names

    def test_find_agents_for_query(self) -> None:
        """Test finding agents that can handle a query type."""
        router = MessageRouter()
        router.register_agent(MockAgent("search1", [QueryType.SEARCH]))
        router.register_agent(MockAgent("multi", [QueryType.SEARCH, QueryType.ANALYTICS]))
        router.register_agent(MockAgent("analytics1", [QueryType.ANALYTICS]))

        search_agents = router.find_agents_for_query(QueryType.SEARCH)
        analytics_agents = router.find_agents_for_query(QueryType.ANALYTICS)

        assert len(search_agents) == 2
        assert len(analytics_agents) == 2

    def test_route_message_to_agent(self) -> None:
        """Test routing a message to a specific agent."""
        router = MessageRouter()
        agent = MockAgent("search_agent", [QueryType.SEARCH], "search results")
        router.register_agent(agent)

        msg = AgentMessage.create(
            sender="orchestrator",
            recipient="search_agent",
            query_type=QueryType.SEARCH,
            content="Find Python books",
        )

        response = router.route(msg)

        assert response.status == AgentStatus.COMPLETED
        assert response.content == "search results"
        assert response.sender == "search_agent"
        assert response.recipient == "orchestrator"
        assert response.parent_id == msg.id
        assert len(agent.received_messages) == 1

    def test_route_to_nonexistent_agent(self) -> None:
        """Test routing to non-existent agent returns error."""
        router = MessageRouter()

        msg = AgentMessage.create(
            sender="orchestrator",
            recipient="nonexistent_agent",
            query_type=QueryType.SEARCH,
            content="test",
        )

        response = router.route(msg)

        assert response.status == AgentStatus.FAILED
        assert "not registered" in response.error

    def test_route_handles_agent_exception(self) -> None:
        """Test that router handles agent exceptions gracefully."""
        router = MessageRouter()
        router.register_agent(FailingAgent("failing_agent"))

        msg = AgentMessage.create(
            sender="orchestrator",
            recipient="failing_agent",
            query_type=QueryType.SEARCH,
            content="test",
        )

        response = router.route(msg)

        assert response.status == AgentStatus.FAILED
        assert "Simulated agent failure" in response.error

    def test_route_to_callable_handler(self) -> None:
        """Test routing to a callable handler."""
        router = MessageRouter()

        def echo_handler(msg: AgentMessage) -> AgentMessage:
            return msg.create_response(
                sender="echo",
                content=f"Echo: {msg.content}",
                status=AgentStatus.COMPLETED,
            )

        router.register_handler(
            name="echo",
            capabilities=[QueryType.SEARCH],
            handler=echo_handler,
        )

        msg = AgentMessage.create(
            sender="test",
            recipient="echo",
            query_type=QueryType.SEARCH,
            content="Hello",
        )

        response = router.route(msg)

        assert response.content == "Echo: Hello"
        assert response.status == AgentStatus.COMPLETED

    def test_broadcast_to_all_capable_agents(self) -> None:
        """Test broadcasting message to all capable agents."""
        router = MessageRouter()
        router.register_agent(MockAgent("search1", [QueryType.SEARCH], "result1"))
        router.register_agent(MockAgent("search2", [QueryType.SEARCH], "result2"))
        router.register_agent(MockAgent("analytics", [QueryType.ANALYTICS], "stats"))

        msg = AgentMessage.create(
            sender="orchestrator",
            recipient="broadcast",
            query_type=QueryType.SEARCH,
            content="test query",
        )

        responses = router.broadcast(msg, query_type=QueryType.SEARCH)

        assert len(responses) == 2
        contents = [r.content for r in responses]
        assert "result1" in contents
        assert "result2" in contents

    def test_message_logging(self) -> None:
        """Test that message logging captures all messages."""
        router = MessageRouter(enable_logging=True)
        router.register_agent(MockAgent("agent", [QueryType.SEARCH]))

        msg = AgentMessage.create(
            sender="test",
            recipient="agent",
            query_type=QueryType.SEARCH,
            content="test",
        )

        router.route(msg)

        log = router.get_message_log()
        assert len(log) == 2  # Original message + response

    def test_logging_disabled_by_default(self) -> None:
        """Test that logging is disabled by default."""
        router = MessageRouter()
        router.register_agent(MockAgent("agent", [QueryType.SEARCH]))

        msg = AgentMessage.create(
            sender="test",
            recipient="agent",
            query_type=QueryType.SEARCH,
            content="test",
        )

        router.route(msg)

        assert len(router.get_message_log()) == 0

    def test_clear_log(self) -> None:
        """Test clearing the message log."""
        router = MessageRouter(enable_logging=True)
        router.register_agent(MockAgent("agent", [QueryType.SEARCH]))

        msg = AgentMessage.create(
            sender="test",
            recipient="agent",
            query_type=QueryType.SEARCH,
            content="test",
        )

        router.route(msg)
        assert len(router.get_message_log()) > 0

        router.clear_log()
        assert len(router.get_message_log()) == 0

    def test_routing_stats(self) -> None:
        """Test getting routing statistics."""
        router = MessageRouter(enable_logging=True)
        router.register_agent(MockAgent("search", [QueryType.SEARCH]))
        router.register_agent(MockAgent("analytics", [QueryType.ANALYTICS]))

        # Route some messages
        for _ in range(3):
            msg = AgentMessage.create(
                sender="test",
                recipient="search",
                query_type=QueryType.SEARCH,
                content="test",
            )
            router.route(msg)

        msg = AgentMessage.create(
            sender="test",
            recipient="analytics",
            query_type=QueryType.ANALYTICS,
            content="stats",
        )
        router.route(msg)

        stats = router.get_routing_stats()

        assert stats["logging_enabled"] is True
        assert stats["total_messages"] == 8  # 4 messages + 4 responses
        assert stats["by_query_type"]["search"] == 6
        assert stats["by_query_type"]["analytics"] == 2


class TestAgentInfo:
    """Tests for AgentInfo dataclass."""

    def test_agent_info_creation(self) -> None:
        """Test creating AgentInfo."""
        agent = MockAgent("test", [QueryType.SEARCH])
        info = AgentInfo(
            name="test",
            capabilities=[QueryType.SEARCH],
            handler=agent,
            description="Test agent",
        )

        assert info.name == "test"
        assert QueryType.SEARCH in info.capabilities
        assert info.description == "Test agent"

    def test_agent_info_default_description(self) -> None:
        """Test that description has sensible default."""
        agent = MockAgent("test", [QueryType.SEARCH])
        info = AgentInfo(
            name="test",
            capabilities=[QueryType.SEARCH],
            handler=agent,
        )

        assert info.description == ""
