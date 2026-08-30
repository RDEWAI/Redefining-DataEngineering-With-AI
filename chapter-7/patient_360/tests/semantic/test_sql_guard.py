"""Safety guard for LLM-generated SQL."""

from __future__ import annotations

import pytest

from patient_360.semantic.sql_guard import GuardError, extract_sql, guard_sql

_ALLOWED = {"unity.gold.patient_summary", "unity.gold.patient_clinical_history"}


def test_extract_strips_sql_fence() -> None:
    text = "Here you go:\n```sql\nSELECT 1\n```\nHope that helps."
    assert extract_sql(text) == "SELECT 1"


def test_extract_without_fence_and_trailing_semicolon() -> None:
    assert extract_sql("SELECT 1;") == "SELECT 1"


def test_select_gets_limit_injected() -> None:
    out = guard_sql(
        "SELECT * FROM unity.gold.patient_summary", allowed_tables=_ALLOWED, max_limit=50
    )
    assert out.endswith("LIMIT 50")


def test_existing_limit_is_preserved() -> None:
    sql = "SELECT * FROM unity.gold.patient_summary LIMIT 5"
    assert guard_sql(sql, allowed_tables=_ALLOWED) == sql


def test_with_cte_allowed() -> None:
    sql = (
        "WITH c AS (SELECT patient_id FROM unity.gold.patient_summary) "
        "SELECT COUNT(*) FROM c"
    )
    out = guard_sql(sql, allowed_tables=_ALLOWED)
    assert out.startswith("WITH")


@pytest.mark.parametrize("bad", [
    "DROP TABLE unity.gold.patient_summary",
    "DELETE FROM unity.gold.patient_summary",
    "INSERT INTO unity.gold.patient_summary VALUES (1)",
    "UPDATE unity.gold.patient_summary SET x = 1",
])
def test_non_select_rejected(bad: str) -> None:
    with pytest.raises(GuardError):
        guard_sql(bad, allowed_tables=_ALLOWED)


def test_multiple_statements_rejected() -> None:
    with pytest.raises(GuardError):
        guard_sql(
            "SELECT 1 FROM unity.gold.patient_summary; DROP TABLE x",
            allowed_tables=_ALLOWED,
        )


def test_foreign_qualified_table_rejected() -> None:
    with pytest.raises(GuardError):
        guard_sql("SELECT * FROM unity.silver.clinical_encounters", allowed_tables=_ALLOWED)
