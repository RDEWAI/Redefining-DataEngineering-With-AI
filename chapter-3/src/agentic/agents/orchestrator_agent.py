"""Orchestrator Agent for multi-agent coordination.

This is the central coordinator that:
- Uses LLM to dynamically plan which agents to call
- Routes to appropriate specialized agents based on query analysis
- Chains agents together passing context between them
- Returns formatted results from agent code execution
- Tracks token usage and logs agent activity

Example:
    >>> from src.agentic.agents.orchestrator_agent import OrchestratorAgent
    >>> orchestrator = OrchestratorAgent()
    >>> result = orchestrator.query("Find available Python books with good signal")
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.agentic.a2a.protocol import AgentMessage, AgentStatus, QueryType
from src.agentic.a2a.server import MessageRouter
from src.agentic.agents.analytics_agent import AnalyticsAgent
from src.agentic.agents.base_agent import AgentLogger
from src.agentic.agents.recommendation_agent import RecommendationAgent
from src.agentic.agents.search_agent import SearchAgent
from src.agentic.llm.base import LLMProvider, Message
from src.agentic.llm.unified_client import UnifiedLLMClient
from src.agentic.tools.tool_registry import format_agent_tools_display, get_agent_tools

# Load .env from chapter-3 directory
# Path: orchestrator_agent.py -> agents/ -> agentic/ -> src/ -> chapter-3/
env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(env_path, override=True)

# Use standard logging with optional JSON formatting via logging_config
logger = logging.getLogger("chapter3.agents.orchestrator")


PLANNER_SYSTEM_PROMPT = """You are an intelligent query planner for a library management system.

Your job is to analyze user queries and create an execution plan using the available agents.

**Available Agents:**

1. **search_agent** - Book discovery and search
   - Find books by title, author, keyword
   - Filter by category, availability, location
   - Use for: "find", "search", "show me", "list", "where is"

2. **analytics_agent** - Statistics and reporting
   - Count books, compute aggregations
   - Find top/most/least patterns
   - Analyze by category, status, signal strength
   - Use for: "how many", "count", "statistics", "top", "most", "average", "which author has more"

3. **recommendation_agent** - Book suggestions with quality filters
   - Recommend books based on preferences
   - Filter by availability and signal strength
   - Use for: "recommend", "suggest", "good books", "what should I read"

**CRITICAL INSTRUCTIONS:**

1. Analyze the query to understand what information is needed
2. Decide which agent(s) to call and in what ORDER
3. Use `depends_on` to specify which previous steps a step needs data from
4. Steps with no dependencies can run in parallel (fan-out)
5. Steps can depend on multiple previous steps (fan-in)
6. Return a JSON plan with the execution steps

**IMPORTANT**: Some queries need MULTIPLE agents. Examples:
- "Recommend books by the author who has most books" → analytics_agent FIRST, THEN recommendation_agent
- "Find fiction books and count them" → search_agent FIRST, THEN analytics_agent
- "Compare fiction and programming books" → search both in parallel, THEN analytics

**Response Format (JSON only, no markdown):**
{
  "analysis": "Brief explanation of what the query needs",
  "plan": [
    {
      "step": 1,
      "agent": "agent_name",
      "task": "What this agent should do",
      "depends_on": []
    },
    {
      "step": 2,
      "agent": "agent_name",
      "task": "What this agent should do, using result from step 1",
      "depends_on": [1]
    }
  ]
}

**Dependency Patterns:**
- `"depends_on": []` - No dependencies, can start immediately
- `"depends_on": [1]` - Needs result from step 1
- `"depends_on": [1, 2]` - Needs results from both step 1 AND step 2 (fan-in)

**Examples:**

Query: "Find Python programming books"
{
  "analysis": "Simple search query for books by keyword",
  "plan": [{"step": 1, "agent": "search_agent", "task": "Search for Python programming books", "depends_on": []}]
}

