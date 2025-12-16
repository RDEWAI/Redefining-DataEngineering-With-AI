"""Integration tests for semantic search with RAG.

Tests the full semantic search pipeline including:
- Embedding generation
- DuckDB VSS vector storage
- Semantic similarity search
- Retrieval accuracy
"""

import tempfile
from datetime import datetime

import numpy as np
import pytest

from src.library.domain import Book, BookStatus, Category, Location


@pytest.fixture
def sample_books() -> list[Book]:
    """Create sample books for testing."""
    now = datetime.now()
    return [
        Book(
            book_id="B001",
            title="Python Programming Fundamentals",
            author="John Smith",
            description="A comprehensive guide to Python programming covering data structures, "
            "algorithms, and object-oriented design. Perfect for beginners learning to code.",
            category=Category.PROGRAMMING,
            location=Location(cabinet=1, rack=1, row=1),
            signal_strength=-40.0,
            timestamp=now,
            status=BookStatus.PRESENT,
        ),
        Book(
            book_id="B002",
            title="The Time Machine",
            author="H.G. Wells",
            description="A classic science fiction novel about a scientist who invents a machine "
            "capable of traveling through time. He journeys to the distant future where "
            "humanity has evolved into two distinct species.",
            category=Category.FICTION,
            location=Location(cabinet=1, rack=1, row=2),
            signal_strength=-45.0,
            timestamp=now,
            status=BookStatus.PRESENT,
        ),
        Book(
            book_id="B003",
            title="A Brief History of Time",
            author="Stephen Hawking",
            description="An exploration of cosmology, black holes, and the nature of time "
            "and space. Hawking explains complex physics concepts in accessible language "
            "for general readers.",
            category=Category.SCIENCE,
            location=Location(cabinet=2, rack=1, row=1),
            signal_strength=-50.0,
            timestamp=now,
            status=BookStatus.PRESENT,
        ),
        Book(
            book_id="B004",
            title="Murder on the Orient Express",
            author="Agatha Christie",
            description="A gripping detective mystery where Hercule Poirot investigates "
            "a murder aboard the famous Orient Express train. Everyone on board "
            "has a motive.",
            category=Category.THRILLER,
            location=Location(cabinet=2, rack=2, row=1),
            signal_strength=-55.0,
            timestamp=now,
            status=BookStatus.PRESENT,
        ),
        Book(
            book_id="B005",
            title="The Roman Empire",
            author="Mary Beard",
            description="An in-depth examination of ancient Rome from its founding to "
            "its fall. Covers politics, culture, military conquests, and daily life "
            "in the Roman world.",
            category=Category.HISTORY,
            location=Location(cabinet=3, rack=1, row=1),
            signal_strength=-42.0,
            timestamp=now,
            status=BookStatus.PRESENT,
        ),
        Book(
            book_id="B006",
            title="Time Travel in Fiction",
            author="James Gleick",
            description="An analysis of how time travel has been portrayed in literature "
            "and film. From H.G. Wells to modern science fiction, explores the "
            "philosophical implications of traveling through time.",
            category=Category.SCIENCE,
            location=Location(cabinet=2, rack=1, row=2),
            signal_strength=-48.0,
            timestamp=now,
            status=BookStatus.PRESENT,
        ),
    ]


@pytest.fixture
def temp_db_path() -> str:
    """Create a temporary database path."""
    import os

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    # Delete the empty file so DuckDB can create a fresh database
    os.unlink(path)
    return path


