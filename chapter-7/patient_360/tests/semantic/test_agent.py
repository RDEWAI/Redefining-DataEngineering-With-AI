"""Agent loop, exercised end-to-end with a fake LLM and a fake executor (no API key/Spark)."""

from __future__ import annotations

import pytest

from patient_360.semantic import load_model
from patient_360.semantic.agent import SemanticSQLAgent
from patient_360.semantic.executor import QueryResult
from patient_360.semantic.llm import Message


class FakeLLM:
    """Returns queued replies in order and records the prompts it received."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.calls: list[list[Message]] = []

    def complete(self, messages: list[Message], **_: object) -> str:
        self.calls.append(messages)
        return self._replies.pop(0)


class FakeExecutor:
    """Yields queued results; a queued Exception is raised to drive the repair loop."""

    def __init__(self, outcomes: list[object]) -> None:
        self._outcomes = list(outcomes)
        self.sql_seen: list[str] = []

    def run(self, sql: str) -> QueryResult:
        self.sql_seen.append(sql)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        assert isinstance(outcome, QueryResult)
        return outcome


@pytest.fixture(scope="module")
def model():
    return load_model()


def test_happy_path_generates_guards_executes_and_answers(model) -> None:
    llm = FakeLLM([
        "```sql\nSELECT COUNT(*) AS n FROM unity.gold.patient_summary\n"
        "WHERE patient_status = 'ALIVE'\n```",
        "There are 5000 living patients.",
    ])
    executor = FakeExecutor([QueryResult(columns=["n"], rows=[(5000,)])])
    agent = SemanticSQLAgent(llm, executor, model=model)

    result = agent.ask("How many living patients are there?")

    assert result.attempts == 1
    assert result.error is None
    assert result.result is not None and result.result.rows == [(5000,)]
    assert "5000" in result.answer
    # a LIMIT was injected by the guard before execution
    assert executor.sql_seen[0].strip().endswith("LIMIT 1000")
    # the system prompt carried the rendered semantic context
    system_msg = llm.calls[0][0]
    assert system_msg.role == "system" and "unity.gold.patient_summary" in system_msg.content


def test_repair_loop_recovers_from_execution_error(model) -> None:
    llm = FakeLLM([
        "```sql\nSELECT bad_col FROM unity.gold.patient_summary\n```",
        "```sql\nSELECT COUNT(*) AS n FROM unity.gold.patient_summary\n```",
        "There are 5767 patients.",
    ])
    executor = FakeExecutor([
        RuntimeError("UNRESOLVED_COLUMN bad_col"),
        QueryResult(columns=["n"], rows=[(5767,)]),
    ])
    agent = SemanticSQLAgent(llm, executor, model=model, max_repairs=1)

    result = agent.ask("How many patients are there?")

    assert result.attempts == 2
    assert result.error is None
    assert result.result is not None and result.result.rows == [(5767,)]
    # the repair prompt fed the execution error back to the LLM
    assert any("UNRESOLVED_COLUMN" in m.content for m in llm.calls[1])


def test_guard_rejection_without_repair_returns_error(model) -> None:
    llm = FakeLLM(["```sql\nDROP TABLE unity.gold.patient_summary\n```"])
    executor = FakeExecutor([])
    agent = SemanticSQLAgent(llm, executor, model=model, max_repairs=0, generate_answer=False)

    result = agent.ask("delete everything")

    assert result.result is None
    assert result.sql is None
    assert result.error is not None and "guard" in result.error.lower()
    assert executor.sql_seen == []  # nothing was ever executed


def test_generate_answer_false_skips_summary_call(model) -> None:
    llm = FakeLLM(["```sql\nSELECT 1 AS n FROM unity.gold.patient_summary\n```"])
    executor = FakeExecutor([QueryResult(columns=["n"], rows=[(1,)])])
    agent = SemanticSQLAgent(llm, executor, model=model, generate_answer=False)

    result = agent.ask("anything")

    assert result.result is not None
    assert result.answer == ""
    assert len(llm.calls) == 1  # no second (summarize) call
