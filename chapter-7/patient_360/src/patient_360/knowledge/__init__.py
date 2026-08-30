"""AI-metadata knowledge base + RAG retrieval for Patient 360.

Loads the four metadata layers — semantic model, ontology, taxonomy and data contracts —
into retrievable documents, builds a lexical (TF-IDF) index, and serves the top-k relevant
chunks as context for an AI consumer. Run it via ``python -m patient_360.knowledge`` or the
``make knowledge-*`` targets. No API key or network is required to build or query the index.
"""

from __future__ import annotations

from patient_360.knowledge.documents import KnowledgeDoc, load_documents
from patient_360.knowledge.index import KnowledgeIndex, build_index
from patient_360.knowledge.retriever import Retriever, load_default_retriever

__all__ = [
    "KnowledgeDoc",
    "load_documents",
    "KnowledgeIndex",
    "build_index",
    "Retriever",
    "load_default_retriever",
]
