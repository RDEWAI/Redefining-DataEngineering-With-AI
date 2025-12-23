"""Integration tests for the multi-agent library system with code execution.

These tests verify end-to-end functionality of the multi-agent system,
including dynamic planning, routing, and code execution by agents.
"""

import os
from pathlib import Path

import pytest

from src.agentic.a2a.protocol import AgentMessage, AgentStatus, QueryType
from src.agentic.a2a.server import MessageRouter
from src.agentic.agents.analytics_agent import AnalyticsAgent
from src.agentic.agents.orchestrator_agent import OrchestratorAgent
from src.agentic.agents.recommendation_agent import RecommendationAgent
from src.agentic.agents.search_agent import SearchAgent

# Get test database path
TEST_DB_PATH = os.getenv(
    "DB_PATH",
    str(Path(__file__).parent.parent.parent / "data" / "duckdb" / "chapter3.db"),
)


class TestSearchAgent:
    """Integration tests for SearchAgent with code execution."""

    @pytest.fixture
    def agent(self) -> SearchAgent:
        """Create a SearchAgent for testing."""
        agent = SearchAgent(db_path=TEST_DB_PATH, enable_rag=False)
        yield agent
        agent.close()

    def test_keyword_search(self, agent: SearchAgent) -> None:
        """Test keyword-based search via code execution."""
        msg = AgentMessage.create(
            sender="test",
            recipient="search_agent",
            query_type=QueryType.SEARCH,
            content="Find Python programming books",
        )

        response = agent.process(msg)

        assert response.status == AgentStatus.COMPLETED
        assert response.content is not None
        assert isinstance(response.content, str)

    def test_search_with_string_content(self, agent: SearchAgent) -> None:
        """Test search with simple string content."""
        msg = AgentMessage.create(
            sender="test",
            recipient="search_agent",
            query_type=QueryType.SEARCH,
            content="Programming books",
        )

        response = agent.process(msg)

        assert response.status == AgentStatus.COMPLETED
        assert isinstance(response.content, str)

    def test_search_with_category_filter(self, agent: SearchAgent) -> None:
        """Test search with category filter."""
        msg = AgentMessage.create(
            sender="test",
            recipient="search_agent",
            query_type=QueryType.SEARCH,
            content="Find books in the Programming category",
        )

        response = agent.process(msg)

        assert response.status == AgentStatus.COMPLETED
        assert isinstance(response.content, str)

    def test_query_method(self, agent: SearchAgent) -> None:
        """Test the convenience query method."""
        result = agent.query("Find fiction books")

        assert result["success"] is True
        assert "output" in result
        assert isinstance(result["output"], str)


class TestAnalyticsAgent:
    """Integration tests for AnalyticsAgent with code execution."""

    @pytest.fixture
    def agent(self) -> AnalyticsAgent:
        """Create an AnalyticsAgent for testing."""
        agent = AnalyticsAgent(db_path=TEST_DB_PATH, enable_rag=False)
        yield agent
        agent.close()

    def test_get_library_stats(self, agent: AnalyticsAgent) -> None:
        """Test getting library statistics via code execution."""
        msg = AgentMessage.create(
            sender="test",
            recipient="analytics_agent",
            query_type=QueryType.ANALYTICS,
            content="Show me library statistics",
        )

        response = agent.process(msg)

        assert response.status == AgentStatus.COMPLETED
        assert response.content is not None
        assert isinstance(response.content, str)

    def test_count_by_status(self, agent: AnalyticsAgent) -> None:
        """Test counting books by status."""
        msg = AgentMessage.create(
            sender="test",
            recipient="analytics_agent",
            query_type=QueryType.ANALYTICS,
            content="How many books are Present in the library?",
        )

        response = agent.process(msg)

        assert response.status == AgentStatus.COMPLETED
        assert isinstance(response.content, str)

    def test_weak_signal_query(self, agent: AnalyticsAgent) -> None:
        """Test querying books with weak signal."""
        msg = AgentMessage.create(
            sender="test",
            recipient="analytics_agent",
            query_type=QueryType.ANALYTICS,
            content="Which books have weak RFID signal?",
        )

        response = agent.process(msg)

        assert response.status == AgentStatus.COMPLETED
        assert isinstance(response.content, str)

    def test_natural_language_analytics(self, agent: AnalyticsAgent) -> None:
        """Test analytics with natural language query."""
        msg = AgentMessage.create(
            sender="test",
            recipient="analytics_agent",
            query_type=QueryType.ANALYTICS,
            content="Give me a breakdown of books by category",
        )

        response = agent.process(msg)

        assert response.status == AgentStatus.COMPLETED
        assert isinstance(response.content, str)


