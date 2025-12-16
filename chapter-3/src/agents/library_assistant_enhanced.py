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


# Base system prompt for code execution (without RAG)
CODE_EXECUTION_SYSTEM_PROMPT_BASE = """You are a Library Data Analyst with Python code execution.

**Database:** library.books (DuckDB, accessed via `_conn`)
- Columns: book_id, title, author, description, category, status, cabinet, rack, row, signal_strength, timestamp
- Status: "Present", "Missing", "Checked Out"
- Categories: "Programming", "History", "Science", "Fiction", "Thriller"

**API Functions Available:**
Use these directly: search_books(), get_book_details(), check_availability(), list_by_category(), list_by_status(), locate_book(), find_books_in_cabinet(), get_weak_signal_books()

**CRITICAL INSTRUCTIONS:**
1. **Write ALL code in a SINGLE block** - Do the ENTIRE task in one code generation, not multiple iterations
2. **ALWAYS print() results** - Empty output wastes tokens on extra iterations
3. **Chain operations together** - If you need search + availability, do BOTH in one block
4. **Use loops for multiple items** - Don't generate code iteratively; use for-loops

**Example - CORRECT (single block):**
```python
# Do EVERYTHING in one code block
results = search_books("Python", category="Programming")
print(f"Found {len(results)} books:")
for book in results:
    avail = check_availability(book['book_id'])
    status = "✓" if avail['available'] else "✗"
    print(f"  {status} {book['title']} - {avail['status']} at {avail.get('location', 'N/A')}")
```

**Example - WRONG (multiple iterations):**
```python
# Iteration 1 - INEFFICIENT
results = search_books("Python")
print(results)
# Then waiting for another iteration to check availability - WASTEFUL!
```
"""

# RAG-specific additions to the system prompt
CODE_EXECUTION_RAG_ADDITIONS = """
**RAG/Semantic Search - WHEN TO USE:**
- `semantic_search(query, top_k=5)` - Find books by meaning, not just keywords
- **RAG indexes**: title, author, description, category (conceptual/text data)
- **NOT in RAG**: status, location, signal_strength, book_id (use tools/SQL instead)
- Use for: "books about time travel", "something like Harry Potter", "adventure stories"
- Do NOT use for: "available books", "missing books", "weak signal", "in cabinet 3"

**Example - RAG + Availability in ONE block:**
```python
# Do EVERYTHING in one code block - search AND check availability
results = semantic_search("science fiction adventures")
print(f"Found {len(results)} similar books:\\n")
for book in results:
    avail = check_availability(book['book_id'])
    status_icon = "✓" if avail['available'] else "✗"
    print(f"  {status_icon} {book['title']} (similarity: {book['similarity']:.3f})")
    print(f"      Status: {avail['status']} | Location: {avail.get('location', 'N/A')}")
```
"""


