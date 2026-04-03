"""Standardized tool functions for library operations.

This module provides tool functions that wrap the BookRepository and
LendingRepository methods in a format suitable for LLM tool calling.
Each function returns structured data that can be serialized to JSON.

All functions include user-friendly error messages and handle edge cases
gracefully.
"""

from typing import Any

from .domain import BookStatus, Category
from .lending_repository import LendingRepository, get_lending_repository
from .repository import BookRepository, get_repository

# Module-level repository instances (lazy initialization)
_repository: BookRepository | None = None
_lending_repository: LendingRepository | None = None


def _get_repo() -> BookRepository:
    """Get or create the module-level repository instance."""
    global _repository
    if _repository is None:
        _repository = get_repository()
    return _repository


def _get_lending_repo() -> LendingRepository:
    """Get or create the module-level lending repository instance."""
    global _lending_repository
    if _lending_repository is None:
        _lending_repository = get_lending_repository()
    return _lending_repository


def set_repository(repo: BookRepository) -> None:
    """Set the repository instance for testing.

    Args:
        repo: BookRepository instance to use
    """
    global _repository
    _repository = repo


def set_lending_repository(repo: LendingRepository) -> None:
    """Set the lending repository instance for testing.

    Args:
        repo: LendingRepository instance to use
    """
    global _lending_repository
    _lending_repository = repo


def close_repository() -> None:
    """Close the module-level repository connections.

    This releases file locks to allow subprocess access to the database.
    """
    global _repository, _lending_repository
    if _repository is not None:
        _repository.close()
    if _lending_repository is not None:
        _lending_repository.close()


def reopen_repository(db_path: str | None = None, read_only: bool = True) -> None:
    """Reopen the module-level repository connections.

    Args:
        db_path: Optional database path (uses default if not provided)
        read_only: If True, open database in read-only mode
    """
    global _repository, _lending_repository
    import os

    path: str = (
        db_path or os.getenv("DB_PATH", "data/duckdb/chapter2.db") or "data/duckdb/chapter2.db"
    )
    if _repository is not None and not _repository.is_open():
        _repository.reopen(path, read_only=read_only)
    if _lending_repository is not None and not _lending_repository.is_open():
        _lending_repository.reopen(path, read_only=read_only)


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


def get_book_details(book_id: str, include_description: bool = True) -> dict[str, Any]:
    """Get complete details for a specific book.

    Args:
        book_id: Book ID (e.g., "B001")
        include_description: If True (default), include the book description.
                            Set to False for token-efficient responses.

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
                "book": book.to_dict(include_description=include_description),
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


def get_popular_books(
    category: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Get popular/featured books, optionally filtered by category.

    This returns books from the catalog as recommendations. Use this when users
    ask for "top books", "popular books", "best books in category".

    NOTE: This does NOT use lending data. For lending-based rankings (actual most lent books),
    use get_most_lent_books() which requires RAG mode.

    Args:
        category: Optional category filter (Programming, History, Science, Fiction, Thriller)
        limit: Maximum number of results (default 10)

    Returns:
        Dictionary with:
        - success: bool indicating if operation was successful
        - count: number of books found
        - books: list of book dictionaries
        - message: user-friendly message

    Example:
        >>> result = get_popular_books("Programming", limit=5)
        >>> print(result["message"])
        Top 5 Programming books (prioritizing available)
    """
    try:
        repo = _get_repo()

        # Validate category if provided
        cat = None
        if category:
            cat = Category(category)

        # Get books, prioritizing available ones
        if cat:
            books = repo.list_by_category(cat)
        else:
            # Get all books
            books = []
            for c in Category:
                books.extend(repo.list_by_category(c))

        # Sort: Available (Present) first, then alphabetically by title
        sorted_books = sorted(
            books, key=lambda b: (0 if b.status == BookStatus.PRESENT else 1, b.title)
        )

        # Limit results
        limited_books = sorted_books[:limit]
        book_list = [book.to_dict() for book in limited_books]

        cat_msg = f" {category}" if category else ""
        message = f"Top {len(book_list)}{cat_msg} books (prioritizing available)"

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
            "message": f"Error getting popular books: {str(e)}",
        }