class TestSemanticSearchIntegration:
    """Integration tests for semantic search."""

    @pytest.mark.skip(reason="Requires sentence-transformers model download")
    def test_full_semantic_search_pipeline(
        self, sample_books: list[Book], temp_db_path: str
    ) -> None:
        """Test full pipeline: embed books, store, and search."""
        from src.rag.embeddings import EmbeddingGenerator
        from src.rag.vector_store import DuckDBVectorStore

        # Initialize components
        generator = EmbeddingGenerator()
        store = DuckDBVectorStore(db_path=temp_db_path)

        # Generate embeddings for all books
        embeddings = generator.embed_books(sample_books)
        book_ids = [book.book_id for book in sample_books]

        # Store embeddings
        store.store_embeddings(book_ids, embeddings)

        # Search for time travel books
        query = "books about time travel and temporal displacement"
        query_embedding = generator.embed_text(query)
        results = store.semantic_search(query_embedding, top_k=3)

        # Verify results
        assert len(results) > 0
        # B002 (Time Machine) and B006 (Time Travel in Fiction) should be top results
        result_ids = [r["book_id"] for r in results]
        assert "B002" in result_ids or "B006" in result_ids

        store.close()

    def test_vector_store_setup_with_mock(self, temp_db_path: str) -> None:
        """Test vector store table creation."""
        from src.rag.vector_store import DuckDBVectorStore

        store = DuckDBVectorStore(db_path=temp_db_path)

        # Verify table was created using the store's connection
        tables = store.conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'library'"
        ).fetchall()
        table_names = [t[0] for t in tables]

        assert "book_embeddings" in table_names
        store.close()

    def test_store_and_retrieve_embeddings(self, temp_db_path: str) -> None:
        """Test storing and retrieving embeddings."""
        from src.rag.vector_store import DuckDBVectorStore

        store = DuckDBVectorStore(db_path=temp_db_path)

        # Create mock embeddings (384-dimensional)
        book_ids = ["B001", "B002", "B003"]
        embeddings = np.random.randn(3, 384).astype(np.float32)
        # Normalize embeddings
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

        # Store embeddings
        store.store_embeddings(book_ids, embeddings)

        # Verify storage
        result = store.conn.execute("SELECT COUNT(*) FROM library.book_embeddings").fetchone()
        assert result[0] == 3

        store.close()

    def test_semantic_search_returns_sorted_by_similarity(self, temp_db_path: str) -> None:
        """Test that search results are sorted by similarity score."""
        from src.rag.vector_store import DuckDBVectorStore

        store = DuckDBVectorStore(db_path=temp_db_path)

        # Create embeddings where B001 is most similar to query
        book_ids = ["B001", "B002", "B003"]
        query_vector = np.array([1.0] + [0.0] * 383, dtype=np.float32)

        # B001 very similar, B002 somewhat similar, B003 different
        embeddings = np.array(
            [
                [0.9] + [0.1] * 383,  # B001 - most similar
                [0.5] + [0.5] * 383,  # B002 - somewhat similar
                [0.1] + [0.9] * 383,  # B003 - least similar
            ],
            dtype=np.float32,
        )
        # Normalize
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

        store.store_embeddings(book_ids, embeddings)

        # Search
        results = store.semantic_search(query_vector, top_k=3)

        assert len(results) == 3
        # B001 should be first (highest similarity)
        assert results[0]["book_id"] == "B001"
        # Similarity scores should be descending
        scores = [r["similarity"] for r in results]
        assert scores == sorted(scores, reverse=True)

        store.close()

    def test_semantic_search_respects_top_k(self, temp_db_path: str) -> None:
        """Test that top_k limits results."""
        from src.rag.vector_store import DuckDBVectorStore

        store = DuckDBVectorStore(db_path=temp_db_path)

        # Store 10 embeddings
        book_ids = [f"B{i:03d}" for i in range(10)]
        embeddings = np.random.randn(10, 384).astype(np.float32)
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

        store.store_embeddings(book_ids, embeddings)

        query_vector = np.random.randn(384).astype(np.float32)
        query_vector = query_vector / np.linalg.norm(query_vector)

        results = store.semantic_search(query_vector, top_k=5)

        assert len(results) == 5

        store.close()

    def test_semantic_search_empty_store(self, temp_db_path: str) -> None:
        """Test search on empty store returns empty list."""
        from src.rag.vector_store import DuckDBVectorStore

        store = DuckDBVectorStore(db_path=temp_db_path)

        query_vector = np.random.randn(384).astype(np.float32)
        results = store.semantic_search(query_vector, top_k=5)

        assert results == []

        store.close()


