#!/usr/bin/env python3
"""Compare traditional tools vs code execution for the same query.

This script demonstrates the token usage difference between:
1. Traditional tool calling (multiple round trips)
2. Code execution (single code generation)

Run the same query in both modes and see the difference!

Enterprise Scale Demo (--enable-dummy-tools):
When enabled, adds 100 enterprise dummy tools across 10 domains to demonstrate
the token efficiency advantage of code execution at enterprise scale.

From Anthropic's "Advanced Tool Use" paper:
    "The token overhead of tool definitions becomes increasingly significant as
    the number of tools grows. For enterprises with hundreds of tools across
    different teams, this can represent a substantial portion of the context budget."

Expected results with dummy tools:
    - Traditional Mode: ~15,000-18,000 tokens for tool definitions alone
    - Code Execution Mode: ~500-800 tokens for API stubs
    - Token Reduction: 80-95%
"""

import os
import sys
from pathlib import Path

# Add chapter-2 directory to path so src.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agentic.agents.library_assistant_enhanced import EnhancedLibraryAssistant
from src.agentic.llm.unified_client import UnifiedLLMClient
from src.agentic.tools.dummy_tools import get_domain_tool_count, get_total_tool_count

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


def print_tool_breakdown(enable_dummy_tools: bool) -> dict[str, int]:
    """Print breakdown of tools by domain.

    Args:
        enable_dummy_tools: Whether dummy tools are enabled

    Returns:
        Dictionary with tool counts by category
    """
    base_tools = 8  # Library tools
    rag_tools = 1  # semantic_search
    dummy_tools = get_total_tool_count() if enable_dummy_tools else 0

    breakdown = {
        "base_library": base_tools,
        "rag": rag_tools,
        "dummy_enterprise": dummy_tools,
        "total": base_tools + rag_tools + dummy_tools
        if enable_dummy_tools
        else base_tools + rag_tools,
    }

    print("\n" + "-" * 60)
    print("TOOL BREAKDOWN")
    print("-" * 60)
    print(f"  Base Library Tools:     {base_tools}")
    print(f"  RAG (semantic_search):  {rag_tools}")

    if enable_dummy_tools:
        print(f"  Enterprise Dummy Tools: {dummy_tools}")
        print()
        print("  Dummy Tools by Domain:")
        domain_counts = get_domain_tool_count()
        for domain, count in domain_counts.items():
            print(f"    - {domain:20} {count}")

    print("-" * 60)
    print(f"  TOTAL TOOLS:            {breakdown['total']}")
    print("-" * 60)

    return breakdown


def estimate_tool_definition_tokens(tool_count: int, include_dummy: bool = False) -> int:
    """Estimate tokens used by tool definitions.

    Tool definitions in JSON schema format typically use:
    - ~150 tokens per simple tool (name, description, basic params)
    - ~180 tokens per enterprise dummy tool (detailed descriptions, complex schemas)

    Args:
        tool_count: Number of tools
        include_dummy: Whether dummy tools with detailed descriptions are included

    Returns:
        Estimated token count for tool definitions
    """
    if include_dummy:
        # Enterprise dummy tools have longer descriptions (~180 tokens each)
        base_tools = 8
        dummy_tools = tool_count - base_tools - 1  # Subtract base + RAG
        return (base_tools * 150) + (1 * 100) + (dummy_tools * 180)
    else:
        return tool_count * 150


