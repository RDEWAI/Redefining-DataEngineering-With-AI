#!/usr/bin/env python3
"""Token comparison benchmark for Traditional vs Code Execution modes.

This script runs a fixed benchmark query in both modes and compares token usage.

Usage:
    python benchmarks/token_comparison.py
    # or
    make benchmark
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add chapter-3 to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path, override=True)


def run_benchmark():
    """Run the token comparison benchmark."""
    print("=" * 70)
    print("Token Comparison Benchmark")
    print("=" * 70)
    print()
    print("Benchmark Query:")
    print("  'Show top 5 categories by missing books with average signal strength'")
    print()
    print("This benchmark compares token usage between:")
    print("  1. Traditional Tool Calling - Multiple tool calls")
    print("  2. Code Execution - Single Python script")
    print()
    print("-" * 70)
    print()

    # Check for API key
    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        print("ERROR: No API key found.")
        print("Set OPENROUTER_API_KEY or LLM_API_KEY in .env file")
        print()
        print("For a quick demo without API calls, run:")
        print("  make compare-modes-enterprise-all")
        return

    try:
        from src.agents.library_assistant import LibraryAssistant
        from src.agents.library_assistant_enhanced import EnhancedLibraryAssistant
        from src.llm.unified_client import UnifiedLLMClient

        # Initialize LLM client
        client = UnifiedLLMClient.from_env()
        print(f"Using LLM: {client.default_model}")
        print()

        benchmark_query = "Show top 5 categories by missing books with average signal strength"

        # Mode 1: Traditional Tool Calling
        print("Mode 1: Traditional Tool Calling")
        print("-" * 40)

        traditional = LibraryAssistant(
            llm_provider=client,
            show_tool_calls=False,
            enable_rag=False,
        )
        traditional_response = traditional.query(benchmark_query)
        traditional_usage = traditional.get_token_usage()

        print(f"  Response length: {len(traditional_response)} chars")
        print(f"  Prompt tokens: {traditional_usage.get('total_prompt_tokens', 'N/A')}")
        print(f"  Completion tokens: {traditional_usage.get('total_completion_tokens', 'N/A')}")
        print(f"  Total tokens: {traditional_usage.get('total_tokens', 'N/A')}")
        print(f"  Tool calls: {traditional_usage.get('tool_calls_count', 'N/A')}")
        print()

        # Mode 2: Code Execution
        print("Mode 2: Code Execution")
        print("-" * 40)

        enhanced = EnhancedLibraryAssistant(
            llm_provider=client,
            show_tool_calls=False,
            enable_rag=False,
        )
        enhanced_response = enhanced.query(benchmark_query)
        enhanced_usage = enhanced.get_token_usage()

        print(f"  Response length: {len(enhanced_response)} chars")
        print(f"  Prompt tokens: {enhanced_usage.get('total_prompt_tokens', 'N/A')}")
        print(f"  Completion tokens: {enhanced_usage.get('total_completion_tokens', 'N/A')}")
        print(f"  Total tokens: {enhanced_usage.get('total_tokens', 'N/A')}")
        print()

        # Comparison
        print("=" * 70)
        print("COMPARISON RESULTS")
        print("=" * 70)

        trad_total = traditional_usage.get("total_tokens", 0)
        exec_total = enhanced_usage.get("total_tokens", 0)

        if trad_total > 0 and exec_total > 0:
            reduction = ((trad_total - exec_total) / trad_total) * 100
            print(f"  Traditional mode: {trad_total:,} tokens")
            print(f"  Code execution:   {exec_total:,} tokens")
            print(f"  Token reduction:  {reduction:.1f}%")

            if reduction > 30:
                print()
                print("  ✓ Code execution demonstrates significant token savings!")
            else:
                print()
                print("  Note: Results may vary based on query complexity")
        else:
            print("  Could not calculate token reduction (missing usage data)")

        print()
        print("-" * 70)
        print("Benchmark complete!")
        print()
        print("For enterprise scale comparison with 100 dummy tools, run:")
        print("  make compare-modes-enterprise-all")

        # Save results
        results = {
            "timestamp": datetime.now().isoformat(),
            "query": benchmark_query,
            "traditional": {
                "tokens": trad_total,
                "tool_calls": traditional_usage.get("tool_calls_count", 0),
            },
            "code_execution": {
                "tokens": exec_total,
            },
            "reduction_percent": round(((trad_total - exec_total) / trad_total) * 100, 1)
            if trad_total > 0
            else 0,
        }

        results_dir = Path(__file__).parent / "results"
        results_dir.mkdir(exist_ok=True)
        results_file = results_dir / "token_comparison.json"

        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)

        print(f"Results saved to: {results_file}")

    except ImportError as e:
        print(f"ERROR: Could not import required modules: {e}")
        print("Make sure you have run 'make dev-setup' first")
    except Exception as e:
        print(f"ERROR: Benchmark failed: {e}")
        raise


if __name__ == "__main__":
    run_benchmark()
