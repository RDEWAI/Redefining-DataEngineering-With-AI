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

from src.agentic.library.repository import BookRepository  # noqa: E402
from src.agentic.tools.dummy_tools import generate_dummy_tools  # noqa: E402


class ToolAPIGenerator:
    """Generate Python API code from library tools.

    This class creates a Python module with functions that wrap the
    BookRepository methods. The generated code includes:
    - Type hints
    - Docstrings
    - Error handling
    - Database connection setup

    Supports agent-specific tool filtering for specialization while
    maintaining backward compatibility (no tools specified = all tools).

    Example:
        >>> repo = BookRepository("library.db")
        >>> generator = ToolAPIGenerator(repo, db_path="library.db")
        >>> api_code = generator.generate_api_code()
        >>> # api_code contains functions like search_books(), get_book_details(), etc.

        # Agent-specific tools:
        >>> generator = ToolAPIGenerator(repo, db_path="library.db",
        ...                              tools=["search_books", "locate_book"])
        >>> api_code = generator.generate_api_code()  # Only search_books and locate_book
    """

    def __init__(
        self,
        repository: BookRepository,
        db_path: str | None = None,
        include_rag: bool = False,
        include_dummy_tools: bool = False,
        tools: list[str] | None = None,
    ):
        """Initialize the API generator.

        Args:
            repository: BookRepository instance for database access
            db_path: Path to database (required for generating API code)
            include_rag: Whether to include semantic_search (RAG) function
            include_dummy_tools: Whether to include enterprise dummy tools
            tools: Optional list of specific tools to include. If None, all tools
                   are included (backward compatible behavior).
        """
        self.repository = repository
        self.db_path = db_path or "data/duckdb/chapter2.db"
        self.include_rag = include_rag
        self.include_dummy_tools = include_dummy_tools
        self.tools = tools  # None = all tools (backward compatible)

    def set_include_rag(self, include_rag: bool) -> None:
        """Set whether to include RAG (semantic_search) function.

        Args:
            include_rag: Whether to include semantic_search
        """
        self.include_rag = include_rag

    def set_include_dummy_tools(self, include_dummy_tools: bool) -> None:
        """Set whether to include enterprise dummy tools.

        Args:
            include_dummy_tools: Whether to include 100 dummy tools
        """
        self.include_dummy_tools = include_dummy_tools

    def _should_include_tool(self, tool_name: str) -> bool:
        """Check if a tool should be included based on filtering.

        Args:
            tool_name: Name of the tool to check

        Returns:
            True if tool should be included, False otherwise
        """
        # If no tools filter specified, include all (backward compatible)
        if self.tools is None:
            return True
        return tool_name in self.tools

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
            "get_library_stats": """get_library_stats() -> Dict[str, Any]
    Get aggregate statistics about the library.

    Returns:
        Dictionary with total_books, available_count, by_status, by_category, weak_signal_count

    Example:
        stats = get_library_stats()
        print(f"Total books: {stats['total_books']}")""",
            "get_popular_books": """get_popular_books(category: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]
    Get popular/featured books, optionally filtered by category.

    Use this to recommend books when users ask for "top books", "popular books",
    "best books in category", etc. This works WITHOUT lending data.
    For lending-based rankings, use get_most_lent_books() which requires RAG mode.

    Args:
        category: Optional category filter (Programming, History, Science, Fiction, Thriller)
        limit: Maximum number of results (default: 10)

    Returns:
        List of featured books with their details

    Example:
        top_programming = get_popular_books("Programming", limit=5)
        for book in top_programming:
            print(f"{book['title']} by {book['author']}")""",
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

            # Add lending tools when RAG is enabled
            tool_help_map[
                "search_lending"
            ] = """search_lending(book_id: Optional[str] = None, patron_segment: Optional[str] = None, region: Optional[str] = None, channel: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]
    Search lending records with optional filters.

    Args:
        book_id: Filter by book ID
        patron_segment: Filter by segment (Individual, Corporate, Educational, Government)
        region: Filter by region (Northeast, Southeast, Midwest, West, International)
        channel: Filter by channel (In-Store, Online, Phone Order, Partner)
        limit: Maximum results (default: 20)

    Returns:
        List of loan dictionaries

    Example:
        loans = search_lending(patron_segment="Corporate", region="Northeast")"""

            tool_help_map["get_book_lending"] = """get_book_lending(book_id: str) -> Dict[str, Any]
    Get all loans for a specific book.

    Args:
        book_id: Book ID (e.g., "B001")

    Returns:
        Dictionary with loans list, total units, and total fees

    Example:
        result = get_book_lending("B001")
        print(f"{result['total_units']} copies lent, ${result['total_fees']:.2f}")"""

            tool_help_map["get_lending_stats"] = """get_lending_stats() -> Dict[str, Any]
    Get aggregate statistics about lending.

    Returns:
        Dictionary with total_loans, total_fees, total_units, by_segment, by_region, by_channel

    Example:
        stats = get_lending_stats()
        print(f"Total fees: ${stats['total_fees']:,.2f}")"""

            tool_help_map[
                "get_most_lent_books"
            ] = """get_most_lent_books(limit: int = 10) -> List[Dict[str, Any]]
    Get most lent books ranked by total quantity lent.

    Args:
        limit: Number of results (default: 10)

    Returns:
        List of books with total_quantity, total_fees, loan_count

    Example:
        top = get_most_lent_books(5)
        for book in top:
            print(f"{book['title']}: {book['total_quantity']} copies lent")"""

            tool_help_map[
                "get_most_fee_waived_loans"
            ] = """get_most_fee_waived_loans(limit: int = 10) -> List[Dict[str, Any]]
    Get loans with the highest fee waiver percentages.

    Use this for "most fee waivers", "highest waiver", "best deals" queries.

    Args:
        limit: Number of results (default: 10)

    Returns:
        List of loans with book info, sorted by fee waiver (highest first)

    Example:
        waived = get_most_fee_waived_loans(5)
        for loan in waived:
            print(f"{loan['title']}: {loan['fee_waiver_percent']} waiver")"""

            tool_help_map[
                "search_lending_semantic"
            ] = """search_lending_semantic(query: str, top_k: int = 10) -> List[Dict[str, Any]]
    Search lending using natural language semantic similarity.

    Use for queries like "bulk corporate loans", "online lending",
    "waived fee programming books".

    Args:
        query: Natural language query describing lending patterns
        top_k: Number of results (default: 10)

    Returns:
        List of loans with similarity scores

    Example:
        results = search_lending_semantic("bulk corporate loans")
        for loan in results:
            print(f"{loan['book_title']} - {loan['quantity']} copies")"""

            # Add replenishment tools when RAG is enabled
            tool_help_map[
                "search_replenish"
            ] = """search_replenish(book_id: Optional[str] = None, supplier: Optional[str] = None, replenish_type: Optional[str] = None, priority: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]
    Search replenishment records with optional filters.

    Args:
        book_id: Filter by book ID
        supplier: Filter by supplier name (e.g., "Ingram", "Baker & Taylor")
        replenish_type: Filter by type (Purchase, Donation, Exchange, Transfer)
        priority: Filter by priority (High, Medium, Low)
        limit: Maximum results (default: 20)

    Returns:
        List of replenishment record dictionaries

    Example:
        orders = search_replenish(supplier="Ingram", priority="High")"""

            tool_help_map[
                "get_book_replenish"
            ] = """get_book_replenish(book_id: str) -> Dict[str, Any]
    Get all replenishment records for a specific book.

    Args:
        book_id: Book ID (e.g., "B001")

    Returns:
        Dictionary with records list, total_units_added, and total_cost

    Example:
        result = get_book_replenish("B001")
        print(f"{result['total_units_added']} units added, ${result['total_cost']:.2f}")"""

            tool_help_map[
                "get_replenish_stats"
            ] = """get_replenish_stats() -> Dict[str, Any]
    Get aggregate statistics about replenishments.

    Returns:
        Dictionary with total_records, total_units, total_cost, by_supplier, by_type, by_priority

    Example:
        stats = get_replenish_stats()
        print(f"Total replenishment cost: ${stats['total_cost']:,.2f}")"""

            tool_help_map[
                "get_most_replenished_books"
            ] = """get_most_replenished_books(limit: int = 10) -> List[Dict[str, Any]]
    Get most restocked books ranked by total quantity added.

    Args:
        limit: Number of results (default: 10)

    Returns:
        List of books with replenish_count, total_units, total_cost

    Example:
        top = get_most_replenished_books(5)
        for book in top:
            print(f"{book['title']}: {book['total_units']} units added")"""

            tool_help_map[
                "get_replenish_by_month"
            ] = """get_replenish_by_month() -> List[Dict[str, Any]]
    Get replenishments aggregated by month for trend analysis.

    Returns:
        List of monthly summaries with records, total_units, total_cost

    Example:
        monthly = get_replenish_by_month()
        for m in monthly:
            print(f"{m['month']}: {m['total_units']} units, ${m['total_cost']:.2f}")"""

            tool_help_map[
                "search_replenish_semantic"
            ] = """search_replenish_semantic(query: str, top_k: int = 10) -> List[Dict[str, Any]]
    Search replenishment data using natural language semantic similarity.

    Use for queries like "urgent programming book restocks", "donated fiction books",
    "bulk orders from Ingram".

    Args:
        query: Natural language query
        top_k: Number of results (default: 10)

    Returns:
        List of replenishment results with similarity scores

    Example:
        results = search_replenish_semantic("urgent high-priority restocks")
        for r in results:
            print(f"{r['title']} - similarity: {r['similarity']}")"""

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
        - Dummy tool API stubs if include_dummy_tools=True
        """
        code_parts = []

        if include_setup:
            code_parts.append(self._generate_imports())
            code_parts.append(self._generate_db_setup())

        # Tool generators mapping - allows filtering by tool name
        tool_generators = {
            "search_books": self._generate_search_books,
            "get_book_details": self._generate_get_book_details,
            "check_availability": self._generate_check_availability,
            "list_by_category": self._generate_list_by_category,
            "list_by_status": self._generate_list_by_status,
            "locate_book": self._generate_locate_book,
            "find_books_in_cabinet": self._generate_find_books_in_cabinet,
            "get_weak_signal_books": self._generate_get_weak_signal_books,
            "get_library_stats": self._generate_get_library_stats,
            "get_popular_books": self._generate_get_popular_books,
        }

        # Add tools based on filtering
        for tool_name, generator in tool_generators.items():
            if self._should_include_tool(tool_name):
                code_parts.append(generator())

        # Conditionally add semantic_search if RAG is enabled AND tool is allowed
        if self.include_rag and self._should_include_tool("semantic_search"):
            code_parts.append(self._generate_semantic_search())

        # Conditionally add lending tools if RAG is enabled
        if self.include_rag:
            lending_tool_generators = {
                "search_lending": self._generate_search_lending,
                "get_book_lending": self._generate_get_book_lending,
                "get_lending_stats": self._generate_get_lending_stats,
                "get_most_lent_books": self._generate_get_most_lent_books,
                "get_most_fee_waived_loans": self._generate_get_most_fee_waived_loans,
                "search_lending_semantic": self._generate_search_lending_semantic,
            }
            for tool_name, generator in lending_tool_generators.items():
                if self._should_include_tool(tool_name):
                    code_parts.append(generator())

        # Conditionally add replenishment tools if RAG is enabled
        if self.include_rag:
            replenish_tool_generators = {
                "search_replenish": self._generate_search_replenish,
                "get_book_replenish": self._generate_get_book_replenish,
                "get_replenish_stats": self._generate_get_replenish_stats,
                "get_most_replenished_books": self._generate_get_most_replenished_books,
                "get_replenish_by_month": self._generate_get_replenish_by_month,
                "search_replenish_semantic": self._generate_search_replenish_semantic,
            }
            for tool_name, generator in replenish_tool_generators.items():
                if self._should_include_tool(tool_name):
                    code_parts.append(generator())

        # Conditionally add dummy tool stubs if enabled
        if self.include_dummy_tools:
            code_parts.append(self._generate_dummy_tool_stubs())

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

    def _generate_get_library_stats(self) -> str:
        """Generate get_library_stats function."""
        return '''
def get_library_stats() -> Dict[str, Any]:
    """Get aggregate statistics about the library.

    Returns:
        Dictionary with:
        - total_books: Total number of books
        - available_count: Number of available (Present) books
        - by_status: Count by status (Present, Missing, Checked Out)
        - by_category: Count by category
        - weak_signal_count: Books with weak RFID signal

    Example:
        >>> stats = get_library_stats()
        >>> print(f"Total: {stats['total_books']}, Available: {stats['available_count']}")
    """
    # Total books and counts by status
    status_counts = _conn.execute("""
        SELECT status, COUNT(*) as count
        FROM library.books
        GROUP BY status
    """).fetchall()

    by_status = {}
    total_books = 0
    available_count = 0
    for status, count in status_counts:
        by_status[status] = count
        total_books += count
        if status == "Present":
            available_count = count

    # Counts by category
    category_counts = _conn.execute("""
        SELECT category, COUNT(*) as count
        FROM library.books
        GROUP BY category
    """).fetchall()

    by_category = {}
    for category, count in category_counts:
        by_category[category] = count

    # Weak signal count
    weak_signal = _conn.execute("""
        SELECT COUNT(*) FROM library.books WHERE signal_strength < -55
    """).fetchone()[0]

    return {
        "total_books": total_books,
        "available_count": available_count,
        "by_status": by_status,
        "by_category": by_category,
        "weak_signal_count": weak_signal
    }
'''

    def _generate_get_popular_books(self) -> str:
        """Generate get_popular_books function for top books by category."""
        return '''
def get_popular_books(category: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Get popular/featured books, optionally filtered by category.

    This returns books from the catalog as recommendations. Use this when users
    ask for "top books", "popular books", "best books in category", "recommended books".

    NOTE: This does NOT use lending data. For lending-based rankings (actual most lent),
    use get_most_lent_books() which requires RAG mode.

    Args:
        category: Optional category filter (Programming, History, Science, Fiction, Thriller)
        limit: Maximum number of results (default: 10)

    Returns:
        List of featured books with their details

    Example:
        >>> top_programming = get_popular_books("Programming", limit=5)
        >>> for book in top_programming:
        ...     print(f"{book['title']} by {book['author']}")
    """
    # Get books, prioritizing available ones
    sql = """
        SELECT book_id, title, author, category, description,
               cabinet, rack, row, signal_strength,
               timestamp, status
        FROM library.books
        WHERE 1=1
    """
    params = []

    if category:
        sql += " AND category = ?"
        params.append(category)

    # Prioritize available books (Present status first)
    sql += " ORDER BY CASE WHEN status = 'Present' THEN 0 ELSE 1 END, title"
    sql += " LIMIT ?"
    params.append(limit)

    results = _conn.execute(sql, params).fetchall()

    books = []
    for row in results:
        books.append({
            "book_id": row[0],
            "title": row[1],
            "author": row[2],
            "category": row[3],
            "description": row[4],
            "location": {
                "cabinet": row[5],
                "rack": row[6],
                "row": row[7]
            },
            "signal_strength": row[8],
            "timestamp": str(row[9]),
            "status": row[10],
            "is_available": row[10] == "Present"
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

    def _generate_search_lending(self) -> str:
        """Generate search_lending function for lending queries."""
        return '''
def search_lending(book_id: Optional[str] = None, patron_segment: Optional[str] = None,
                   region: Optional[str] = None, channel: Optional[str] = None,
                   limit: int = 20) -> List[Dict[str, Any]]:
    """Search lending records with optional filters.

    Args:
        book_id: Filter by book ID
        patron_segment: Filter by segment (Individual, Corporate, Educational, Government)
        region: Filter by region (Northeast, Southeast, Midwest, West, International)
        channel: Filter by channel (In-Store, Online, Phone Order, Partner)
        limit: Maximum number of results (default: 20)

    Returns:
        List of loan dictionaries

    Example:
        >>> loans = search_lending(patron_segment="Corporate", region="Northeast")
        >>> print(f"Found {len(loans)} corporate loans in Northeast")
    """
    sql = """
        SELECT loan_id, book_id, loan_date, quantity, lending_fee, total_fees,
               fee_waiver, payment_method, patron_id, patron_segment, region, channel
        FROM library.lending
        WHERE 1=1
    """
    params = []

    if book_id:
        sql += " AND book_id = ?"
        params.append(book_id)
    if patron_segment:
        sql += " AND patron_segment = ?"
        params.append(patron_segment)
    if region:
        sql += " AND region = ?"
        params.append(region)
    if channel:
        sql += " AND channel = ?"
        params.append(channel)

    sql += " ORDER BY loan_date DESC LIMIT ?"
    params.append(limit)

    results = _conn.execute(sql, params).fetchall()

    loans = []
    for row in results:
        loans.append({
            "loan_id": row[0],
            "book_id": row[1],
            "loan_date": str(row[2]),
            "quantity": row[3],
            "lending_fee": float(row[4]),
            "total_fees": float(row[5]),
            "fee_waiver": float(row[6]),
            "payment_method": row[7],
            "patron_id": row[8],
            "patron_segment": row[9],
            "region": row[10],
            "channel": row[11]
        })

    return loans
'''

    def _generate_get_book_lending(self) -> str:
        """Generate get_book_lending function."""
        return '''
def get_book_lending(book_id: str) -> Dict[str, Any]:
    """Get all loans for a specific book.

    Args:
        book_id: Book ID (e.g., "B001")

    Returns:
        Dictionary with loans list, total units lent, and total fees

    Example:
        >>> result = get_book_lending("B001")
        >>> print(f"{result['total_units']} copies lent, ${result['total_fees']:.2f}")
    """
    # Get book info
    book = get_book_details(book_id)
    if not book:
        return {"success": False, "message": f"Book {book_id} not found"}

    # Get all loans
    results = _conn.execute("""
        SELECT loan_id, book_id, loan_date, quantity, lending_fee, total_fees,
               fee_waiver, payment_method, patron_id, patron_segment, region, channel
        FROM library.lending
        WHERE book_id = ?
        ORDER BY loan_date DESC
    """, [book_id]).fetchall()

    loans = []
    total_units = 0
    total_fees = 0

    for row in results:
        total_units += row[3]
        total_fees += float(row[5])
        loans.append({
            "loan_id": row[0],
            "loan_date": str(row[2]),
            "quantity": row[3],
            "lending_fee": float(row[4]),
            "total_fees": float(row[5]),
            "patron_segment": row[9],
            "region": row[10],
            "channel": row[11]
        })

    return {
        "success": True,
        "book_id": book_id,
        "book_title": book["title"],
        "book_author": book["author"],
        "loans": loans,
        "total_units": total_units,
        "total_fees": total_fees,
        "loan_count": len(loans)
    }
'''

    def _generate_get_lending_stats(self) -> str:
        """Generate get_lending_stats function."""
        return '''
def get_lending_stats() -> Dict[str, Any]:
    """Get aggregate statistics about lending.

    Returns:
        Dictionary with total_loans, total_fees, total_units, by_segment, by_region, by_channel

    Example:
        >>> stats = get_lending_stats()
        >>> print(f"Total fees: ${stats['total_fees']:,.2f}")
    """
    # Get totals
    totals = _conn.execute("""
        SELECT
            COUNT(*) as total_loans,
            SUM(total_fees) as total_fees,
            SUM(quantity) as total_units,
            COUNT(DISTINCT patron_id) as unique_patrons
        FROM library.lending
    """).fetchone()

    # By segment
    by_segment = {}
    segment_results = _conn.execute("""
        SELECT patron_segment, COUNT(*) as count, SUM(total_fees) as fees
        FROM library.lending
        GROUP BY patron_segment
    """).fetchall()
    for row in segment_results:
        by_segment[row[0]] = {"count": row[1], "fees": float(row[2])}

    # By region
    by_region = {}
    region_results = _conn.execute("""
        SELECT region, COUNT(*) as count, SUM(total_fees) as fees
        FROM library.lending
        GROUP BY region
    """).fetchall()
    for row in region_results:
        by_region[row[0]] = {"count": row[1], "fees": float(row[2])}

    # By channel
    by_channel = {}
    channel_results = _conn.execute("""
        SELECT channel, COUNT(*) as count, SUM(total_fees) as fees
        FROM library.lending
        GROUP BY channel
    """).fetchall()
    for row in channel_results:
        by_channel[row[0]] = {"count": row[1], "fees": float(row[2])}

    return {
        "total_loans": totals[0],
        "total_fees": float(totals[1]) if totals[1] else 0.0,
        "total_units": totals[2] if totals[2] else 0,
        "unique_patrons": totals[3] if totals[3] else 0,
        "by_segment": by_segment,
        "by_region": by_region,
        "by_channel": by_channel
    }
'''

    def _generate_get_most_lent_books(self) -> str:
        """Generate get_most_lent_books function."""
        return '''
def get_most_lent_books(limit: int = 10) -> List[Dict[str, Any]]:
    """Get most lent books ranked by total quantity lent.

    Args:
        limit: Number of results (default: 10)

    Returns:
        List of books with total_quantity, total_fees, loan_count

    Example:
        >>> top = get_most_lent_books(5)
        >>> for book in top:
        ...     print(f"{book['title']}: {book['total_quantity']} copies lent")
    """
    results = _conn.execute("""
        SELECT
            l.book_id,
            b.title,
            b.author,
            b.category,
            SUM(l.quantity) as total_quantity,
            SUM(l.total_fees) as total_fees,
            COUNT(l.loan_id) as loan_count
        FROM library.lending l
        JOIN library.books b ON l.book_id = b.book_id
        GROUP BY l.book_id, b.title, b.author, b.category
        ORDER BY total_quantity DESC
        LIMIT ?
    """, [limit]).fetchall()

    books = []
    for row in results:
        books.append({
            "book_id": row[0],
            "title": row[1],
            "author": row[2],
            "category": row[3],
            "total_quantity": row[4],
            "total_fees": float(row[5]),
            "loan_count": row[6]
        })

    return books
'''

    def _generate_get_most_fee_waived_loans(self) -> str:
        """Generate get_most_fee_waived_loans function."""
        return '''
def get_most_fee_waived_loans(limit: int = 10) -> List[Dict[str, Any]]:
    """Get loans with the highest fee waiver percentages.

    Use this when users ask about "most fee waivers", "highest waiver",
    "biggest waiver", or "best deals".

    Args:
        limit: Number of results (default: 10)

    Returns:
        List of loans with book info, sorted by fee waiver (highest first)

    Example:
        >>> top_waived = get_most_fee_waived_loans(5)
        >>> for loan in top_waived:
        ...     print(f"{loan['title']}: {loan['fee_waiver_percent']} waiver")
    """
    results = _conn.execute("""
        SELECT
            l.loan_id,
            l.book_id,
            b.title,
            b.author,
            b.category,
            l.fee_waiver,
            l.lending_fee,
            l.total_fees,
            l.quantity,
            l.patron_segment,
            l.region,
            l.channel
        FROM library.lending l
        JOIN library.books b ON l.book_id = b.book_id
        ORDER BY l.fee_waiver DESC
        LIMIT ?
    """, [limit]).fetchall()

    loans = []
    for row in results:
        fee_waiver_val = float(row[5])
        loans.append({
            "loan_id": row[0],
            "book_id": row[1],
            "title": row[2],
            "book_title": row[2],  # Alias for LLM convenience
            "author": row[3],
            "category": row[4],
            "fee_waiver": fee_waiver_val,
            "fee_waiver_percent": f"{fee_waiver_val:.0f}%",  # Already stored as percentage
            "lending_fee": float(row[6]),
            "total_fees": float(row[7]),
            "quantity": row[8],
            "patron_segment": row[9],
            "region": row[10],
            "channel": row[11]
        })

    return loans
'''

    def _generate_search_lending_semantic(self) -> str:
        """Generate search_lending_semantic function for lending RAG."""
        return '''
def search_lending_semantic(query: str, top_k: int = 10) -> List[Dict[str, Any]]:
    """Search lending using natural language semantic similarity.

    Use for queries like "bulk corporate loans", "online lending",
    "waived fee programming books".

    Args:
        query: Natural language query describing lending patterns
        top_k: Number of results (default: 10)

    Returns:
        List of loans with similarity scores

    Example:
        >>> results = search_lending_semantic("bulk corporate loans")
        >>> for loan in results:
        ...     print(f"{loan['book_title']} - {loan['quantity']} copies")
    """
    from sentence_transformers import SentenceTransformer

    # Load embedding model (cached after first load)
    model = SentenceTransformer("all-MiniLM-L6-v2")

    # Generate query embedding
    query_embedding = model.encode(query, convert_to_numpy=True, normalize_embeddings=True)
    query_list = query_embedding.tolist()

    # Search lending embeddings
    results = _conn.execute("""
        SELECT
            le.loan_id,
            array_cosine_similarity(le.embedding, ?::FLOAT[384]) as similarity
        FROM library.lending_embeddings le
        ORDER BY similarity DESC
        LIMIT ?
    """, [query_list, top_k]).fetchall()

    if not results:
        return []

    # Enrich with loan and book details
    loans = []
    for loan_id, similarity in results:
        loan_row = _conn.execute("""
            SELECT l.loan_id, l.book_id, l.loan_date, l.quantity, l.lending_fee,
                   l.total_fees, l.fee_waiver, l.payment_method, l.patron_id,
                   l.patron_segment, l.region, l.channel,
                   b.title, b.author
            FROM library.lending l
            JOIN library.books b ON l.book_id = b.book_id
            WHERE l.loan_id = ?
        """, [loan_id]).fetchone()

        if loan_row:
            loans.append({
                "loan_id": loan_row[0],
                "book_id": loan_row[1],
                "loan_date": str(loan_row[2]),
                "quantity": loan_row[3],
                "lending_fee": float(loan_row[4]),
                "total_fees": float(loan_row[5]),
                "fee_waiver": float(loan_row[6]),
                "payment_method": loan_row[7],
                "patron_id": loan_row[8],
                "patron_segment": loan_row[9],
                "region": loan_row[10],
                "channel": loan_row[11],
                "book_title": loan_row[12],
                "book_author": loan_row[13],
                "similarity": round(similarity, 3)
            })

    return loans
'''

    def _generate_search_replenish(self) -> str:
        """Generate search_replenish function."""
        return '''
def search_replenish(book_id: Optional[str] = None, supplier: Optional[str] = None,
                     replenish_type: Optional[str] = None, condition: Optional[str] = None,
                     funding_source: Optional[str] = None, priority: Optional[str] = None,
                     limit: int = 20) -> List[Dict[str, Any]]:
    """Search replenishment records with optional filters.

    Args:
        book_id: Filter by book ID (e.g., "B001")
        supplier: Filter by supplier (Ingram, Baker & Taylor, Brodart, Direct Publisher, Amazon Business)
        replenish_type: Filter by type (New Acquisition, Replacement, Restock, Donation, Return Processing)
        condition: Filter by condition (New, Refurbished, Used - Good, Used - Fair)
        funding_source: Filter by funding source (Operating Budget, Grant, Donation Fund, Special Collection, Emergency Fund)
        priority: Filter by priority (Urgent, High, Normal, Low)
        limit: Maximum number of results

    Example:
        records = search_replenish(supplier="Ingram", replenish_type="Restock")
    """
    conditions = []
    params = []
    if book_id:
        conditions.append("r.book_id = ?")
        params.append(book_id)
    if supplier:
        conditions.append("r.supplier = ?")
        params.append(supplier)
    if replenish_type:
        conditions.append("r.replenish_type = ?")
        params.append(replenish_type)
    if condition:
        conditions.append("r.condition = ?")
        params.append(condition)
    if funding_source:
        conditions.append("r.funding_source = ?")
        params.append(funding_source)
    if priority:
        conditions.append("r.priority = ?")
        params.append(priority)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    query = f"""
        SELECT r.replenish_id, r.book_id, b.title, r.replenish_date, r.quantity,
               r.unit_cost, r.total_cost, r.discount_pct, r.supplier,
               r.replenish_type, r.condition, r.funding_source, r.priority
        FROM library.replenish r
        JOIN library.books b ON r.book_id = b.book_id
        {where_clause}
        ORDER BY r.replenish_date DESC
        LIMIT {limit}
    """
    rows = _conn.execute(query, params).fetchall() if params else _conn.execute(query).fetchall()
    return [{"replenish_id": r[0], "book_id": r[1], "title": r[2], "replenish_date": str(r[3]),
             "quantity": r[4], "unit_cost": float(r[5]), "total_cost": float(r[6]),
             "discount_pct": float(r[7]), "supplier": r[8], "replenish_type": r[9],
             "condition": r[10], "funding_source": r[11], "priority": r[12]} for r in rows]
'''

    def _generate_get_book_replenish(self) -> str:
        """Generate get_book_replenish function."""
        return '''
def get_book_replenish(book_id: str) -> Dict[str, Any]:
    """Get all replenishment records for a specific book.

    Args:
        book_id: Book ID (e.g., "B001")

    Example:
        result = get_book_replenish("B001")
    """
    rows = _conn.execute("""
        SELECT r.replenish_id, r.replenish_date, r.quantity, r.unit_cost, r.total_cost,
               r.supplier, r.replenish_type, r.condition, r.funding_source, r.priority
        FROM library.replenish r
        WHERE r.book_id = ?
        ORDER BY r.replenish_date DESC
    """, [book_id]).fetchall()
    book = _conn.execute("SELECT title FROM library.books WHERE book_id = ?", [book_id]).fetchone()
    records = [{"replenish_id": r[0], "replenish_date": str(r[1]), "quantity": r[2],
                "unit_cost": float(r[3]), "total_cost": float(r[4]), "supplier": r[5],
                "replenish_type": r[6], "condition": r[7], "funding_source": r[8],
                "priority": r[9]} for r in rows]
    total_units = sum(r["quantity"] for r in records)
    total_cost = sum(r["total_cost"] for r in records)
    return {"book_id": book_id, "title": book[0] if book else "Unknown",
            "replenishment_count": len(records), "total_units_added": total_units,
            "total_cost": round(total_cost, 2), "records": records}
'''

    def _generate_get_replenish_stats(self) -> str:
        """Generate get_replenish_stats function."""
        return '''
def get_replenish_stats() -> Dict[str, Any]:
    """Get aggregate statistics about replenishments.

    Example:
        stats = get_replenish_stats()
    """
    totals = _conn.execute("""
        SELECT COUNT(*) as total_records, SUM(quantity) as total_units,
               SUM(total_cost) as total_cost, AVG(total_cost) as avg_cost
        FROM library.replenish
    """).fetchone()
    by_supplier = _conn.execute("""
        SELECT supplier, COUNT(*) as records, SUM(quantity) as units, SUM(total_cost) as cost
        FROM library.replenish GROUP BY supplier ORDER BY cost DESC
    """).fetchall()
    by_type = _conn.execute("""
        SELECT replenish_type, COUNT(*) as records, SUM(quantity) as units
        FROM library.replenish GROUP BY replenish_type ORDER BY records DESC
    """).fetchall()
    by_priority = _conn.execute("""
        SELECT priority, COUNT(*) as records
        FROM library.replenish GROUP BY priority ORDER BY records DESC
    """).fetchall()
    return {
        "total_records": totals[0], "total_units": totals[1],
        "total_cost": round(float(totals[2]), 2), "avg_cost_per_order": round(float(totals[3]), 2),
        "by_supplier": [{"supplier": r[0], "records": r[1], "units": r[2], "cost": round(float(r[3]), 2)} for r in by_supplier],
        "by_type": [{"type": r[0], "records": r[1], "units": r[2]} for r in by_type],
        "by_priority": [{"priority": r[0], "records": r[1]} for r in by_priority],
    }
'''

    def _generate_get_most_replenished_books(self) -> str:
        """Generate get_most_replenished_books function."""
        return '''
def get_most_replenished_books(limit: int = 10) -> List[Dict[str, Any]]:
    """Get most replenished books ranked by total quantity added.

    Args:
        limit: Maximum number of results (default 10)

    Example:
        top_books = get_most_replenished_books(limit=5)
    """
    rows = _conn.execute(f"""
        SELECT r.book_id, b.title, b.author, b.category,
               COUNT(*) as replenish_count, SUM(r.quantity) as total_units,
               SUM(r.total_cost) as total_cost
        FROM library.replenish r
        JOIN library.books b ON r.book_id = b.book_id
        GROUP BY r.book_id, b.title, b.author, b.category
        ORDER BY total_units DESC
        LIMIT {limit}
    """).fetchall()
    return [{"book_id": r[0], "title": r[1], "author": r[2], "category": r[3],
             "replenish_count": r[4], "total_units": r[5],
             "total_cost": round(float(r[6]), 2)} for r in rows]
'''

    def _generate_get_replenish_by_month(self) -> str:
        """Generate get_replenish_by_month function."""
        return '''
def get_replenish_by_month() -> List[Dict[str, Any]]:
    """Get replenishments aggregated by month for trend analysis.

    Example:
        monthly = get_replenish_by_month()
    """
    rows = _conn.execute("""
        SELECT strftime(replenish_date, '%Y-%m') as month,
               COUNT(*) as records, SUM(quantity) as total_units, SUM(total_cost) as total_cost
        FROM library.replenish
        GROUP BY month ORDER BY month DESC
    """).fetchall()
    return [{"month": r[0], "records": r[1], "total_units": r[2],
             "total_cost": round(float(r[3]), 2)} for r in rows]
'''

    def _generate_search_replenish_semantic(self) -> str:
        """Generate search_replenish_semantic function."""
        return '''
def search_replenish_semantic(query: str, top_k: int = 10) -> List[Dict[str, Any]]:
    """Search replenishment data using natural language semantic similarity.

    Use for queries like "urgent programming book restocks", "donated fiction books",
    "bulk orders from Ingram".

    Args:
        query: Natural language query
        top_k: Maximum number of results

    Example:
        results = search_replenish_semantic("urgent high-priority restocks")
    """
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        model = SentenceTransformer("all-MiniLM-L6-v2")
        query_embedding = model.encode(query).tolist()
        rows = _conn.execute(f"""
            SELECT re.book_id, b.title, b.author,
                   array_cosine_similarity(re.embedding::FLOAT[384], {query_embedding}::FLOAT[384]) as similarity
            FROM library.replenish_embeddings re
            JOIN library.books b ON re.book_id = b.book_id
            ORDER BY similarity DESC
            LIMIT {top_k}
        """).fetchall()
        results = []
        for book_id, title, author, sim in rows:
            records = _conn.execute("""
                SELECT supplier, replenish_type, priority, SUM(quantity) as units
                FROM library.replenish WHERE book_id = ? GROUP BY supplier, replenish_type, priority
            """, [book_id]).fetchall()
            results.append({"book_id": book_id, "title": title, "author": author,
                             "similarity": round(float(sim), 4),
                             "replenishments": [{"supplier": r[0], "type": r[1], "priority": r[2], "units": r[3]} for r in records]})
        return results
    except Exception as e:
        return [{"error": str(e)}]
'''

    def _generate_dummy_tool_stubs(self) -> str:
        """Generate lightweight API stubs for dummy tools (code execution mode).

        This generates compact function stubs that return mock responses.
        The key benefit: ~650 tokens vs ~18,000 tokens for full tool definitions.

        Returns:
            Python code with all dummy tool function stubs
        """
        # Generate a compact stub header
        code_lines = [
            "# Enterprise Dummy Tools - API Stubs (100 tools across 10 domains)",
            "# These are lightweight mock implementations for token efficiency demo",
            "from datetime import datetime",
            "",
            "def _mock_response(domain: str, tool: str, **kwargs):",
            '    """Generate mock response for dummy tools."""',
            "    return {",
            '        "success": True,',
            '        "domain": domain,',
            '        "tool": tool,',
            '        "message": f"Mock response from {domain}.{tool}",',
            '        "input": kwargs,',
            '        "data": {"mock": True, "timestamp": datetime.now().isoformat()},',
            "    }",
            "",
        ]

        # Generate stubs for each dummy tool
        dummy_tools = generate_dummy_tools()
        for tool in dummy_tools:
            # Extract parameter names from input_schema
            params = tool.input_schema.get("properties", {})
            required = set(tool.input_schema.get("required", []))

            # Build function signature - IMPORTANT: required params first, then optional
            # Python requires non-default args before default args
            required_param_strs = []
            optional_param_strs = []

            for param_name, param_def in params.items():
                if param_name in required:
                    required_param_strs.append(param_name)
                else:
                    default = param_def.get("default", None)
                    if default is None:
                        optional_param_strs.append(f"{param_name}=None")
                    elif isinstance(default, str):
                        optional_param_strs.append(f'{param_name}="{default}"')
                    else:
                        optional_param_strs.append(f"{param_name}={default}")

            # Combine: required params first, then optional params with defaults
            param_strs = required_param_strs + optional_param_strs
            params_str = ", ".join(param_strs)

            # Generate compact function stub
            code_lines.extend(
                [
                    f"def {tool.name}({params_str}):",
                    f'    """(Mock) {tool.description[:60]}..."""',
                    f'    return _mock_response("{tool.domain.value}", "{tool.name}", '
                    f"**{{k: v for k, v in locals().items() if k != 'domain'}})",
                    "",
                ]
            )

        return "\n".join(code_lines)

    def get_tool_descriptions(self) -> dict[str, str]:
        """Get descriptions of all available tool functions.

        Returns:
            Dictionary mapping function names to their descriptions

        Useful for:
        - Generating LLM prompts
        - Documentation generation
        - API discovery

        Note: Respects tool filtering if tools parameter was set.
        """
        all_descriptions = {
            "search_books": "Search books by title, author, or category",
            "get_book_details": "Get detailed information for a specific book",
            "check_availability": "Check if a book is available for checkout",
            "list_by_category": "List all books in a specific category",
            "list_by_status": "List all books with a specific status",
            "locate_book": "Get the physical location of a book",
            "find_books_in_cabinet": "Find all books in a specific cabinet or rack",
            "get_weak_signal_books": "Find books with weak RFID signal strength",
            "get_library_stats": "Get aggregate statistics about the library",
            "get_popular_books": "Get popular/top books, optionally filtered by category (no lending needed)",
        }

        # Filter descriptions based on tools parameter
        descriptions = {
            name: desc for name, desc in all_descriptions.items() if self._should_include_tool(name)
        }

        # Conditionally add semantic_search if RAG is enabled AND tool is allowed
        if self.include_rag and self._should_include_tool("semantic_search"):
            descriptions["semantic_search"] = (
                "Search books using natural language semantic similarity (RAG)"
            )

        # Conditionally add lending tools if RAG is enabled
        if self.include_rag:
            lending_descriptions = {
                "search_lending": "Search lending records with optional filters",
                "get_book_lending": "Get all loans for a specific book",
                "get_lending_stats": "Get aggregate statistics about lending",
                "get_most_lent_books": "Get most lent books by quantity",
                "get_most_fee_waived_loans": "Get loans with highest fee waivers",
                "search_lending_semantic": "Search lending using natural language similarity",
            }
            for name, desc in lending_descriptions.items():
                if self._should_include_tool(name):
                    descriptions[name] = desc

        # Conditionally add replenishment tools if RAG is enabled
        if self.include_rag:
            replenish_descriptions = {
                "search_replenish": "Search replenishment records with optional filters",
                "get_book_replenish": "Get all replenishments for a specific book",
                "get_replenish_stats": "Get aggregate statistics about replenishments",
                "get_most_replenished_books": "Get most restocked books by total quantity added",
                "get_replenish_by_month": "Get monthly replenishment trends",
                "search_replenish_semantic": "Search replenishments using natural language similarity",
            }
            for name, desc in replenish_descriptions.items():
                if self._should_include_tool(name):
                    descriptions[name] = desc

        # Conditionally add dummy tool descriptions if enabled
        if self.include_dummy_tools:
            dummy_tools = generate_dummy_tools()
            for tool in dummy_tools:
                descriptions[tool.name] = tool.description[:80] + "..."

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
