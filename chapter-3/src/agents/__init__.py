"""AI agents for library management.

This package contains various AI agents for interacting with the library:
- LibraryAssistant: Traditional JSON schema tool use pattern
"""

from .library_assistant import (
    TOOL_DEFINITIONS,
    LibraryAssistant,
    create_assistant,
    get_tool_function,
    get_tools_for_llm,
    interactive_repl,
)

__all__ = [
    "LibraryAssistant",
    "TOOL_DEFINITIONS",
    "create_assistant",
    "get_tool_function",
    "get_tools_for_llm",
    "interactive_repl",
]
