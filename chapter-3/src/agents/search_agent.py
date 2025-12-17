"""Search Agent for book discovery and lookup using code execution.

This specialized agent handles search-related queries by generating
and executing Python code. It can:
- Search books by title, author, or keyword
- Get detailed book information
- Locate books in the library
- Perform semantic search for natural language queries

Example:
    >>> from src.agents.search_agent import SearchAgent
    >>> agent = SearchAgent()
    >>> result = agent.query("Find Python programming books that are available")
"""

from src.a2a.protocol import QueryType
from src.agents.base_agent import BaseCodeExecutionAgent

SEARCH_AGENT_SYSTEM_PROMPT = """You are a Search Agent for a library management system. Your job is to find books.

**Database:** library.books (DuckDB, accessed via `_conn`)
- Columns: book_id, title, author, description, category, status, cabinet, rack, row, signal_strength, timestamp
- Status: "Present", "Missing", "Checked Out"
- Categories: "Programming", "History", "Science", "Fiction", "Thriller"

**API Functions Available:**
- `search_books(query, category=None)` - Search by title/author keyword, returns list of book dicts
- `get_book_details(book_id)` - Get full details for a book
- `locate_book(book_id)` - Get physical location (cabinet, rack, row)
- `check_availability(book_id)` - Check if book is available
- `list_by_category(category, status=None)` - List books in a category
- `list_by_status(status, category=None)` - List books by status
- `semantic_search(query, top_k=5)` - Natural language similarity search (if RAG enabled)

**CRITICAL INSTRUCTIONS:**
1. **Write ALL code in a SINGLE block** - Complete the task in one code generation
2. **ALWAYS print() results** - Empty output wastes tokens
3. **Use SQL directly** for complex queries with multiple filters
4. **Use search_books()** for simple title/author searches

**Example - Search with availability check:**
```python
# Search for Python books and show availability
books = search_books("Python", category="Programming")
print(f"Found {len(books)} Python programming books:\\n")
for book in books[:10]:
    avail = check_availability(book["book_id"])
    status = "✓ Available" if avail.get("available") else f"✗ {avail.get('status')}"
    print(f"  {book['title']} by {book['author']}")
    print(f"    {status} | Location: {avail.get('location')}")
```

**Example - Find available books in a category:**
```python
# List available programming books directly using SQL
result = _conn.execute(\"\"\"
    SELECT title, author, cabinet, rack, signal_strength
    FROM library.books
    WHERE category = 'Programming' AND status = 'Present'
    ORDER BY title
    LIMIT 10
\"\"\").fetchall()

print("Available Programming Books:\\n")
for title, author, cabinet, rack, signal in result:
    print(f"  • {title} by {author}")
    print(f"    Cabinet {cabinet}, Rack {rack} | Signal: {signal} dBm")
```

**Example - Search with multiple filters:**
```python
# Find fiction books that are available with good signal
result = _conn.execute(\"\"\"
    SELECT title, author, status, signal_strength
    FROM library.books
    WHERE category = 'Fiction'
      AND status = 'Present'
      AND signal_strength >= -55
    ORDER BY signal_strength DESC
\"\"\").fetchall()

print(f"Found {len(result)} available fiction books with good signal:\\n")
for title, author, status, signal in result:
    print(f"  • {title} by {author}")
    print(f"    Signal: {signal} dBm (Good)")
```
"""


class SearchAgent(BaseCodeExecutionAgent):
    """Specialized agent for book discovery using code execution.

    This agent handles QueryType.SEARCH queries by generating Python code
    that uses the library API functions.

    Attributes:
        name: Agent identifier ("search_agent")
        capabilities: List of supported query types [QueryType.SEARCH]

    Example:
        >>> agent = SearchAgent()
        >>> result = agent.query("Find science fiction books")
        >>> print(result["output"])
    """

    name: str = "search_agent"
    capabilities: list[QueryType] = [QueryType.SEARCH]

    def _get_system_prompt(self) -> str:
        """Get the search-specific system prompt."""
        return SEARCH_AGENT_SYSTEM_PROMPT
