"""The rendered context block carries the facts the NL-to-SQL agent needs."""

from __future__ import annotations

import pytest

from patient_360.semantic import load_model, render_context


@pytest.fixture(scope="module")
def context() -> str:
    return render_context(load_model())


def test_all_tables_present(context: str) -> None:
    for table in (
        "unity.gold.patient_summary",
        "unity.gold.patient_clinical_history",
        "unity.gold.patient_billing_summary",
    ):
        assert table in context


def test_measure_sql_and_join_present(context: str) -> None:
    assert "COUNT(DISTINCT encounter_id)" in context
    # join graph arrow
    assert "-> patient_summary.`patient_id`" in context


def test_exact_literals_and_glossary_present(context: str) -> None:
    # coded values must reach the prompt so the agent filters correctly
    assert "M, S, D, W" in context
    assert "marital_status = 'M'" in context


def test_empty_columns_flagged(context: str) -> None:
    assert "[NO DATA IN CURRENT LOAD]" in context
    assert "[EMPTY IN CURRENT LOAD]" in context


def test_verified_query_sql_present(context: str) -> None:
    assert "WHERE patient_status = 'ALIVE'" in context
