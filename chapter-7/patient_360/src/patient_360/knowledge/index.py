"""Build and persist a lexical (TF-IDF) index over the knowledge documents.

Deliberately dependency-light: a pure-Python TF-IDF with cosine similarity, so the
``knowledge-metadata`` build and ``ai-search`` run offline, deterministically, and with no API
key. The document text is stored in the index file, so retrieval needs only the index (not the
source YAML), and the retrieved text can be fed straight to an LLM as RAG context.

The index format is intentionally simple JSON, so it is diff-friendly and could be swapped for
an embedding-based vector store later without changing the retriever's interface.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from patient_360.knowledge.documents import PROJECT_ROOT, KnowledgeDoc, load_documents

DEFAULT_INDEX_PATH = PROJECT_ROOT / ".rag" / "knowledge_index.json"
_INDEX_VERSION = 1
_TOKEN_RE = re.compile(r"[a-z0-9_]{2,}")


def tokenize(text: str) -> list[str]:
    """Lowercase word/number tokens (>= 2 chars); the whole tokenizer for index + query."""
    return _TOKEN_RE.findall(text.lower())


def _normalize(vec: dict[str, float]) -> dict[str, float]:
    norm = math.sqrt(sum(w * w for w in vec.values()))
    if norm == 0.0:
        return vec
    return {t: w / norm for t, w in vec.items()}


@dataclass
class _Indexed:
    doc: KnowledgeDoc
    vector: dict[str, float]


@dataclass
class KnowledgeIndex:
    """A queryable TF-IDF index over :class:`KnowledgeDoc` records."""

    entries: list[_Indexed]
    idf: dict[str, float]
    built_from: list[str] = field(default_factory=list)

    # -- query -------------------------------------------------------------
    def _query_vector(self, query: str) -> dict[str, float]:
        counts = Counter(tokenize(query))
        vec = {t: tf * self.idf[t] for t, tf in counts.items() if t in self.idf}
        return _normalize(vec)

    def search(
        self,
        query: str,
        *,
        k: int = 5,
        kind: str | None = None,
        exclude: set[str] | None = None,
    ) -> list[tuple[KnowledgeDoc, float]]:
        """Return the top-``k`` (document, cosine score) pairs.

        ``kind`` restricts to a single metadata kind; ``exclude`` drops the given kinds (e.g.
        skip ``semantic`` when the caller already renders the full semantic model separately).
        """
        qvec = self._query_vector(query)
        if not qvec:
            return []
        scored: list[tuple[KnowledgeDoc, float]] = []
        for entry in self.entries:
            if kind and entry.doc.kind != kind:
                continue
            if exclude and entry.doc.kind in exclude:
                continue
            score = sum(w * entry.vector.get(t, 0.0) for t, w in qvec.items())
            if score > 0.0:
                scored.append((entry.doc, score))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:k]

    @property
    def docs(self) -> list[KnowledgeDoc]:
        return [e.doc for e in self.entries]

    # -- persistence -------------------------------------------------------
    def to_dict(self) -> dict[str, object]:
        return {
            "version": _INDEX_VERSION,
            "built_from": self.built_from,
            "idf": self.idf,
            "docs": [
                {**e.doc.model_dump(), "vector": e.vector} for e in self.entries
            ],
        }

    def save(self, path: str | Path | None = None) -> Path:
        out = Path(path) if path is not None else DEFAULT_INDEX_PATH
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return out

    @classmethod
    def load(cls, path: str | Path | None = None) -> KnowledgeIndex:
        src = Path(path) if path is not None else DEFAULT_INDEX_PATH
        if not src.is_file():
            raise FileNotFoundError(
                f"knowledge index not found: {src} — run `make knowledge-metadata` first"
            )
        data = json.loads(src.read_text(encoding="utf-8"))
        entries = [
            _Indexed(
                doc=KnowledgeDoc.model_validate({k: v for k, v in d.items() if k != "vector"}),
                vector={t: float(w) for t, w in d.get("vector", {}).items()},
            )
            for d in data.get("docs", [])
        ]
        idf = {t: float(w) for t, w in data.get("idf", {}).items()}
        return cls(entries=entries, idf=idf, built_from=list(data.get("built_from", [])))


def build_index(docs: list[KnowledgeDoc]) -> KnowledgeIndex:
    """Compute smoothed TF-IDF vectors for ``docs`` and return a queryable index."""
    if not docs:
        raise ValueError("no documents to index — are the metadata folders present?")

    n = len(docs)
    doc_freq: Counter[str] = Counter()
    doc_counts: list[Counter[str]] = []
    for doc in docs:
        counts = Counter(tokenize(f"{doc.title}\n{doc.text}"))
        doc_counts.append(counts)
        doc_freq.update(counts.keys())

    # smoothed idf: never zero, so a term shared by all docs still contributes a little
    idf = {t: math.log((n + 1) / (df + 1)) + 1.0 for t, df in doc_freq.items()}

    entries: list[_Indexed] = []
    for doc, counts in zip(docs, doc_counts):
        vec = _normalize({t: tf * idf[t] for t, tf in counts.items()})
        entries.append(_Indexed(doc=doc, vector=vec))

    built_from = sorted({doc.source.split("/", 1)[0] for doc in docs})
    return KnowledgeIndex(entries=entries, idf=idf, built_from=built_from)


def build_default_index(project_root: str | Path | None = None) -> KnowledgeIndex:
    """Load every metadata folder and build the index in one call."""
    return build_index(load_documents(project_root))