def compare_modes(
    query: str,
    llm_provider: UnifiedLLMClient,
    db_path: str,
    enable_rag: bool = False,
    enable_dummy_tools: bool = False,
) -> dict[str, dict[str, int]]:
    """Compare traditional vs code execution for a single query.

    Args:
        query: The query to test
        llm_provider: LLM client
        db_path: Database path
        enable_rag: Whether to enable RAG (semantic search) for this query
        enable_dummy_tools: Whether to include 100 enterprise dummy tools

    Returns:
        Dictionary with usage stats for both modes
    """
    print("\n" + "=" * 80)
    print(f"QUERY: {query}")
    if enable_rag:
        print("[RAG ENABLED] semantic_search tool available")
    if enable_dummy_tools:
        print("[ENTERPRISE SCALE] 100 dummy tools enabled across 10 domains")
    print("=" * 80)

    # Mode 1: Traditional tool calls
    rag_status = "ON" if enable_rag else "OFF"
    dummy_status = "ON" if enable_dummy_tools else "OFF"
    print(f"\n[MODE 1] TRADITIONAL TOOL CALLS (RAG: {rag_status}, Dummy Tools: {dummy_status})")
    print("-" * 80)

    assistant_traditional = EnhancedLibraryAssistant(
        llm_provider=llm_provider,
        mode="traditional",
        db_path=db_path,
        show_tool_calls=True,
        enable_rag=enable_rag,
        enable_dummy_tools=enable_dummy_tools,
    )

    tool_count_trad = assistant_traditional.get_tool_count()
    print(f"Tools loaded: {tool_count_trad}")

    response_trad = assistant_traditional.query(query)
    usage_trad = assistant_traditional.get_token_usage()

    print(f"\nResponse:\n{response_trad}\n")
    print(f"Tokens: {usage_trad['total_tokens']:,}")
    print(f"   - Prompt: {usage_trad['total_prompt_tokens']:,}")
    print(f"   - Completion: {usage_trad['total_completion_tokens']:,}")
    print(f"   - Tool calls: {usage_trad['tool_calls_count']}")

    # Estimate tool definition overhead
    if enable_dummy_tools:
        est_tool_tokens = estimate_tool_definition_tokens(tool_count_trad, include_dummy=True)
        print(f"   - Est. tool definition overhead: ~{est_tool_tokens:,} tokens")

    # Mode 2: Code execution
    print(f"\n[MODE 2] CODE EXECUTION (RAG: {rag_status}, Dummy Tools: {dummy_status})")
    print("-" * 80)

    assistant_code = EnhancedLibraryAssistant(
        llm_provider=llm_provider,
        mode="code_execution",
        db_path=db_path,
        show_tool_calls=True,
        enable_rag=enable_rag,
        enable_dummy_tools=enable_dummy_tools,
    )

    tool_count_code = assistant_code.get_tool_count()
    print(f"Tools available via API stubs: {tool_count_code}")

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

    return {
        "traditional": usage_trad,
        "code_execution": usage_code,
        "tool_count": {"traditional": tool_count_trad, "code_execution": tool_count_code},
    }


def print_enterprise_summary(
    results: list[dict[str, dict[str, int]]], enable_dummy_tools: bool
) -> None:
    """Print summary of enterprise scale comparison results.

    Args:
        results: List of comparison results from multiple queries
        enable_dummy_tools: Whether dummy tools were enabled
    """
    if not results:
        return

    print("\n")
    print("=" * 80)
    print("ENTERPRISE SCALE COMPARISON SUMMARY")
    print("=" * 80)

    total_trad_tokens = sum(r["traditional"]["total_tokens"] for r in results)
    total_code_tokens = sum(r["code_execution"]["total_tokens"] for r in results)

    print(f"\nQueries executed: {len(results)}")
    print(f"Dummy tools enabled: {'YES (100 tools)' if enable_dummy_tools else 'NO'}")

    print("\n" + "-" * 60)
    print("AGGREGATE TOKEN USAGE")
    print("-" * 60)
    print(f"  Traditional mode total:    {total_trad_tokens:,} tokens")
    print(f"  Code execution mode total: {total_code_tokens:,} tokens")

    if total_trad_tokens > 0:
        total_diff = total_trad_tokens - total_code_tokens
        total_reduction_pct = (total_diff / total_trad_tokens) * 100
        print(f"  Total tokens saved:        {total_diff:,} tokens")
        print(f"  Overall reduction:         {total_reduction_pct:.1f}%")

        if enable_dummy_tools:
            print()
            print("-" * 60)
            print("ENTERPRISE SCALE ANALYSIS")
            print("-" * 60)
            print("  Token overhead from 100 enterprise tools:")
            est_overhead = estimate_tool_definition_tokens(
                109, include_dummy=True
            )  # 8 base + 1 RAG + 100 dummy
            print(f"    - Traditional (JSON Schema): ~{est_overhead:,} tokens per request")
            print("    - Code Execution (API stubs): ~600-800 tokens per request")
            print()
            if total_reduction_pct >= 80:
                print("  [PASS] Enterprise scale token reduction meets 80%+ target")
            else:
                print("  [INFO] Token reduction below 80% target")
                print("         This may be due to query-specific factors")

    print()
    print("=" * 80)