Query: "How many books are missing?"
{
  "analysis": "Analytics query to count books by status",
  "plan": [{"step": 1, "agent": "analytics_agent", "task": "Count books with status Missing", "depends_on": []}]
}

Query: "Recommend fiction books by the author who has the most books"
{
  "analysis": "Need to first find the author with most books, then recommend their fiction books",
  "plan": [
    {"step": 1, "agent": "analytics_agent", "task": "Find which author has the most books in the library", "depends_on": []},
    {"step": 2, "agent": "recommendation_agent", "task": "Recommend fiction books by the author identified in step 1", "depends_on": [1]}
  ]
}

Query: "Find science books, count how many are available, and recommend the best ones"
{
  "analysis": "Multi-step: search, then analytics, then recommendations based on both",
  "plan": [
    {"step": 1, "agent": "search_agent", "task": "Find science books", "depends_on": []},
    {"step": 2, "agent": "analytics_agent", "task": "Count how many science books are available from step 1", "depends_on": [1]},
    {"step": 3, "agent": "recommendation_agent", "task": "Recommend the best available science books using search results from step 1 and counts from step 2", "depends_on": [1, 2]}
  ]
}

Query: "Compare fiction and programming books - find both and analyze which category has more available"
{
  "analysis": "Parallel search for two categories, then combined analytics",
  "plan": [
    {"step": 1, "agent": "search_agent", "task": "Find all fiction books", "depends_on": []},
    {"step": 2, "agent": "search_agent", "task": "Find all programming books", "depends_on": []},
    {"step": 3, "agent": "analytics_agent", "task": "Compare availability between fiction (step 1) and programming (step 2) books", "depends_on": [1, 2]}
  ]
}

