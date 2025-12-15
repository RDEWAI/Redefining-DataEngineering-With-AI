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

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agents.library_assistant_enhanced import EnhancedLibraryAssistant
from llm.unified_client import UnifiedLLMClient

# Sample queries to test
SAMPLE_QUERIES = [
    "Show me details for book B001",  # Simple - uses API call
    "Search for Python books in Programming category",  # Simple - uses API call
    "Show me the top 5 categories by number of missing books",  # Complex - uses SQL
    "Find books with weak RFID signal and show their locations",  # Medium - uses SQL
    "How many books are in each status category?",  # Complex - uses SQL
]


def compare_modes(query: str, llm_provider: UnifiedLLMClient, db_path: str):
    """Compare traditional vs code execution for a single query.

    Args:
        query: The query to test
        llm_provider: LLM client
        db_path: Database path
    """
    print("\n" + "=" * 80)
    print(f"QUERY: {query}")
    print("=" * 80)

    # Mode 1: Traditional tool calls
    print("\n🔧 MODE 1: TRADITIONAL TOOL CALLS")
    print("-" * 80)

    assistant_traditional = EnhancedLibraryAssistant(
        llm_provider=llm_provider,
        mode="traditional",
        db_path=db_path,
        show_tool_calls=True,
    )

    response_trad = assistant_traditional.query(query)
    usage_trad = assistant_traditional.get_token_usage()

    print(f"\nResponse:\n{response_trad}\n")
    print(f"📊 Tokens: {usage_trad['total_tokens']:,}")
    print(f"   - Prompt: {usage_trad['total_prompt_tokens']:,}")
    print(f"   - Completion: {usage_trad['total_completion_tokens']:,}")
    print(f"   - Tool calls: {usage_trad['tool_calls_count']}")

    # Mode 2: Code execution
    print("\n💻 MODE 2: CODE EXECUTION")
    print("-" * 80)

    assistant_code = EnhancedLibraryAssistant(
        llm_provider=llm_provider,
        mode="code_execution",
        db_path=db_path,
        show_tool_calls=True,
    )

    response_code = assistant_code.query(query)
    usage_code = assistant_code.get_token_usage()

    print(f"\nResponse:\n{response_code}\n")
    print(f"📊 Tokens: {usage_code['total_tokens']:,}")
    print(f"   - Prompt: {usage_code['total_prompt_tokens']:,}")
    print(f"   - Completion: {usage_code['total_completion_tokens']:,}")

    # Comparison
    print("\n" + "=" * 80)
    print("📈 COMPARISON")
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
        print(f"\n✅ Code execution SAVED {token_diff:,} tokens ({reduction_pct:.1f}% reduction)")
    elif token_diff < 0:
        print(f"\n⚠️  Traditional was more efficient by {abs(token_diff):,} tokens")
    else:
        print("\n➡️  Both modes used the same number of tokens")

    print("=" * 80)


def main():
    """Run comparison demo."""
    import argparse

    parser = argparse.ArgumentParser(description="Compare traditional tools vs code execution")
    parser.add_argument("--query", help="Custom query to test (if not provided, shows menu)")
    parser.add_argument("--db-path", help="Path to DuckDB database (default: from DB_PATH env var)")
    parser.add_argument("--all", action="store_true", help="Run all sample queries")

    args = parser.parse_args()

    # Initialize LLM
    try:
        llm = UnifiedLLMClient.from_env()
    except Exception as e:
        print(f"❌ Error initializing LLM client: {e}")
        print("Make sure you have configured LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL in .env")
        sys.exit(1)

    # Get database path
    db_path = args.db_path or os.getenv("DB_PATH", "data/duckdb/chapter3.db")

    if not os.path.exists(db_path):
        print(f"❌ Database not found at: {db_path}")
        print("Run 'make load-data' first to create the database")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("TOKEN USAGE COMPARISON: Traditional Tools vs Code Execution")
    print("=" * 80)
    print(f"Database: {db_path}")
    print(f"Model: {llm.default_model}")

    if args.all:
        # Run all sample queries
        print(f"\nRunning all {len(SAMPLE_QUERIES)} sample queries...")
        for i, query in enumerate(SAMPLE_QUERIES, 1):
            query_type = "🔧 API" if i <= 2 else "🗄️  SQL"
            print(f"\n\n{'*' * 80}")
            print(f"SAMPLE QUERY {i}/{len(SAMPLE_QUERIES)} [{query_type}]")
            print("*" * 80)
            compare_modes(query, llm, db_path)

    elif args.query:
        # Run custom query
        compare_modes(args.query, llm, db_path)

    else:
        # Interactive menu
        print("\nSelect a sample query to test:")
        for i, query in enumerate(SAMPLE_QUERIES, 1):
            # Add indicators for query type
            if i <= 2:
                indicator = "🔧 API"
            else:
                indicator = "🗄️  SQL"
            print(f"  {i}. {query} [{indicator}]")
        print(f"  {len(SAMPLE_QUERIES) + 1}. Enter custom query")
        print(f"  {len(SAMPLE_QUERIES) + 2}. Run all queries")

        try:
            choice = input(f"\nEnter choice (1-{len(SAMPLE_QUERIES) + 2}): ").strip()
            choice_num = int(choice)

            if 1 <= choice_num <= len(SAMPLE_QUERIES):
                query = SAMPLE_QUERIES[choice_num - 1]
                compare_modes(query, llm, db_path)

            elif choice_num == len(SAMPLE_QUERIES) + 1:
                query = input("\nEnter your query: ").strip()
                if query:
                    compare_modes(query, llm, db_path)
                else:
                    print("No query entered.")

            elif choice_num == len(SAMPLE_QUERIES) + 2:
                print(f"\nRunning all {len(SAMPLE_QUERIES)} sample queries...")
                for i, query in enumerate(SAMPLE_QUERIES, 1):
                    query_type = "🔧 API" if i <= 2 else "🗄️  SQL"
                    print(f"\n\n{'*' * 80}")
                    print(f"SAMPLE QUERY {i}/{len(SAMPLE_QUERIES)} [{query_type}]")
                    print("*" * 80)
                    compare_modes(query, llm, db_path)

            else:
                print("Invalid choice.")

        except ValueError:
            print("Invalid input.")
        except KeyboardInterrupt:
            print("\n\nCancelled.")


if __name__ == "__main__":
    main()
