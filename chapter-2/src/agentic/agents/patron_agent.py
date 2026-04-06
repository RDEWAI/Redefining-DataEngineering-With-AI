"""Patron Agent - Library patron-facing assistant.

Handles patron queries: searching the collection, checking availability,
and locating books on the shelf. Has no access to lending revenue,
replenishment, or operational analytics — those belong to the
Coordination Agent.

Tools (8 total):
  Base (7):  search_books, get_book_details, check_availability,
             locate_book, find_books_in_cabinet,
             list_by_category, list_by_status
  RAG  (1):  semantic_search

Usage:
    make patron-agent      # Start interactive CLI (RAG on)
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from chapter-2 directory
env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(env_path, override=True)

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.agentic.agents.library_assistant import (  # noqa: E402
    SEMANTIC_SEARCH_TOOL,
    TOOL_DEFINITIONS,
    LibraryAssistant,
)
from src.agentic.llm.unified_client import UnifiedLLMClient  # noqa: E402

# ─────────────────────────────────────────────────────────────────
# System prompt
# ─────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a Library Patron Assistant helping library members find books on the shelf.

You can help patrons with:
- Searching for books by title, author, or keyword
- Checking whether a book is available for checkout
- Locating books by cabinet, rack, and row
- Browsing books by category or availability status
- Natural language / semantic book search (when RAG is enabled)

You do NOT have access to lending revenue, borrowing statistics, replenishment
records, or library operational data. If a patron asks about those topics,
let them know that information is managed by library staff and is not available
through the patron portal.
"""

# ─────────────────────────────────────────────────────────────────
# Tool subsets
# ─────────────────────────────────────────────────────────────────

_PATRON_BASE_TOOL_NAMES = {
    "search_books",
    "get_book_details",
    "check_availability",
    "locate_book",
    "find_books_in_cabinet",
    "list_by_category",
    "list_by_status",
}

PATRON_BASE_TOOLS = [t for t in TOOL_DEFINITIONS if t.name in _PATRON_BASE_TOOL_NAMES]

# RAG: only semantic book search — no revenue or operational data
PATRON_RAG_TOOLS = [SEMANTIC_SEARCH_TOOL]


# ─────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────

def create_patron_agent(enable_rag: bool = False) -> LibraryAssistant:
    """Create a Patron Agent instance.

    Args:
        enable_rag: Whether to enable semantic search and lending tools.

    Returns:
        LibraryAssistant configured with patron-specific tools.
    """
    llm_provider = UnifiedLLMClient.from_env()
    return LibraryAssistant(
        llm_provider=llm_provider,
        system_prompt=SYSTEM_PROMPT,
        enable_rag=enable_rag,
        base_tool_definitions=PATRON_BASE_TOOLS,
        rag_tool_definitions=PATRON_RAG_TOOLS,
    )


# ─────────────────────────────────────────────────────────────────
# Interactive REPL
# ─────────────────────────────────────────────────────────────────

def interactive_repl(enable_rag: bool = False) -> None:
    """Run an interactive CLI for the Patron Agent."""
    print()
    print("Patron Agent - Library Assistant for Members")
    print("=" * 50)
    print()

    try:
        agent = create_patron_agent(enable_rag=enable_rag)
    except Exception as e:
        print(f"Error: {e}")
        print()
        print("Please ensure your LLM configuration is set in .env:")
        print("  LLM_BASE_URL=your-api-base-url")
        print("  LLM_API_KEY=your-api-key")
        print("  LLM_MODEL=your-model-name")
        sys.exit(1)

    base_count = len(PATRON_BASE_TOOLS)
    rag_count = len(PATRON_RAG_TOOLS)
    rag_status = "ON" if enable_rag else "OFF"
    total_tools = base_count + (rag_count if enable_rag else 0)

    print(f"Tools: {base_count} base (inventory/shelf) + {rag_count} RAG (semantic search) = {total_tools} active")
    print()
    print("Type /help for commands. Ask me anything about the library collection!")
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

        if user_input.startswith("/"):
            command = user_input.lower()

            if command == "/help":
                rag_s = "ON" if agent.is_rag_enabled() else "OFF"
                print()
                print("Commands:")
                print("  /help     - Show this help message")
                print("  /settings - Show current settings")
                print("  /stats    - Show token usage statistics")
                print("  /tools    - Toggle tool call display")
                print(f"  /rag      - Toggle semantic search + lending tools (currently: {rag_s})")
                print("  /clear    - Clear conversation history")
                print("  /reset    - Reset token usage counters")
                print("  /quit     - Exit")
                print()
                continue

            if command == "/settings":
                tools_s = "ON" if agent._show_tool_calls else "OFF"
                rag_s = "ON" if agent.is_rag_enabled() else "OFF"
                print()
                print("Patron Agent Settings:")
                print("-" * 40)
                print("  Role:           Library Patron Assistant")
                print(f"  Base tools:     {base_count} (search, availability, location, category/status)")
                print(f"  RAG:            {rag_s} (+{rag_count} semantic search tool when ON)")
                print(f"  Tool display:   {tools_s}")
                print(f"  Active tools:   {agent.get_tool_count()}")
                print("-" * 40)
                print()
                continue

            if command == "/rag":
                new_rag = not agent.is_rag_enabled()
                agent.set_rag_enabled(new_rag)
                status = "ON" if new_rag else "OFF"
                print(f"RAG: {status} (total tools: {agent.get_tool_count()})")
                if new_rag:
                    print("  Now available:")
                    print("    - semantic_search: natural language book search")
                print()
                continue

            if command == "/tools":
                agent._show_tool_calls = not agent._show_tool_calls
                status = "ON" if agent._show_tool_calls else "OFF"
                print(f"Tool call display: {status}")
                print()
                continue

            if command == "/stats":
                usage = agent.get_token_usage()
                print()
                print("Token Usage:")
                print(f"  Queries:            {usage['query_count']}")
                print(f"  Tool calls:         {usage['tool_calls_count']}")
                print(f"  Prompt tokens:      {usage['total_prompt_tokens']}")
                print(f"  Completion tokens:  {usage['total_completion_tokens']}")
                print(f"  Total tokens:       {usage['total_tokens']}")
                print()
                continue

            if command == "/clear":
                agent.clear_conversation()
                print("Conversation cleared.")
                print()
                continue

            if command == "/reset":
                agent.reset_token_usage()
                print("Token usage reset.")
                print()
                continue

            if command in ("/quit", "/exit", "/q"):
                print("Goodbye!")
                break

            print(f"Unknown command: {user_input}")
            print("Type /help for available commands.")
            print()
            continue

        print()
        try:
            response = agent.query(user_input)
            print(f"A: {response}")
        except Exception as e:
            print(f"Error: {e}")
            print("Please try again or type /help for assistance.")
        print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Patron Agent - Library patron assistant")
    parser.add_argument("--rag", action="store_true", help="Enable RAG/semantic search by default")
    args = parser.parse_args()

    interactive_repl(enable_rag=args.rag)
