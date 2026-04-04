"""Integration tests for assistants with enterprise dummy tools enabled.

Tests for Phase 7.5 - Enterprise Tool Scale Demonstration:
- T7.5-036: Create test_assistant_dummy.py
- T7.5-037: Test LibraryAssistant initializes with dummy tools enabled
- T7.5-038: Test EnhancedLibraryAssistant initializes with dummy tools enabled
- T7.5-039: Test library queries still work correctly with dummy tools present
- T7.5-040: Test token usage increases in traditional mode with dummy tools

These tests verify that adding 100 enterprise dummy tools doesn't break
the core library functionality and demonstrates the token overhead.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from src.agentic.tools.dummy_tools import get_total_tool_count  # noqa: E402

# Skip tests if database is not available
DB_PATH = os.getenv("DB_PATH", str(Path(__file__).parent.parent.parent / "data/duckdb/chapter2.db"))
SKIP_IF_NO_DB = pytest.mark.skipif(
    not os.path.exists(DB_PATH),
    reason=f"Database not found at {DB_PATH}. Run 'make load-data' first.",
)


class TestLibraryAssistantWithDummyTools:
    """Integration tests for LibraryAssistant with dummy tools enabled."""

    @SKIP_IF_NO_DB
    def test_assistant_initializes_with_dummy_tools(self):
        """T7.5-037: Test LibraryAssistant initializes with dummy tools enabled."""
        from src.agentic.agents.library_assistant import LibraryAssistant
        from src.agentic.llm.base import LLMProvider

        # Mock the LLM provider
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.default_model = "test-model"

        # Create assistant with dummy tools enabled
        assistant = LibraryAssistant(
            llm_provider=mock_provider,
            enable_dummy_tools=True,
        )

        # Verify dummy tools are enabled
        assert assistant.is_dummy_tools_enabled() is True

        # Verify tool count includes dummy tools
        # Base library tools (10) + RAG (0 if disabled) + Dummy tools (100) = 110
        base_tools = 10  # 10 library tools (including get_library_stats and get_popular_books)
        expected_count = base_tools + get_total_tool_count()
        actual_count = assistant.get_tool_count()

        assert (
            actual_count == expected_count
        ), f"Expected {expected_count} tools (10 base + 100 dummy), got {actual_count}"

    @SKIP_IF_NO_DB
    def test_assistant_toggle_dummy_tools(self):
        """Test toggling dummy tools on and off."""
        from src.agentic.agents.library_assistant import LibraryAssistant
        from src.agentic.llm.base import LLMProvider

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.default_model = "test-model"

        # Start without dummy tools
        assistant = LibraryAssistant(
            llm_provider=mock_provider,
            enable_dummy_tools=False,
        )

        base_count = assistant.get_tool_count()
        assert assistant.is_dummy_tools_enabled() is False
        assert (
            base_count == 10
        )  # 10 library tools (including get_library_stats and get_popular_books)

        # Enable dummy tools
        assistant.set_dummy_tools_enabled(True)
        assert assistant.is_dummy_tools_enabled() is True

        # Tool count should increase by 100
        new_count = assistant.get_tool_count()
        assert (
            new_count == base_count + 100
        ), f"Expected {base_count + 100} tools after enabling dummy tools, got {new_count}"

        # Disable dummy tools
        assistant.set_dummy_tools_enabled(False)
        assert assistant.is_dummy_tools_enabled() is False
        assert assistant.get_tool_count() == base_count

    @SKIP_IF_NO_DB
    def test_assistant_with_rag_and_dummy_tools(self):
        """Test assistant with both RAG and dummy tools enabled."""
        from src.agentic.agents.library_assistant import LibraryAssistant
        from src.agentic.llm.base import LLMProvider

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.default_model = "test-model"

        # Create assistant with both RAG and dummy tools
        assistant = LibraryAssistant(
            llm_provider=mock_provider,
            enable_rag=True,
            enable_dummy_tools=True,
        )

        # 10 base + 12 RAG/lending/replenish tools + 100 dummy = 122
        expected_count = 10 + 12 + 100
        actual_count = assistant.get_tool_count()

        assert (
            actual_count == expected_count
        ), f"Expected {expected_count} tools (10 base + 12 RAG/lending/replenish + 100 dummy), got {actual_count}"


class TestEnhancedLibraryAssistantWithDummyTools:
    """Integration tests for EnhancedLibraryAssistant with dummy tools enabled."""

    @SKIP_IF_NO_DB
    def test_enhanced_assistant_initializes_with_dummy_tools(self):
        """T7.5-038: Test EnhancedLibraryAssistant initializes with dummy tools enabled."""
        from src.agentic.agents.library_assistant_enhanced import EnhancedLibraryAssistant
        from src.agentic.llm.base import LLMProvider

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.default_model = "test-model"

        # Create enhanced assistant with dummy tools enabled
        assistant = EnhancedLibraryAssistant(
            llm_provider=mock_provider,
            enable_dummy_tools=True,
            db_path=DB_PATH,
        )

        # Verify dummy tools are enabled
        assert assistant.is_dummy_tools_enabled() is True

        # Verify tool count includes dummy tools (in traditional mode)
        assistant.set_mode("traditional")
        traditional_count = assistant.get_tool_count()

        # 10 base + 0 RAG + 100 dummy = 110 (traditional uses 10 base tools)
        expected_traditional = 10 + 100
        assert (
            traditional_count == expected_traditional
        ), f"Expected {expected_traditional} tools in traditional mode, got {traditional_count}"

    @SKIP_IF_NO_DB
    def test_enhanced_assistant_code_execution_mode_with_dummy_tools(self):
        """Test code execution mode includes dummy tool API stubs."""
        from src.agentic.agents.library_assistant_enhanced import EnhancedLibraryAssistant
        from src.agentic.llm.base import LLMProvider

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.default_model = "test-model"

        assistant = EnhancedLibraryAssistant(
            llm_provider=mock_provider,
            mode="code_execution",
            enable_dummy_tools=True,
            db_path=DB_PATH,
        )

        assert assistant.get_mode() == "code_execution"
        assert assistant.is_dummy_tools_enabled() is True

        # In code execution mode, tool count should still include dummy tools
        code_count = assistant.get_tool_count()
        expected_code = (
            10 + 100
        )  # 10 library API tools + dummy (includes get_library_stats and get_popular_books)
        assert (
            code_count == expected_code
        ), f"Expected {expected_code} tools in code mode, got {code_count}"

    @SKIP_IF_NO_DB
    def test_enhanced_assistant_mode_switching_with_dummy_tools(self):
        """Test switching modes preserves dummy tools setting."""
        from src.agentic.agents.library_assistant_enhanced import EnhancedLibraryAssistant
        from src.agentic.llm.base import LLMProvider

        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.default_model = "test-model"

        assistant = EnhancedLibraryAssistant(
            llm_provider=mock_provider,
            mode="traditional",
            enable_dummy_tools=True,
            db_path=DB_PATH,
        )

        # Start in traditional mode
        assert assistant.get_mode() == "traditional"
        assert assistant.is_dummy_tools_enabled() is True
        _ = assistant.get_tool_count()  # Just verify it doesn't error

        # Switch to code execution mode
        assistant.set_mode("code_execution")
        assert assistant.get_mode() == "code_execution"
        assert assistant.is_dummy_tools_enabled() is True  # Should persist

        # Switch back to traditional
        assistant.set_mode("traditional")
        assert assistant.is_dummy_tools_enabled() is True  # Should still persist


class TestLibraryQueriesWithDummyTools:
    """Tests to verify library queries still work with dummy tools present."""

    @SKIP_IF_NO_DB
    def test_library_tools_still_accessible(self):
        """T7.5-039: Test library queries still work correctly with dummy tools present."""
        from src.agentic.agents.library_assistant import get_tool_function  # noqa: E402

        # Verify all library tool functions are still accessible
        library_tools = [
            "search_books",
            "get_book_details",
            "check_availability",
            "list_by_category",
            "list_by_status",
            "locate_book",
            "find_books_in_cabinet",
            "get_weak_signal_books",
            "get_library_stats",
            "get_popular_books",
        ]

        for tool_name in library_tools:
            try:
                func = get_tool_function(tool_name, include_dummy_tools=True)
                assert callable(func), f"{tool_name} is not callable"
            except ValueError as e:
                pytest.fail(f"Could not get library tool {tool_name}: {e}")

    @SKIP_IF_NO_DB
    def test_library_tool_execution_with_dummy_tools_enabled(self):
        """Test that library tools execute correctly when dummy tools are also loaded."""
        from library import tools as library_tools

        # Execute a simple library tool
        result = library_tools.get_library_stats()

        assert "success" in result
        assert result["success"] is True
        assert "stats" in result

        # Verify we have books in the database (nested in stats)
        stats = result["stats"]
        assert "total_books" in stats
        assert stats["total_books"] > 0, "Expected books in database"

    @SKIP_IF_NO_DB
    def test_get_tool_function_returns_dummy_tool(self):
        """Test that get_tool_function can retrieve dummy tools."""
        from src.agentic.agents.library_assistant import get_tool_function

        # Try to get a dummy tool function
        func = get_tool_function("engineering_run_build", include_dummy_tools=True)

        assert callable(func)

        # Execute the dummy tool
        result = func(project="test-project")
        assert result["success"] is True
        assert result["domain"] == "engineering"

    @SKIP_IF_NO_DB
    def test_get_tool_function_raises_for_unknown_tool(self):
        """Test that get_tool_function raises for unknown tools."""
        from src.agentic.agents.library_assistant import get_tool_function

        with pytest.raises(ValueError, match="Unknown tool"):
            get_tool_function("nonexistent_tool", include_dummy_tools=True)


class TestTokenUsageWithDummyTools:
    """Tests for token usage impact of dummy tools."""

    @SKIP_IF_NO_DB
    def test_tool_definitions_count_increases_with_dummy_tools(self):
        """T7.5-040: Verify tool definition count increases with dummy tools."""
        from src.agentic.agents.library_assistant import get_tools_for_llm

        # Get tools without dummy tools
        tools_without_dummy = get_tools_for_llm(include_rag=False, include_dummy_tools=False)

        # Get tools with dummy tools
        tools_with_dummy = get_tools_for_llm(include_rag=False, include_dummy_tools=True)

        # Verify counts
        assert (
            len(tools_without_dummy) == 10
        ), f"Expected 10 base tools, got {len(tools_without_dummy)}"
        assert (
            len(tools_with_dummy) == 110
        ), f"Expected 110 tools (10 + 100), got {len(tools_with_dummy)}"

        # Verify difference is exactly 100
        diff = len(tools_with_dummy) - len(tools_without_dummy)
        assert diff == 100, f"Expected difference of 100, got {diff}"

    @SKIP_IF_NO_DB
    def test_estimate_token_overhead(self):
        """Estimate and verify token overhead from tool definitions."""
        import json

        from src.agentic.agents.library_assistant import get_tools_for_llm  # noqa: E402

        # Get tools with and without dummy tools
        tools_without = get_tools_for_llm(include_rag=False, include_dummy_tools=False)
        tools_with = get_tools_for_llm(include_rag=False, include_dummy_tools=True)

        # Estimate token overhead (rough: ~4 chars per token)
        json_without = json.dumps(tools_without)
        json_with = json.dumps(tools_with)

        chars_without = len(json_without)
        chars_with = len(json_with)
        char_increase = chars_with - chars_without

        # Estimate tokens (rough approximation: ~4 chars per token)
        tokens_without_est = chars_without // 4
        tokens_with_est = chars_with // 4
        token_increase_est = tokens_with_est - tokens_without_est

        # Log the estimates for debugging
        print("\nTool definition size estimates:")
        print(f"  Without dummy tools: ~{tokens_without_est:,} tokens ({chars_without:,} chars)")
        print(f"  With dummy tools:    ~{tokens_with_est:,} tokens ({chars_with:,} chars)")
        print(f"  Increase:            ~{token_increase_est:,} tokens ({char_increase:,} chars)")

        # Verify significant increase
        # Enterprise dummy tools should add substantial token overhead
        assert (
            token_increase_est > 10000
        ), f"Expected >10,000 token increase from dummy tools, got ~{token_increase_est}"

    def test_tool_api_generator_dummy_stubs_size(self):
        """Verify code execution mode API stubs are much smaller."""
        from src.agentic.code_execution.tool_api import ToolAPIGenerator
        from src.agentic.library.repository import BookRepository

        # Create generator with dummy tools
        repo = MagicMock(spec=BookRepository)
        generator = ToolAPIGenerator(
            repository=repo,
            db_path="test.db",
            include_rag=False,
            include_dummy_tools=True,
        )

        # Generate API code (what code execution mode uses)
        api_code = generator.generate_api_code(include_setup=False)

        # Estimate tokens
        api_chars = len(api_code)
        api_tokens_est = api_chars // 4

        print("\nAPI stub size estimates:")
        print(f"  API code: ~{api_tokens_est:,} tokens ({api_chars:,} chars)")

        # API stubs should be much smaller than JSON tool definitions
        # This is the key token efficiency advantage
        # The API stubs include 100 dummy tools but should still be reasonable
        assert (
            api_tokens_est < 20000
        ), f"API stubs too large: ~{api_tokens_est} tokens. Expected efficient representation."


class TestToolAPIGeneratorWithDummyTools:
    """Tests for ToolAPIGenerator with dummy tools."""

    def test_generator_includes_dummy_tool_stubs(self):
        """Test that ToolAPIGenerator generates dummy tool API stubs."""
        from src.agentic.code_execution.tool_api import ToolAPIGenerator
        from src.agentic.library.repository import BookRepository

        repo = MagicMock(spec=BookRepository)
        generator = ToolAPIGenerator(
            repository=repo,
            db_path="test.db",
            include_dummy_tools=True,
        )

        api_code = generator.generate_api_code(include_setup=False)

        # Verify dummy tool functions are present
        assert "engineering_run_build" in api_code
        assert "data_query_warehouse" in api_code
        assert "security_scan_vulnerabilities" in api_code
        assert "_mock_response" in api_code

    def test_generator_excludes_dummy_stubs_when_disabled(self):
        """Test that dummy tool stubs are excluded when disabled."""
        from src.agentic.code_execution.tool_api import ToolAPIGenerator
        from src.agentic.library.repository import BookRepository

        repo = MagicMock(spec=BookRepository)
        generator = ToolAPIGenerator(
            repository=repo,
            db_path="test.db",
            include_dummy_tools=False,
        )

        api_code = generator.generate_api_code(include_setup=False)

        # Verify dummy tool functions are NOT present
        assert "engineering_run_build" not in api_code
        assert "_mock_response" not in api_code

        # But library tools should still be present
        assert "search_books" in api_code
        assert "get_book_details" in api_code

    def test_generator_toggle_dummy_tools(self):
        """Test toggling dummy tools in generator."""
        from src.agentic.code_execution.tool_api import ToolAPIGenerator
        from src.agentic.library.repository import BookRepository

        repo = MagicMock(spec=BookRepository)
        generator = ToolAPIGenerator(
            repository=repo,
            db_path="test.db",
            include_dummy_tools=False,
        )

        # Initially off
        api_without = generator.generate_api_code(include_setup=False)
        assert "engineering_run_build" not in api_without

        # Toggle on
        generator.set_include_dummy_tools(True)
        api_with = generator.generate_api_code(include_setup=False)
        assert "engineering_run_build" in api_with

        # Toggle off
        generator.set_include_dummy_tools(False)
        api_without_again = generator.generate_api_code(include_setup=False)
        assert "engineering_run_build" not in api_without_again
