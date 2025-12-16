"""Tool-to-API transformer for code execution.

This module converts library tool functions into Python API code that can be
executed in the sandbox. This allows LLMs to generate code that calls library
functions instead of using JSON tool calls.

Token efficiency: Single code block vs. multiple tool call round trips.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from library.repository import BookRepository  # noqa: E402


class ToolAPIGenerator:
    """Generate Python API code from library tools.

    This class creates a Python module with functions that wrap the
    BookRepository methods. The generated code includes:
    - Type hints
    - Docstrings
    - Error handling
    - Database connection setup

    Example:
        >>> repo = BookRepository("library.db")
        >>> generator = ToolAPIGenerator(repo, db_path="library.db")
        >>> api_code = generator.generate_api_code()
        >>> # api_code contains functions like search_books(), get_book_details(), etc.
    """

    def __init__(
        self,
        repository: BookRepository,
        db_path: str | None = None,
        include_rag: bool = False,
    ):
        """Initialize the API generator.

        Args:
            repository: BookRepository instance for database access
            db_path: Path to database (required for generating API code)
            include_rag: Whether to include semantic_search (RAG) function
        """
        self.repository = repository
        self.db_path = db_path or "data/duckdb/chapter3.db"
        self.include_rag = include_rag

    def set_include_rag(self, include_rag: bool) -> None:
        """Set whether to include RAG (semantic_search) function.

        Args:
            include_rag: Whether to include semantic_search
        """
        self.include_rag = include_rag

    def generate_discovery_functions(self) -> str:
        """Generate tool discovery functions for progressive loading.

        Returns:
            Python code with list_tools() and get_tool_help() functions

        This implements Anthropic's progressive loading pattern where
        the LLM discovers tools on-demand instead of loading all upfront.
        """
        tool_docs = self.get_tool_descriptions()

        # Create a mapping of tool names to their full documentation
        tool_help_map = {
            "search_books": """search_books(query: str, category: Optional[str] = None) -> List[Dict[str, Any]]
    Search books by title, author, or keyword.

    Args:
        query: Search query string (matches title or author)
        category: Optional category filter (Programming, History, Science, Fiction, Thriller)

    Returns:
        List of matching books with all fields

    Example:
        books = search_books("Python", category="Programming")""",
            "get_book_details": """get_book_details(book_id: str) -> Optional[Dict[str, Any]]
    Get detailed information for a specific book.

    Args:
        book_id: Unique book identifier (e.g., "B001")

    Returns:
        Book details dictionary or None if not found""",
            "check_availability": """check_availability(book_id: str) -> Dict[str, Any]
    Check if a book is available for checkout.

    Args:
        book_id: Unique book identifier

    Returns:
        Dictionary with availability status and details""",
            "list_by_category": """list_by_category(category: str, status: Optional[str] = None) -> List[Dict[str, Any]]
    List all books in a specific category.

    Args:
        category: Category name (Programming, History, Science, Fiction, Thriller)
        status: Optional status filter (Present, Missing, Checked Out)

    Returns:
        List of books in the category""",
            "list_by_status": """list_by_status(status: str, category: Optional[str] = None) -> List[Dict[str, Any]]
    List all books with a specific status.

    Args:
        status: Book status (Present, Missing, Checked Out)
        category: Optional category filter

    Returns:
        List of books with the specified status""",
            "locate_book": """locate_book(book_id: str) -> Optional[Dict[str, Any]]
    Get the physical location of a book.

    Args:
        book_id: Unique book identifier

    Returns:
        Location dictionary or None if not found""",
            "find_books_in_cabinet": """find_books_in_cabinet(cabinet: int, rack: Optional[int] = None) -> List[Dict[str, Any]]
    Find all books in a specific cabinet or rack.

    Args:
        cabinet: Cabinet number
        rack: Optional rack number within cabinet

    Returns:
        List of books in the specified location""",
            "get_weak_signal_books": """get_weak_signal_books(threshold: float = -55.0) -> List[Dict[str, Any]]
    Find books with weak RFID signal strength.

    Args:
        threshold: Signal strength threshold in dBm (default: -55)

    Returns:
        List of books with signal below threshold""",
        }

        # Conditionally add semantic_search if RAG is enabled
        if self.include_rag:
            tool_help_map[
                "semantic_search"
            ] = """semantic_search(query: str, top_k: int = 5) -> List[Dict[str, Any]]
    Search books using natural language semantic similarity (RAG).

    Use this when the user asks about books "about" a topic, "like" something,
    or uses vague/conceptual descriptions.

    Args:
        query: Natural language search query (e.g., "books about time travel")
        top_k: Number of results to return (default: 5)

    Returns:
        List of books with similarity scores

    Example:
        results = semantic_search("books about time travel")
        for book in results:
            print(f"{book['title']} - similarity: {book['similarity']}")"""

        # Generate the discovery functions
        code = f'''
# Tool Discovery Functions (Progressive Loading Pattern)

_TOOL_DESCRIPTIONS = {repr(tool_docs)}
_TOOL_HELP = {repr(tool_help_map)}

def list_tools():
    """List all available API functions.

    Returns:
        List of tool names

    Example:
        >>> tools = list_tools()
        >>> print(tools)
        ['search_books', 'get_book_details', 'check_availability', ...]
    """
    return list(_TOOL_DESCRIPTIONS.keys())

def get_tool_help(tool_name: str) -> str:
    """Get detailed help for a specific tool.

    Args:
        tool_name: Name of the tool

    Returns:
        Help text with signature, arguments, and examples

    Example:
        >>> help_text = get_tool_help('search_books')
        >>> print(help_text)
    """
    if tool_name not in _TOOL_HELP:
        available = ', '.join(list_tools())
        return f"Unknown tool: {{tool_name}}. Available tools: {{available}}"

    return _TOOL_HELP[tool_name]
'''
        return code

    def generate_api_code(self, include_setup: bool = True) -> str:
        """Generate complete Python API code for library tools.

        Args:
            include_setup: If True, include imports and database setup.
                          If False, only generate function definitions (for sandbox injection).

        Returns:
            Python code string with all tool functions defined

        The generated code includes:
        - Import statements (if include_setup=True)
        - Database connection setup (if include_setup=True)
        - All library tool functions with docstrings
        - semantic_search only if include_rag=True
        """
        code_parts = []

        if include_setup:
            code_parts.append(self._generate_imports())
            code_parts.append(self._generate_db_setup())

        code_parts.extend(
            [
                self._generate_search_books(),
                self._generate_get_book_details(),
                self._generate_check_availability(),
                self._generate_list_by_category(),
                self._generate_list_by_status(),
                self._generate_locate_book(),
                self._generate_find_books_in_cabinet(),
                self._generate_get_weak_signal_books(),
            ]
        )

        # Conditionally add semantic_search if RAG is enabled
        if self.include_rag:
            code_parts.append(self._generate_semantic_search())

        return "\n\n".join(code_parts)

    def _generate_imports(self) -> str:
        """Generate import statements."""
        return """# Library API - Auto-generated tool functions