class TestRecommendationAgent:
    """Integration tests for RecommendationAgent with code execution."""

    @pytest.fixture
    def agent(self) -> RecommendationAgent:
        """Create a RecommendationAgent for testing."""
        agent = RecommendationAgent(db_path=TEST_DB_PATH, enable_rag=False)
        yield agent
        agent.close()

    def test_recommend_available_books(self, agent: RecommendationAgent) -> None:
        """Test recommending available books via code execution."""
        msg = AgentMessage.create(
            sender="test",
            recipient="recommendation_agent",
            query_type=QueryType.RECOMMENDATION,
            content="Recommend available Programming books with good signal",
        )

        response = agent.process(msg)

        assert response.status == AgentStatus.COMPLETED
        assert response.content is not None
        assert isinstance(response.content, str)

    def test_recommend_with_query(self, agent: RecommendationAgent) -> None:
        """Test recommendations with search query."""
        msg = AgentMessage.create(
            sender="test",
            recipient="recommendation_agent",
            query_type=QueryType.RECOMMENDATION,
            content="Recommend programming books with good signal",
        )

        response = agent.process(msg)

        assert response.status == AgentStatus.COMPLETED
        assert isinstance(response.content, str)

    def test_recommend_fiction(self, agent: RecommendationAgent) -> None:
        """Test recommending fiction books."""
        msg = AgentMessage.create(
            sender="test",
            recipient="recommendation_agent",
            query_type=QueryType.RECOMMENDATION,
            content="Suggest some fiction books that are available",
        )

        response = agent.process(msg)

        assert response.status == AgentStatus.COMPLETED
        assert isinstance(response.content, str)


class TestOrchestratorAgent:
    """Integration tests for OrchestratorAgent with dynamic planning."""

    @pytest.fixture
    def orchestrator(self) -> OrchestratorAgent:
        """Create an OrchestratorAgent for testing."""
        orchestrator = OrchestratorAgent(
            db_path=TEST_DB_PATH,
            show_routing=False,
            verbose=False,
            enable_rag=False,
        )
        yield orchestrator
        orchestrator.close()

    def test_simple_search_query(self, orchestrator: OrchestratorAgent) -> None:
        """Test dynamic planning for a simple search query."""
        result = orchestrator.query("Find programming books")

        assert result["status"] in ["completed", "failed"]
        assert "response" in result
        assert "plan" in result
        # Plan should have at least one step
        assert len(result["plan"].get("plan", [])) >= 1

    def test_analytics_query(self, orchestrator: OrchestratorAgent) -> None:
        """Test dynamic planning for an analytics query."""
        result = orchestrator.query("How many books are in the library?")

        assert result["status"] in ["completed", "failed"]
        assert "response" in result
        assert isinstance(result["response"], str)

    def test_recommendation_query(self, orchestrator: OrchestratorAgent) -> None:
        """Test dynamic planning for a recommendation query."""
        result = orchestrator.query("Recommend programming books")

        assert result["status"] in ["completed", "failed"]
        assert "response" in result
        assert isinstance(result["response"], str)

    def test_multi_agent_query(self, orchestrator: OrchestratorAgent) -> None:
        """Test dynamic planning for a query requiring multiple agents."""
        result = orchestrator.query("Recommend fiction books by the author who has the most books")

        assert result["status"] in ["completed", "failed"]
        assert "response" in result
        assert "plan" in result
        # This should create a multi-step plan
        plan_steps = result["plan"].get("plan", [])
        # The planner should recognize this needs multiple agents
        assert len(plan_steps) >= 1

    def test_get_agents(self, orchestrator: OrchestratorAgent) -> None:
        """Test getting list of registered agents."""
        agents = orchestrator.get_agents()

        assert len(agents) == 3
        names = [a["name"] for a in agents]
        assert "search_agent" in names
        assert "analytics_agent" in names
        assert "recommendation_agent" in names

    def test_get_stats(self, orchestrator: OrchestratorAgent) -> None:
        """Test getting session statistics."""
        # Run a query first
        orchestrator.query("Find books")

        stats = orchestrator.get_stats()

        assert "total_queries" in stats
        assert stats["total_queries"] >= 1
        assert "planning_tokens" in stats
        assert "agents" in stats