def get_code_execution_system_prompt(include_rag: bool = False) -> str:
    """Get the system prompt for code execution mode.

    Args:
        include_rag: Whether to include RAG/semantic search instructions

    Returns:
        System prompt string
    """
    if include_rag:
        # Insert RAG additions after API functions list
        base = CODE_EXECUTION_SYSTEM_PROMPT_BASE.replace(
            "get_weak_signal_books()",
            "get_weak_signal_books(), semantic_search()",
        )
        return base + CODE_EXECUTION_RAG_ADDITIONS
    return CODE_EXECUTION_SYSTEM_PROMPT_BASE


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
        enable_rag: bool = False,
    ) -> None:
        """Initialize the Enhanced Library Assistant."""
        self._llm_provider = llm_provider
        self._verbose = verbose
        self._show_tool_calls = show_tool_calls
        self._enable_rag = enable_rag

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
        self._tool_api_generator = ToolAPIGenerator(
            self._repository, db_path=self._db_path, include_rag=enable_rag
        )

        # Traditional assistant (for traditional mode)
        self._traditional_assistant = LibraryAssistant(
            llm_provider=llm_provider,
            verbose=verbose,
            show_tool_calls=show_tool_calls,
            enable_rag=enable_rag,
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

    def set_rag_enabled(self, enabled: bool) -> None:
        """Enable or disable RAG (semantic search) tool.

        Args:
            enabled: Whether to enable RAG
        """
        self._enable_rag = enabled
        self._traditional_assistant.set_rag_enabled(enabled)
        self._tool_api_generator.set_include_rag(enabled)
        # Reset conversation to apply new system prompt
        self.reset_conversation()

    def is_rag_enabled(self) -> bool:
        """Check if RAG is enabled.

        Returns:
            True if RAG is enabled
        """
        return self._enable_rag

    def reset_conversation(self) -> None:
        """Reset conversation history and token counters."""
        if self._mode == AssistantMode.TRADITIONAL:
            # Reset traditional assistant
            self._traditional_assistant = LibraryAssistant(
                llm_provider=self._llm_provider,
                verbose=self._verbose,
                show_tool_calls=self._show_tool_calls,
                enable_rag=self._enable_rag,
            )
        else:
            # Reset code execution history with system prompt based on RAG setting
            system_prompt = get_code_execution_system_prompt(include_rag=self._enable_rag)
            self._code_exec_history = [Message(role="system", content=system_prompt)]

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

        # Reset sandbox state for new query (Anthropic pattern: fresh state per query)
        self._sandbox.reset_state()

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

            # Use stateful execution - variables persist between iterations (Anthropic pattern)
            result = self._sandbox.execute_stateful(
                code, db_path=self._db_path, api_code=full_api_code
            )

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
        default="code_execution",
        help="Execution mode (default: code_execution)",
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
    rag_status = "ON" if assistant.is_rag_enabled() else "OFF"
    print(f"RAG:  {rag_status}")
    print("\nCommands:")
    print("  /mode traditional    - Switch to traditional tool calls")
    print("  /mode code           - Switch to code execution")
    print("  /rag                 - Toggle semantic search/RAG")
    print("  /settings            - Show current settings")
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
                    rag_status = "ON" if assistant.is_rag_enabled() else "OFF"
                    print("\nAvailable commands:")
                    print("  /mode traditional - Switch to traditional tool calls")
                    print("  /mode code       - Switch to code execution")
                    print(
                        f"  /rag             - Toggle semantic search/RAG (currently: {rag_status})"
                    )
                    print("  /settings        - Show current settings")
                    print("  /reset           - Reset conversation")
                    print("  /tokens          - Show token usage")
                    print("  /quit            - Exit")

                elif cmd == "/settings":
                    mode = assistant.get_mode()
                    mode_display = (
                        "Traditional (JSON tools)"
                        if mode == "traditional"
                        else "Code Execution (Python)"
                    )
                    rag_status = "ON" if assistant.is_rag_enabled() else "OFF"
                    tools_status = "ON" if assistant._show_tool_calls else "OFF"
                    print()
                    print("Current Settings:")
                    print("-" * 40)
                    print(f"  Mode:          {mode_display}")
                    print(f"  RAG:           {rag_status}")
                    print(f"  Tool Display:  {tools_status}")
                    print(f"  Base URL:      {os.getenv('LLM_BASE_URL', 'not set')}")
                    print(f"  Model:         {os.getenv('LLM_MODEL', 'not set')}")
                    print(f"  DB Path:       {assistant._db_path}")
                    print("-" * 40)

                elif cmd == "/reset":
                    assistant.reset_conversation()
                    print("Conversation and token counters reset.")

                elif cmd == "/tokens":
                    assistant.print_token_summary()

                elif cmd == "/rag":
                    new_rag_status = not assistant.is_rag_enabled()
                    assistant.set_rag_enabled(new_rag_status)
                    status = "ON" if new_rag_status else "OFF"
                    print(f"Semantic search (RAG): {status}")
                    if new_rag_status:
                        print(
                            "  The assistant can now use semantic_search for natural language queries."
                        )
                        print(
                            "  Try: 'Find books about time travel' or 'something like Harry Potter'"
                        )

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