# RAG components (lazy initialization)
_embedding_generator = None
_vector_store = None


def _get_rag_components() -> tuple:
    """Get or create RAG components (embedding generator and vector store)."""
    global _embedding_generator, _vector_store

    if _embedding_generator is None:
        # Try relative import first (works for make assistant/assistant-rag),
        # then src-prefixed (works for scripts that add chapter-2 to path)
        try:
            from rag.embeddings import EmbeddingGenerator
        except ImportError:
            from src.agentic.rag.embeddings import EmbeddingGenerator

        _embedding_generator = EmbeddingGenerator()

    if _vector_store is None:
        from pathlib import Path

        try:
            from rag.vector_store import DuckDBVectorStore
        except ImportError:
            from src.agentic.rag.vector_store import DuckDBVectorStore

        db_path = Path(__file__).parent.parent.parent.parent / "data" / "duckdb" / "chapter2.db"
        _vector_store = DuckDBVectorStore(db_path=str(db_path), read_only=True)

    return _embedding_generator, _vector_store


def semantic_search(
    query: str,
    top_k: int = 5,
) -> dict[str, Any]:
    """Search books using natural language semantic similarity.

    Uses RAG (Retrieval-Augmented Generation) with vector embeddings to find
    books semantically similar to the query. This is useful for queries like
    "books about time travel" or "something about programming for beginners".

    Args:
        query: Natural language search query
        top_k: Maximum number of results (default 5)

    Returns:
        Dictionary with:
        - success: bool indicating if search was successful
        - count: number of results found
        - books: list of book dictionaries with similarity scores
        - message: user-friendly message

    Example:
        >>> result = semantic_search("books about time travel")
        >>> print(result["message"])
        Found 5 books semantically similar to 'books about time travel'
    """
    try:
        generator, store = _get_rag_components()

        # Check if embeddings exist
        if store.get_embedding_count() == 0:
            return {
                "success": False,
                "count": 0,
                "books": [],
                "message": "Semantic search not available. Run 'make generate-embeddings' first.",
            }

        # Generate query embedding
        query_embedding = generator.embed_text(query)

        # Search for similar books
        results = store.semantic_search(query_embedding, top_k=top_k)

        if not results:
            return {
                "success": True,
                "count": 0,
                "books": [],
                "message": f"No books found semantically similar to '{query}'",
            }

        # Enrich results with book details
        repo = _get_repo()
        enriched_results = []
        for result in results:
            book = repo.get_book_by_id(result["book_id"])
            if book:
                book_dict = book.to_dict(include_description=True)
                book_dict["similarity"] = round(result["similarity"], 3)
                enriched_results.append(book_dict)

        message = f"Found {len(enriched_results)} book(s) semantically similar to '{query}'"

        return {
            "success": True,
            "count": len(enriched_results),
            "books": enriched_results,
            "message": message,
        }
    except Exception as e:
        return {
            "success": False,
            "count": 0,
            "books": [],
            "message": f"Error in semantic search: {str(e)}",
        }


# =============================================================================
# Lending tools
# =============================================================================

# Lending RAG components (lazy initialization)
_lending_embedding_generator = None
_lending_vector_store = None


def _get_lending_rag_components() -> tuple:
    """Get or create lending RAG components (embedding generator and vector store)."""
    global _lending_embedding_generator, _lending_vector_store

    if _lending_embedding_generator is None:
        try:
            from rag.embeddings import EmbeddingGenerator
        except ImportError:
            from src.agentic.rag.embeddings import EmbeddingGenerator

        _lending_embedding_generator = EmbeddingGenerator()

    if _lending_vector_store is None:
        from pathlib import Path

        try:
            from rag.vector_store import LendingVectorStore
        except ImportError:
            from src.agentic.rag.vector_store import LendingVectorStore

        db_path = Path(__file__).parent.parent.parent.parent / "data" / "duckdb" / "chapter2.db"
        _lending_vector_store = LendingVectorStore(db_path=str(db_path), read_only=True)

    return _lending_embedding_generator, _lending_vector_store