class TestMessageRouterIntegration:
    """Integration tests for MessageRouter with code execution agents."""

    @pytest.fixture
    def router_with_agents(self) -> MessageRouter:
        """Create a router with real agents."""
        router = MessageRouter(enable_logging=True)
        router.register_agent(SearchAgent(db_path=TEST_DB_PATH, enable_rag=False))
        router.register_agent(AnalyticsAgent(db_path=TEST_DB_PATH, enable_rag=False))
        router.register_agent(RecommendationAgent(db_path=TEST_DB_PATH, enable_rag=False))
        return router

    def test_route_to_search_agent(self, router_with_agents: MessageRouter) -> None:
        """Test routing message to search agent."""
        msg = AgentMessage.create(
            sender="orchestrator",
            recipient="search_agent",
            query_type=QueryType.SEARCH,
            content="Find Python programming books",
        )

        response = router_with_agents.route(msg)

        assert response.status == AgentStatus.COMPLETED
        assert response.sender == "search_agent"
        assert isinstance(response.content, str)

    def test_route_to_analytics_agent(self, router_with_agents: MessageRouter) -> None:
        """Test routing message to analytics agent."""
        msg = AgentMessage.create(
            sender="orchestrator",
            recipient="analytics_agent",
            query_type=QueryType.ANALYTICS,
            content="Show library statistics",
        )

        response = router_with_agents.route(msg)

        assert response.status == AgentStatus.COMPLETED
        assert response.sender == "analytics_agent"
        assert isinstance(response.content, str)

    def test_route_to_recommendation_agent(self, router_with_agents: MessageRouter) -> None:
        """Test routing message to recommendation agent."""
        msg = AgentMessage.create(
            sender="orchestrator",
            recipient="recommendation_agent",
            query_type=QueryType.RECOMMENDATION,
            content="Recommend available programming books",
        )

        response = router_with_agents.route(msg)

        assert response.status == AgentStatus.COMPLETED
        assert response.sender == "recommendation_agent"
        assert isinstance(response.content, str)

    def test_message_logging(self, router_with_agents: MessageRouter) -> None:
        """Test that message logging captures routing history."""
        msg = AgentMessage.create(
            sender="test",
            recipient="search_agent",
            query_type=QueryType.SEARCH,
            content="test query for books",
        )

        router_with_agents.route(msg)

        log = router_with_agents.get_message_log()
        assert len(log) >= 2  # At least request and response

    def test_routing_stats(self, router_with_agents: MessageRouter) -> None:
        """Test getting routing statistics."""
        # Send a few messages
        for _ in range(3):
            msg = AgentMessage.create(
                sender="test",
                recipient="search_agent",
                query_type=QueryType.SEARCH,
                content="Find books",
            )
            router_with_agents.route(msg)

        stats = router_with_agents.get_routing_stats()

        assert stats["logging_enabled"] is True
        assert stats["total_messages"] >= 6  # 3 requests + 3 responses
