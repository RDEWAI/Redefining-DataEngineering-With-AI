"""Enhanced Library Assistant with dual modes: traditional tools vs code execution.

This module extends LibraryAssistant to support two modes:
1. Traditional mode: Uses JSON schema tool calls (baseline)
2. Code execution mode: Generates and executes Python code (token efficient)

The user can choose which mode to use, allowing them to compare:
- Token usage for the same query
- Response quality
- Execution time

This is designed for educational purposes to demonstrate the token reduction
benefits of code execution vs traditional tool calling.
"""

import os
import sys
from enum import Enum
from pathlib import Path
from typing import cast

from dotenv import load_dotenv

# Load .env from chapter-3 directory
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path, override=True)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


# Import traditional assistant for delegation
from agents.library_assistant import (  # noqa: E402
    LibraryAssistant,
    TokenUsage,
)
from code_execution.sandbox import CodeSandbox  # noqa: E402
from code_execution.tool_api import ToolAPIGenerator  # noqa: E402
from library.repository import BookRepository  # noqa: E402
from llm.base import LLMProvider, Message  # noqa: E402


class AssistantMode(Enum):
    """Assistant execution mode."""

    TRADITIONAL = "traditional"
    CODE_EXECUTION = "code_execution"


# Minimal system prompt for progressive tool loading (Anthropic pattern)
CODE_EXECUTION_SYSTEM_PROMPT = """You are a Library Data Analyst with Python code execution.

**Database:** library.books (DuckDB, accessed via `_conn`)
- Columns: book_id, title, author, description, category, status, cabinet, rack, row, signal_strength, timestamp
- Status: "Present", "Missing", "Checked Out"
- Categories: "Programming", "History", "Science", "Fiction", "Thriller"

**API Functions Available:**
Use these directly: search_books(), get_book_details(), check_availability(), list_by_category(), list_by_status(), locate_book(), find_books_in_cabinet(), get_weak_signal_books()

**Tool Discovery (optional):**
- `list_tools()` - List all API functions
- `get_tool_help(name)` - Get function signature/docs

**Instructions:**
1. **Simple lookups**: Use API functions directly (e.g., `get_book_details("B001")`)
2. **Complex analytics**: Use `_conn.execute()` for SQL queries
3. **Unsure**: Call `get_tool_help('function_name')` for details
4. Always print results
5. **IMPORTANT**: Always generate Python code (not raw SQL). Wrap SQL in _conn.execute()

**Examples:**
```python
# Direct API use (preferred for simple lookups)
book = get_book_details("B001")
print(book)

# SQL for complex queries
result = _conn.execute('''
    SELECT category, COUNT(*) as count
    FROM library.books WHERE status = 'Missing'
    GROUP BY category ORDER BY count DESC
''').fetchdf()
print(result)
```
"""


