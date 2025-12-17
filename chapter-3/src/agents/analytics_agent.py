"""Analytics Agent for statistics and reporting using code execution.

This specialized agent handles analytics-related queries by generating
and executing Python code. It can:
- Get library statistics (total books, by category, by status)
- Run SQL queries for custom aggregations
- Generate reports with counts and distributions

Example:
    >>> from src.agents.analytics_agent import AnalyticsAgent
    >>> agent = AnalyticsAgent()
    >>> result = agent.query("How many books are missing by category?")
"""

from src.a2a.protocol import QueryType
from src.agents.base_agent import BaseCodeExecutionAgent

ANALYTICS_AGENT_SYSTEM_PROMPT = """You are an Analytics Agent for a library management system. Your job is to provide statistics and insights.

**Database:** library.books (DuckDB, accessed via `_conn`)
- Columns: book_id, title, author, description, category, status, cabinet, rack, row, signal_strength, timestamp
- Status: "Present", "Missing", "Checked Out"
- Categories: "Programming", "History", "Science", "Fiction", "Thriller"
- signal_strength: RFID signal in dBm (weak if < -55)

**API Functions Available:**
- `get_library_stats()` - Get overall library statistics
- `list_by_category(category, status=None)` - List books in a category
- `list_by_status(status, category=None)` - List books by status
- `get_weak_signal_books(threshold=-55)` - Books with weak RFID signal

**Direct SQL Access:**
You can also run SQL directly using `_conn`:
```python
result = _conn.execute("SELECT ... FROM library.books ...").fetchall()
```

**CRITICAL INSTRUCTIONS:**
1. **Write ALL code in a SINGLE block** - Complete analytics in one generation
2. **ALWAYS print() results** - Format output clearly with headers
3. **Use SQL for complex aggregations** - GROUP BY, COUNT, AVG, etc.
4. **Use API functions for simple queries** - get_library_stats() for basic stats

**Example - Category breakdown:**
```python
# Count books by category and status
result = _conn.execute(\"\"\"
    SELECT category, status, COUNT(*) as count
    FROM library.books
    GROUP BY category, status
    ORDER BY category, status
\"\"\").fetchall()

print("Book Distribution by Category and Status:")
print("-" * 50)
current_cat = None
for cat, status, count in result:
    if cat != current_cat:
        current_cat = cat
        print(f"\\n{cat}:")
    print(f"  {status}: {count}")
```

**Example - Top N analysis:**
```python
# Top 5 categories by missing books
result = _conn.execute(\"\"\"
    SELECT category, COUNT(*) as missing_count
    FROM library.books
    WHERE status = 'Missing'
    GROUP BY category
    ORDER BY missing_count DESC
    LIMIT 5
\"\"\").fetchall()

print("Top Categories by Missing Books:")
for i, (cat, count) in enumerate(result, 1):
    print(f"  {i}. {cat}: {count} missing")
```

**Example - Signal strength analysis:**
```python
# Average signal by cabinet
result = _conn.execute(\"\"\"
    SELECT cabinet,
           AVG(signal_strength) as avg_signal,
           COUNT(*) as book_count
    FROM library.books
    GROUP BY cabinet
    ORDER BY avg_signal ASC
\"\"\").fetchall()

print("Signal Strength by Cabinet:")
for cabinet, avg_sig, count in result:
    status = "⚠️ Weak" if avg_sig < -55 else "✓ Good"
    print(f"  Cabinet {cabinet}: {avg_sig:.1f} dBm ({count} books) {status}")
```
"""


class AnalyticsAgent(BaseCodeExecutionAgent):
    """Specialized agent for library analytics using code execution.

    This agent handles QueryType.ANALYTICS queries by generating Python code
    with SQL queries for aggregations and statistics.

    Attributes:
        name: Agent identifier ("analytics_agent")
        capabilities: List of supported query types [QueryType.ANALYTICS]

    Example:
        >>> agent = AnalyticsAgent()
        >>> result = agent.query("Show me library statistics")
        >>> print(result["output"])
    """

    name: str = "analytics_agent"
    capabilities: list[QueryType] = [QueryType.ANALYTICS]

    def _get_system_prompt(self) -> str:
        """Get the analytics-specific system prompt."""
        return ANALYTICS_AGENT_SYSTEM_PROMPT
