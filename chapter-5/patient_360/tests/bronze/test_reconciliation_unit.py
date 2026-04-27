"""Unit tests for the Bronze reconciliation runner (STORY-02-005).

Covers both the happy path and the SE-evidence fail-closed path
(LLD §8.6.1, Decision 16).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from patient_360.bronze import reconciliation as R


class _FakeRow(dict):
    def __getitem__(self, key):  # noqa: D401
        return super().__getitem__(key)


class _FakeDF:
    def __init__(self, rows):
        self._rows = rows

    def collect(self):
        return [_FakeRow(r) for r in self._rows]

    def where(self, _):
        return self

    def count(self):
        return len(self._rows)


class _FakeSpark:
    def __init__(self, *, stats_count: int = 1, table_rows: int = 5):
        self._stats_count = stats_count
        self._table_rows = table_rows
        self.last_sql: str | None = None
        self.stopped = False

    def sql(self, q):
        self.last_sql = q
        return _FakeDF([{"n": self._stats_count}])

    def table(self, _name):
        return _FakeDF([{} for _ in range(self._table_rows)])

    def stop(self):
        self.stopped = True


# --------------------------------------------------------------------------- #
# SE-evidence gate                                                            #
# --------------------------------------------------------------------------- #


def test_assert_se_run_evidence_pass():
    spark = _FakeSpark(stats_count=3)
    n = R.assert_se_run_evidence(spark, run_id="r1", ds="2026-04-27")
    assert n == 3
    assert "bronze_se_stats" in spark.last_sql
    assert "meta_dq_run_id" in spark.last_sql
    assert "meta_dq_run_date" in spark.last_sql


def test_assert_se_run_evidence_fail_closed():
    spark = _FakeSpark(stats_count=0)
    with pytest.raises(R.SERunMissingError, match="SE_RUN_MISSING_FOR_DS=2026-04-27"):
        R.assert_se_run_evidence(spark, run_id="r1", ds="2026-04-27")


def test_se_run_missing_is_reconciliation_error():
    """SERunMissingError is a subclass of ReconciliationError so callers
    can catch the broader class."""
    assert issubclass(R.SERunMissingError, R.ReconciliationError)


# --------------------------------------------------------------------------- #
# Run() orchestration                                                          #
# --------------------------------------------------------------------------- #


def test_load_configs_missing_dir(tmp_path):
    with pytest.raises(FileNotFoundError):
        R.load_configs(tmp_path / "nope")


def test_run_happy_path(monkeypatch, tmp_path):
    # write 1 minimal config
    (tmp_path / "patients.yml").write_text(
        "table: synthea_patients\ntarget: unity.bronze.synthea_patients\n"
    )
    spark = _FakeSpark(stats_count=2, table_rows=10)

    args = SimpleNamespace(ds="2026-04-27", run_id="r-1", configs_dir=str(tmp_path))
    rc = R.run(args, spark=spark)
    assert rc == 0
    assert spark.stopped


def test_run_fail_closed_path(tmp_path):
    (tmp_path / "patients.yml").write_text(
        "table: synthea_patients\ntarget: unity.bronze.synthea_patients\n"
    )
    spark = _FakeSpark(stats_count=0)
    args = SimpleNamespace(ds="2026-04-27", run_id="r-2", configs_dir=str(tmp_path))
    with pytest.raises(R.SERunMissingError):
        R.run(args, spark=spark)
