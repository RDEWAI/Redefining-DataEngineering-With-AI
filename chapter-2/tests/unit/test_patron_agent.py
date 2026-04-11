"""Unit tests for the Patron Agent.

PatronAgent has access to library inventory and shelf location only.
No lending revenue, replenishment, or operational analytics.

Tools (8 total):
  Base (7):  search_books, get_book_details, check_availability,
             locate_book, find_books_in_cabinet, list_by_category, list_by_status
  RAG  (1):  semantic_search
"""

from unittest.mock import MagicMock

import pytest

from src.agentic.agents.patron_agent import (
    PATRON_BASE_TOOLS,
    PATRON_RAG_TOOLS,
)
from src.agentic.llm.base import LLMProvider


@pytest.fixture
def mock_llm() -> MagicMock:
    provider = MagicMock(spec=LLMProvider)
    provider.default_model = "mock-model"
    return provider


@pytest.fixture
def patron_agent(mock_llm: MagicMock) -> object:
    from src.agentic.agents.library_assistant import LibraryAssistant
    from src.agentic.agents.patron_agent import PATRON_BASE_TOOLS, PATRON_RAG_TOOLS, SYSTEM_PROMPT

    return LibraryAssistant(
        llm_provider=mock_llm,
        system_prompt=SYSTEM_PROMPT,
        enable_rag=True,
        base_tool_definitions=PATRON_BASE_TOOLS,
        rag_tool_definitions=PATRON_RAG_TOOLS,
    )


# ── Tool set tests ──────────────────────────────────────────────────────────


def test_patron_base_tool_count() -> None:
    assert len(PATRON_BASE_TOOLS) == 7


def test_patron_base_tool_names() -> None:
    names = {t.name for t in PATRON_BASE_TOOLS}
    assert names == {
        "search_books",
        "get_book_details",
        "check_availability",
        "locate_book",
        "find_books_in_cabinet",
        "list_by_category",
        "list_by_status",
    }


def test_patron_rag_tool_count() -> None:
    assert len(PATRON_RAG_TOOLS) == 1


def test_patron_rag_tool_names() -> None:
    names = {t.name for t in PATRON_RAG_TOOLS}
    assert names == {"semantic_search"}


def test_patron_agent_has_8_tools(patron_agent: object) -> None:
    assert patron_agent.get_tool_count() == 8  # type: ignore[attr-defined]


def test_patron_agent_has_no_revenue_tools(patron_agent: object) -> None:
    tool_names = {t.name for t in patron_agent._tools}  # type: ignore[attr-defined]
    revenue_tools = {
        "get_lending_stats",
        "search_lending",
        "get_book_lending",
        "get_most_lent_books",
        "search_lending_semantic",
        "search_replenish",
        "get_book_replenish",
        "get_replenish_stats",
        "get_most_replenished_books",
        "get_replenish_by_month",
        "search_replenish_semantic",
        "get_popular_books",
        "get_library_stats",
        "get_weak_signal_books",
    }
    assert tool_names.isdisjoint(revenue_tools)
