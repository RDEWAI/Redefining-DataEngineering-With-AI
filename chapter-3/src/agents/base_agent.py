"""Base agent class with code execution support.

All specialized agents inherit from this base class which provides:
- LLM integration for code generation
- Code sandbox for safe execution
- API functions injected into the sandbox
- Token usage tracking

This follows the Anthropic pattern where code execution is preferred
over traditional tool calling for token efficiency.
"""

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.a2a.protocol import AgentMessage, AgentStatus, QueryType
from src.code_execution.sandbox import CodeSandbox
from src.code_execution.tool_api import ToolAPIGenerator
from src.library.repository import get_repository
from src.llm.base import LLMProvider, LLMResponse, Message
from src.llm.unified_client import UnifiedLLMClient

# Load .env from chapter-3 directory
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path, override=True)


@dataclass
class AgentTokenUsage:
    """Track token usage for an agent."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    query_count: int = 0
    code_executions: int = 0
    last_query_tokens: int = 0

    def add(self, response: LLMResponse) -> None:
        """Add tokens from an LLM response."""
        usage = response.usage or {}
        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.last_query_tokens = prompt + completion

    def increment_query(self) -> None:
        """Increment query count."""
        self.query_count += 1

    def increment_code_execution(self) -> None:
        """Increment code execution count."""
        self.code_executions += 1

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "query_count": self.query_count,
            "code_executions": self.code_executions,
            "last_query_tokens": self.last_query_tokens,
        }

    def reset(self) -> None:
        """Reset all counters."""
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.query_count = 0
        self.code_executions = 0
        self.last_query_tokens = 0


@dataclass
class AgentLogEntry:
    """A log entry for agent activity."""

    timestamp: datetime
    agent_name: str
    event: str
    details: str = ""
    tokens_used: int = 0
    duration_ms: int = 0


@dataclass
class AgentLogger:
    """Logger for agent activity."""

    entries: list[AgentLogEntry] = field(default_factory=list)
    enabled: bool = True

    def log(
        self,
        agent_name: str,
        event: str,
        details: str = "",
        tokens_used: int = 0,
        duration_ms: int = 0,
    ) -> None:
        """Add a log entry."""
        if self.enabled:
            self.entries.append(
                AgentLogEntry(
                    timestamp=datetime.now(),
                    agent_name=agent_name,
                    event=event,
                    details=details,
                    tokens_used=tokens_used,
                    duration_ms=duration_ms,
                )
            )

    def get_entries(self, agent_name: str | None = None) -> list[AgentLogEntry]:
        """Get log entries, optionally filtered by agent."""
        if agent_name:
            return [e for e in self.entries if e.agent_name == agent_name]
        return self.entries

    def clear(self) -> None:
        """Clear all log entries."""
        self.entries = []


class BaseCodeExecutionAgent:
    """Base agent class that uses code execution for all operations.

    This base class provides:
    - LLM-driven code generation
    - Safe code execution in a sandbox
    - API functions available in the execution context
    - Token usage tracking

    Subclasses should:
    1. Set `name` and `capabilities` class attributes
    2. Override `_get_system_prompt()` to provide specialized instructions
    3. Optionally override `_post_process_result()` for custom result handling

    Example:
        >>> class MyAgent(BaseCodeExecutionAgent):
        ...     name = "my_agent"
        ...     capabilities = [QueryType.SEARCH]
        ...
        ...     def _get_system_prompt(self) -> str:
        ...         return "You are a specialized search agent..."
    """

    name: str = "base_agent"
    capabilities: list[QueryType] = []

    def __init__(
        self,
        db_path: str | None = None,
        llm_provider: LLMProvider | None = None,
        verbose: bool = False,
        enable_rag: bool = True,
        logger: AgentLogger | None = None,
        tools: list[str] | None = None,
    ) -> None:
        """Initialize the base agent.

        Args:
            db_path: Path to DuckDB database. If None, uses default.
            llm_provider: LLM provider for code generation. If None, uses UnifiedLLMClient.
            verbose: Whether to print debug information.
            enable_rag: Whether to include semantic search in available functions.
            logger: Shared logger for agent activity. If None, creates a new one.
            tools: Optional list of specific tools for this agent. If None, all tools
                   are available (backward compatible). Use this for agent specialization.
        """
        if db_path is None:
            db_path = os.getenv(
                "DB_PATH",
                str(Path(__file__).parent.parent.parent / "data" / "duckdb" / "chapter3.db"),
            )

        self.db_path = db_path
        self.verbose = verbose
        self.enable_rag = enable_rag
        self.tools = tools  # Agent-specific tools (None = all tools)

        # Initialize LLM provider
        self._llm_provider: LLMProvider
        if llm_provider is None:
            self._llm_provider = UnifiedLLMClient.from_env()
        else:
            self._llm_provider = llm_provider

        # Initialize code execution components
        self._repository = get_repository(db_path, read_only=True)
        self._sandbox = CodeSandbox()
        self._tool_api_generator = ToolAPIGenerator(
            self._repository,
            db_path=db_path,
            include_rag=enable_rag,
            include_dummy_tools=False,
            tools=tools,  # Pass agent-specific tools for specialization
        )

        # Conversation history for multi-turn code generation
        self._conversation_history: list[Message] = []

        # Token tracking
        self._token_usage = AgentTokenUsage()

        # Shared logger
        self._logger = logger if logger else AgentLogger()

    def can_handle(self, query_type: QueryType) -> bool:
        """Check if this agent can handle the given query type."""
        return query_type in self.capabilities

    def _get_system_prompt(self) -> str:
        """Get the system prompt for this agent.

        Subclasses should override this to provide specialized instructions.

        Returns:
            System prompt string for code generation.
        """
        raise NotImplementedError("Subclasses must implement _get_system_prompt()")

    def _get_api_functions(self) -> str:
        """Get the API functions code to inject into the sandbox.

        Returns:
            Python code string with API function definitions.
        """
        discovery_code = self._tool_api_generator.generate_discovery_functions()
        api_functions = self._tool_api_generator.generate_api_code(include_setup=False)
        return discovery_code + "\n\n" + api_functions

    def process(self, message: AgentMessage) -> AgentMessage:
        """Process a message using code execution.

        Args:
            message: The incoming message to process.

        Returns:
            Response message with results or error.
        """
        import time

        start_time = time.time()
        self._token_usage.increment_query()

        try:
            # Reset conversation for new message
            self._conversation_history = [Message(role="system", content=self._get_system_prompt())]

            # Parse the query from message content
            if isinstance(message.content, str):
                query = message.content
            elif isinstance(message.content, dict):
                query = message.content.get("query", str(message.content))
            else:
                query = str(message.content)

            # Log agent invocation
            self._logger.log(
                agent_name=self.name,
                event="INVOKED",
                details=f"Query: {query[:100]}{'...' if len(query) > 100 else ''}",
            )

            # Add user query to conversation
            self._conversation_history.append(Message(role="user", content=query))

            # Generate and execute code
            result = self._generate_and_execute(query)

            duration_ms = int((time.time() - start_time) * 1000)

            if result["success"]:
                self._logger.log(
                    agent_name=self.name,
                    event="COMPLETED",
                    details=f"Output length: {len(result['output'])} chars",
                    tokens_used=self._token_usage.last_query_tokens,
                    duration_ms=duration_ms,
                )
                return message.create_response(
                    sender=self.name,
                    content=result["output"],
                    status=AgentStatus.COMPLETED,
                )
            else:
                self._logger.log(
                    agent_name=self.name,
                    event="FAILED",
                    details=result.get("error", "Unknown error"),
                    tokens_used=self._token_usage.last_query_tokens,
                    duration_ms=duration_ms,
                )
                return message.create_response(
                    sender=self.name,
                    content=None,
                    status=AgentStatus.FAILED,
                    error=result.get("error", "Unknown error"),
                )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self._logger.log(
                agent_name=self.name,
                event="ERROR",
                details=str(e),
                duration_ms=duration_ms,
            )
            return message.create_response(
                sender=self.name,
                content=None,
                status=AgentStatus.FAILED,
                error=f"Agent error: {str(e)}",
            )

    def _generate_and_execute(self, _query: str, max_iterations: int = 2) -> dict[str, Any]:
        """Generate code using LLM and execute it.

        Args:
            query: The user's query.
            max_iterations: Maximum code generation/execution attempts.

        Returns:
            Dict with success status and output or error.
        """
        self._token_usage.last_query_tokens = 0

        for iteration in range(max_iterations):
            # Generate code
            response = self._llm_provider.generate(
                messages=self._conversation_history,
                temperature=0.0,
            )

            # Track tokens
            self._token_usage.add(response)

            # Extract code from response
            code = self._extract_code(response.content or "")

            if not code:
                # No code generated - return the text response
                return {
                    "success": True,
                    "output": response.content or "No response generated.",
                }

            if self.verbose:
                print()
                print(f"   💻 [{self.name}] Generated Code:")
                print("   " + "─" * 50)
                # Indent code for cleaner display
                for line in code.split("\n"):
                    print(f"      {line}")
                print("   " + "─" * 50)

            # Log code generation
            self._logger.log(
                agent_name=self.name,
                event="CODE_GENERATED",
                details=f"Iteration {iteration + 1}, {len(code)} chars",
            )

            # Execute code
            api_code = self._get_api_functions()
            result = self._sandbox.execute(code, db_path=self.db_path, api_code=api_code)
            self._token_usage.increment_code_execution()

            if result["success"]:
                output = result["stdout"].strip()
                if output:
                    self._logger.log(
                        agent_name=self.name,
                        event="CODE_EXECUTED",
                        details=f"Success, output: {len(output)} chars",
                    )
                    return {"success": True, "output": output}
                else:
                    # Empty output - ask LLM to fix
                    self._conversation_history.append(
                        Message(role="assistant", content=response.content or "")
                    )
                    self._conversation_history.append(
                        Message(
                            role="user",
                            content="The code executed but produced no output. Please add print() statements to show results.",
                        )
                    )
            else:
                # Execution error - ask LLM to fix
                error = result["stderr"]
                self._logger.log(
                    agent_name=self.name,
                    event="CODE_ERROR",
                    details=f"Error: {error[:100]}",
                )
                self._conversation_history.append(
                    Message(role="assistant", content=response.content or "")
                )
                self._conversation_history.append(
                    Message(
                        role="user",
                        content=f"Code execution error:\n{error}\n\nPlease fix the code.",
                    )
                )

        return {
            "success": False,
            "error": "Failed to generate working code after multiple attempts.",
        }

    def _extract_code(self, response: str) -> str:
        """Extract Python code from LLM response.

        Args:
            response: LLM response text.

        Returns:
            Extracted code or empty string if no code block found.
        """
        if "```python" in response:
            start = response.find("```python") + len("```python")
            end = response.find("```", start)
            if end != -1:
                return response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + len("```")
            end = response.find("```", start)
            if end != -1:
                return response[start:end].strip()
        return ""

    def get_token_usage(self) -> dict[str, int]:
        """Get token usage statistics.

        Returns:
            Dictionary with token counts.
        """
        return self._token_usage.to_dict()

    def reset_stats(self) -> None:
        """Reset token usage statistics."""
        self._token_usage.reset()

    def query(self, user_query: str) -> dict[str, Any]:
        """Convenience method for direct querying.

        Args:
            user_query: The user's query string.

        Returns:
            Dict with query results.
        """
        message = AgentMessage.create(
            sender="user",
            recipient=self.name,
            query_type=self.capabilities[0] if self.capabilities else QueryType.SEARCH,
            content=user_query,
        )
        response = self.process(message)

        return {
            "success": response.status == AgentStatus.COMPLETED,
            "output": response.content,
            "error": response.error,
        }

    def close(self) -> None:
        """Clean up resources."""
        self._repository.close()
