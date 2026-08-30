"""CLI for the semantic model and agent: ``python -m patient_360.semantic <command>``.

Commands:
  validate [semantic_dir]   Cross-check the model against the Gold contracts; exit 1 on CRITICAL.
  render   [semantic_dir]   Print the LLM prompt context block for the model.
  ask "<question>"          Answer one business question (LLM + Spark; needs LLM_MODEL's provider
                            key, e.g. ANTHROPIC_API_KEY, + the docker stack).
  chat                      Interactive REPL over the Gold tables (type 'exit' to quit).
"""

from __future__ import annotations

import sys

from patient_360.semantic.loader import DEFAULT_SEMANTIC_DIR, load_model
from patient_360.semantic.render import render_context
from patient_360.semantic.validate import main as validate_main

_USAGE = "usage: python -m patient_360.semantic {validate|render|ask|chat} [args]"


def _print_result(result: object) -> None:
    # Imported lazily so validate/render work without the agent's optional deps.
    from patient_360.semantic.agent import AgentResult, _format_rows

    assert isinstance(result, AgentResult)
    if result.sql:
        print(f"\nSQL:\n{result.sql}\n")
    if result.result is not None:
        print(_format_rows(result.result))
    print(f"\nAnswer: {result.answer}")
    if result.error:
        print(f"(note: {result.error})", file=sys.stderr)


def _cmd_ask(rest: list[str]) -> int:
    if not rest:
        print('usage: python -m patient_360.semantic ask "<question>"', file=sys.stderr)
        return 2
    from patient_360.semantic.agent import build_default_agent

    agent = build_default_agent()
    _print_result(agent.ask(" ".join(rest)))
    return 0


def _cmd_chat() -> int:
    from patient_360.semantic.agent import build_default_agent

    agent = build_default_agent()
    print("Patient 360 analytics — ask a question about the Gold tables ('exit' to quit).")
    while True:
        try:
            question = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if question.lower() in {"exit", "quit", ":q"}:
            return 0
        if not question:
            continue
        _print_result(agent.ask(question))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print(_USAGE)
        return 0 if args else 2

    command, rest = args[0], args[1:]
    if command == "validate":
        return validate_main(rest)
    if command == "render":
        semantic_dir = rest[0] if rest else str(DEFAULT_SEMANTIC_DIR)
        print(render_context(load_model(semantic_dir)), end="")
        return 0
    if command == "ask":
        return _cmd_ask(rest)
    if command == "chat":
        return _cmd_chat()

    print(f"unknown command {command!r}\n{_USAGE}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
