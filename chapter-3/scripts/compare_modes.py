#!/usr/bin/env python3
"""Compare traditional tools vs code execution for the same query.

This script demonstrates the token usage difference between:
1. Traditional tool calling (multiple round trips)
2. Code execution (single code generation)

Run the same query in both modes and see the difference!
"""

import os
import sys
from pathlib import Path

# Add chapter-3 directory to path so src.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.library_assistant_enhanced import EnhancedLibraryAssistant
from src.llm.unified_client import UnifiedLLMClient

# Sample queries to test
# Format: (query, requires_rag)
SAMPLE_QUERIES = [
    ("Show me details for book B001", False),  # Simple - uses API call
    ("Search for Python books in Programming category", False),  # Simple - uses API call
    ("Show me the top 5 categories by number of missing books", False),  # Complex - uses SQL
    ("Find books with weak RFID signal and show their locations", False),  # Medium - uses SQL
    ("How many books are in each status category?", False),  # Complex - uses SQL
    # RAG + API combined query
    (
        "Find books similar to science fiction adventures, and tell me which ones are available and where I can find them.",
        True,
    ),  # RAG + API
]


def compare_modes(
    query: str, llm_provider: UnifiedLLMClient, db_path: str, enable_rag: bool = False
):
    """Compare traditional vs code execution for a single query.

    Args:
        query: The query to test
        llm_provider: LLM client
        db_path: Database path
        enable_rag: Whether to enable RAG (semantic search) for this query
    """
    print("\n" + "=" * 80)
    print(f"QUERY: {query}")
    if enable_rag:
        print("[RAG ENABLED] semantic_search tool available")
    print("=" * 80)

    # Mode 1: Traditional tool calls
    rag_status = "ON" if enable_rag else "OFF"
    print(f"\n[MODE 1] TRADITIONAL TOOL CALLS (RAG: {rag_status})")
    print("-" * 80)

    assistant_traditional = EnhancedLibraryAssistant(
        llm_provider=llm_provider,
        mode="traditional",
        db_path=db_path,
        show_tool_calls=True,
        enable_rag=enable_rag,
    )

    response_trad = assistant_traditional.query(query)
    usage_trad = assistant_traditional.get_token_usage()

    print(f"\nResponse:\n{response_trad}\n")
    print(f"Tokens: {usage_trad['total_tokens']:,}")
    print(f"   - Prompt: {usage_trad['total_prompt_tokens']:,}")
    print(f"   - Completion: {usage_trad['total_completion_tokens']:,}")
    print(f"   - Tool calls: {usage_trad['tool_calls_count']}")

    # Mode 2: Code execution
    print(f"\n[MODE 2] CODE EXECUTION (RAG: {rag_status})")
    print("-" * 80)

    assistant_code = EnhancedLibraryAssistant(
        llm_provider=llm_provider,
        mode="code_execution",
        db_path=db_path,
        show_tool_calls=True,
        enable_rag=enable_rag,
    )

    response_code = assistant_code.query(query)
    usage_code = assistant_code.get_token_usage()

    print(f"\nResponse:\n{response_code}\n")
    print(f"Tokens: {usage_code['total_tokens']:,}")
    print(f"   - Prompt: {usage_code['total_prompt_tokens']:,}")
    print(f"   - Completion: {usage_code['total_completion_tokens']:,}")

    # Comparison
    print("\n" + "=" * 80)
    print("COMPARISON")
    print("=" * 80)

    token_diff = usage_trad["total_tokens"] - usage_code["total_tokens"]
    if usage_trad["total_tokens"] > 0:
        reduction_pct = (token_diff / usage_trad["total_tokens"]) * 100
    else:
        reduction_pct = 0

    print(f"Traditional tokens:     {usage_trad['total_tokens']:,}")
    print(f"Code execution tokens:  {usage_code['total_tokens']:,}")
    print(f"Difference:             {token_diff:,} tokens ({reduction_pct:+.1f}%)")

    if token_diff > 0:
        print(f"\n>>> Code execution SAVED {token_diff:,} tokens ({reduction_pct:.1f}% reduction)")
    elif token_diff < 0:
        print(f"\n>>> Traditional was more efficient by {abs(token_diff):,} tokens")
    else:
        print("\n>>> Both modes used the same number of tokens")

    print("=" * 80)


