"""DuckDB vector store for semantic search.

This module provides the DuckDBVectorStore class for storing and searching
vector embeddings using DuckDB's VSS (Vector Similarity Search) extension.

The vector store uses cosine similarity for searching, with support for
HNSW indexing for efficient approximate nearest neighbor search.

Example:
    >>> from src.agentic.rag.vector_store import DuckDBVectorStore
    >>> store = DuckDBVectorStore(db_path="data/duckdb/chapter2.db")
    >>> store.store_embeddings(book_ids, embeddings)
    >>> results = store.semantic_search(query_embedding, top_k=5)
"""

from pathlib import Path
from typing import Any

import duckdb
import numpy as np

# Default embedding dimension (all-MiniLM-L6-v2)
DEFAULT_EMBEDDING_DIM = 384


class DuckDBVectorStore:
    """Vector store for book embeddings using DuckDB.

    Stores book embeddings and provides semantic search using cosine similarity.
    Uses DuckDB's VSS extension for efficient vector operations.

    Args:
        db_path: Path to DuckDB database file
        embedding_dim: Dimension of embedding vectors (default 384)

    Attributes:
        conn: DuckDB connection
        embedding_dim: Dimension of stored embeddings

    Example:
        >>> store = DuckDBVectorStore("data/duckdb/chapter2.db")
        >>> store.store_embeddings(["B001", "B002"], embeddings_array)
        >>> results = store.semantic_search(query_vector, top_k=5)
    """

    def __init__(
        self,
        db_path: str | None = None,
        embedding_dim: int = DEFAULT_EMBEDDING_DIM,
        read_only: bool = False,
        connection: duckdb.DuckDBPyConnection | None = None,
    ) -> None:
        """Initialize vector store with DuckDB connection.

        Creates the book_embeddings table if it doesn't exist.

        Args:
            db_path: Path to DuckDB database. If None, uses default path.
            embedding_dim: Dimension of embedding vectors.
            read_only: If True, open database in read-only mode.
            connection: Optional existing DuckDB connection to use.
        """
        self.embedding_dim = embedding_dim
        self.read_only = read_only
        self._owns_connection = connection is None

        if connection is not None:
            self.conn = connection
            self.db_path = None
        else:
            if db_path is None:
                db_path = str(
                    Path(__file__).parent.parent.parent.parent / "data" / "duckdb" / "chapter2.db"
                )
            self.db_path = db_path
            self.conn = duckdb.connect(db_path, read_only=read_only)

        if not read_only:
            self._setup_table()

    def _setup_table(self) -> None:
        """Create the book_embeddings table if it doesn't exist."""
        # Ensure library schema exists
        self.conn.execute("CREATE SCHEMA IF NOT EXISTS library")

        # Create embeddings table with FLOAT array for vector storage
        self.conn.execute(f"""
            CREATE TABLE IF NOT EXISTS library.book_embeddings (
                book_id VARCHAR PRIMARY KEY,
                embedding FLOAT[{self.embedding_dim}] NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def close(self) -> None:
        """Close the database connection if owned by this store."""
        if self._owns_connection and self.conn is not None:
            self.conn.close()
            self.conn = None  # type: ignore[assignment]

    def store_embeddings(
        self,
        book_ids: list[str],
        embeddings: np.ndarray,
    ) -> None:
        """Store book embeddings in the vector store.

        If a book_id already exists, its embedding is updated.

        Args:
            book_ids: List of book IDs
            embeddings: Numpy array of shape (n_books, embedding_dim)

        Raises:
            ValueError: If book_ids and embeddings lengths don't match
        """
        if len(book_ids) != len(embeddings):
            raise ValueError(
                f"book_ids length ({len(book_ids)}) must match "
                f"embeddings length ({len(embeddings)})"
            )

        # Use INSERT OR REPLACE for upsert behavior
        for book_id, embedding in zip(book_ids, embeddings):
            embedding_list = embedding.tolist()
            self.conn.execute(
                """
                INSERT OR REPLACE INTO library.book_embeddings (book_id, embedding)
                VALUES (?, ?)
                """,
                (book_id, embedding_list),
            )

    def semantic_search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search for similar books using cosine similarity.

        Args:
            query_embedding: Query vector of shape (embedding_dim,)
            top_k: Number of results to return

        Returns:
            List of dicts with 'book_id' and 'similarity' keys,
            sorted by similarity (highest first)
        """
        # Check if table is empty
        count_row = self.conn.execute("SELECT COUNT(*) FROM library.book_embeddings").fetchone()
        count = count_row[0] if count_row else 0

        if count == 0:
            return []

        # Convert query embedding to list for DuckDB
        query_list = query_embedding.tolist()

        # Use array_cosine_similarity for cosine similarity search
        # DuckDB VSS extension provides this function
        results = self.conn.execute(
            f"""
            SELECT
                book_id,
                array_cosine_similarity(embedding, ?::FLOAT[{self.embedding_dim}]) as similarity
            FROM library.book_embeddings
            ORDER BY similarity DESC
            LIMIT ?
            """,
            (query_list, top_k),
        ).fetchall()

        return [{"book_id": row[0], "similarity": row[1]} for row in results]

    def update_embedding(self, book_id: str, embedding: np.ndarray) -> None:
        """Update embedding for a specific book.

        Args:
            book_id: Book ID to update
            embedding: New embedding vector
        """
        embedding_list = embedding.tolist()
        self.conn.execute(
            """
            UPDATE library.book_embeddings
            SET embedding = ?, created_at = CURRENT_TIMESTAMP
            WHERE book_id = ?
            """,
            (embedding_list, book_id),
        )

    def delete_embedding(self, book_id: str) -> None:
        """Delete embedding for a specific book.

        Args:
            book_id: Book ID to delete
        """
        self.conn.execute(
            "DELETE FROM library.book_embeddings WHERE book_id = ?",
            (book_id,),
        )

    def get_embedding_count(self) -> int:
        """Get total number of stored embeddings.

        Returns:
            Count of embeddings in the store
        """
        result = self.conn.execute("SELECT COUNT(*) FROM library.book_embeddings").fetchone()
        return result[0] if result else 0

    def create_hnsw_index(self) -> None:
        """Create HNSW index for faster approximate search.

        Call this after all embeddings are stored for better
        query performance on large datasets.
        """
        # DuckDB VSS extension HNSW index
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS book_embeddings_hnsw_idx
            ON library.book_embeddings
            USING HNSW (embedding)
            WITH (metric = 'cosine')
        """)

    def get_embedding(self, book_id: str) -> np.ndarray | None:
        """Get embedding for a specific book.

        Args:
            book_id: Book ID to retrieve

        Returns:
            Numpy array of embedding, or None if not found
        """
        result = self.conn.execute(
            "SELECT embedding FROM library.book_embeddings WHERE book_id = ?",
            (book_id,),
        ).fetchone()

        if result is None:
            return None

        return np.array(result[0], dtype=np.float32)


class SalesVectorStore:
    """Vector store for sales embeddings using DuckDB.

    Stores sales embeddings and provides semantic search using cosine similarity.
    Uses DuckDB's VSS extension for efficient vector operations.

    Args:
        db_path: Path to DuckDB database file
        embedding_dim: Dimension of embedding vectors (default 384)

    Attributes:
        conn: DuckDB connection
        embedding_dim: Dimension of stored embeddings

    Example:
        >>> store = SalesVectorStore("data/duckdb/chapter2.db")
        >>> store.store_embeddings(["S0001", "S0002"], embeddings_array)
        >>> results = store.semantic_search(query_vector, top_k=10)
    """

    def __init__(
        self,
        db_path: str | None = None,
        embedding_dim: int = DEFAULT_EMBEDDING_DIM,
        read_only: bool = False,
        connection: duckdb.DuckDBPyConnection | None = None,
    ) -> None:
        """Initialize vector store with DuckDB connection.

        Creates the sales_embeddings table if it doesn't exist.

        Args:
            db_path: Path to DuckDB database. If None, uses default path.
            embedding_dim: Dimension of embedding vectors.
            read_only: If True, open database in read-only mode.
            connection: Optional existing DuckDB connection to use.
        """
        self.embedding_dim = embedding_dim
        self.read_only = read_only
        self._owns_connection = connection is None

        if connection is not None:
            self.conn = connection
            self.db_path = None
        else:
            if db_path is None:
                db_path = str(
                    Path(__file__).parent.parent.parent.parent / "data" / "duckdb" / "chapter2.db"
                )
            self.db_path = db_path
            self.conn = duckdb.connect(db_path, read_only=read_only)

        if not read_only:
            self._setup_table()

    def _setup_table(self) -> None:
        """Create the sales_embeddings table if it doesn't exist."""
        # Ensure library schema exists
        self.conn.execute("CREATE SCHEMA IF NOT EXISTS library")

        # Create embeddings table with FLOAT array for vector storage
        self.conn.execute(f"""
            CREATE TABLE IF NOT EXISTS library.sales_embeddings (
                sale_id VARCHAR PRIMARY KEY,
                embedding FLOAT[{self.embedding_dim}] NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def close(self) -> None:
        """Close the database connection if owned by this store."""
        if self._owns_connection and self.conn is not None:
            self.conn.close()
            self.conn = None  # type: ignore[assignment]

    def store_embeddings(
        self,
        sale_ids: list[str],
        embeddings: np.ndarray,
    ) -> None:
        """Store sales embeddings in the vector store.

        If a sale_id already exists, its embedding is updated.

        Args:
            sale_ids: List of sale IDs
            embeddings: Numpy array of shape (n_sales, embedding_dim)

        Raises:
            ValueError: If sale_ids and embeddings lengths don't match
        """
        if len(sale_ids) != len(embeddings):
            raise ValueError(
                f"sale_ids length ({len(sale_ids)}) must match "
                f"embeddings length ({len(embeddings)})"
            )

        # Use INSERT OR REPLACE for upsert behavior
        for sale_id, embedding in zip(sale_ids, embeddings):
            embedding_list = embedding.tolist()
            self.conn.execute(
                """
                INSERT OR REPLACE INTO library.sales_embeddings (sale_id, embedding)
                VALUES (?, ?)
                """,
                (sale_id, embedding_list),
            )

    def semantic_search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for similar sales using cosine similarity.

        Args:
            query_embedding: Query vector of shape (embedding_dim,)
            top_k: Number of results to return

        Returns:
            List of dicts with 'sale_id' and 'similarity' keys,
            sorted by similarity (highest first)
        """
        # Check if table is empty
        count_row = self.conn.execute("SELECT COUNT(*) FROM library.sales_embeddings").fetchone()
        count = count_row[0] if count_row else 0

        if count == 0:
            return []

        # Convert query embedding to list for DuckDB
        query_list = query_embedding.tolist()

        # Use array_cosine_similarity for cosine similarity search
        results = self.conn.execute(
            f"""
            SELECT
                sale_id,
                array_cosine_similarity(embedding, ?::FLOAT[{self.embedding_dim}]) as similarity
            FROM library.sales_embeddings
            ORDER BY similarity DESC
            LIMIT ?
            """,
            (query_list, top_k),
        ).fetchall()

        return [{"sale_id": row[0], "similarity": row[1]} for row in results]

    def get_embedding_count(self) -> int:
        """Get total number of stored sales embeddings.

        Returns:
            Count of embeddings in the store
        """
        result = self.conn.execute("SELECT COUNT(*) FROM library.sales_embeddings").fetchone()
        return result[0] if result else 0

    def create_hnsw_index(self) -> None:
        """Create HNSW index for faster approximate search.

        Call this after all embeddings are stored for better
        query performance on large datasets.
        """
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS sales_embeddings_hnsw_idx
            ON library.sales_embeddings
            USING HNSW (embedding)
            WITH (metric = 'cosine')
        """)


def semantic_search_cli() -> None:
    """Interactive CLI for semantic search.

    This is a CLI utility function called by `make semantic-search`.
    Allows users to enter natural language queries and see matching books.
    """
    from src.agentic.library.repository import BookRepository
    from src.agentic.rag.embeddings import EmbeddingGenerator

    db_path = Path(__file__).parent.parent.parent.parent / "data" / "duckdb" / "chapter2.db"

    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        print("Run 'make load-data' first.")
        return

    print("Initializing semantic search...")
    generator = EmbeddingGenerator()
    store = DuckDBVectorStore(db_path=str(db_path), read_only=True)
    repo = BookRepository(db_path=str(db_path), read_only=True)

    # Check if embeddings exist
    if store.get_embedding_count() == 0:
        print("No embeddings found. Run 'make generate-embeddings' first.")
        store.close()
        repo.close()
        return

    print(f"Loaded {store.get_embedding_count()} book embeddings")
    print("\nEnter a natural language query to search books.")
    print("Examples: 'books about time travel', 'programming tutorials'")
    print("Type 'quit' to exit.\n")

    while True:
        try:
            query = input("Query: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not query or query.lower() == "quit":
            break

        # Generate query embedding
        query_embedding = generator.embed_text(query)

        # Search
        results = store.semantic_search(query_embedding, top_k=5)

        if not results:
            print("No results found.\n")
            continue

        print(f"\nTop {len(results)} results:\n")
        for i, result in enumerate(results, 1):
            book = repo.get_book_by_id(result["book_id"])
            if book:
                print(f"{i}. {book.title} by {book.author}")
                print(f"   Category: {book.category.value}")
                print(f"   Similarity: {result['similarity']:.3f}")
                print(f"   Description: {book.description[:100]}...")
                print()

    store.close()
    repo.close()
    print("\nGoodbye!")