class EnhancedLibraryAssistant:
    """Library Assistant with dual modes: traditional tools vs code execution.

    This assistant can operate in two modes:
    1. Traditional mode: Uses JSON tool calls (multiple round trips)
    2. Code execution mode: Generates Python code (single execution)

    The mode can be set at initialization or switched during a session,
    allowing users to compare token usage for the same query.

    Args:
        llm_provider: The LLM provider to use
        mode: Execution mode (traditional or code_execution)
        db_path: Path to DuckDB database
        verbose: Whether to print debug information
        show_tool_calls: Whether to display tool calls/code

    Example:
        >>> from llm.unified_client import UnifiedLLMClient
        >>> llm = UnifiedLLMClient.from_env()
        >>>
        >>> # Traditional mode
        >>> assistant = EnhancedLibraryAssistant(llm, mode="traditional")
        >>> response = assistant.query("What programming books are available?")
        >>> print(f"Tokens used: {assistant.get_token_usage()['total_tokens']}")
        >>>
        >>> # Code execution mode
        >>> assistant.set_mode("code_execution")
        >>> assistant.reset_conversation()
        >>> response = assistant.query("What programming books are available?")
        >>> print(f"Tokens used: {assistant.get_token_usage()['total_tokens']}")
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        mode: str | AssistantMode = AssistantMode.TRADITIONAL,
        db_path: str | None = None,
        verbose: bool = False,
        show_tool_calls: bool = True,
    ) -> None:
        """Initialize the Enhanced Library Assistant."""
        self._llm_provider = llm_provider
        self._verbose = verbose
        self._show_tool_calls = show_tool_calls

        # Parse mode
        if isinstance(mode, str):
            mode = AssistantMode(mode)
        self._mode = mode

        # Setup database path
        self._db_path = db_path or os.getenv("DB_PATH", "data/duckdb/chapter3.db")

        # Initialize components based on mode
        # Use read_only=True to allow concurrent access and match sandbox behavior
        self._repository = BookRepository(db_path=self._db_path, read_only=True)
        self._sandbox = CodeSandbox()
        self._tool_api_generator = ToolAPIGenerator(self._repository, db_path=self._db_path)

        # Traditional assistant (for traditional mode)
        self._traditional_assistant = LibraryAssistant(
            llm_provider=llm_provider,
            verbose=verbose,
            show_tool_calls=show_tool_calls,
        )

        # Token tracking
        self._token_usage = TokenUsage()

        # Code execution conversation history
        self._code_exec_history: list[Message] = []

        # Initialize conversation
        self.reset_conversation()

    def set_mode(self, mode: str | AssistantMode) -> None:
        """Change the assistant's execution mode.

        Args:
            mode: New mode ("traditional" or "code_execution")
        """
        if isinstance(mode, str):
            mode = AssistantMode(mode)

        old_mode = self._mode
        self._mode = mode

        if self._verbose:
            print(f"Mode changed: {old_mode.value} → {mode.value}")

    def get_mode(self) -> str:
        """Get the current mode.

        Returns:
            Current mode as string
        """
        return self._mode.value

    def reset_conversation(self) -> None:
        """Reset conversation history and token counters."""
        if self._mode == AssistantMode.TRADITIONAL:
            # Reset traditional assistant
            self._traditional_assistant = LibraryAssistant(
                llm_provider=self._llm_provider,
                verbose=self._verbose,
                show_tool_calls=self._show_tool_calls,
            )
        else:
            # Reset code execution history with minimal system prompt
            # (no tool descriptions - progressive loading pattern)
            self._code_exec_history = [Message(role="system", content=CODE_EXECUTION_SYSTEM_PROMPT)]

        self._token_usage.reset()

    def query(self, user_input: str) -> str:
        """Process a user query in the current mode.

        Args:
            user_input: The user's question or request

        Returns:
            The assistant's response text
        """
        self._token_usage.increment_query()

        if self._mode == AssistantMode.TRADITIONAL:
            return self._query_traditional(user_input)
        else:
            return self._query_code_execution(user_input)

    def _query_traditional(self, user_input: str) -> str:
        """Handle query using traditional tool calls."""
        if self._verbose:
            print(f"\n[TRADITIONAL MODE] Processing query: {user_input}")

        response = self._traditional_assistant.query(user_input)

        # Copy token usage from traditional assistant
        trad_usage = self._traditional_assistant.get_token_usage()
        self._token_usage.total_prompt_tokens = trad_usage["total_prompt_tokens"]
        self._token_usage.total_completion_tokens = trad_usage["total_completion_tokens"]
        self._token_usage.tool_calls_count = trad_usage["tool_calls_count"]

        return str(response)

    def _query_code_execution(self, user_input: str) -> str:
        """Handle query using code execution with iterative feedback."""
        if self._verbose:
            print(f"\n[CODE EXECUTION MODE] Processing query: {user_input}")

        # Add user message
        self._code_exec_history.append(Message(role="user", content=user_input))

        # Iterative code execution loop (like tool calling)
        max_iterations = 3
        for iteration in range(max_iterations):
            # Generate code
            response = self._llm_provider.generate(
                messages=self._code_exec_history,
                temperature=0.0,  # Deterministic for code
            )

            # Track tokens
            self._token_usage.add(response)

            # Extract code from response
            code = self._extract_code_from_response(response.content or "")

            # If no code generated, this is the final response
            if not code:
                self._code_exec_history.append(
                    Message(role="assistant", content=response.content or "")
                )
                return str(response.content or "")

            if self._show_tool_calls:
                print("\n" + "=" * 60)
                print(f"📝 GENERATED CODE (Iteration {iteration + 1}):")
                print("=" * 60)

                # Highlight what's being done
                if "_conn.execute" in code:
                    print("🗄️  Action: Direct SQL Query")
                if (
                    "search_books" in code
                    or "get_book_details" in code
                    or "list_by_category" in code
                ):
                    print("🔧 Action: API Function Call")
                if ".df()" in code or "pd." in code:
                    print("📊 Action: Data Processing with pandas")

                print("=" * 60)
                print(code)
                print("=" * 60)

            # Execute code with progressive loading (Anthropic pattern)
            # Inject discovery functions + API functions
            # Discovery functions are small and allow on-demand tool exploration
            discovery_code = self._tool_api_generator.generate_discovery_functions()
            api_functions = self._tool_api_generator.generate_api_code(include_setup=False)
            full_api_code = discovery_code + "\n\n" + api_functions

            result = self._sandbox.execute(code, db_path=self._db_path, api_code=full_api_code)

            # Add assistant's code generation to history
            self._code_exec_history.append(
                Message(role="assistant", content=response.content or "")
            )

            if result["success"]:
                output = result["stdout"]

                # Show execution output to user
                if self._show_tool_calls:
                    print("\n" + "=" * 60)
                    print("✅ EXECUTION OUTPUT:")
                    print("=" * 60)
                    print(output)
                    print("=" * 60)

                if self._verbose:
                    print("\n[EXECUTION SUCCESS] Output shown above")

                # Feed execution results back to LLM for reflection
                result_message = f"Code executed successfully. Output:\n```\n{output}\n```\n\nProvide a final answer based on these results, or generate new code if needed."
                self._code_exec_history.append(Message(role="user", content=result_message))

                # Get LLM reflection on results
                final_response = self._llm_provider.generate(
                    messages=self._code_exec_history,
                    temperature=0.0,
                )
                self._token_usage.add(final_response)

                # Check if LLM wants to generate more code or give final answer
                final_code = self._extract_code_from_response(final_response.content or "")

                if not final_code:
                    # No more code - this is the final answer
                    self._code_exec_history.append(
                        Message(role="assistant", content=final_response.content or "")
                    )
                    return str(final_response.content or "")

                # LLM generated more code - continue loop

            else:
                error = result["stderr"]
                if self._verbose:
                    print(f"\n[EXECUTION FAILED] Error:\n{error}")

                # Feed error back to LLM so it can fix the code
                error_message = f"Code execution failed with error:\n```\n{error}\n```\n\nPlease fix the code or provide an explanation."
                self._code_exec_history.append(Message(role="user", content=error_message))
                # Continue loop to let LLM try again

        # Max iterations reached
        return "Unable to complete the query after multiple attempts. Please try rephrasing your question."

    def _extract_code_from_response(self, response: str) -> str:
        """Extract Python code from LLM response.

        Args:
            response: LLM response text

        Returns:
            Extracted Python code
        """
        # Look for code blocks
        if "```python" in response:
            # Extract from ```python ... ```
            start = response.find("```python") + len("```python")
            end = response.find("```", start)
            if end != -1:
                return response[start:end].strip()
        elif "```" in response:
            # Extract from ``` ... ```
            start = response.find("```") + len("```")
            end = response.find("```", start)
            if end != -1:
                return response[start:end].strip()

        # No code block found - this is a natural language response, not code
        return ""

    def get_token_usage(self) -> dict[str, int]:
        """Get token usage statistics for current session.

        Returns:
            Dictionary with token counts
        """
        return cast(dict[str, int], self._token_usage.to_dict())

    def print_token_summary(self) -> None:
        """Print a formatted summary of token usage."""
        usage = self.get_token_usage()
        print("\n" + "=" * 60)
        print(f"MODE: {self._mode.value.upper()}")
        print("=" * 60)
        print(f"Queries:           {usage['query_count']}")
        print(f"Tool calls:        {usage['tool_calls_count']}")
        print(f"Prompt tokens:     {usage['total_prompt_tokens']:,}")
        print(f"Completion tokens: {usage['total_completion_tokens']:,}")
        print(f"TOTAL TOKENS:      {usage['total_tokens']:,}")
        print("=" * 60)


def run_interactive_cli() -> None:
    """Run an interactive CLI for the enhanced library assistant."""
    import argparse

    from llm.unified_client import UnifiedLLMClient

    parser = argparse.ArgumentParser(
        description="Enhanced Library Assistant - Compare traditional tools vs code execution"
    )
    parser.add_argument(
        "--mode",
        choices=["traditional", "code_execution"],
        default="traditional",
        help="Execution mode (default: traditional)",
    )
    parser.add_argument("--db-path", help="Path to DuckDB database (default: from DB_PATH env var)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--hide-tools", action="store_true", help="Hide tool calls/generated code")

    args = parser.parse_args()

    # Initialize LLM client
    try:
        llm = UnifiedLLMClient.from_env()
    except Exception as e:
        print(f"Error initializing LLM client: {e}")
        print("Make sure you have configured LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL in .env")
        sys.exit(1)

    # Initialize assistant
    assistant = EnhancedLibraryAssistant(
        llm_provider=llm,
        mode=args.mode,
        db_path=args.db_path,
        verbose=args.verbose,
        show_tool_calls=not args.hide_tools,
    )

    print("\n" + "=" * 60)
    print("Enhanced Library Assistant")
    print("=" * 60)
    print(f"Mode: {assistant.get_mode()}")
    print("\nCommands:")
    print("  /mode traditional     - Switch to traditional tool calls")
    print("  /mode code           - Switch to code execution")
    print("  /reset               - Reset conversation and token counters")
    print("  /tokens              - Show token usage summary")
    print("  /help                - Show this help")
    print("  /quit or /exit       - Exit")
    print("=" * 60)

    while True:
        try:
            user_input = input("\nYou: ").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.startswith("/"):
                cmd = user_input.lower()

                if cmd in ["/quit", "/exit"]:
                    print("Goodbye!")
                    break

                elif cmd == "/help":
                    print("\nAvailable commands:")
                    print("  /mode traditional - Switch to traditional tool calls")
                    print("  /mode code       - Switch to code execution")
                    print("  /reset           - Reset conversation")
                    print("  /tokens          - Show token usage")
                    print("  /quit            - Exit")

                elif cmd == "/reset":
                    assistant.reset_conversation()
                    print("Conversation and token counters reset.")

                elif cmd == "/tokens":
                    assistant.print_token_summary()

                elif cmd.startswith("/mode "):
                    new_mode = cmd.split()[1]
                    if new_mode in ["traditional", "code", "code_execution"]:
                        if new_mode == "code":
                            new_mode = "code_execution"
                        assistant.set_mode(new_mode)
                        assistant.reset_conversation()
                        print(f"Mode changed to: {assistant.get_mode()}")
                        print("Conversation reset.")
                    else:
                        print(f"Unknown mode: {new_mode}")
                        print("Use: /mode traditional OR /mode code")

                else:
                    print(f"Unknown command: {user_input}")
                    print("Type /help for available commands")

                continue

            # Process query
            response = assistant.query(user_input)
            print(f"\nAssistant: {response}")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")
            if args.verbose:
                import traceback

                traceback.print_exc()


if __name__ == "__main__":
    run_interactive_cli()
