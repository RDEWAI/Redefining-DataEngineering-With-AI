"""Data Analysis Agent for complex analytics queries.

This agent combines code execution with semantic search to handle
complex data analysis requests. It can:
- Execute generated Python code for analytics
- Use semantic search for book discovery
- Generate reports with charts and tables

Example:
    >>> from src.agents.data_analysis_agent import DataAnalysisAgent
    >>> agent = DataAnalysisAgent()
    >>> result = agent.analyze("Show top 5 categories by missing books")
"""

import json
from pathlib import Path
from typing import Any

from src.code_execution.sandbox import CodeSandbox
from src.library.repository import get_repository
from src.rag.embeddings import EmbeddingGenerator
from src.rag.vector_store import DuckDBVectorStore
from src.tools.tool_registry import create_library_tool_registry


class DataAnalysisAgent:
    """Agent for complex data analysis using code execution and RAG.

    This agent handles analytical queries that require:
    - Custom Python code execution for aggregations
    - Semantic search for finding relevant books
    - Integration of multiple data sources

    Args:
        db_path: Path to DuckDB database. If None, uses default.

    Attributes:
        sandbox: CodeSandbox for safe code execution
        vector_store: Vector store for semantic search
        repository: Book repository for direct queries
    """

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize the data analysis agent.

        Args:
            db_path: Path to DuckDB database
        """
        if db_path is None:
            db_path = str(Path(__file__).parent.parent.parent / "data" / "duckdb" / "chapter3.db")

        self.db_path = db_path
        self.sandbox = CodeSandbox()
        self.repository = get_repository(db_path, read_only=True)
        self.tool_registry = create_library_tool_registry()

        # Lazy initialization for embeddings
        self._embedding_generator: EmbeddingGenerator | None = None
        self._vector_store: DuckDBVectorStore | None = None

    @property
    def embedding_generator(self) -> EmbeddingGenerator:
        """Get or create embedding generator."""
        if self._embedding_generator is None:
            self._embedding_generator = EmbeddingGenerator()
        return self._embedding_generator

    @property
    def vector_store(self) -> DuckDBVectorStore:
        """Get or create vector store."""
        if self._vector_store is None:
            self._vector_store = DuckDBVectorStore(db_path=self.db_path, read_only=True)
        return self._vector_store

    def close(self) -> None:
        """Clean up resources."""
        self.repository.close()
        if self._vector_store is not None:
            self._vector_store.close()

    def semantic_search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search for books using semantic similarity.

        Args:
            query: Natural language search query
            top_k: Number of results to return

        Returns:
            List of book dicts with similarity scores
        """
        # Check if embeddings exist
        if self.vector_store.get_embedding_count() == 0:
            return []

        # Generate query embedding
        query_embedding = self.embedding_generator.embed_text(query)

        # Search
        results = self.vector_store.semantic_search(query_embedding, top_k)

        # Enrich with book details
        enriched_results = []
        for result in results:
            book = self.repository.get_book_by_id(result["book_id"])
            if book:
                enriched_results.append(
                    {
                        **book.to_dict(include_description=True),
                        "similarity": result["similarity"],
                    }
                )

        return enriched_results

    def execute_analysis(
        self,
        code: str,
    ) -> dict[str, Any]:
        """Execute Python code for data analysis.

        Args:
            code: Python code to execute

        Returns:
            Dict with execution result or error
        """
        result = self.sandbox.execute(code, db_path=self.db_path)

        if result["success"]:
            return {
                "success": True,
                "output": result["stdout"],
            }
        else:
            return {
                "success": False,
                "error": result["stderr"],
            }

    def analyze(
        self,
        query: str,
        use_semantic_search: bool = True,
    ) -> dict[str, Any]:
        """Analyze a natural language query.

        Determines whether to use semantic search, code execution,
        or both based on the query.

        Args:
            query: Natural language analysis query
            use_semantic_search: Whether to try semantic search first

        Returns:
            Dict with analysis results
        """
        query_lower = query.lower()

        # Check for tool-based queries first (more specific)
        tool_keywords = [
            "weak signal",
            "signal strength",
            "rfid",
        ]
        if any(kw in query_lower for kw in tool_keywords):
            return self._use_tools(query)

        # Check if this is an analytics query requiring code
        analytics_keywords = [
            "top",
            "average",
            "count",
            "sum",
            "statistics",
            "stats",
            "compare",
            "trend",
            "distribution",
            "by category",
            "by categories",
        ]

        if any(kw in query_lower for kw in analytics_keywords):
            # Generate analysis code
            code = self._generate_analytics_code(query)
            result = self.execute_analysis(code)

            return {
                "type": "code_execution",
                "query": query,
                "code": code,
                "result": result,
            }

        # Check if this is a semantic search query
        semantic_keywords = [
            "about",
            "like",
            "similar",
            "related",
            "find books",
            "that book",
            "books on",
            "something about",
        ]

        if use_semantic_search and any(kw in query_lower for kw in semantic_keywords):
            results = self.semantic_search(query, top_k=5)
            if results:
                return {
                    "type": "semantic_search",
                    "query": query,
                    "results": results,
                }

        # Fall back to tool-based response
        return self._use_tools(query)

    def _generate_analytics_code(self, query: str) -> str:
        """Generate Python code for an analytics query.

        This is a simplified code generator. In production, this would
        use an LLM to generate the code.

        Args:
            query: Analytics query

        Returns:
            Python code string
        """
        query_lower = query.lower()

        # Pattern matching for common queries
        if (
            "top" in query_lower
            and ("category" in query_lower or "categories" in query_lower)
            and "missing" in query_lower
        ):
            return '''
import duckdb

conn = duckdb.connect(db_path, read_only=True)
result = conn.execute("""
    SELECT
        category,
        COUNT(*) as missing_count,
        AVG(signal_strength) as avg_signal
    FROM library.books
    WHERE status = 'Missing'
    GROUP BY category
    ORDER BY missing_count DESC
    LIMIT 5
""").fetchall()
conn.close()

print("Top Categories by Missing Books:")
for row in result:
    print(f"  {row[0]}: {row[1]} missing, avg signal: {row[2]:.1f} dBm")
'''

        if "statistics" in query_lower or "stats" in query_lower:
            return '''
import duckdb

conn = duckdb.connect(db_path, read_only=True)

# Get overall stats
total = conn.execute("SELECT COUNT(*) FROM library.books").fetchone()[0]
by_status = conn.execute("""
    SELECT status, COUNT(*) FROM library.books GROUP BY status
""").fetchall()
by_category = conn.execute("""
    SELECT category, COUNT(*) FROM library.books GROUP BY category
""").fetchall()

conn.close()

print(f"Library Statistics:")
print(f"  Total Books: {total}")
print("  By Status:")
for status, count in by_status:
    print(f"    {status}: {count}")
print("  By Category:")
for category, count in by_category:
    print(f"    {category}: {count}")
'''

        if "weak signal" in query_lower:
            return '''
import duckdb

conn = duckdb.connect(db_path, read_only=True)
result = conn.execute("""
    SELECT book_id, title, signal_strength, status
    FROM library.books
    WHERE signal_strength < -55
    ORDER BY signal_strength ASC
    LIMIT 10
""").fetchall()
conn.close()

print("Books with Weak RFID Signal:")
for row in result:
    print(f"  {row[0]}: {row[1]}")
    print(f"    Signal: {row[2]} dBm, Status: {row[3]}")
'''

        # Default: run a general query
        return '''
import duckdb

conn = duckdb.connect(db_path, read_only=True)
result = conn.execute("""
    SELECT category, status, COUNT(*) as count
    FROM library.books
    GROUP BY category, status
    ORDER BY category, status
""").fetchall()
conn.close()

print("Book Distribution by Category and Status:")
for row in result:
    print(f"  {row[0]} - {row[1]}: {row[2]}")
'''

    def _use_tools(self, query: str) -> dict[str, Any]:
        """Use registered tools to answer a query.

        Args:
            query: User query

        Returns:
            Dict with tool results
        """
        query_lower = query.lower()

        # Try to match to a tool
        if "search" in query_lower:
            # Extract search term (simplified)
            search_term = query.replace("search for", "").replace("search", "").strip()
            result = self.tool_registry.execute_tool("search_books", query=search_term)
            return {"type": "tool", "tool": "search_books", "result": result}

        if "stats" in query_lower or "statistics" in query_lower:
            result = self.tool_registry.execute_tool("get_library_stats")
            return {"type": "tool", "tool": "get_library_stats", "result": result}

        if "weak" in query_lower and "signal" in query_lower:
            result = self.tool_registry.execute_tool("get_weak_signal_books")
            return {"type": "tool", "tool": "get_weak_signal_books", "result": result}

        # Default: return stats
        result = self.tool_registry.execute_tool("get_library_stats")
        return {"type": "tool", "tool": "get_library_stats", "result": result}


