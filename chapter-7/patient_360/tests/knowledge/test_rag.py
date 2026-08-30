"""Offline tests for the knowledge RAG base (no API key / Spark / network needed).

Covers the loader over the real metadata folders, the TF-IDF index round-trip, and that a
handful of intent-bearing queries retrieve the metadata layer a human would expect.
"""

from __future__ import annotations

from patient_360.knowledge.documents import KIND_DIRS, load_documents
from patient_360.knowledge.index import KnowledgeIndex, build_default_index, build_index, tokenize
from patient_360.knowledge.retriever import Retriever


def test_loads_all_four_metadata_layers() -> None:
    docs = load_documents()
    kinds = {d.kind for d in docs}
    assert kinds == set(KIND_DIRS), f"missing metadata layers: {set(KIND_DIRS) - kinds}"
    # every document carries indexable text and a project-relative source path
    assert all(d.text and d.source.endswith(".yml") for d in docs)


def test_tokenizer_is_lowercase_wordish() -> None:
    # lowercased, split on non-word chars, single-char tokens (e.g. the "3") dropped.
    assert tokenize("Prescription-Medication rxNumber=3 ml") == [
        "prescription", "medication", "rxnumber", "ml",
    ]


def _retriever() -> Retriever:
    return Retriever(build_default_index())


def test_ontology_query_retrieves_provider_relation() -> None:
    top = _retriever().search("which provider conducts an encounter", k=3)
    assert top, "expected at least one hit"
    titles = {doc.title for doc, _ in top}
    assert {"Provider", "Encounter"} & titles
    assert any(doc.kind == "ontology" for doc, _ in top)


def test_taxonomy_query_retrieves_medication_hierarchy() -> None:
    top = _retriever().search("prescription vs over-the-counter medication classification", k=3)
    assert any(doc.kind == "taxonomy" and "Medication" in doc.title for doc, _ in top)


def test_data_contract_query_retrieves_latency_caveat() -> None:
    top = _retriever().search("nightly lab refresh latency timing caveat", k=3)
    assert any(doc.kind == "data_contract" for doc, _ in top)


def test_kind_filter_restricts_results() -> None:
    hits = _retriever().search("patient", k=5, kind="data_contract")
    assert hits and all(doc.kind == "data_contract" for doc, _ in hits)


def test_context_block_is_prompt_ready() -> None:
    block = _retriever().context("encounter class taxonomy", k=2)
    assert block.startswith("# Retrieved knowledge")
    assert "###" in block


def test_index_roundtrip_preserves_search(tmp_path) -> None:
    index = build_default_index()
    path = index.save(tmp_path / "idx.json")
    reloaded = KnowledgeIndex.load(path)
    q = "average recovery cost by encounter class"
    assert [d.id for d, _ in index.search(q, k=3)] == [d.id for d, _ in reloaded.search(q, k=3)]


def test_empty_docs_raise() -> None:
    import pytest

    with pytest.raises(ValueError):
        build_index([])


# --- ai-search: the agent reads knowledge (RAG) + data (Gold), exercised with fakes ---


class _FakeLLM:
    def __init__(self, replies):
        self._replies = list(replies)
        self.calls = []

    def complete(self, messages, **_):
        self.calls.append(messages)
        return self._replies.pop(0)


class _FakeExecutor:
    def __init__(self, result):
        self._result = result
        self.sql_seen = []

    def run(self, sql):
        self.sql_seen.append(sql)
        return self._result


def test_ai_search_injects_retrieved_knowledge_into_prompt() -> None:
    from patient_360.semantic.agent import SemanticSQLAgent
    from patient_360.semantic.executor import QueryResult

    retriever = build_default_index()  # KnowledgeIndex also satisfies .search; wrap in Retriever
    agent = SemanticSQLAgent(
        _FakeLLM([
            "```sql\nSELECT COUNT(DISTINCT provider_name) AS n "
            "FROM unity.gold.patient_clinical_history\n```",
            "There are 261 providers.",
        ]),
        _FakeExecutor(QueryResult(columns=["n"], rows=[(261,)])),
        retriever=Retriever(retriever),
    )

    question = "which provider conducts an encounter"
    result = agent.ask(question)

    # the exact system prompt the agent built for this question (semantic model + RAG block)
    system_prompt = agent._system_prompt(agent._retrieve(question))
    assert "unity.gold.patient_clinical_history" in system_prompt   # rendered semantic model
    assert "Retrieved knowledge" in system_prompt                    # the RAG augmentation block
    assert "conducts" in system_prompt                               # from ontology/provider.yml
    assert result.result is not None and result.result.rows == [(261,)]
