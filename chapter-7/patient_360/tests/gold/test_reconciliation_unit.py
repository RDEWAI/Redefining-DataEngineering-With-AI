"""Unit tests for :mod:`patient_360.gold.reconciliation` (STORY-05-006).

``reconciliation_gold`` reconciles ``unity.gold.*`` row counts against their
``unity.silver.*`` sources within the DQS §4/§5 tolerance, asserts
patient_summary completeness (= 5,767 current patients; NFR-4 / DQ-FLD-106),
and asserts allergy cross-field completeness (DQ-FLD-138). These tests exercise
the row-count + completeness contract and the fail-closed raise WITHOUT a live
Spark session — a stubbed ``spark`` returns per-FQN row counts (and a distinct
patient count + an allergy-violation count), and records the SQL/table calls it
is handed. Covers positive reconciliation, tolerance-breach fail, and
completeness-fail (patient + allergy) cases per the story ## Verification block.
"""

from __future__ import annotations

import pytest

from patient_360.gold import reconciliation as recon

_ENV = "DEV"
_DS = "2026-07-15"
_RUN = "20260715T000000"

# Verified DQS §4 baselines (DQ-STA-014..019): the "golden" happy-path counts.
_PATIENTS = recon.EXPECTED_PATIENT_COUNT  # 5767, current clinical_patients
_ENCOUNTERS = 340532


class _FakeRow:
    def __init__(self, n: int):
        self._n = n

    def __getitem__(self, key):
        assert key == "n"
        return self._n


class _FakeResult:
    def __init__(self, n: int):
        self._n = n

    def collect(self):
        return [_FakeRow(self._n)]


class _FakeFrame:
    """A frame for one FQN. ``count()`` honours the last ``where`` predicate via
    ``where_counts``; ``select(...).distinct().count()`` returns ``distinct``.
    """

    def __init__(self, base: int, *, where_counts: dict[str, int] | None = None, distinct: int | None = None):
        self._base = base
        self._where_counts = where_counts or {}
        self._distinct = distinct if distinct is not None else base
        self._pending = base
        self._distinct_mode = False

    def where(self, cond: str):
        self._pending = self._where_counts.get(cond, self._base)
        return self

    def select(self, *_cols):
        self._distinct_mode = True
        return self

    def distinct(self):
        return self

    def count(self) -> int:
        return self._distinct if self._distinct_mode else self._pending


class _FakeSpark:
    """Returns a fresh :class:`_FakeFrame` per FQN; ``sql`` returns the
    configured allergy-violation count for the violation query.
    """

    def __init__(self, frames: dict[str, dict], *, allergy_violations: int = 0):
        self._frames = frames
        self._allergy_violations = allergy_violations
        self.sql_queries: list[str] = []
        self.table_calls: list[str] = []

    def table(self, fqn: str) -> _FakeFrame:
        self.table_calls.append(fqn)
        spec = self._frames[fqn]
        return _FakeFrame(
            spec["base"],
            where_counts=spec.get("where_counts"),
            distinct=spec.get("distinct"),
        )

    def sql(self, q: str) -> _FakeResult:
        self.sql_queries.append(q)
        return _FakeResult(self._allergy_violations)


def _healthy_frames(
    *,
    gold_summary: int = _PATIENTS,
    silver_patients_current: int = _PATIENTS,
    gold_history: int = _ENCOUNTERS,
    silver_encounters: int = _ENCOUNTERS,
    gold_billing: int = _ENCOUNTERS,
    summary_distinct: int | None = None,
) -> dict[str, dict]:
    return {
        "unity.gold.patient_summary": {
            "base": gold_summary,
            "distinct": summary_distinct if summary_distinct is not None else gold_summary,
        },
        "unity.silver.clinical_patients": {
            "base": silver_patients_current,
            "where_counts": {"is_current = TRUE": silver_patients_current},
        },
        "unity.gold.patient_clinical_history": {"base": gold_history},
        "unity.silver.clinical_encounters": {"base": silver_encounters},
        "unity.gold.patient_billing_summary": {"base": gold_billing},
    }


# ---------------------------------------------------------------------------
# FQN helpers
# ---------------------------------------------------------------------------
def test_fqn_helpers_qualify_and_pass_through(monkeypatch):
    monkeypatch.delenv("SE_UC_CATALOG", raising=False)
    assert recon._silver_fqn("clinical_patients") == "unity.silver.clinical_patients"
    assert recon._gold_fqn("patient_summary") == "unity.gold.patient_summary"
    # already-qualified FQN passes through unchanged
    assert recon._gold_fqn("unity.gold.patient_summary") == "unity.gold.patient_summary"


