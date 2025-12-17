"""Library Assistant with traditional JSON schema tool use.

This module implements a Library Assistant that uses traditional JSON schema
tools for baseline token measurement. It supports multi-turn conversations,
token usage logging, and both OpenRouter and Ollama backends.

The assistant demonstrates the traditional tool use pattern as described
in the Anthropic tool use documentation, serving as a baseline for
comparison with code execution patterns.
"""

import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load .env from chapter-3 directory (override=True to replace existing env vars)
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path, override=True)

# Add parent directory to path for imports
# Add both src/ and chapter-3/ to support both import styles
sys.path.insert(0, str(Path(__file__).parent.parent))  # src/
sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # chapter-3/

from library import tools as library_tools  # noqa: E402
from llm.base import (  # noqa: E402
    LLMProvider,
    LLMResponse,
    Message,
    ToolCall,
    ToolDefinition,
)
from logging_config import get_logger  # noqa: E402
from tools.dummy_tools import (  # noqa: E402
    generate_dummy_tool_definitions,
    get_dummy_tool_functions,
)

# Initialize logger
logger = get_logger("chapter3.agents.library_assistant")

# System prompt for the Library Assistant
SYSTEM_PROMPT = """You are a helpful Library Assistant with access to a library management system.

You can help users with:
- Searching for books by title, author, or keyword
- Checking book availability and location
- Getting library statistics
- Finding books by category or status
- Locating books in specific cabinets and racks
- Identifying books with weak RFID signal that may need maintenance

When answering questions, use the available tools to get accurate information.
Always provide helpful, concise responses based on the tool results.

If a user asks about something you cannot help with (not related to the library),
politely explain that you're a Library Assistant focused on library-related queries.
"""

# Tool definitions matching contracts/llm-tools.json
TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="search_books",
        description="Search books by title, author, or keyword. Returns matching books with their availability status and location.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to match against title or author",
                },
                "category": {
                    "type": "string",
                    "enum": ["Programming", "History", "Science", "Fiction", "Thriller"],
                    "description": "Optional category filter",
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "description": "Maximum number of results",
                },
            },
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="get_book_details",
        description="Get complete details for a specific book including physical location, RFID signal strength, and availability status.",
        parameters={
            "type": "object",
            "properties": {
                "book_id": {
                    "type": "string",
                    "description": "Book ID (e.g., 'B001')",
                },
            },
            "required": ["book_id"],
        },
    ),
    ToolDefinition(
        name="check_availability",
        description="Check if a book is available for checkout and get its current shelf location.",
        parameters={
            "type": "object",
            "properties": {
                "book_id": {
                    "type": "string",
                    "description": "Book ID to check",
                },
            },
            "required": ["book_id"],
        },
    ),
    ToolDefinition(
        name="list_by_category",
        description="List all books in a specific category with optional status filter.",
        parameters={
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["Programming", "History", "Science", "Fiction", "Thriller"],
                    "description": "Category to filter by",
                },
                "status": {
                    "type": "string",
                    "enum": ["Present", "Missing", "Checked Out"],
                    "description": "Optional status filter",
                },
            },
            "required": ["category"],
        },
    ),
    ToolDefinition(
        name="list_by_status",
        description="List all books with a specific availability status.",
        parameters={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["Present", "Missing", "Checked Out"],
                    "description": "Status to filter by",
                },
                "category": {
                    "type": "string",
                    "enum": ["Programming", "History", "Science", "Fiction", "Thriller"],
                    "description": "Optional category filter",
                },
            },
            "required": ["status"],
        },
    ),
    ToolDefinition(
        name="locate_book",
        description="Get the physical location of a book (Cabinet, Rack, Row number).",
        parameters={
            "type": "object",
            "properties": {
                "book_id": {
                    "type": "string",
                    "description": "Book ID to locate",
                },
            },
            "required": ["book_id"],
        },
    ),
    ToolDefinition(
        name="find_books_in_cabinet",
        description="List all books in a specific cabinet, optionally filtered by rack.",
        parameters={
            "type": "object",
            "properties": {
                "cabinet": {
                    "type": "integer",
                    "description": "Cabinet number",
                },
                "rack": {
                    "type": "integer",
                    "description": "Optional rack number within cabinet",
                },
            },
            "required": ["cabinet"],
        },
    ),
    ToolDefinition(
        name="get_weak_signal_books",
        description="Get books with weak RFID signal strength that may need maintenance or relocation.",
        parameters={
            "type": "object",
            "properties": {
                "threshold": {
                    "type": "number",
                    "default": -55,
                    "description": "Signal strength threshold in dBm (default: -55, weaker signals are below this)",
                },
            },
            "required": [],
        },
    ),
    ToolDefinition(
        name="get_library_stats",
        description="Get aggregate statistics about the library: total books, counts by category, counts by status.",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
]

