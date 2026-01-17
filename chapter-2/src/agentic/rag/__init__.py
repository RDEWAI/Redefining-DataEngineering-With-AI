"""RAG components: embeddings and vector store.

This package provides semantic search capabilities for the library:

Example:
    >>> from src.agentic.rag import EmbeddingGenerator, DuckDBVectorStore
    >>> generator = EmbeddingGenerator()
    >>> store = DuckDBVectorStore()
    >>> embedding = generator.embed_text("books about time travel")
    >>> results = store.semantic_search(embedding, top_k=5)
"""

from .embeddings import (
    DEFAULT_EMBEDDING_DIM,
    DEFAULT_MODEL_NAME,
    EmbeddingGenerator,
    create_book_text_for_embedding,
    generate_all_embeddings,
)
from .vector_store import DuckDBVectorStore, semantic_search_cli

__all__ = [
    "EmbeddingGenerator",
    "DuckDBVectorStore",
    "create_book_text_for_embedding",
    "generate_all_embeddings",
    "semantic_search_cli",
    "DEFAULT_MODEL_NAME",
    "DEFAULT_EMBEDDING_DIM",
]
