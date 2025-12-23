"""Simple RAG Demo Package.

This package demonstrates the core concept of Retrieval-Augmented Generation (RAG)
using a minimal library dataset example.

The demo shows:
1. Without RAG: LLM cannot answer questions about specific library books
2. With RAG: LLM can answer accurately by retrieving relevant context

Usage:
    python -m src.rag.simple_rag

    # Or via Makefile:
    make rag-demo
"""

from .simple_rag import LibraryRAG, run_demo

__all__ = ["LibraryRAG", "run_demo"]