def search_lending(
    book_id: str | None = None,
    patron_segment: str | None = None,
    region: str | None = None,
    channel: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Search lending records with optional filters.

    Args:
        book_id: Filter by book ID
        patron_segment: Filter by segment (Individual, Corporate, Educational, Government)
        region: Filter by region (Northeast, Southeast, Midwest, West, International)
        channel: Filter by channel (In-Store, Online, Phone Order, Partner)
        limit: Maximum number of results (default 20)

    Returns:
        Dictionary with:
        - success: bool indicating if search was successful
        - count: number of results found
        - loans: list of loan dictionaries
        - message: user-friendly message
    """
    try:
        repo = _get_lending_repo()
        loans = repo.search_lending(
            book_id=book_id,
            patron_segment=patron_segment,
            region=region,
            channel=channel,
            limit=limit,
        )

        loans_list = [loan.to_dict() for loan in loans]

        filters = []
        if book_id:
            filters.append(f"book '{book_id}'")
        if patron_segment:
            filters.append(f"segment '{patron_segment}'")
        if region:
            filters.append(f"region '{region}'")
        if channel:
            filters.append(f"channel '{channel}'")

        filter_msg = f" for {', '.join(filters)}" if filters else ""
        message = f"Found {len(loans)} loan(s){filter_msg}"

        return {
            "success": True,
            "count": len(loans_list),
            "loans": loans_list,
            "message": message,
        }
    except Exception as e:
        return {
            "success": False,
            "count": 0,
            "loans": [],
            "message": f"Error searching lending: {str(e)}",
        }


def get_book_lending(book_id: str) -> dict[str, Any]:
    """Get all loans for a specific book.

    Args:
        book_id: Book ID (e.g., "B001")

    Returns:
        Dictionary with:
        - success: bool indicating if operation was successful
        - count: number of loans found
        - loans: list of loan dictionaries
        - book_info: book title and author if found
        - message: user-friendly message
    """
    try:
        lending_repo = _get_lending_repo()
        book_repo = _get_repo()

        book = book_repo.get_book_by_id(book_id)
        if not book:
            return {
                "success": False,
                "count": 0,
                "loans": [],
                "book_info": None,
                "message": f"No book found with ID '{book_id}'",
            }

        loans = lending_repo.get_lending_for_book(book_id)
        loans_list = [loan.to_dict() for loan in loans]

        total_fees = sum(float(loan.total_fees) for loan in loans)
        total_units = sum(loan.quantity for loan in loans)

        message = f"'{book.title}' has {len(loans)} loan(s): {total_units} copies lent, ${total_fees:.2f} total fees"

        return {
            "success": True,
            "count": len(loans_list),
            "loans": loans_list,
            "book_info": {"title": book.title, "author": book.author},
            "total_units": total_units,
            "total_fees": total_fees,
            "message": message,
        }
    except Exception as e:
        return {
            "success": False,
            "count": 0,
            "loans": [],
            "book_info": None,
            "message": f"Error getting book lending: {str(e)}",
        }


def get_lending_stats() -> dict[str, Any]:
    """Get aggregate statistics about lending.

    Returns:
        Dictionary with:
        - success: bool indicating if operation was successful
        - stats: dictionary of lending statistics
        - message: summary message
    """
    try:
        repo = _get_lending_repo()
        stats = repo.get_lending_stats()

        message = (
            f"Total: {stats['total_loans']} loans, ${stats['total_fees']:,.2f} fees, "
            f"{stats['total_units']} copies lent, {stats['unique_patrons']} unique patrons"
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
            "message": f"Error retrieving lending statistics: {str(e)}",
        }


def get_most_lent_books(limit: int = 10) -> dict[str, Any]:
    """Get most lent books ranked by total quantity lent.

    Args:
        limit: Maximum number of results (default 10)

    Returns:
        Dictionary with:
        - success: bool indicating if operation was successful
        - count: number of results
        - books: list of most-lent book dictionaries
        - message: user-friendly message
    """
    try:
        repo = _get_lending_repo()
        top_books = repo.get_most_lent_books(limit=limit)

        if top_books:
            top_book = top_books[0]
            message = f"Top {len(top_books)} most lent books. #1: '{top_book['title']}' with {top_book['total_quantity']} copies lent (${top_book['total_fees']:.2f})"
        else:
            message = "No lending data found"

        return {
            "success": True,
            "count": len(top_books),
            "books": top_books,
            "message": message,
        }
    except Exception as e:
        return {
            "success": False,
            "count": 0,
            "books": [],
            "message": f"Error getting most lent books: {str(e)}",
        }


def search_lending_semantic(
    query: str,
    top_k: int = 10,
) -> dict[str, Any]:
    """Search lending using natural language semantic similarity.

    Uses RAG with vector embeddings to find loans semantically similar to the query.
    This is useful for queries like "bulk corporate loans", "holiday online lending",
    "waived fee programming books".

    Args:
        query: Natural language search query
        top_k: Maximum number of results (default 10)

    Returns:
        Dictionary with:
        - success: bool indicating if search was successful
        - count: number of results found
        - loans: list of loan dictionaries with similarity scores
        - message: user-friendly message
    """
    try:
        generator, store = _get_lending_rag_components()

        # Check if embeddings exist
        if store.get_embedding_count() == 0:
            return {
                "success": False,
                "count": 0,
                "loans": [],
                "message": "Lending semantic search not available. Run 'make generate-lending-embeddings' first.",
            }

        # Generate query embedding
        query_embedding = generator.embed_text(query)

        # Search for similar loans
        results = store.semantic_search(query_embedding, top_k=top_k)

        if not results:
            return {
                "success": True,
                "count": 0,
                "loans": [],
                "message": f"No loans found semantically similar to '{query}'",
            }

        # Enrich results with loan and book details
        lending_repo = _get_lending_repo()
        book_repo = _get_repo()
        enriched_results = []
        for result in results:
            loan = lending_repo.get_loan_by_id(result["loan_id"])
            if loan:
                loan_dict = loan.to_dict()
                loan_dict["similarity"] = round(result["similarity"], 3)
                # Add book info
                book = book_repo.get_book_by_id(loan.book_id)
                if book:
                    loan_dict["book_title"] = book.title
                    loan_dict["book_author"] = book.author
                enriched_results.append(loan_dict)

        message = f"Found {len(enriched_results)} loan(s) semantically similar to '{query}'"

        return {
            "success": True,
            "count": len(enriched_results),
            "loans": enriched_results,
            "message": message,
        }
    except Exception as e:
        return {
            "success": False,
            "count": 0,
            "loans": [],
            "message": f"Error in lending semantic search: {str(e)}",
        }


# Export all tool functions
__all__ = [
    # Book tools (always available)
    "search_books",
    "get_book_details",
    "check_availability",
    "list_by_category",
    "list_by_status",
    "locate_book",
    "find_books_in_cabinet",
    "get_weak_signal_books",
    "get_library_stats",
    "get_popular_books",  # Top books by category (no lending data needed)
    # RAG book tools (requires RAG mode)
    "semantic_search",
    # Lending tools (requires RAG mode)
    "search_lending",
    "get_book_lending",
    "get_lending_stats",
    "get_most_lent_books",
    "search_lending_semantic",
    # Repository management
    "set_repository",
    "set_lending_repository",
    "close_repository",
    "reopen_repository",
]
