"""Standardized tool functions for library operations.

This module provides tool functions that wrap the BookRepository methods
in a format suitable for LLM tool calling. Each function returns structured
data that can be serialized to JSON.

All functions include user-friendly error messages and handle edge cases
gracefully.
"""

from typing import Any

from .domain import BookStatus, Category
from .repository import BookRepository, get_repository

# Module-level repository instance (lazy initialization)
_repository: BookRepository | None = None


def _get_repo() -> BookRepository:
    """Get or create the module-level repository instance."""
    global _repository
    if _repository is None:
        _repository = get_repository()
    return _repository


def set_repository(repo: BookRepository) -> None:
    """Set the repository instance for testing.

    Args:
        repo: BookRepository instance to use
    """
    global _repository
    _repository = repo


def search_books(
    query: str,
    category: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Search books by title, author, or keyword.

    Args:
        query: Search query to match against title or author
        category: Optional category filter (Programming, History, Science, Fiction, Thriller)
        limit: Maximum number of results (default 10)

    Returns:
        Dictionary with:
        - success: bool indicating if search was successful
        - count: number of results found
        - books: list of book dictionaries
        - message: user-friendly message

    Example:
        >>> result = search_books("Python", category="Programming")
        >>> print(result["message"])
        Found 3 books matching 'Python' in Programming
    """
    try:
        repo = _get_repo()

        cat = Category(category) if category else None
        books = repo.search_books(query, category=cat, limit=limit)

        book_list = [book.to_dict() for book in books]

        if books:
            cat_msg = f" in {category}" if category else ""
            message = f"Found {len(books)} book(s) matching '{query}'{cat_msg}"
        else:
            message = f"No books found matching '{query}'"

        return {
            "success": True,
            "count": len(book_list),
            "books": book_list,
            "message": message,
        }
    except ValueError:
        return {
            "success": False,
            "count": 0,
            "books": [],
            "message": f"Invalid category: {category}. Valid options are: Programming, History, Science, Fiction, Thriller",
        }
    except Exception as e:
        return {
            "success": False,
            "count": 0,
            "books": [],
            "message": f"Error searching books: {str(e)}",
        }


def get_book_details(book_id: str) -> dict[str, Any]:
    """Get complete details for a specific book.

    Args:
        book_id: Book ID (e.g., "B001")

    Returns:
        Dictionary with:
        - success: bool indicating if book was found
        - book: book dictionary if found, None otherwise
        - message: user-friendly message

    Example:
        >>> result = get_book_details("B001")
        >>> print(result["book"]["title"])
        Python Programming
    """
    try:
        repo = _get_repo()
        book = repo.get_book_by_id(book_id)

        if book:
            return {
                "success": True,
                "book": book.to_dict(),
                "message": f"Found book: {book.title} by {book.author}",
            }
        else:
            return {
                "success": False,
                "book": None,
                "message": f"No book found with ID '{book_id}'. Please check the book ID and try again.",
            }
    except Exception as e:
        return {
            "success": False,
            "book": None,
            "message": f"Error retrieving book details: {str(e)}",
        }


def check_availability(book_id: str) -> dict[str, Any]:
    """Check if a book is available for checkout.

    Args:
        book_id: Book ID to check

    Returns:
        Dictionary with:
        - success: bool indicating if check was successful
        - available: bool indicating if book is available
        - status: current book status
        - location: location string if available
        - message: user-friendly message
    """
    try:
        repo = _get_repo()
        book = repo.get_book_by_id(book_id)

        if book:
            location_str = str(book.location) if book.is_available else None

            if book.is_available:
                message = f"'{book.title}' is available at {book.location}"
            elif book.status == BookStatus.CHECKED_OUT:
                message = f"'{book.title}' is currently checked out"
            else:
                message = f"'{book.title}' is marked as missing"

            return {
                "success": True,
                "available": book.is_available,
                "status": book.status.value,
                "location": location_str,
                "title": book.title,
                "message": message,
            }
        else:
            return {
                "success": False,
                "available": False,
                "status": None,
                "location": None,
                "title": None,
                "message": f"No book found with ID '{book_id}'. Please check the book ID and try again.",
            }
    except Exception as e:
        return {
            "success": False,
            "available": False,
            "status": None,
            "location": None,
            "title": None,
            "message": f"Error checking availability: {str(e)}",
        }


def list_by_category(
    category: str,
    status: str | None = None,
) -> dict[str, Any]:
    """List all books in a specific category.

    Args:
        category: Category to filter by (Programming, History, Science, Fiction, Thriller)
        status: Optional status filter (Present, Missing, Checked Out)

    Returns:
        Dictionary with:
        - success: bool indicating if operation was successful
        - count: number of books found
        - books: list of book dictionaries
        - message: user-friendly message
    """
    try:
        repo = _get_repo()
        cat = Category(category)
        stat = BookStatus(status) if status else None

        books = repo.list_by_category(cat, status=stat)
        book_list = [book.to_dict() for book in books]

        status_msg = f" with status '{status}'" if status else ""
        message = f"Found {len(books)} book(s) in {category}{status_msg}"

        return {
            "success": True,
            "count": len(book_list),
            "books": book_list,
            "message": message,
        }
    except ValueError:
        valid_cats = ", ".join([c.value for c in Category])
        valid_stats = ", ".join([s.value for s in BookStatus])
        return {
            "success": False,
            "count": 0,
            "books": [],
            "message": f"Invalid value. Valid categories: {valid_cats}. Valid statuses: {valid_stats}",
        }
    except Exception as e:
        return {
            "success": False,
            "count": 0,
            "books": [],
            "message": f"Error listing books: {str(e)}",
        }


def list_by_status(
    status: str,
    category: str | None = None,
) -> dict[str, Any]:
    """List all books with a specific availability status.

    Args:
        status: Status to filter by (Present, Missing, Checked Out)
        category: Optional category filter

    Returns:
        Dictionary with:
        - success: bool indicating if operation was successful
        - count: number of books found
        - books: list of book dictionaries
        - message: user-friendly message
    """
    try:
        repo = _get_repo()
        stat = BookStatus(status)
        cat = Category(category) if category else None

        books = repo.list_by_status(stat, category=cat)
        book_list = [book.to_dict() for book in books]

        cat_msg = f" in {category}" if category else ""
        message = f"Found {len(books)} book(s) with status '{status}'{cat_msg}"

        return {
            "success": True,
            "count": len(book_list),
            "books": book_list,
            "message": message,
        }
    except ValueError:
        valid_stats = ", ".join([s.value for s in BookStatus])
        valid_cats = ", ".join([c.value for c in Category])
        return {
            "success": False,
            "count": 0,
            "books": [],
            "message": f"Invalid value. Valid statuses: {valid_stats}. Valid categories: {valid_cats}",
        }
    except Exception as e:
        return {
            "success": False,
            "count": 0,
            "books": [],
            "message": f"Error listing books: {str(e)}",
        }


def locate_book(book_id: str) -> dict[str, Any]:
    """Get the physical location of a book.

    Args:
        book_id: Book ID to locate

    Returns:
        Dictionary with:
        - success: bool indicating if book was found
        - location: location dictionary if found
        - location_string: human-readable location string
        - message: user-friendly message
    """
    try:
        repo = _get_repo()
        book = repo.get_book_by_id(book_id)

        if book:
            return {
                "success": True,
                "book_id": book.book_id,
                "title": book.title,
                "location": {
                    "cabinet": book.location.cabinet,
                    "rack": book.location.rack,
                    "row": book.location.row,
                },
                "location_string": str(book.location),
                "status": book.status.value,
                "message": f"'{book.title}' is located at {book.location}"
                if book.status == BookStatus.PRESENT
                else f"'{book.title}' was last seen at {book.location} (currently {book.status.value})",
            }
        else:
            return {
                "success": False,
                "book_id": book_id,
                "title": None,
                "location": None,
                "location_string": None,
                "status": None,
                "message": f"No book found with ID '{book_id}'. Please check the book ID and try again.",
            }
    except Exception as e:
        return {
            "success": False,
            "book_id": book_id,
            "title": None,
            "location": None,
            "location_string": None,
            "status": None,
            "message": f"Error locating book: {str(e)}",
        }


def find_books_in_cabinet(
    cabinet: int,
    rack: int | None = None,
) -> dict[str, Any]:
    """List all books in a specific cabinet.

    Args:
        cabinet: Cabinet number
        rack: Optional rack number within cabinet

    Returns:
        Dictionary with:
        - success: bool indicating if operation was successful
        - count: number of books found
        - books: list of book dictionaries
        - message: user-friendly message
    """
    try:
        repo = _get_repo()

        if cabinet < 1:
            return {
                "success": False,
                "count": 0,
                "books": [],
                "message": "Cabinet number must be at least 1",
            }

        if rack is not None and rack < 1:
            return {
                "success": False,
                "count": 0,
                "books": [],
                "message": "Rack number must be at least 1",
            }

        books = repo.find_books_in_cabinet(cabinet, rack=rack)
        book_list = [book.to_dict() for book in books]

        rack_msg = f", Rack {rack}" if rack else ""
        if books:
            message = f"Found {len(books)} book(s) in Cabinet {cabinet}{rack_msg}"
        else:
            message = f"No books found in Cabinet {cabinet}{rack_msg}"

        return {
            "success": True,
            "count": len(book_list),
            "cabinet": cabinet,
            "rack": rack,
            "books": book_list,
            "message": message,
        }
    except Exception as e:
        return {
            "success": False,
            "count": 0,
            "cabinet": cabinet,
            "rack": rack,
            "books": [],
            "message": f"Error finding books in cabinet: {str(e)}",
        }


def get_weak_signal_books(threshold: float = -55.0) -> dict[str, Any]:
    """Get books with weak RFID signal that may need maintenance.

    Args:
        threshold: Signal strength threshold in dBm (default -55)

    Returns:
        Dictionary with:
        - success: bool indicating if operation was successful
        - count: number of books with weak signal
        - books: list of book dictionaries (ordered by signal strength)
        - message: user-friendly message
    """
    try:
        repo = _get_repo()
        books = repo.get_weak_signal_books(threshold=threshold)
        book_list = [book.to_dict() for book in books]

        if books:
            message = f"Found {len(books)} book(s) with weak signal (below {threshold} dBm). Consider maintenance or relocation."
        else:
            message = (
                f"No books found with weak signal (below {threshold} dBm). RFID coverage is good!"
            )

        return {
            "success": True,
            "count": len(book_list),
            "threshold": threshold,
            "books": book_list,
            "message": message,
        }
    except Exception as e:
        return {
            "success": False,
            "count": 0,
            "threshold": threshold,
            "books": [],
            "message": f"Error checking signal strength: {str(e)}",
        }


def get_library_stats() -> dict[str, Any]:
    """Get aggregate statistics about the library.

    Returns:
        Dictionary with:
        - success: bool indicating if operation was successful
        - stats: dictionary of library statistics
        - message: summary message
    """
    try:
        repo = _get_repo()
        stats = repo.get_library_stats()

        message = (
            f"Library has {stats['total_books']} books: "
            f"{stats['available_count']} available, "
            f"{stats['by_status'].get('Checked Out', 0)} checked out, "
            f"{stats['by_status'].get('Missing', 0)} missing. "
            f"{stats['weak_signal_count']} books have weak RFID signal."
        )

        return {
            "success": True,
            "stats": stats,
            "message": message,
        }
    except Exception as e:
        return {
            "success": False,
            "stats": None,
            "message": f"Error retrieving library statistics: {str(e)}",
        }


# Export all tool functions
__all__ = [
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