# ---------------------------------------------------------------------------
# Positive reconciliation
# ---------------------------------------------------------------------------
def test_run_reconciliation_all_pass():
    spark = _FakeSpark(_healthy_frames(), allergy_violations=0)
    results = recon.run_reconciliation(spark, ds=_DS, meta_dq_run_id=_RUN, env=_ENV)
    # 3 row-count rules + patient completeness + allergy completeness
    assert len(results) == 5
    assert all(r.passed for r in results)
    # allergy check issued a size()-based cross-field violation query
    assert any("has_allergy" in q and "size(allergies)" in q for q in spark.sql_queries)


def test_row_count_within_tolerance_passes():
    # billing summary within ±5% of encounters passes (DQ-STA-019)
    frames = _healthy_frames(gold_billing=int(_ENCOUNTERS * 1.04))
    spark = _FakeSpark(frames)
    rule = recon.gold_row_count_rules()[2]  # DQ-STA-019 billing
    assert rule.rule_id == "DQ-STA-019"
    assert recon.check_row_count(spark, rule).passed


# ---------------------------------------------------------------------------
# Tolerance-breach fail
# ---------------------------------------------------------------------------
def test_row_count_tolerance_breach_fails_closed():
    # patient_clinical_history off by 10% vs clinical_encounters (>±0.1%)
    frames = _healthy_frames(gold_history=int(_ENCOUNTERS * 1.10))
    spark = _FakeSpark(frames)
    with pytest.raises(recon.GoldReconciliationError) as exc:
        recon.run_reconciliation(spark, ds=_DS, meta_dq_run_id=_RUN, env=_ENV)
    assert f"GOLD_RECON_FAILED_FOR_DS={_DS}" in str(exc.value)
    assert "DQ-REC-005" in str(exc.value)


def test_empty_silver_source_requires_empty_gold():
    # Silver source empty but Gold non-empty → fail closed (no fabricated rows)
    rule = recon.RowCountRule("DQ-REC-005", "clinical_encounters", "patient_clinical_history")
    frames = {
        "unity.silver.clinical_encounters": {"base": 0},
        "unity.gold.patient_clinical_history": {"base": 42},
    }
    spark = _FakeSpark(frames)
    assert recon.check_row_count(spark, rule).passed is False


# ---------------------------------------------------------------------------
# Completeness fail — patient (NFR-4 / DQ-FLD-106)
# ---------------------------------------------------------------------------
def test_patient_completeness_grain_equality_fail():
    # gold summary != current clinical_patients → completeness fails
    frames = _healthy_frames(gold_summary=_PATIENTS - 50, summary_distinct=_PATIENTS - 50)
    spark = _FakeSpark(frames)
    result = recon.check_patient_completeness(spark)
    assert result.passed is False
    with pytest.raises(recon.GoldReconciliationError) as exc:
        recon.run_reconciliation(spark, ds=_DS, meta_dq_run_id=_RUN, env=_ENV)
    assert "PATIENT-COMPLETENESS" in str(exc.value)


def test_patient_completeness_grain_uniqueness_fail():
    # distinct patient_id < row count → duplicate patients (DQ-FLD-106 breach)
    frames = _healthy_frames(summary_distinct=_PATIENTS - 5)
    spark = _FakeSpark(frames)
    assert recon.check_patient_completeness(spark).passed is False


def test_patient_completeness_happy_path():
    spark = _FakeSpark(_healthy_frames())
    assert recon.check_patient_completeness(spark).passed


# ---------------------------------------------------------------------------
# Completeness fail — allergy (DQ-FLD-138)
# ---------------------------------------------------------------------------
def test_allergy_completeness_violation_fails_closed():
    spark = _FakeSpark(_healthy_frames(), allergy_violations=3)
    result = recon.check_allergy_completeness(spark)
    assert result.passed is False
    assert "violations: 3" in result.detail
    with pytest.raises(recon.GoldReconciliationError) as exc:
        recon.run_reconciliation(spark, ds=_DS, meta_dq_run_id=_RUN, env=_ENV)
    assert "DQ-FLD-138" in str(exc.value)


def test_allergy_completeness_clean_passes():
    spark = _FakeSpark(_healthy_frames(), allergy_violations=0)
    assert recon.check_allergy_completeness(spark).passed


# ---------------------------------------------------------------------------
# main(args) runner contract mirrors bronze
# ---------------------------------------------------------------------------
def test_parse_args_contract():
    args = recon.parse_args(["--ds", _DS, "--meta-dq-run-id", _RUN])
    assert args.ds == _DS
    assert args.meta_dq_run_id == _RUN


def test_default_rule_set_targets_three_gold_tables():
    rules = recon.gold_row_count_rules()
    targets = {r.target for r in rules}
    assert targets == {
        "patient_summary",
        "patient_clinical_history",
        "patient_billing_summary",
    }
