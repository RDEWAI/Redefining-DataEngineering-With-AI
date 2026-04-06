"""Coordination Agent - Library operations assistant for staff.

Handles staff queries: collection analytics, RFID monitoring,
lending revenue and statistics, replenishment tracking, and reporting.
This is the only agent with access to lending revenue and replenishment data.

Tools (14 total):
  Base (3):  get_library_stats, get_weak_signal_books, get_popular_books
  RAG (11):  get_lending_stats, search_lending, get_book_lending,
             get_most_lent_books, search_lending_semantic,
             search_replenish, get_book_replenish, get_replenish_stats,
             get_most_replenished_books, get_replenish_by_month,
             search_replenish_semantic

Usage:
    make coordination-agent    # Start interactive CLI (RAG on)
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from chapter-2 directory
env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(env_path, override=True)

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.agentic.agents.library_assistant import (  # noqa: E402
    LENDING_SEMANTIC_SEARCH_TOOL,
    LENDING_TOOL_DEFINITIONS,
    REPLENISH_SEMANTIC_SEARCH_TOOL,
    REPLENISH_TOOL_DEFINITIONS,
    TOOL_DEFINITIONS,
    LibraryAssistant,
)
from src.agentic.llm.unified_client import UnifiedLLMClient  # noqa: E402

# ─────────────────────────────────────────────────────────────────
# System prompt
# ─────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a Library Coordination Assistant supporting library staff and administrators.

You have access to operational and revenue data that is not available to patrons:
- Library collection statistics and overall health
- RFID signal monitoring for maintenance alerts
- Popular and featured book rankings
- Lending revenue, fees, and borrowing statistics by segment, region, and channel
- Replenishment orders: supplier, type, funding source, priority, and monthly trends

Use this data to answer operational queries such as:
- "Which book generates the most lending revenue?"
- "What are the most replenished books this quarter?"
- "Show lending stats by patron segment"
- "Which books need RFID maintenance?"

If someone asks about browsing the collection, checking out books, or locating
a specific title on the shelf, direct them to the Patron Agent.
"""

# ─────────────────────────────────────────────────────────────────
# Tool subsets
# ─────────────────────────────────────────────────────────────────

_COORD_BASE_TOOL_NAMES = {
    "get_library_stats",
    "get_weak_signal_books",
    "get_popular_books",
}

COORDINATION_BASE_TOOLS = [t for t in TOOL_DEFINITIONS if t.name in _COORD_BASE_TOOL_NAMES]

# RAG: full lending revenue suite + full replenishment suite
COORDINATION_RAG_TOOLS = [
    *LENDING_TOOL_DEFINITIONS,        # get_lending_stats, search_lending, get_book_lending,
                                       # get_most_lent_books, get_lending_by_month (if present)
    LENDING_SEMANTIC_SEARCH_TOOL,      # search_lending_semantic
    *REPLENISH_TOOL_DEFINITIONS,       # search_replenish, get_book_replenish,
                                       # get_replenish_stats, get_most_replenished_books,
                                       # get_replenish_by_month
    REPLENISH_SEMANTIC_SEARCH_TOOL,    # search_replenish_semantic
]


# ─────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────

def create_coordination_agent(enable_rag: bool = False) -> LibraryAssistant:
    """Create a Coordination Agent instance.

    Args:
        enable_rag: Whether to enable replenishment and lending analytics tools.

    Returns:
        LibraryAssistant configured with coordination-specific tools.
    """
    llm_provider = UnifiedLLMClient.from_env()
    return LibraryAssistant(
        llm_provider=llm_provider,
        system_prompt=SYSTEM_PROMPT,
        enable_rag=enable_rag,
        base_tool_definitions=COORDINATION_BASE_TOOLS,
        rag_tool_definitions=COORDINATION_RAG_TOOLS,
    )


# ─────────────────────────────────────────────────────────────────
# Interactive REPL
# ─────────────────────────────────────────────────────────────────

def interactive_repl(enable_rag: bool = False) -> None:
    """Run an interactive CLI for the Coordination Agent."""
    print()
    print("Coordination Agent - Library Operations Assistant")
    print("=" * 50)
    print()

    try:
        agent = create_coordination_agent(enable_rag=enable_rag)
    except Exception as e:
        print(f"Error: {e}")
        print()
        print("Please ensure your LLM configuration is set in .env:")
        print("  LLM_BASE_URL=your-api-base-url")
        print("  LLM_API_KEY=your-api-key")
        print("  LLM_MODEL=your-model-name")
        sys.exit(1)

    base_count = len(COORDINATION_BASE_TOOLS)
    rag_count = len(COORDINATION_RAG_TOOLS)
    rag_status = "ON" if enable_rag else "OFF"
    total_tools = base_count + (rag_count if enable_rag else 0)

    print(f"Tools: {base_count} base + {rag_count} RAG (RAG={rag_status}) = {total_tools} active")
    print()
    print("Type /help for commands. Ask me anything about library operations!")
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
                print(f"  /rag      - Toggle replenishment + lending analytics (currently: {rag_s})")
                print("  /clear    - Clear conversation history")
                print("  /reset    - Reset token usage counters")
                print("  /quit     - Exit")
                print()
                continue

            if command == "/settings":
                tools_s = "ON" if agent._show_tool_calls else "OFF"
                rag_s = "ON" if agent.is_rag_enabled() else "OFF"
                print()
                print("Coordination Agent Settings:")
                print("-" * 40)
                print("  Role:           Library Operations Assistant")
                print(f"  Base tools:     {base_count} (stats, RFID monitoring, popular books)")
                print(f"  RAG:            {rag_s} (+{rag_count} lending/replenishment tools when ON)")
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
                    print("    - Lending: get_lending_stats, search_lending, get_book_lending,")
                    print("               get_most_lent_books, search_lending_semantic")
                    print("    - Replenish: search_replenish, get_book_replenish,")
                    print("                 get_replenish_stats, get_most_replenished_books,")
                    print("                 get_replenish_by_month, search_replenish_semantic")
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

    parser = argparse.ArgumentParser(description="Coordination Agent - Library operations assistant")
    parser.add_argument("--rag", action="store_true", help="Enable RAG/replenishment tools by default")
    args = parser.parse_args()

    interactive_repl(enable_rag=args.rag)