import duckdb
from typing import List, Dict, Any, Optional"""

    def _generate_db_setup(self) -> str:
        """Generate database connection setup."""
        return f"""
# Database connection (read-only for safety)
DB_PATH = {repr(self.db_path)}
_conn = duckdb.connect(DB_PATH, read_only=True)
"""

    def _generate_search_books(self) -> str:
        """Generate search_books function."""
        return '''
def search_books(query: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search books by title, author, or category.

    Args:
        query: Search query string (matches title or author)
        category: Optional category filter (Programming, History, Science, Fiction, Thriller)

    Returns:
        List of matching books (without description for token efficiency)

    Example:
        >>> books = search_books("Python", category="Programming")
        >>> print(f"Found {len(books)} books")
    """
    sql = """
        SELECT book_id, title, author, category,
               cabinet, rack, row, signal_strength,
               timestamp, status
        FROM library.books
        WHERE (title ILIKE ? OR author ILIKE ?)
    """
    params = [f"%{query}%", f"%{query}%"]

    if category:
        sql += " AND category = ?"
        params.append(category)

    sql += " ORDER BY title"

    results = _conn.execute(sql, params).fetchall()

    books = []
    for row in results:
        books.append({
            "book_id": row[0],
            "title": row[1],
            "author": row[2],
            "category": row[3],
            "location": {
                "cabinet": row[4],
                "rack": row[5],
                "row": row[6]
            },
            "signal_strength": row[7],
            "timestamp": str(row[8]),
            "status": row[9]
        })

    return books
