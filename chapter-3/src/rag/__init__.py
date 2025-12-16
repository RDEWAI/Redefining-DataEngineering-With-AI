"""RAG components: embeddings and vector store.

This package provides semantic search capabilities for the library:
- EmbeddingGenerator: Creates vector embeddings from book text
- DuckDBVectorStore: Stores and searches embeddings using DuckDB

Example:
    >>> from rag import EmbeddingGenerator, DuckDBVectorStore
    >>> generator = EmbeddingGenerator()
    >>> store = DuckDBVectorStore()
    >>> embedding = generator.embed_text("books about time travel")
    >>> results = store.semantic_search(embedding, top_k=5)
"""

# Use relative imports for compatibility with different run contexts
try:
    from rag.embeddings import (
        DEFAULT_EMBEDDING_DIM,
        DEFAULT_MODEL_NAME,
        EmbeddingGenerator,
        create_book_text_for_embedding,
        generate_all_embeddings,
    )
    from rag.vector_store import DuckDBVectorStore, semantic_search_cli
except ImportError:
    from src.rag.embeddings import (
        DEFAULT_EMBEDDING_DIM,
        DEFAULT_MODEL_NAME,
        EmbeddingGenerator,
        create_book_text_for_embedding,
        generate_all_embeddings,
    )
    from src.rag.vector_store import DuckDBVectorStore, semantic_search_cli

__all__ = [
    "EmbeddingGenerator",
    "DuckDBVectorStore",
    "create_book_text_for_embedding",
    "generate_all_embeddings",
    "semantic_search_cli",
    "DEFAULT_MODEL_NAME",
    "DEFAULT_EMBEDDING_DIM",
]
