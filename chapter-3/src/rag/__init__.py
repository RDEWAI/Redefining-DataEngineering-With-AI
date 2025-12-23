"""Simple RAG Demo Package.

This package demonstrates the core concept of Retrieval-Augmented Generation (RAG)
using a minimal library dataset example.

The demo shows:
1. Without RAG: LLM cannot answer questions about specific library books
2. With RAG: LLM can answer accurately by retrieving relevant context

Usage:
    make llm       # Chat without RAG (see hallucinations)
    make llm-rag   # Chat with RAG (see accurate answers)
"""

from .simple_rag import LibraryRAG, llm_chat

__all__ = ["LibraryRAG", "llm_chat"]