'''

    def _generate_get_book_details(self) -> str:
        """Generate get_book_details function."""
        return '''
def get_book_details(book_id: str) -> Optional[Dict[str, Any]]:
    """Get detailed information for a specific book.

    Args:
        book_id: Unique book identifier (e.g., "B001")

    Returns:
        Book details dictionary or None if not found

    Example:
        >>> book = get_book_details("B001")
        >>> if book:
        ...     print(f"{book['title']} by {book['author']}")
    """
    result = _conn.execute("""
        SELECT book_id, title, author, description, category,
               cabinet, rack, row, signal_strength,
               timestamp, status
        FROM library.books
        WHERE book_id = ?
    """, [book_id]).fetchone()

    if not result:
        return None

    return {
        "book_id": result[0],
        "title": result[1],
        "author": result[2],
        "description": result[3],
        "category": result[4],
        "location": {
            "cabinet": result[5],
            "rack": result[6],
            "row": result[7]
        },
        "signal_strength": result[8],
        "timestamp": str(result[9]),
        "status": result[10],
        "has_weak_signal": result[8] < -55,
        "is_available": result[10] == "Present"
    }
'''

    def _generate_check_availability(self) -> str:
        """Generate check_availability function."""
        return '''
def check_availability(book_id: str) -> Dict[str, Any]:
    """Check if a book is available for checkout.

    Args:
        book_id: Unique book identifier

    Returns:
        Dictionary with availability status and details

    Example:
        >>> status = check_availability("B001")
        >>> if status['available']:
        ...     print(f"Book is at {status['location']}")
    """
    book = get_book_details(book_id)

    if not book:
        return {
            "available": False,
            "status": "Not Found",
            "location": None
        }

    return {
        "available": book["status"] == "Present",
        "status": book["status"],
        "location": f"Cabinet {book['location']['cabinet']}, Rack {book['location']['rack']}, Row {book['location']['row']}",
        "signal_strength": book["signal_strength"],
        "has_weak_signal": book["has_weak_signal"]
    }
'''

    def _generate_list_by_category(self) -> str:
        """Generate list_by_category function."""
        return '''