class TestRetrievalAccuracy:
    """Tests for retrieval accuracy metrics."""

    @pytest.mark.skip(reason="Requires sentence-transformers model download")
    def test_time_travel_query_precision(self, sample_books: list[Book], temp_db_path: str) -> None:
        """Test that time travel query retrieves relevant books.

        Expected relevant books:
        - B002: The Time Machine (fiction about time travel)
        - B006: Time Travel in Fiction (analysis of time travel)

        Target: 70%+ precision at k=3 (at least 2 of top 3 are relevant)
        """
        from src.rag.embeddings import EmbeddingGenerator
        from src.rag.vector_store import DuckDBVectorStore

        generator = EmbeddingGenerator()
        store = DuckDBVectorStore(db_path=temp_db_path)

        # Store all books
        embeddings = generator.embed_books(sample_books)
        book_ids = [book.book_id for book in sample_books]
        store.store_embeddings(book_ids, embeddings)

        # Query for time travel
        query = "that book about time travel"
        query_embedding = generator.embed_text(query)
        results = store.semantic_search(query_embedding, top_k=3)

        # Check precision
        relevant_ids = {"B002", "B006"}
        retrieved_ids = {r["book_id"] for r in results}
        precision = len(relevant_ids & retrieved_ids) / len(results)

        # At least 2 of 3 results should be relevant (66% precision)
        assert precision >= 0.66, f"Precision {precision:.2%} below 66% threshold"

        store.close()

    @pytest.mark.skip(reason="Requires sentence-transformers model download")
    def test_programming_query_precision(self, sample_books: list[Book], temp_db_path: str) -> None:
        """Test that programming query retrieves relevant books."""
        from src.rag.embeddings import EmbeddingGenerator
        from src.rag.vector_store import DuckDBVectorStore

        generator = EmbeddingGenerator()
        store = DuckDBVectorStore(db_path=temp_db_path)

        embeddings = generator.embed_books(sample_books)
        book_ids = [book.book_id for book in sample_books]
        store.store_embeddings(book_ids, embeddings)

        query = "books about coding and software development"
        query_embedding = generator.embed_text(query)
        results = store.semantic_search(query_embedding, top_k=3)

        # B001 (Python Programming) should be in top results
        result_ids = [r["book_id"] for r in results]
        assert "B001" in result_ids

        store.close()


class TestVectorStoreOperations:
    """Tests for vector store CRUD operations."""

    def test_update_embedding(self, temp_db_path: str) -> None:
        """Test updating an existing embedding."""
        from src.rag.vector_store import DuckDBVectorStore

        store = DuckDBVectorStore(db_path=temp_db_path)

        # Store initial embedding
        initial_embedding = np.array([1.0] + [0.0] * 383, dtype=np.float32)
        store.store_embeddings(["B001"], initial_embedding.reshape(1, -1))

        # Update with new embedding
        new_embedding = np.array([0.0] + [1.0] * 383, dtype=np.float32)
        store.update_embedding("B001", new_embedding)

        # Verify update
        result = store.conn.execute(
            "SELECT embedding FROM library.book_embeddings WHERE book_id = 'B001'"
        ).fetchone()

        # The stored embedding should be the new one
        stored = np.array(result[0])
        assert np.allclose(stored[:2], [0.0, 1.0], atol=0.01)

        store.close()

    def test_delete_embedding(self, temp_db_path: str) -> None:
        """Test deleting an embedding."""
        from src.rag.vector_store import DuckDBVectorStore

        store = DuckDBVectorStore(db_path=temp_db_path)

        # Store embeddings
        embeddings = np.random.randn(3, 384).astype(np.float32)
        store.store_embeddings(["B001", "B002", "B003"], embeddings)

        # Delete one
        store.delete_embedding("B002")

        # Verify deletion
        result = store.conn.execute("SELECT COUNT(*) FROM library.book_embeddings").fetchone()
        assert result[0] == 2

        # Verify correct one was deleted
        remaining = store.conn.execute(
            "SELECT book_id FROM library.book_embeddings ORDER BY book_id"
        ).fetchall()
        remaining_ids = [r[0] for r in remaining]
        assert remaining_ids == ["B001", "B003"]

        store.close()

    def test_get_embedding_count(self, temp_db_path: str) -> None:
        """Test getting total embedding count."""
        from src.rag.vector_store import DuckDBVectorStore

        store = DuckDBVectorStore(db_path=temp_db_path)

        assert store.get_embedding_count() == 0

        embeddings = np.random.randn(5, 384).astype(np.float32)
        book_ids = [f"B{i:03d}" for i in range(5)]
        store.store_embeddings(book_ids, embeddings)

        assert store.get_embedding_count() == 5

        store.close()
