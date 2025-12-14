"""Library management domain and repository layer.

This package provides:
- Domain classes: Book, BookStatus, Category, Location
- Repository: BookRepository for DuckDB queries
- Tools: Standardized tool functions for LLM integration

Example:
    >>> from src.library import Book, BookRepository, search_books
    >>> repo = BookRepository(db_path="data/duckdb/library.db")
    >>> results = search_books("Python")
"""

from .domain import Book, BookStatus, Category, Location
from .repository import BookRepository, get_repository
from .tools import (
    check_availability,
    find_books_in_cabinet,
    get_book_details,
    get_library_stats,
    get_weak_signal_books,
    list_by_category,
    list_by_status,
    locate_book,
    search_books,
    set_repository,
)

__all__ = [
    # Domain classes
    "Book",
    "BookStatus",
    "Category",
    "Location",
    # Repository
    "BookRepository",
    "get_repository",
    # Tool functions
    "search_books",
    "get_book_details",
    "check_availability",
    "list_by_category",
    "list_by_status",
    "locate_book",
    "find_books_in_cabinet",
    "get_weak_signal_books",
    "get_library_stats",
    "set_repository",
]