Return ONLY the JSON, no additional text or markdown formatting.
"""


class OrchestratorAgent:
    """Central orchestrator for the multi-agent library system.

    Uses LLM-based planning to dynamically decide which agents to call
    and in what order. Each agent uses code execution to generate and
    run Python code that answers queries.

    Attributes:
        name: Agent identifier ("orchestrator")
        capabilities: All query types (can route any query)
        router: Message router for agent communication

    Example:
        >>> orchestrator = OrchestratorAgent()
        >>> result = orchestrator.query("What programming books are available?")
        >>> print(result["response"])
    """

    name: str = "orchestrator"
    capabilities: list[QueryType] = list(QueryType)

    def __init__(
        self,
        db_path: str | None = None,
        llm_provider: LLMProvider | None = None,
        verbose: bool = True,
        show_routing: bool = True,
        enable_rag: bool = True,
    ) -> None:
        """Initialize the orchestrator agent.

        Args:
            db_path: Path to DuckDB database. If None, uses default.
            llm_provider: LLM provider to pass to agents. If None, agents use their default.
            verbose: Whether to print detailed debug information (default True)
            show_routing: Whether to display routing decisions to user
            enable_rag: Whether to enable RAG/semantic search in agents
        """
        if db_path is None:
            db_path = os.getenv(
                "DB_PATH",
                str(Path(__file__).parent.parent.parent.parent / "data" / "duckdb" / "chapter3.db"),
            )

        self.db_path = db_path
        self.verbose = verbose
        self.show_routing = show_routing
        self.enable_rag = enable_rag

        # Initialize LLM provider for planning
        self._llm_provider: LLMProvider
        if llm_provider is None:
            self._llm_provider = UnifiedLLMClient.from_env()
        else:
            self._llm_provider = llm_provider

        # Shared logger for all agents
        self._logger = AgentLogger(enabled=verbose)

        # Initialize message router
        self.router = MessageRouter(enable_logging=verbose)

        # Initialize specialized agents with their specific tools
        # Each agent gets ONLY the tools relevant to its role (industry best practice)
        self._search_agent = SearchAgent(
            db_path=db_path,
            llm_provider=llm_provider,
            verbose=verbose,
            enable_rag=enable_rag,
            logger=self._logger,
            tools=get_agent_tools("search_agent", include_rag=enable_rag),
        )
        self._analytics_agent = AnalyticsAgent(
            db_path=db_path,
            llm_provider=llm_provider,
            verbose=verbose,
            enable_rag=enable_rag,
            logger=self._logger,
            tools=get_agent_tools("analytics_agent", include_rag=enable_rag),
        )
        self._recommendation_agent = RecommendationAgent(
            db_path=db_path,
            llm_provider=llm_provider,
            verbose=verbose,
            enable_rag=enable_rag,
            logger=self._logger,
            tools=get_agent_tools("recommendation_agent", include_rag=enable_rag),
        )

        # Agent mapping
        self._agents = {
            "search_agent": self._search_agent,
            "analytics_agent": self._analytics_agent,
            "recommendation_agent": self._recommendation_agent,
        }

        # Register agents with router
        self.router.register_agent(
            self._search_agent,
            description="Handles book search and discovery queries using code execution",
        )
        self.router.register_agent(
            self._analytics_agent,
            description="Handles statistics and analytics queries using code execution",
        )
        self.router.register_agent(
            self._recommendation_agent,
            description="Handles book recommendation queries using code execution",
        )

        # Statistics
        self._query_count = 0
        self._planning_tokens = 0
        self._session_start = datetime.now()

    def can_handle(self, _query_type: QueryType) -> bool:
        """The orchestrator can handle all query types."""
        return True

    def set_verbose(self, enabled: bool) -> None:
        """Enable or disable verbose logging."""
        self.verbose = enabled
        self._logger.enabled = enabled
        # Propagate to all agents so they show/hide generated code
        for agent in self._agents.values():
            agent.verbose = enabled
        if enabled:
            print("✓ Verbose logging ENABLED (agents will show generated code)")
        else:
            print("✓ Verbose logging DISABLED")

    def set_rag(self, enabled: bool) -> None:
        """Enable or disable RAG/semantic search.

        Note: This requires re-initializing agents to take effect.
        """
        self.enable_rag = enabled
        # Update each agent's enable_rag flag
        for agent in self._agents.values():
            agent.enable_rag = enabled
        if enabled:
            print("✓ RAG/Semantic Search ENABLED")
            print("  Agents now have access to semantic_search() function")
        else:
            print("✓ RAG/Semantic Search DISABLED")
            print("  Agents will use keyword-based search only")

    def print_tools(self) -> None:
        """Print available tools/API functions for agents."""
        # Use the formatted display from tool_registry
        print(format_agent_tools_display(include_rag=self.enable_rag))

    def _create_plan(self, query: str) -> dict[str, Any]:
        """Use LLM to create an execution plan for the query.

        Args:
            query: The user's query

        Returns:
            Execution plan with steps and agents
        """
        messages = [
            Message(role="system", content=PLANNER_SYSTEM_PROMPT),
            Message(role="user", content=f"Query: {query}"),
        ]

        response = self._llm_provider.generate(
            messages=messages,
            temperature=0.0,
        )

        # Track planning tokens (both per-query and cumulative)
        query_planning_tokens = 0
        if response.usage:
            query_planning_tokens = response.usage.get("total_tokens", 0)
            self._planning_tokens += query_planning_tokens

        # Parse JSON response
        content = response.content or "{}"

        # Remove markdown code blocks if present
        content = content.strip()
        if content.startswith("```"):
            # Remove ```json or ``` at start
            content = re.sub(r"^```(?:json)?\n?", "", content)
            # Remove ``` at end
            content = re.sub(r"\n?```$", "", content)

        try:
            plan: dict[str, Any] = json.loads(content)
            plan["_planning_tokens"] = query_planning_tokens
            return plan
        except json.JSONDecodeError:
            # Fallback: single search agent
            return {
                "analysis": "Could not parse plan, defaulting to search",
                "plan": [
                    {
                        "step": 1,
                        "agent": "search_agent",
                        "task": query,
                        "needs_previous": False,
                    }
                ],
                "_planning_tokens": query_planning_tokens,
            }

    def _execute_plan(self, plan: dict[str, Any], original_query: str) -> dict[str, Any]:
        """Execute the planned steps with flexible dependency support.

        Args:
            plan: The execution plan from _create_plan
            original_query: The original user query

        Returns:
            Aggregated results from all steps

        Supports:
            - depends_on: [] - No dependencies
            - depends_on: [1] - Needs result from step 1
            - depends_on: [1, 2] - Needs results from steps 1 AND 2 (fan-in)
            - Backward compatible with needs_previous: true/false
        """
        steps = plan.get("plan", [])
        results: list[dict[str, Any]] = []
        # Store all step outputs keyed by step number for flexible dependencies
        step_outputs: dict[int, str] = {}

        for step in steps:
            step_num = step.get("step", 1)
            agent_name = step.get("agent", "search_agent")
            task = step.get("task", original_query)

            # Support both new depends_on and legacy needs_previous
            depends_on: list[int] = step.get("depends_on", [])
            needs_previous = step.get("needs_previous", False)

            # Backward compatibility: convert needs_previous to depends_on
            if not depends_on and needs_previous and step_num > 1:
                depends_on = [step_num - 1]

            # Agent emoji mapping
            agent_emoji = {
                "search_agent": "🔍",
                "analytics_agent": "📊",
                "recommendation_agent": "⭐",
            }.get(agent_name, "🔹")

            if self.show_routing:
                print()
                print(f"   ┌─ Step {step_num}: {agent_emoji} {agent_name}")
                print(f"   │  Task: {task}")

            # Build the query for this step with context from dependencies
            step_query = task
            if depends_on:
                # Collect context from all dependent steps
                context_parts: list[str] = []
                for dep_step in depends_on:
                    if dep_step in step_outputs:
                        context_parts.append(f"[Step {dep_step} output]:\n{step_outputs[dep_step]}")

                if context_parts:
                    context_str = "\n\n".join(context_parts)
                    step_query = f"{task}\n\nContext from previous steps:\n{context_str}"

                    if self.show_routing:
                        dep_str = ", ".join(str(d) for d in depends_on)
                        total_chars = sum(len(step_outputs.get(d, "")) for d in depends_on)
                        print(
                            f"   │  📎 Context: Using output from step(s) {dep_str} ({total_chars} chars)"
                        )

            if self.show_routing:
                print("   │")

            # Get the agent
            agent = self._agents.get(agent_name)
            if not agent:
                results.append(
                    {
                        "step": step_num,
                        "agent": agent_name,
                        "status": "failed",
                        "error": f"Unknown agent: {agent_name}",
                    }
                )
                continue

            # Log routing decision with dependency info
            if depends_on:
                dep_str = ", ".join(str(d) for d in depends_on)
                routing_details = f"Step {step_num} → {agent_name} (depends_on: [{dep_str}])"
            else:
                routing_details = f"Step {step_num} → {agent_name} (no dependencies)"
            self._logger.log(
                agent_name=self.name,
                event="ROUTING",
                details=routing_details,
            )

            # Determine query type for the message
            query_type_map = {
                "search_agent": QueryType.SEARCH,
                "analytics_agent": QueryType.ANALYTICS,
                "recommendation_agent": QueryType.RECOMMENDATION,
            }
            query_type = query_type_map.get(agent_name, QueryType.SEARCH)

            # Create and route message
            message = AgentMessage.create(
                sender=self.name,
                recipient=agent_name,
                query_type=query_type,
                content=step_query,
            )

            response = self.router.route(message)

            step_result = {
                "step": step_num,
                "agent": agent_name,
                "task": task,
                "depends_on": depends_on,
                "status": response.status.value,
                "output": response.content if response.status == AgentStatus.COMPLETED else None,
                "error": response.error if response.status == AgentStatus.FAILED else None,
            }
            results.append(step_result)

            # Store output for dependent steps
            if response.status == AgentStatus.COMPLETED:
                step_outputs[step_num] = response.content

        # Final output is from the last successful step
        final_output = None
        for step_result in reversed(results):
            if step_result.get("output"):
                final_output = step_result["output"]
                break

        return {
            "analysis": plan.get("analysis", ""),
            "steps": results,
            "final_output": final_output,
        }

    def query(self, user_query: str) -> dict[str, Any]:
        """Process a user query through the multi-agent system.

        Uses LLM-based planning to dynamically decide which agents to call.
        """
        start_time = time.time()
        self._query_count += 1

        if self.show_routing:
            print()
            print("🧠 Orchestrator: Analyzing query and creating plan...")

        # Create execution plan using LLM
        plan = self._create_plan(user_query)

        if self.show_routing:
            print(f"   Analysis: {plan.get('analysis', 'N/A')}")
            print(f"   Plan: {len(plan.get('plan', []))} step(s)")

        # Execute the plan
        execution_result = self._execute_plan(plan, user_query)

        duration_ms = int((time.time() - start_time) * 1000)

        # Format the response
        steps = execution_result.get("steps", [])
        final_output = execution_result.get("final_output")

        # Build response text
        if len(steps) == 1:
            # Single agent query
            response_text = final_output or "No results found."
        else:
            # Multi-agent query - show all results
            response_parts = []
            for step_result in steps:
                agent = step_result["agent"]
                output = step_result.get("output")
                if output:
                    agent_emoji = {
                        "search_agent": "📚",
                        "analytics_agent": "📊",
                        "recommendation_agent": "⭐",
                    }.get(agent, "🔹")
                    agent_label = {
                        "search_agent": "SEARCH RESULTS",
                        "analytics_agent": "ANALYTICS",
                        "recommendation_agent": "RECOMMENDATIONS",
                    }.get(agent, agent.upper())
                    response_parts.append(f"{agent_emoji} **{agent_label}**\n{output}")

            response_text = "\n\n".join(response_parts) if response_parts else "No results found."

        result: dict[str, Any] = {
            "query": user_query,
            "plan": plan,
            "status": "completed" if final_output else "failed",
            "duration_ms": duration_ms,
            "response": response_text,
            "data": execution_result,
        }

        # Print summary if verbose
        if self.verbose:
            query_planning_tokens = plan.get("_planning_tokens", 0)
            self._print_query_summary(steps, duration_ms, query_planning_tokens)

        return result

    def _print_query_summary(
        self, steps: list[dict], duration_ms: int, planning_tokens: int = 0
    ) -> None:
        """Print a summary of the query execution."""
        print()
        print("─" * 50)
        print("📊 Query Summary")
        print(f"   Steps executed: {len(steps)}")
        print(f"   Duration: {duration_ms}ms")
        print()

        # Get token usage from agents involved
        total_agent_tokens = 0
        for step in steps:
            agent_name = step.get("agent")
            if not isinstance(agent_name, str):
                continue
            agent = self._agents.get(agent_name)
            if agent:
                usage = agent.get_token_usage()
                tokens = usage.get("last_query_tokens", 0)
                total_agent_tokens += tokens
                print(f"   {agent_name}: {tokens:,} tokens")

        print(f"   orchestrator (planning): {planning_tokens:,} tokens")
        print()
        total_tokens = total_agent_tokens + planning_tokens
        print(f"   📈 TOTAL: {total_tokens:,} tokens")
        print("─" * 50)

    def get_stats(self) -> dict[str, Any]:
        """Get comprehensive statistics for the session."""
        search_usage = self._search_agent.get_token_usage()
        analytics_usage = self._analytics_agent.get_token_usage()
        recommendation_usage = self._recommendation_agent.get_token_usage()

        total_tokens = (
            search_usage["total_tokens"]
            + analytics_usage["total_tokens"]
            + recommendation_usage["total_tokens"]
            + self._planning_tokens
        )

        return {
            "session_start": self._session_start.isoformat(),
            "total_queries": self._query_count,
            "total_tokens": total_tokens,
            "planning_tokens": self._planning_tokens,
            "agents": {
                "search_agent": search_usage,
                "analytics_agent": analytics_usage,
                "recommendation_agent": recommendation_usage,
            },
            "log_entries": len(self._logger.entries),
        }

    def print_stats(self) -> None:
        """Print formatted statistics."""
        stats = self.get_stats()
        print()
        print("=" * 60)
        print("📊 SESSION STATISTICS")
        print("=" * 60)
        print(f"Session started: {stats['session_start']}")
        print(f"Total queries: {stats['total_queries']}")
        print(f"Total tokens: {stats['total_tokens']:,}")
        print(f"Planning tokens: {stats['planning_tokens']:,}")
        print()
        print("Per-Agent Breakdown:")
        for agent_name, usage in stats["agents"].items():
            print(f"\n  {agent_name}:")
            print(f"    Queries: {usage['query_count']}")
            print(f"    Prompt tokens: {usage['prompt_tokens']:,}")
            print(f"    Completion tokens: {usage['completion_tokens']:,}")
            print(f"    Total tokens: {usage['total_tokens']:,}")
            print(f"    Code executions: {usage['code_executions']}")
        print()
        print(f"Log entries: {stats['log_entries']}")
        print("=" * 60)

    def print_logs(self, last_n: int | None = None) -> None:
        """Print agent activity logs."""
        entries = self._logger.entries
        if last_n:
            entries = entries[-last_n:]

        print()
        print("=" * 80)
        print("📝 AGENT ACTIVITY LOG")
        print("=" * 80)

        if not entries:
            print("\n  No log entries.\n")
        else:
            # Group entries by query (using INVOKED as delimiter)
            for i, entry in enumerate(entries):
                # New query starts with INVOKED event - add spacing
                if entry.event == "INVOKED" and i > 0:
                    print()

                ts = entry.timestamp.strftime("%H:%M:%S.%f")[:-3]

                # Event-specific formatting with emojis
                event_emoji = {
                    "ROUTING": "🔀",
                    "INVOKED": "🚀",
                    "CODE_GENERATED": "💻",
                    "CODE_EXECUTED": "✅",
                    "CODE_ERROR": "❌",
                    "COMPLETED": "✓",
                    "FAILED": "✗",
                    "ERROR": "⚠️",
                }.get(entry.event, "•")

                # Format tokens and duration
                metrics = []
                if entry.tokens_used:
                    metrics.append(f"{entry.tokens_used:,} tokens")
                if entry.duration_ms:
                    metrics.append(f"{entry.duration_ms}ms")
                metrics_str = f" ({', '.join(metrics)})" if metrics else ""

                print(f"\n  [{ts}] {event_emoji} {entry.agent_name}")
                print(f"            Event: {entry.event}{metrics_str}")
                if entry.details:
                    print(f"            Details: {entry.details[:80]}")

        print()
        print("=" * 80)

    def reset_stats(self) -> None:
        """Reset all statistics and logs."""
        self._search_agent.reset_stats()
        self._analytics_agent.reset_stats()
        self._recommendation_agent.reset_stats()
        self._logger.clear()
        self._query_count = 0
        self._planning_tokens = 0
        self._session_start = datetime.now()
        print("✓ Statistics and logs reset")

    def get_agents(self) -> list[dict[str, Any]]:
        """Get information about registered agents."""
        agents = []
        for agent_info in self.router.list_agents():
            agents.append(
                {
                    "name": agent_info.name,
                    "capabilities": [c.value for c in agent_info.capabilities],
                    "description": agent_info.description,
                }
            )
        return agents

    def close(self) -> None:
        """Clean up resources."""
        self._search_agent.close()
        self._analytics_agent.close()
        self._recommendation_agent.close()


def run_interactive_cli() -> None:
    """Run an interactive CLI for the multi-agent system."""
    print("\n" + "=" * 60)
    print("Multi-Agent Library System (Dynamic Planning)")
    print("=" * 60)
    print()
    print("This system uses LLM-powered planning to dynamically decide")
    print("which agents to call for your queries.")
    print()
    print("Worker Agents:")
    print("  • SearchAgent: Book discovery and search")
    print("  • AnalyticsAgent: Statistics and reporting")
    print("  • RecommendationAgent: Book suggestions with quality filters")
    print()
    print("Coordinator:")
    print("  • OrchestratorAgent: Analyzes queries, plans execution, chains agents")
    print()
    print("Commands:")
    print("  /tools     - Show available tools/API functions")
    print("  /agents    - Show registered agents")
    print("  /rag       - Toggle RAG/semantic search")
    print("  /verbose   - Toggle verbose logging (currently ON)")
    print("  /stats     - Show token usage and statistics")
    print("  /logs      - Show agent activity logs")
    print("  /reset     - Reset statistics and logs")
    print("  /help      - Show this help message")
    print("  /quit      - Exit")
    print()
    print("Example queries:")
    print('  • "Find books about Adventures"')
    print('  • "How many books are missing?"')
    print('  • "Recommend fiction books by the author who has the most books"')
    print('  • "Find science books, count them, and recommend the best"')
    print("=" * 60)
    print()

    try:
        orchestrator = OrchestratorAgent(verbose=True)
    except Exception as e:
        print(f"Error initializing orchestrator: {e}")
        print("Make sure your database and LLM configuration are set up correctly.")
        sys.exit(1)

    while True:
        try:
            user_input = input("\nYou: ").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.startswith("/"):
                cmd = user_input.lower()

                if cmd in ["/quit", "/exit", "/q"]:
                    orchestrator.print_stats()
                    print("\nGoodbye!")
                    break

                elif cmd == "/help":
                    print("\nCommands:")
                    print("  /tools   - Show available tools/API functions")
                    print("  /agents  - Show registered agents")
                    print("  /rag     - Toggle RAG/semantic search")
                    print("  /verbose - Toggle verbose logging")
                    print("  /stats   - Show token usage and statistics")
                    print("  /logs    - Show agent activity logs")
                    print("  /reset   - Reset statistics and logs")
                    print("  /help    - Show this help")
                    print("  /quit    - Exit")
                    continue

                elif cmd == "/tools":
                    orchestrator.print_tools()
                    continue

                elif cmd == "/rag":
                    orchestrator.set_rag(not orchestrator.enable_rag)
                    continue

                elif cmd == "/agents":
                    print("\nWorker Agents:")
                    for agent in orchestrator.get_agents():
                        print(f"  • {agent['name']}")
                        print(f"    Capabilities: {', '.join(agent['capabilities'])}")
                        print(f"    Description: {agent['description']}")
                    print("\nCoordinator:")
                    print("  • orchestrator_agent")
                    print("    Capabilities: planning, delegation, chaining")
                    print(
                        "    Description: LLM-powered coordinator that analyzes queries and delegates to worker agents"
                    )
                    continue

                elif cmd == "/stats":
                    orchestrator.print_stats()
                    continue

                elif cmd == "/logs":
                    orchestrator.print_logs()
                    continue

                elif cmd.startswith("/logs "):
                    try:
                        n = int(cmd.split()[1])
                        orchestrator.print_logs(last_n=n)
                    except (ValueError, IndexError):
                        print("Usage: /logs [number]")
                    continue

                elif cmd == "/verbose":
                    orchestrator.set_verbose(not orchestrator.verbose)
                    continue

                elif cmd == "/reset":
                    orchestrator.reset_stats()
                    continue

                else:
                    print(f"Unknown command: {user_input}")
                    print("Type /help for available commands")
                    continue

            # Process query
            result = orchestrator.query(user_input)
            print()
            print(f"Assistant:\n{result['response']}")

        except KeyboardInterrupt:
            print("\n")
            orchestrator.print_stats()
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")

    orchestrator.close()


if __name__ == "__main__":
    run_interactive_cli()