def main() -> None:
    """Interactive CLI for data analysis agent."""
    print("Data Analysis Agent")
    print("=" * 40)
    print("Enter analysis queries or 'quit' to exit.")
    print()
    print("Examples:")
    print("  - Show library statistics")
    print("  - Top 5 categories by missing books")
    print("  - Books about time travel")
    print("  - Find books with weak signal")
    print()

    agent = DataAnalysisAgent()

    try:
        while True:
            try:
                query = input("Query: ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not query or query.lower() == "quit":
                break

            result = agent.analyze(query)
            print()
            print(f"Analysis Type: {result['type']}")
            print("-" * 40)

            if result["type"] == "semantic_search":
                for i, book in enumerate(result["results"], 1):
                    print(f"{i}. {book['title']} by {book['author']}")
                    print(f"   Similarity: {book['similarity']:.3f}")
                    print(f"   Category: {book['category']}")
                    print()

            elif result["type"] == "code_execution":
                if result["result"]["success"]:
                    print(result["result"]["output"])
                else:
                    print(f"Error: {result['result']['error']}")

            elif result["type"] == "tool":
                print(f"Tool: {result['tool']}")
                print(json.dumps(result["result"], indent=2, default=str))

            print()

    finally:
        agent.close()
        print("\nGoodbye!")


if __name__ == "__main__":
    main()
