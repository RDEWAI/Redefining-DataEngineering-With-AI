"""AI agents for library management.

This package contains various AI agents for interacting with the library:
- LibraryAssistant: Traditional JSON schema tool use pattern
- EnhancedLibraryAssistant: Dual-mode assistant (traditional + code execution)
- SearchAgent: Specialized agent for book discovery and search
- AnalyticsAgent: Specialized agent for statistics and reporting
- RecommendationAgent: Specialized agent for book recommendations
- OrchestratorAgent: Central coordinator for multi-agent system
"""

from .analytics_agent import AnalyticsAgent
from .library_assistant import (
    TOOL_DEFINITIONS,
    LibraryAssistant,
    create_assistant,
    get_tool_function,
    get_tools_for_llm,
    interactive_repl,
)
from .library_assistant_enhanced import AssistantMode, EnhancedLibraryAssistant
from .orchestrator_agent import OrchestratorAgent
from .recommendation_agent import RecommendationAgent

# Multi-agent system components
from .search_agent import SearchAgent

__all__ = [
    # Traditional assistant
    "LibraryAssistant",
    "TOOL_DEFINITIONS",
    "create_assistant",
    "get_tool_function",
    "get_tools_for_llm",
    "interactive_repl",
    # Enhanced assistant
    "EnhancedLibraryAssistant",
    "AssistantMode",
    # Multi-agent system
    "SearchAgent",
    "AnalyticsAgent",
    "RecommendationAgent",
    "OrchestratorAgent",
]
