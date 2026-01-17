"""Chapter 2: AI Engineering with Library Management Data.

All components are now under the `agentic` subpackage.
Import from `src.agentic.*` for all functionality.

Example:
    >>> from src.agentic.library import BookRepository
    >>> from src.agentic.llm import OpenRouterProvider
    >>> from src.agentic.agents import LibraryAssistant
"""

__version__ = "0.1.0"

# Re-export agentic package for convenience
from . import agentic

__all__ = ["agentic"]
