"""Natural-language-to-SQL agent over the Patient 360 Gold tables.

Pipeline per question:

    1. generate  — ask the LLM for one Spark SQL SELECT, grounded in the rendered semantic
                   model (:func:`patient_360.semantic.render.render_context`).
    2. guard     — enforce a read-only, single-statement, allow-listed query
                   (:mod:`patient_360.semantic.sql_guard`).
    3. execute   — run it against ``unity.gold.*`` (:class:`SparkGoldExecutor`).
    4. repair    — on a guard/execution error, feed the error back and retry (bounded).
    5. summarize — turn the rows into a short natural-language answer.

The LLM client and executor are injected, so the whole loop is unit-testable with fakes and
needs no API key or Spark session.
"""

from __future__ import annotations

from dataclasses import dataclass

from patient_360.semantic.executor import GoldExecutor, QueryResult
from patient_360.semantic.llm import LLMClient, Message
from patient_360.semantic.loader import load_model
from patient_360.semantic.render import render_context
from patient_360.semantic.schema import SemanticModel
from patient_360.semantic.sql_guard import GuardError, extract_sql, guard_sql

_SQL_INSTRUCTIONS = """\
You translate the user's question into exactly ONE read-only Spark SQL query over the tables
described above.

Rules:
- Output ONLY the SQL, inside a single ```sql code block. No prose.
- One statement, a SELECT (optionally a WITH ... SELECT). Never INSERT/UPDATE/DELETE/DDL.
- Reference tables by their full name (unity.gold.*).
- Use the EXACT literal values listed for a column, and map business words via the glossary.
- Financial/cost columns exist only on unity.gold.patient_billing_summary.
- If the question cannot be answered from these tables, return: SELECT 'unanswerable' AS note.
"""

_ANSWER_INSTRUCTIONS = """\
You are a healthcare data analyst. Answer the user's question in 1-3 plain sentences using
ONLY the provided query results. State concrete numbers. If the result is empty or zero, say
there is no matching data rather than inventing an answer. Do not mention SQL.
"""

_MAX_PREVIEW_ROWS = 20


@dataclass
class AgentResult:
    """Everything the agent produced for one question."""

    question: str
    sql: str | None
    result: QueryResult | None
    answer: str
    error: str | None
    attempts: int


def _format_rows(result: QueryResult, *, limit: int = _MAX_PREVIEW_ROWS) -> str:
    header = " | ".join(result.columns)
    body = "\n".join(
        " | ".join("NULL" if v is None else str(v) for v in row)
        for row in result.rows[:limit]
    )
    more = "" if result.row_count <= limit else f"\n... ({result.row_count - limit} more rows)"
    return f"{header}\n{body}{more}" if body else f"{header}\n(no rows)"


class SemanticSQLAgent:
    """Answer business questions by generating, guarding, and running SQL over Gold."""

    def __init__(
        self,
        llm: LLMClient,
        executor: GoldExecutor,
        model: SemanticModel | None = None,
        *,
        max_repairs: int = 1,
        max_rows: int = 1000,
        generate_answer: bool = True,
    ) -> None:
        self.llm = llm
        self.executor = executor
        self.model = model or load_model()
        self.context = render_context(self.model)
        self.allowed_tables = set(self.model.tables())
        self.max_repairs = max_repairs
        self.max_rows = max_rows
        self.generate_answer = generate_answer

    def _system_prompt(self) -> str:
        return f"{self.context}\n\n{_SQL_INSTRUCTIONS}"

    def generate_sql(
        self, question: str, *, error: str | None = None, prev_sql: str | None = None
    ) -> str:
        """Ask the LLM for SQL; when ``error`` is set, ask it to repair ``prev_sql``."""
        if error is None:
            user = question
        else:
            user = (
                f"The previous SQL for this question failed.\n"
                f"Question: {question}\n"
                f"SQL:\n{prev_sql}\n"
                f"Error: {error}\n"
                f"Return a corrected single read-only SELECT."
            )
        raw = self.llm.complete(
            [Message("system", self._system_prompt()), Message("user", user)]
        )
        return extract_sql(raw)

    def _summarize(self, question: str, sql: str, result: QueryResult) -> str:
        preview = _format_rows(result)
        messages = [
            Message("system", _ANSWER_INSTRUCTIONS),
            Message(
                "user",
                f"Question: {question}\nSQL: {sql}\n"
                f"Results ({result.row_count} rows):\n{preview}",
            ),
        ]
        return self.llm.complete(messages, max_tokens=400).strip()

    def ask(self, question: str) -> AgentResult:
        """Run the full generate -> guard -> execute -> repair -> summarize loop."""
        error: str | None = None
        prev: str | None = None
        sql: str | None = None
        result: QueryResult | None = None

        for attempt in range(self.max_repairs + 1):
            raw_sql = self.generate_sql(question, error=error, prev_sql=prev)
            try:
                sql = guard_sql(
                    raw_sql, allowed_tables=self.allowed_tables, max_limit=self.max_rows
                )
            except GuardError as exc:
                error = f"rejected by SQL guard: {exc}"
                prev, sql = raw_sql, None
                continue
            try:
                result = self.executor.run(sql)
                error = None
                break
            except Exception as exc:  # noqa: BLE001 - surface any execution error to the repair loop
                error, prev, result = str(exc), sql, None

        attempts = attempt + 1
        if result is not None:
            answer = self._summarize(question, sql, result) if self.generate_answer else ""
        else:
            answer = f"I couldn't answer that. Last error: {error}"
        return AgentResult(question, sql, result, answer, error, attempts)


def build_default_agent(**kwargs: object) -> SemanticSQLAgent:
    """Wire an agent from the environment: OpenAI-compatible LLM + Spark Gold executor."""
    from patient_360.semantic.executor import SparkGoldExecutor
    from patient_360.semantic.llm import build_llm_from_env

    max_rows = int(kwargs.pop("max_rows", 1000))  # type: ignore[arg-type]
    return SemanticSQLAgent(
        build_llm_from_env(),
        SparkGoldExecutor(max_rows=max_rows),
        max_rows=max_rows,
        **kwargs,  # type: ignore[arg-type]
    )