def main():
    """Run comparison demo."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Compare traditional tools vs code execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Enterprise Scale Demo:
  Use --enable-dummy-tools to add 100 enterprise dummy tools across 10 domains.
  This demonstrates the token efficiency advantage of code execution at scale.

  Example:
    python compare_modes.py --enable-dummy-tools --all

  Expected results with dummy tools:
    - Traditional Mode: ~15,000-18,000 tokens for tool definitions
    - Code Execution Mode: ~500-800 tokens for API stubs
    - Token Reduction: 80-95%
        """,
    )
    parser.add_argument("--query", help="Custom query to test (if not provided, shows menu)")
    parser.add_argument("--db-path", help="Path to DuckDB database (default: from DB_PATH env var)")
    parser.add_argument("--all", action="store_true", help="Run all sample queries")

    # RAG options - mutually exclusive
    rag_group = parser.add_mutually_exclusive_group()
    rag_group.add_argument("--rag", action="store_true", help="Enable RAG/semantic search")
    rag_group.add_argument("--no-rag", action="store_true", help="Disable RAG/semantic search")

    # Enterprise scale demo
    parser.add_argument(
        "--enable-dummy-tools",
        action="store_true",
        help="Enable 100 enterprise dummy tools across 10 domains for scale demo",
    )

    args = parser.parse_args()

    # Initialize LLM
    try:
        llm = UnifiedLLMClient.from_env()
    except Exception as e:
        print(f"[ERROR] Error initializing LLM client: {e}")
        print("Make sure you have configured LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL in .env")
        sys.exit(1)

    # Get database path
    db_path = args.db_path or os.getenv("DB_PATH", "data/duckdb/chapter2.db")

    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found at: {db_path}")
        print("Run 'make load-data' first to create the database")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("TOKEN USAGE COMPARISON: Traditional Tools vs Code Execution")
    print("=" * 80)
    print("Settings:")
    print(f"  Database:    {db_path}")
    print(f"  Model:       {llm.default_model}")
    print(f"  Base URL:    {os.getenv('LLM_BASE_URL', 'not set')}")
    print("  RAG:         Per-query (RAG+API indicates RAG enabled)")
    print(
        f"  Dummy Tools: {'ENABLED (100 enterprise tools)' if args.enable_dummy_tools else 'disabled'}"
    )

    # Print tool breakdown if dummy tools enabled
    if args.enable_dummy_tools:
        print_tool_breakdown(args.enable_dummy_tools)

    # Determine RAG override
    def get_rag_setting(default_rag: bool) -> bool:
        """Get RAG setting with override support."""
        if args.rag:
            return True
        elif args.no_rag:
            return False
        return default_rag

    # Track results for summary
    all_results: list[dict[str, dict[str, int]]] = []

    if args.all:
        # Run all sample queries
        print(f"\nRunning all {len(SAMPLE_QUERIES)} sample queries...")
        if args.rag:
            print("[!] RAG OVERRIDE: --rag flag forces RAG ON for all queries")
        elif args.no_rag:
            print("[!] RAG OVERRIDE: --no-rag flag forces RAG OFF for all queries")
        if args.enable_dummy_tools:
            print("[!] ENTERPRISE SCALE: 100 dummy tools enabled for all queries")

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
            result = compare_modes(
                query,
                llm,
                db_path,
                enable_rag=effective_rag,
                enable_dummy_tools=args.enable_dummy_tools,
            )
            all_results.append(result)

        # Print enterprise summary if dummy tools enabled
        if args.enable_dummy_tools:
            print_enterprise_summary(all_results, args.enable_dummy_tools)

    elif args.query:
        # Run custom query (default RAG to False unless --rag specified)
        enable_rag = get_rag_setting(False)
        result = compare_modes(
            args.query,
            llm,
            db_path,
            enable_rag=enable_rag,
            enable_dummy_tools=args.enable_dummy_tools,
        )
        all_results.append(result)

        if args.enable_dummy_tools:
            print_enterprise_summary(all_results, args.enable_dummy_tools)

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
                result = compare_modes(
                    query,
                    llm,
                    db_path,
                    enable_rag=enable_rag,
                    enable_dummy_tools=args.enable_dummy_tools,
                )
                all_results.append(result)

                if args.enable_dummy_tools:
                    print_enterprise_summary(all_results, args.enable_dummy_tools)

            elif choice_num == len(SAMPLE_QUERIES) + 1:
                query = input("\nEnter your query: ").strip()
                enable_rag_input = input("Enable RAG/semantic search? (y/N): ").strip().lower()
                enable_rag = enable_rag_input in ("y", "yes")
                if query:
                    result = compare_modes(
                        query,
                        llm,
                        db_path,
                        enable_rag=enable_rag,
                        enable_dummy_tools=args.enable_dummy_tools,
                    )
                    all_results.append(result)

                    if args.enable_dummy_tools:
                        print_enterprise_summary(all_results, args.enable_dummy_tools)
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
                    result = compare_modes(
                        query,
                        llm,
                        db_path,
                        enable_rag=effective_rag,
                        enable_dummy_tools=args.enable_dummy_tools,
                    )
                    all_results.append(result)

                if args.enable_dummy_tools:
                    print_enterprise_summary(all_results, args.enable_dummy_tools)

            else:
                print("Invalid choice.")

        except ValueError:
            print("Invalid input.")
        except KeyboardInterrupt:
            print("\n\nCancelled.")


if __name__ == "__main__":
    main()