# RAG tool definition (added separately so it can be toggled)
SEMANTIC_SEARCH_TOOL = ToolDefinition(
    name="semantic_search",
    description="Search books using natural language semantic similarity. Use this when the user asks about books 'about' a topic, 'like' something, or uses vague/conceptual descriptions. Examples: 'books about time travel', 'something like Harry Potter', 'programming tutorials for beginners'. NOT for structured queries that need counting or aggregation.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language search query describing what the user is looking for",
            },
            "top_k": {
                "type": "integer",
                "default": 5,
                "description": "Maximum number of results (default 5)",
            },
        },
        "required": ["query"],
    },
)

# Mapping from tool names to implementation functions
TOOL_FUNCTION_MAP: dict[str, Callable[..., dict[str, Any]]] = {
    "search_books": library_tools.search_books,
    "get_book_details": library_tools.get_book_details,
    "check_availability": library_tools.check_availability,
    "list_by_category": library_tools.list_by_category,
    "list_by_status": library_tools.list_by_status,
    "locate_book": library_tools.locate_book,
    "find_books_in_cabinet": library_tools.find_books_in_cabinet,
    "get_weak_signal_books": library_tools.get_weak_signal_books,
    "get_library_stats": library_tools.get_library_stats,
    "semantic_search": library_tools.semantic_search,
}


def get_tools_for_llm(
    include_rag: bool = False,
    include_dummy_tools: bool = False,
) -> list[dict[str, Any]]:
    """Get tool definitions in OpenAI/LLM format.

    Args:
        include_rag: If True, include the semantic_search RAG tool.
        include_dummy_tools: If True, include 100 enterprise dummy tools.

    Returns:
        List of tool definitions in the format expected by OpenAI-compatible APIs.
    """
    tools = [tool.to_openai_format() for tool in TOOL_DEFINITIONS]
    if include_rag:
        tools.append(SEMANTIC_SEARCH_TOOL.to_openai_format())
    if include_dummy_tools:
        dummy_defs = generate_dummy_tool_definitions()
        tools.extend([t.to_openai_format() for t in dummy_defs])
    return tools


def get_tool_function(
    name: str,
    include_dummy_tools: bool = False,
) -> Callable[..., dict[str, Any]]:
    """Get the implementation function for a tool.

    Args:
        name: Tool name
        include_dummy_tools: If True, also search dummy tool functions

    Returns:
        The callable function that implements the tool

    Raises:
        ValueError: If the tool name is unknown
    """
    if name in TOOL_FUNCTION_MAP:
        return TOOL_FUNCTION_MAP[name]

    if include_dummy_tools:
        dummy_funcs = get_dummy_tool_functions()
        if name in dummy_funcs:
            func: Callable[..., dict[str, Any]] = dummy_funcs[name]
            return func

    raise ValueError(f"Unknown tool: {name}")


@dataclass
class TokenUsage:
    """Track token usage across queries."""

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    query_count: int = 0
    tool_calls_count: int = 0

    def add(self, response: LLMResponse) -> None:
        """Add tokens from a response."""
        usage = response.usage or {}
        self.total_prompt_tokens += usage.get("prompt_tokens", 0)
        self.total_completion_tokens += usage.get("completion_tokens", 0)

    def add_tool_calls(self, count: int) -> None:
        """Record tool calls."""
        self.tool_calls_count += count

    def increment_query(self) -> None:
        """Increment the query count."""
        self.query_count += 1

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "query_count": self.query_count,
            "tool_calls_count": self.tool_calls_count,
        }

    def reset(self) -> None:
        """Reset all counters."""
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.query_count = 0
        self.tool_calls_count = 0