def list_by_category(category: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all books in a specific category.

    Args:
        category: Category name (Programming, History, Science, Fiction, Thriller)
        status: Optional status filter (Present, Missing, Checked Out)

    Returns:
        List of books in the category (without description for token efficiency)

    Example:
        >>> books = list_by_category("Programming", status="Present")
        >>> print(f"Found {len(books)} available programming books")
    """
    sql = """
        SELECT book_id, title, author, category,
               cabinet, rack, row, signal_strength,
               timestamp, status
        FROM library.books
        WHERE category = ?
    """
    params = [category]

    if status:
        sql += " AND status = ?"
        params.append(status)

    sql += " ORDER BY title"

    results = _conn.execute(sql, params).fetchall()

    books = []
    for row in results:
        books.append({
            "book_id": row[0],
            "title": row[1],
            "author": row[2],
            "category": row[3],
            "location": {
                "cabinet": row[4],
                "rack": row[5],
                "row": row[6]
            },
            "signal_strength": row[7],
            "timestamp": str(row[8]),
            "status": row[9]
        })

    return books
'''

    def _generate_list_by_status(self) -> str:
        """Generate list_by_status function."""
        return '''
def list_by_status(status: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all books with a specific status.

    Args:
        status: Book status (Present, Missing, Checked Out)
        category: Optional category filter

    Returns:
        List of books with the specified status (without description for token efficiency)

    Example:
        >>> missing_books = list_by_status("Missing")
        >>> print(f"{len(missing_books)} books are missing")
    """
    sql = """
        SELECT book_id, title, author, category,
               cabinet, rack, row, signal_strength,
               timestamp, status
        FROM library.books
        WHERE status = ?
    """
    params = [status]

    if category:
        sql += " AND category = ?"
        params.append(category)

    sql += " ORDER BY category, title"

    results = _conn.execute(sql, params).fetchall()

    books = []
    for row in results:
        books.append({
            "book_id": row[0],
            "title": row[1],
            "author": row[2],
            "category": row[3],
            "location": {
                "cabinet": row[4],
                "rack": row[5],
                "row": row[6]
            },
            "signal_strength": row[7],
            "timestamp": str(row[8]),
            "status": row[9]
        })

    return books
'''

    def _generate_locate_book(self) -> str:
        """Generate locate_book function."""
        return '''
def locate_book(book_id: str) -> Optional[Dict[str, Any]]:
    """Get the physical location of a book.

    Args:
        book_id: Unique book identifier

    Returns:
        Location dictionary or None if not found

    Example:
        >>> location = locate_book("B001")
        >>> if location:
        ...     print(f"Book is in {location['description']}")
    """
    book = get_book_details(book_id)

    if not book:
        return None

    return {
        "book_id": book["book_id"],
        "title": book["title"],
        "cabinet": book["location"]["cabinet"],
        "rack": book["location"]["rack"],
        "row": book["location"]["row"],
        "description": f"Cabinet {book['location']['cabinet']}, Rack {book['location']['rack']}, Row {book['location']['row']}",
        "signal_strength": book["signal_strength"],
        "status": book["status"]
    }
'''

    def _generate_find_books_in_cabinet(self) -> str:
        """Generate find_books_in_cabinet function."""
        return '''
def find_books_in_cabinet(cabinet: int, rack: Optional[int] = None) -> List[Dict[str, Any]]:
    """Find all books in a specific cabinet or rack.

    Args:
        cabinet: Cabinet number
        rack: Optional rack number within cabinet

    Returns:
        List of books in the specified location (without description for token efficiency)

    Example:
        >>> books = find_books_in_cabinet(3, rack=2)
        >>> print(f"Found {len(books)} books in Cabinet 3, Rack 2")
    """
    sql = """
        SELECT book_id, title, author, category,
               cabinet, rack, row, signal_strength,
               timestamp, status
        FROM library.books
        WHERE cabinet = ?
    """
    params = [cabinet]

    if rack is not None:
        sql += " AND rack = ?"
        params.append(rack)

    sql += " ORDER BY rack, row, title"

    results = _conn.execute(sql, params).fetchall()

    books = []
    for row in results:
        books.append({
            "book_id": row[0],
            "title": row[1],
            "author": row[2],
            "category": row[3],
            "location": {
                "cabinet": row[4],
                "rack": row[5],
                "row": row[6]
            },
            "signal_strength": row[7],
            "timestamp": str(row[8]),
            "status": row[9]
        })

    return books
'''

    def _generate_get_weak_signal_books(self) -> str:
        """Generate get_weak_signal_books function."""
        return '''
def get_weak_signal_books(threshold: float = -55.0) -> List[Dict[str, Any]]:
    """Find books with weak RFID signal strength.

    Args:
        threshold: Signal strength threshold in dBm (default: -55)

    Returns:
        List of books with signal below threshold (without description for token efficiency)

    Example:
        >>> weak_books = get_weak_signal_books()
        >>> print(f"{len(weak_books)} books need RFID maintenance")
    """
    results = _conn.execute("""
        SELECT book_id, title, author, category,
               cabinet, rack, row, signal_strength,
               timestamp, status
        FROM library.books
        WHERE signal_strength < ?
        ORDER BY signal_strength ASC
    """, [threshold]).fetchall()

    books = []
    for row in results:
        books.append({
            "book_id": row[0],
            "title": row[1],
            "author": row[2],
            "category": row[3],
            "location": {
                "cabinet": row[4],
                "rack": row[5],
                "row": row[6]
            },
            "signal_strength": row[7],
            "timestamp": str(row[8]),
            "status": row[9]
        })

    return books
'''

    def _generate_semantic_search(self) -> str:
        """Generate semantic_search function for RAG."""
        return '''
def semantic_search(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Search books using natural language semantic similarity (RAG).

    Use this when the user asks about books "about" a topic, "like" something,
    or uses vague/conceptual descriptions like "time travel" or "adventure stories".

    Args:
        query: Natural language search query
        top_k: Number of results to return (default: 5)

    Returns:
        List of books with similarity scores, sorted by relevance

    Example:
        >>> results = semantic_search("books about time travel")
        >>> for book in results:
        ...     print(f"{book['title']} - similarity: {book['similarity']}")
    """
    from sentence_transformers import SentenceTransformer
    import numpy as np

    # Load embedding model (cached after first load)
    model = SentenceTransformer("all-MiniLM-L6-v2")

    # Generate query embedding
    query_embedding = model.encode(query, convert_to_numpy=True, normalize_embeddings=True)

    # Search using cosine similarity in DuckDB
    query_list = query_embedding.tolist()

    results = _conn.execute(f"""
        SELECT
            be.book_id,
            array_cosine_similarity(be.embedding, ?::FLOAT[384]) as similarity
        FROM library.book_embeddings be
        ORDER BY similarity DESC
        LIMIT ?
    """, [query_list, top_k]).fetchall()

    if not results:
        return []

    # Get book details for each result
    books = []
    for book_id, similarity in results:
        book = get_book_details(book_id)
        if book:
            book["similarity"] = round(similarity, 3)
            books.append(book)

    return books
'''

    def get_tool_descriptions(self) -> dict[str, str]:
        """Get descriptions of all available tool functions.

        Returns:
            Dictionary mapping function names to their descriptions

        Useful for:
        - Generating LLM prompts
        - Documentation generation
        - API discovery
        """
        descriptions = {
            "search_books": "Search books by title, author, or category",
            "get_book_details": "Get detailed information for a specific book",
            "check_availability": "Check if a book is available for checkout",
            "list_by_category": "List all books in a specific category",
            "list_by_status": "List all books with a specific status",
            "locate_book": "Get the physical location of a book",
            "find_books_in_cabinet": "Find all books in a specific cabinet or rack",
            "get_weak_signal_books": "Find books with weak RFID signal strength",
        }

        # Conditionally add semantic_search if RAG is enabled
        if self.include_rag:
            descriptions["semantic_search"] = (
                "Search books using natural language semantic similarity (RAG)"
            )

        return descriptions

    def generate_usage_examples(self) -> str:
        """Generate code examples for using the API.

        Returns:
            Python code string with usage examples

        Useful for:
        - LLM prompt engineering
        - Testing
        - Documentation
        """
        return """
# Example usage of library API functions

# 1. Search for books
python_books = search_books("Python", category="Programming")
print(f"Found {len(python_books)} Python programming books")

# 2. Get book details
book = get_book_details("B001")
if book:
    print(f"{book['title']} by {book['author']}")
    print(f"Location: Cabinet {book['location']['cabinet']}, Rack {book['location']['rack']}")

# 3. Check availability
status = check_availability("B001")
if status['available']:
    print(f"Book is available at {status['location']}")
else:
    print(f"Book status: {status['status']}")

# 4. List books by category
history_books = list_by_category("History", status="Present")
print(f"{len(history_books)} history books available")

# 5. Find missing books
missing = list_by_status("Missing")
print(f"{len(missing)} books are missing")

# 6. Locate a specific book
location = locate_book("B001")
if location:
    print(f"Found at {location['description']}")

# 7. Browse books in a cabinet
cabinet_books = find_books_in_cabinet(3, rack=2)
print(f"{len(cabinet_books)} books in Cabinet 3, Rack 2")

# 8. Find books needing RFID maintenance
weak_signal = get_weak_signal_books(threshold=-55)
print(f"{len(weak_signal)} books need RFID maintenance")
"""
