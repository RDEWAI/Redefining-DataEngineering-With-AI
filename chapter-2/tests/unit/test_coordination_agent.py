"""Unit tests for the Coordination Agent.

CoordinationAgent has exclusive access to lending revenue and replenishment data.
Patrons cannot access any of these tools.

Tools (14 total):
  Base (3):  get_library_stats, get_weak_signal_books, get_popular_books
  RAG (11):  get_lending_stats, search_lending, get_book_lending,
             get_most_lent_books, search_lending_semantic,
             search_replenish, get_book_replenish, get_replenish_stats,
             get_most_replenished_books, get_replenish_by_month,
             search_replenish_semantic
"""

from unittest.mock import MagicMock

import pytest

from src.agentic.agents.coordination_agent import (
    COORDINATION_BASE_TOOLS,
    COORDINATION_RAG_TOOLS,
)
from src.agentic.llm.base import LLMProvider


@pytest.fixture
def mock_llm() -> MagicMock:
    provider = MagicMock(spec=LLMProvider)
    provider.default_model = "mock-model"
    return provider


@pytest.fixture
def coordination_agent(mock_llm: MagicMock) -> object:
    from src.agentic.agents.coordination_agent import (
        COORDINATION_BASE_TOOLS,
        COORDINATION_RAG_TOOLS,
        SYSTEM_PROMPT,
    )
    from src.agentic.agents.library_assistant import LibraryAssistant

    return LibraryAssistant(
        llm_provider=mock_llm,
        system_prompt=SYSTEM_PROMPT,
        enable_rag=True,
        base_tool_definitions=COORDINATION_BASE_TOOLS,
        rag_tool_definitions=COORDINATION_RAG_TOOLS,
    )


# ── Tool set tests ──────────────────────────────────────────────────────────


def test_coordination_base_tool_count() -> None:
    assert len(COORDINATION_BASE_TOOLS) == 3


def test_coordination_base_tool_names() -> None:
    names = {t.name for t in COORDINATION_BASE_TOOLS}
    assert names == {
        "get_library_stats",
        "get_weak_signal_books",
        "get_popular_books",
    }


def test_coordination_rag_tool_count() -> None:
    assert len(COORDINATION_RAG_TOOLS) == 11


def test_coordination_rag_tool_names() -> None:
    names = {t.name for t in COORDINATION_RAG_TOOLS}
    assert names == {
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
    }


def test_coordination_agent_has_14_tools(coordination_agent: object) -> None:
    assert coordination_agent.get_tool_count() == 14  # type: ignore[attr-defined]


def test_coordination_agent_has_no_patron_shelf_tools(coordination_agent: object) -> None:
    tool_names = {t.name for t in coordination_agent._tools}  # type: ignore[attr-defined]
    patron_only = {
        "search_books",
        "get_book_details",
        "check_availability",
        "locate_book",
        "find_books_in_cabinet",
        "list_by_category",
        "list_by_status",
        "semantic_search",
    }
    assert tool_names.isdisjoint(patron_only)


def test_patron_and_coordination_tools_are_disjoint() -> None:
    from src.agentic.agents.patron_agent import PATRON_BASE_TOOLS, PATRON_RAG_TOOLS

    patron_names = {t.name for t in PATRON_BASE_TOOLS + PATRON_RAG_TOOLS}
    coord_names = {t.name for t in COORDINATION_BASE_TOOLS + COORDINATION_RAG_TOOLS}
    assert patron_names.isdisjoint(coord_names)


def test_combined_tool_count_equals_22() -> None:
    from src.agentic.agents.patron_agent import PATRON_BASE_TOOLS, PATRON_RAG_TOOLS

    patron_names = {t.name for t in PATRON_BASE_TOOLS + PATRON_RAG_TOOLS}
    coord_names = {t.name for t in COORDINATION_BASE_TOOLS + COORDINATION_RAG_TOOLS}
    assert len(patron_names | coord_names) == 22