class LibraryAssistant:
    """Library Assistant with traditional JSON schema tool use.

    This assistant uses traditional tool calling patterns with JSON schemas
    for function definitions. It supports multi-turn conversations and
    tracks token usage for comparison with code execution patterns.

    Args:
        llm_provider: The LLM provider to use (OpenRouter or Ollama)
        system_prompt: Custom system prompt (defaults to SYSTEM_PROMPT)
        max_tool_iterations: Maximum number of tool calling rounds per query
        verbose: Whether to print debug information
        show_tool_calls: Whether to display tool calls (educational output, default True)
        enable_dummy_tools: Whether to include 100 enterprise dummy tools (for scale demo)

    Example:
        >>> from llm.openrouter_client import OpenRouterProvider
        >>> provider = OpenRouterProvider()
        >>> assistant = LibraryAssistant(llm_provider=provider)
        >>> response = assistant.query("What programming books are available?")
        >>> print(response)
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        system_prompt: str | None = None,
        max_tool_iterations: int = 10,
        verbose: bool = False,
        show_tool_calls: bool = True,
        enable_rag: bool = False,
        enable_dummy_tools: bool = False,
    ) -> None:
        """Initialize the Library Assistant."""
        self._provider = llm_provider
        self._system_prompt = system_prompt or SYSTEM_PROMPT
        self._max_tool_iterations = max_tool_iterations
        self._verbose = verbose
        self._show_tool_calls = show_tool_calls
        self._enable_rag = enable_rag
        self._enable_dummy_tools = enable_dummy_tools
        self._token_usage = TokenUsage()

        # Get tools based on RAG and dummy tools settings
        self._tools = self._get_tool_definitions()

        # Initialize conversation with system message
        self._conversation_history: list[Message] = [
            Message(role="system", content=self._system_prompt)
        ]

    def _get_tool_definitions(self) -> list[ToolDefinition]:
        """Get the list of tool definitions based on RAG and dummy tools settings."""
        tools = list(TOOL_DEFINITIONS)
        if self._enable_rag:
            tools.append(SEMANTIC_SEARCH_TOOL)
        if self._enable_dummy_tools:
            tools.extend(generate_dummy_tool_definitions())
        return tools

    def set_rag_enabled(self, enabled: bool) -> None:
        """Enable or disable RAG (semantic search) tool.

        Args:
            enabled: Whether to enable RAG
        """
        self._enable_rag = enabled
        self._tools = self._get_tool_definitions()

    def is_rag_enabled(self) -> bool:
        """Check if RAG is enabled.

        Returns:
            True if RAG is enabled
        """
        return self._enable_rag

    def set_dummy_tools_enabled(self, enabled: bool) -> None:
        """Enable or disable enterprise dummy tools.

        Args:
            enabled: Whether to enable dummy tools (100 tools across 10 domains)
        """
        self._enable_dummy_tools = enabled
        self._tools = self._get_tool_definitions()

    def is_dummy_tools_enabled(self) -> bool:
        """Check if dummy tools are enabled.

        Returns:
            True if dummy tools are enabled
        """
        return self._enable_dummy_tools

    def get_tool_count(self) -> int:
        """Get the current number of tools available.

        Returns:
            Number of tool definitions currently loaded
        """
        return len(self._tools)

    def query(self, user_input: str) -> str:
        """Process a user query and return a response.

        This method handles the complete query cycle including:
        - Adding the user message to conversation history
        - Calling the LLM with tools
        - Executing any tool calls
        - Continuing until a final text response is received
        - Tracking token usage

        Args:
            user_input: The user's question or request

        Returns:
            The assistant's response text

        Example:
            >>> response = assistant.query("Find Python programming books")
            >>> print(response)
        """
        logger.info(
            "Processing query",
            extra={
                "query_length": len(user_input),
                "mode": "traditional",
                "tool_count": len(self._tools),
                "rag_enabled": self._enable_rag,
                "dummy_tools_enabled": self._enable_dummy_tools,
            },
        )

        # Add user message to history
        self._conversation_history.append(Message(role="user", content=user_input))
        self._token_usage.increment_query()

        # Tool calling loop
        iterations = 0
        while iterations < self._max_tool_iterations:
            iterations += 1

            if self._verbose:
                print(f"[Iteration {iterations}] Calling LLM...")

            # Show LLM call (educational output)
            if self._show_tool_calls:
                model_name = self._provider.default_model
                if iterations == 1:
                    print()
                    print(f"🤖 LLM Call #{iterations} → {model_name}")
                    print("   └─ Analyzing query and deciding on tools...")
                else:
                    print(f"🤖 LLM Call #{iterations} → {model_name}")
                    print("   └─ Processing tool results and generating response...")

            # Call the LLM
            response = self._provider.generate(
                messages=self._conversation_history,
                tools=self._tools,
                tool_choice="auto",
            )

            # Track token usage
            self._token_usage.add(response)

            # If no tool calls, we have a final response
            if not response.has_tool_calls:
                if self._show_tool_calls:
                    print("   ✓ Response ready (no more tool calls needed)")
                    print()
                final_content = (
                    response.content or "I apologize, but I couldn't generate a response."
                )
                self._conversation_history.append(Message(role="assistant", content=final_content))
                return final_content

            # Show tool decision (educational output)
            if self._show_tool_calls:
                print(f"   → Decided to call {len(response.tool_calls)} tool(s)")
                print()

            # Process tool calls
            if self._verbose:
                print(
                    f"[Iteration {iterations}] Processing {len(response.tool_calls)} tool call(s)"
                )

            # Show tool calls to user (educational output)
            if self._show_tool_calls:
                print(
                    f"🔧 Tool Call{'s' if len(response.tool_calls) > 1 else ''} ({len(response.tool_calls)}):"
                )
                print("-" * 40)

            # Add assistant message with tool calls
            tool_calls_dict = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": tc.arguments,
                    },
                }
                for tc in response.tool_calls
            ]
            self._conversation_history.append(
                Message(
                    role="assistant",
                    content=response.content,
                    tool_calls=tool_calls_dict,
                )
            )

            # Execute each tool call and add results
            for tool_call in response.tool_calls:
                # Show tool call details (educational)
                if self._show_tool_calls:
                    args = json.loads(tool_call.arguments) if tool_call.arguments else {}
                    print(f"  📞 Calling: {tool_call.name}()")
                    if args:
                        for key, value in args.items():
                            print(f"     └─ {key}: {value}")

                result = self._execute_tool(tool_call)

                # Show tool result summary (educational)
                if self._show_tool_calls:
                    if result.get("success", False):
                        msg = result.get("message", "Success")
                        print(f"  ✅ Result: {msg}")
                    else:
                        msg = result.get("message", "Failed")
                        print(f"  ❌ Result: {msg}")
                    print()

                self._conversation_history.append(
                    Message(
                        role="tool",
                        content=json.dumps(result),
                        tool_call_id=tool_call.id,
                        name=tool_call.name,
                    )
                )
                self._token_usage.add_tool_calls(1)

        # Max iterations reached
        return (
            "I apologize, but I've reached the maximum number of operations. "
            "Please try rephrasing your question or breaking it into smaller parts."
        )

    def _execute_tool(self, tool_call: ToolCall) -> dict[str, Any]:
        """Execute a single tool call.

        Args:
            tool_call: The tool call to execute

        Returns:
            The result of the tool execution
        """
        tool_name = tool_call.name

        if self._verbose:
            print(f"  Executing tool: {tool_name}")
            print(f"  Arguments: {tool_call.arguments}")

        try:
            # Get the tool function (check dummy tools if enabled)
            func = get_tool_function(
                tool_name,
                include_dummy_tools=self._enable_dummy_tools,
            )
        except ValueError as e:
            available = list(TOOL_FUNCTION_MAP.keys())
            if self._enable_dummy_tools:
                available.append("(+100 dummy tools)")
            return {
                "success": False,
                "error": str(e),
                "message": f"Unknown tool '{tool_name}'. Available: {', '.join(available)}",
            }

        try:
            # Parse arguments
            args = json.loads(tool_call.arguments) if tool_call.arguments else {}

            # Execute the tool
            result = func(**args)

            if self._verbose:
                print(f"  Result: {json.dumps(result, indent=2)[:200]}...")

            return result

        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Invalid JSON arguments: {str(e)}",
                "message": "The tool arguments could not be parsed. Please provide valid JSON.",
            }
        except TypeError as e:
            return {
                "success": False,
                "error": f"Invalid arguments: {str(e)}",
                "message": f"The tool '{tool_name}' received invalid arguments. Error: {str(e)}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"An error occurred while executing '{tool_name}': {str(e)}",
            }

    def get_token_usage(self) -> dict[str, int]:
        """Get the current token usage statistics.

        Returns:
            Dictionary with token usage counts
        """
        return self._token_usage.to_dict()

    def reset_token_usage(self) -> None:
        """Reset token usage counters to zero."""
        self._token_usage.reset()

    def clear_conversation(self) -> None:
        """Clear conversation history, keeping only the system message."""
        self._conversation_history = [Message(role="system", content=self._system_prompt)]

    def get_conversation_history(self) -> list[dict[str, Any]]:
        """Get the current conversation history.

        Returns:
            List of messages in the conversation
        """
        return [msg.to_dict() for msg in self._conversation_history]


def create_assistant(
    provider: str = "openrouter",
    model: str | None = None,
    verbose: bool = False,
    enable_dummy_tools: bool = False,
) -> LibraryAssistant:
    """Create a Library Assistant with the specified provider.

    Args:
        provider: LLM provider to use (deprecated - now uses UnifiedLLMClient)
        model: Model to use (deprecated - now uses LLM_MODEL env var)
        verbose: Whether to print debug information
        enable_dummy_tools: Whether to enable 100 enterprise dummy tools for scale demo

    Returns:
        Configured LibraryAssistant instance

    Raises:
        ValueError: If the provider is not supported
    """
    # Use UnifiedLLMClient for consistency with enhanced assistant
    from llm.unified_client import UnifiedLLMClient

    llm_provider = UnifiedLLMClient.from_env()
    return LibraryAssistant(
        llm_provider=llm_provider, verbose=verbose, enable_dummy_tools=enable_dummy_tools
    )


def interactive_repl(enable_rag: bool = False, enable_dummy_tools: bool = False) -> None:
    """Run an interactive REPL for the Library Assistant.

    This function starts an interactive session where users can
    query the Library Assistant and see responses in real-time.

    Args:
        enable_rag: If True, enable RAG/semantic search by default
        enable_dummy_tools: If True, enable 100 enterprise dummy tools for scale demo
    """
    mode_str = "RAG Mode" if enable_rag else "Traditional Mode"
    if enable_dummy_tools:
        mode_str = f"{mode_str} + Enterprise Dummy Tools"
    print(f"Library Assistant - {mode_str}")
    print("=" * 50)
    print()

    # Show configuration from environment
    base_url = os.getenv("LLM_BASE_URL", "not set")
    model = os.getenv("LLM_MODEL", "not set")

    print(f"Base URL: {base_url}")
    print(f"Model: {model}")
    if enable_rag:
        print("RAG: ENABLED (semantic_search tool available)")
    if enable_dummy_tools:
        print("Dummy Tools: ENABLED (100 enterprise tools across 10 domains)")
    print()

    try:
        assistant = create_assistant(verbose=False, enable_dummy_tools=enable_dummy_tools)
        if enable_rag:
            assistant.set_rag_enabled(True)
    except Exception as e:
        print(f"Error: {e}")
        print()
        print("Please ensure your LLM configuration is set in .env:")
        print("  LLM_BASE_URL=your-api-base-url")
        print("  LLM_API_KEY=your-api-key")
        print("  LLM_MODEL=your-model-name")
        sys.exit(1)

    rag_status = "ON" if enable_rag else "OFF"
    tool_count = assistant.get_tool_count()
    dummy_status = "ON" if assistant.is_dummy_tools_enabled() else "OFF"
    print(f"Tools: {tool_count} available")
    if assistant.is_dummy_tools_enabled():
        print("  └─ 100 enterprise dummy tools ENABLED for scale demo")
    print()
    print("Commands:")
    print("  /help        - Show this help message")
    print("  /settings    - Show current settings")
    print("  /stats       - Show token usage statistics")
    print("  /tools       - Toggle tool call display (currently: ON)")
    print(f"  /rag         - Toggle semantic search/RAG (currently: {rag_status})")
    print(f"  /dummy-tools - Toggle 100 enterprise dummy tools (currently: {dummy_status})")
    print("  /clear       - Clear conversation history")
    print("  /reset       - Reset token usage counters")
    print("  /quit        - Exit the assistant")
    print()
    print("Ask me anything about the library!")
    print("-" * 50)
    print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        # Handle commands
        if user_input.startswith("/"):
            command = user_input.lower()

            if command == "/help":
                tools_status = "ON" if assistant._show_tool_calls else "OFF"
                rag_status = "ON" if assistant.is_rag_enabled() else "OFF"
                dummy_status = "ON" if assistant.is_dummy_tools_enabled() else "OFF"
                print()
                print("Commands:")
                print("  /help        - Show this help message")
                print("  /settings    - Show current settings")
                print("  /stats       - Show token usage statistics")
                print(f"  /tools       - Toggle tool call display (currently: {tools_status})")
                print(f"  /rag         - Toggle semantic search/RAG (currently: {rag_status})")
                print(
                    f"  /dummy-tools - Toggle 100 enterprise dummy tools (currently: {dummy_status})"
                )
                print("  /clear       - Clear conversation history")
                print("  /reset       - Reset token usage counters")
                print("  /quit        - Exit the assistant")
                print()
                continue

            if command == "/settings":
                tools_status = "ON" if assistant._show_tool_calls else "OFF"
                rag_status = "ON" if assistant.is_rag_enabled() else "OFF"
                dummy_status = "ON" if assistant.is_dummy_tools_enabled() else "OFF"
                tool_count = assistant.get_tool_count()
                print()
                print("Current Settings:")
                print("-" * 40)
                print("  Mode:          Traditional (JSON tools)")
                print(f"  RAG:           {rag_status}")
                print(f"  Dummy Tools:   {dummy_status}")
                print(f"  Tool Count:    {tool_count}")
                print(f"  Tool Display:  {tools_status}")
                print(f"  Base URL:      {os.getenv('LLM_BASE_URL', 'not set')}")
                print(f"  Model:         {os.getenv('LLM_MODEL', 'not set')}")
                print("-" * 40)
                print()
                continue

            if command == "/tools":
                assistant._show_tool_calls = not assistant._show_tool_calls
                status = "ON" if assistant._show_tool_calls else "OFF"
                print(f"Tool call display: {status}")
                print()
                continue

            if command == "/rag":
                new_rag_status = not assistant.is_rag_enabled()
                assistant.set_rag_enabled(new_rag_status)
                status = "ON" if new_rag_status else "OFF"
                print(f"Semantic search (RAG): {status}")
                if new_rag_status:
                    print(
                        "  The assistant can now use semantic_search for natural language queries."
                    )
                    print("  Try: 'Find books about time travel' or 'something like Harry Potter'")
                print()
                continue

            if command == "/dummy-tools":
                new_dummy_status = not assistant.is_dummy_tools_enabled()
                assistant.set_dummy_tools_enabled(new_dummy_status)
                status = "ON" if new_dummy_status else "OFF"
                tool_count = assistant.get_tool_count()
                print(f"Enterprise dummy tools: {status}")
                print(f"  Total tools available: {tool_count}")
                if new_dummy_status:
                    print("  100 enterprise tools added across 10 domains:")
                    print("    Engineering, Data Platform, Security, HR, Finance,")
                    print("    Marketing, Sales, Support, Infrastructure, ML Platform")
                    print()
                    print("  This demonstrates token overhead at enterprise scale.")
                    print("  Compare with code execution mode for 80%+ token reduction.")
                print()
                continue

            if command == "/stats":
                usage = assistant.get_token_usage()
                print()
                print("Token Usage Statistics:")
                print(f"  Queries: {usage['query_count']}")
                print(f"  Tool calls: {usage['tool_calls_count']}")
                print(f"  Prompt tokens: {usage['total_prompt_tokens']}")
                print(f"  Completion tokens: {usage['total_completion_tokens']}")
                print(f"  Total tokens: {usage['total_tokens']}")
                print()
                continue

            if command == "/clear":
                assistant.clear_conversation()
                print("Conversation history cleared.")
                print()
                continue

            if command == "/reset":
                assistant.reset_token_usage()
                print("Token usage counters reset.")
                print()
                continue

            if command in ("/quit", "/exit", "/q"):
                print("Goodbye!")
                break

            print(f"Unknown command: {user_input}")
            print("Type /help for available commands.")
            print()
            continue

        # Process query
        print()
        try:
            response = assistant.query(user_input)
            print(f"A: {response}")
        except Exception as e:
            print(f"Error: {e}")
            print("Please try again or type /help for assistance.")
        print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Library Assistant")
    parser.add_argument(
        "--rag",
        action="store_true",
        help="Enable RAG/semantic search by default",
    )
    parser.add_argument(
        "--dummy-tools",
        action="store_true",
        help="Enable 100 enterprise dummy tools across 10 domains for scale demo",
    )
    args = parser.parse_args()

    interactive_repl(enable_rag=args.rag, enable_dummy_tools=args.dummy_tools)