def main():
    """Run comparison demo."""
    import argparse

    parser = argparse.ArgumentParser(description="Compare traditional tools vs code execution")
    parser.add_argument("--query", help="Custom query to test (if not provided, shows menu)")
    parser.add_argument("--db-path", help="Path to DuckDB database (default: from DB_PATH env var)")
    parser.add_argument("--all", action="store_true", help="Run all sample queries")

    # RAG options - mutually exclusive
    rag_group = parser.add_mutually_exclusive_group()
    rag_group.add_argument("--rag", action="store_true", help="Enable RAG/semantic search")
    rag_group.add_argument("--no-rag", action="store_true", help="Disable RAG/semantic search")

    args = parser.parse_args()

    # Initialize LLM
    try:
        llm = UnifiedLLMClient.from_env()
    except Exception as e:
        print(f"[ERROR] Error initializing LLM client: {e}")
        print("Make sure you have configured LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL in .env")
        sys.exit(1)

    # Get database path
    db_path = args.db_path or os.getenv("DB_PATH", "data/duckdb/chapter3.db")

    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found at: {db_path}")
        print("Run 'make load-data' first to create the database")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("TOKEN USAGE COMPARISON: Traditional Tools vs Code Execution")
    print("=" * 80)
    print("Settings:")
    print(f"  Database:  {db_path}")
    print(f"  Model:     {llm.default_model}")
    print(f"  Base URL:  {os.getenv('LLM_BASE_URL', 'not set')}")
    print("  RAG:       Per-query (RAG+API indicates RAG enabled)")

    # Determine RAG override
    def get_rag_setting(default_rag: bool) -> bool:
        """Get RAG setting with override support."""
        if args.rag:
            return True
        elif args.no_rag:
            return False
        return default_rag

    if args.all:
        # Run all sample queries
        print(f"\nRunning all {len(SAMPLE_QUERIES)} sample queries...")
        if args.rag:
            print("[!] RAG OVERRIDE: --rag flag forces RAG ON for all queries")
        elif args.no_rag:
            print("[!] RAG OVERRIDE: --no-rag flag forces RAG OFF for all queries")

        for i, (query, requires_rag) in enumerate(SAMPLE_QUERIES, 1):
            effective_rag = get_rag_setting(requires_rag)
            if effective_rag:
                query_type = "RAG+API"
            elif i <= 2:
                query_type = "API"
            else:
                query_type = "SQL"
            print(f"\n\n{'*' * 80}")
            print(f"SAMPLE QUERY {i}/{len(SAMPLE_QUERIES)} [{query_type}]")
            print("*" * 80)
            compare_modes(query, llm, db_path, enable_rag=effective_rag)

    elif args.query:
        # Run custom query (default RAG to False unless --rag specified)
        enable_rag = get_rag_setting(False)
        compare_modes(args.query, llm, db_path, enable_rag=enable_rag)

    else:
        # Interactive menu
        print("\nSelect a sample query to test:")
        for i, (query, requires_rag) in enumerate(SAMPLE_QUERIES, 1):
            # Add indicators for query type (plain text for terminal compatibility)
            if requires_rag:
                indicator = "RAG+API"
            elif i <= 2:
                indicator = "API"
            else:
                indicator = "SQL"
            print(f"  {i}. [{indicator:7}] {query}")
        print(f"  {len(SAMPLE_QUERIES) + 1}. Enter custom query")
        print(f"  {len(SAMPLE_QUERIES) + 2}. Run all queries")

        try:
            choice = input(f"\nEnter choice (1-{len(SAMPLE_QUERIES) + 2}): ").strip()
            choice_num = int(choice)

            if 1 <= choice_num <= len(SAMPLE_QUERIES):
                query, default_rag = SAMPLE_QUERIES[choice_num - 1]
                # Allow override of RAG setting
                rag_default_str = "Y/n" if default_rag else "y/N"
                enable_rag_input = (
                    input(f"Enable RAG/semantic search? ({rag_default_str}): ").strip().lower()
                )
                if enable_rag_input == "":
                    enable_rag = default_rag  # Use default
                else:
                    enable_rag = enable_rag_input in ("y", "yes")
                compare_modes(query, llm, db_path, enable_rag=enable_rag)

            elif choice_num == len(SAMPLE_QUERIES) + 1:
                query = input("\nEnter your query: ").strip()
                enable_rag_input = input("Enable RAG/semantic search? (y/N): ").strip().lower()
                enable_rag = enable_rag_input in ("y", "yes")
                if query:
                    compare_modes(query, llm, db_path, enable_rag=enable_rag)
                else:
                    print("No query entered.")

            elif choice_num == len(SAMPLE_QUERIES) + 2:
                # Ask about RAG override for all queries
                rag_override = (
                    input("RAG setting for all queries? (default/on/off): ").strip().lower()
                )
                print(f"\nRunning all {len(SAMPLE_QUERIES)} sample queries...")

                for i, (query, requires_rag) in enumerate(SAMPLE_QUERIES, 1):
                    # Apply RAG override
                    if rag_override == "on":
                        effective_rag = True
                    elif rag_override == "off":
                        effective_rag = False
                    else:
                        effective_rag = requires_rag

                    if effective_rag:
                        query_type = "RAG+API"
                    elif i <= 2:
                        query_type = "API"
                    else:
                        query_type = "SQL"
                    print(f"\n\n{'*' * 80}")
                    print(f"SAMPLE QUERY {i}/{len(SAMPLE_QUERIES)} [{query_type}]")
                    print("*" * 80)
                    compare_modes(query, llm, db_path, enable_rag=effective_rag)

            else:
                print("Invalid choice.")

        except ValueError:
            print("Invalid input.")
        except KeyboardInterrupt:
            print("\n\nCancelled.")


if __name__ == "__main__":
    main()
