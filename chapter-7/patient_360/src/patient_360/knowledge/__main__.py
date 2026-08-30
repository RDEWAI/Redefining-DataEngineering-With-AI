"""CLI for the knowledge RAG base: ``python -m patient_360.knowledge <command>``.

Commands:
  build  [--out PATH]                 Load the metadata folders, build the TF-IDF index, write it.
  ask    "<question>"                 AI search: answer an NLP question by reading ALL knowledge
                                      (semantic + ontology + taxonomy + data contracts, via RAG)
                                      AND the Gold data (NL->SQL). Needs the LLM key + Spark stack.
  stats  [--index PATH]               Print document counts by kind for the built index.
  search "<query>" [-k N] [--kind K]  Print the ranked metadata hits for a query (retrieval only).
  context "<query>" [-k N] [--kind K] Print the concatenated RAG context block for a query.

`build`/`search`/`context`/`stats` run offline (no API key / network). `ask` additionally calls
the LLM (LLM_MODEL + provider key) and Spark/Unity Catalog to read the Gold tables.
--kind filters to one of: semantic | ontology | taxonomy | data_contract.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from patient_360.knowledge.index import DEFAULT_INDEX_PATH, KnowledgeIndex, build_default_index
from patient_360.knowledge.retriever import Retriever


def _load_retriever(index_path: str | None) -> Retriever:
    """Load the persisted index; fall back to building it in memory if it isn't there yet."""
    try:
        return Retriever(KnowledgeIndex.load(index_path))
    except FileNotFoundError:
        print(
            "(no persisted index — building in memory; run `make knowledge-metadata` to cache it)",
            file=sys.stderr,
        )
        return Retriever(build_default_index())


def _cmd_ask(args: argparse.Namespace) -> int:
    # Imported lazily so build/search/stats work without the agent's LLM/Spark deps.
    from patient_360.semantic.agent import _format_rows, build_default_agent

    agent = build_default_agent(retriever=_load_retriever(args.index))
    result = agent.ask(args.query)
    if result.sql:
        print(f"\nSQL:\n{result.sql}\n")
    if result.result is not None:
        print(_format_rows(result.result))
    print(f"\nAnswer:    {result.answer}")
    if result.knowledge_used:
        print(f"Knowledge: {result.knowledge_used}")
    if result.error:
        print(f"(note: {result.error})", file=sys.stderr)
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    index = build_default_index()
    out = index.save(args.out)
    by_kind = Counter(doc.kind for doc in index.docs)
    kinds = ", ".join(f"{k}={n}" for k, n in sorted(by_kind.items()))
    print(f"Built knowledge index: {len(index.docs)} documents ({kinds})")
    print(f"  layers: {', '.join(index.built_from)}")
    print(f"  written to: {out}")
    return 0


def _cmd_stats(args: argparse.Namespace) -> int:
    index = KnowledgeIndex.load(args.index)
    by_kind = Counter(doc.kind for doc in index.docs)
    print(f"Knowledge index at {args.index or DEFAULT_INDEX_PATH}: {len(index.docs)} documents")
    for kind, n in sorted(by_kind.items()):
        print(f"  {kind:<14} {n}")
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    retriever = Retriever(KnowledgeIndex.load(args.index))
    print(retriever.format_hits(args.query, k=args.k, kind=args.kind))
    return 0


def _cmd_context(args: argparse.Namespace) -> int:
    retriever = Retriever(KnowledgeIndex.load(args.index))
    block = retriever.context(args.query, k=args.k, kind=args.kind)
    print(block if block else f"(no metadata matched {args.query!r})")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m patient_360.knowledge")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="build and persist the knowledge index")
    p_build.add_argument("--out", default=None, help=f"index path (default {DEFAULT_INDEX_PATH})")
    p_build.set_defaults(func=_cmd_build)

    p_ask = sub.add_parser("ask", help="answer an NLP question over all knowledge + Gold data")
    p_ask.add_argument("query")
    p_ask.add_argument("--index", default=None)
    p_ask.set_defaults(func=_cmd_ask)

    p_stats = sub.add_parser("stats", help="document counts by kind")
    p_stats.add_argument("--index", default=None)
    p_stats.set_defaults(func=_cmd_stats)

    for name, func, help_text in (
        ("search", _cmd_search, "ranked metadata hits for a query"),
        ("context", _cmd_context, "concatenated RAG context block for a query"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("query")
        p.add_argument("-k", type=int, default=5, help="number of documents to retrieve")
        p.add_argument(
            "--kind",
            choices=["semantic", "ontology", "taxonomy", "data_contract"],
            default=None,
        )
        p.add_argument("--index", default=None)
        p.set_defaults(func=func)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
