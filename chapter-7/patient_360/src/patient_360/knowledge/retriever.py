"""Retrieve metadata context from the knowledge index — the R in RAG.

Thin wrapper over :class:`patient_360.knowledge.index.KnowledgeIndex` that adds the formatting
an AI consumer needs: a ranked hit list (``format_hits``) and a ready-to-inject context block
(``context``) that concatenates the top-k retrieved documents. The NL-to-SQL agent (or any MCP
tool) can call :meth:`Retriever.context` to ground a prompt in the ontology / taxonomy / data
contracts on top of the semantic model it already renders.
"""

from __future__ import annotations

from pathlib import Path

from patient_360.knowledge.index import DEFAULT_INDEX_PATH, KnowledgeIndex


class Retriever:
    """Search the knowledge index and format results for humans or an LLM prompt."""

    def __init__(self, index: KnowledgeIndex) -> None:
        self.index = index

    def search(
        self, query: str, *, k: int = 5, kind: str | None = None, exclude: set[str] | None = None
    ):
        return self.index.search(query, k=k, kind=kind, exclude=exclude)

    def format_hits(
        self, query: str, *, k: int = 5, kind: str | None = None, exclude: set[str] | None = None
    ) -> str:
        hits = self.search(query, k=k, kind=kind, exclude=exclude)
        if not hits:
            return f"(no metadata matched {query!r})"
        lines = []
        for rank, (doc, score) in enumerate(hits, start=1):
            lines.append(f"{rank:>2}. [{score:.3f}] ({doc.kind}) {doc.title}  —  {doc.source}")
        return "\n".join(lines)

    def context(
        self, query: str, *, k: int = 5, kind: str | None = None, exclude: set[str] | None = None
    ) -> str:
        """Concatenate the top-k retrieved documents into a prompt-ready RAG context block."""
        hits = self.search(query, k=k, kind=kind, exclude=exclude)
        if not hits:
            return ""
        blocks = [
            f"### {doc.title}  ({doc.kind}, {doc.source}, relevance {score:.3f})\n{doc.text}"
            for doc, score in hits
        ]
        header = "# Retrieved knowledge (semantic / ontology / taxonomy / data contracts)"
        return header + "\n\n" + "\n\n".join(blocks) + "\n"


def load_default_retriever(index_path: str | Path | None = None) -> Retriever:
    """Load the persisted index (default ``.rag/knowledge_index.json``) into a Retriever."""
    path = Path(index_path) if index_path is not None else DEFAULT_INDEX_PATH
    return Retriever(KnowledgeIndex.load(path))
