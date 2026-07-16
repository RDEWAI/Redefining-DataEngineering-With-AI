"""Unit tests for the Silver reconciliation gate (STORY-04-010).

``reconciliation_silver`` reuses :func:`patient_360.utils.reconciliation.
check_se_run_evidence` with the Silver layer's table list (LLD §5.5 /
§8.6.1 v1.20). These tests exercise the layer-parameterized, per-table
MANAGED SE-stats UC-table SE-RUN-EVIDENCE contract WITHOUT a live Spark
session — a stubbed ``spark`` object records the 3-part FQN identifiers it is
handed and returns a per-table row count. ``spark.catalog.tableExists`` gates
absent tables.
"""

from __future__ import annotations

import pytest

from patient_360.utils import reconciliation as recon

_ENV = "DEV"


class _FakeFrame:
    def __init__(self, n: int):
        self._n = n

    def where(self, _cond: str):
        return self

    def count(self) -> int:
        return self._n


class _FakeCatalog:
    def __init__(self, existing: set[str]):
        self._existing = existing

    def tableExists(self, fqn: str) -> bool:  # noqa: N802 — Spark API name
        return fqn in self._existing


class _FakeSpark:
    """Records table identifiers; returns per-table counts by substring."""

    def __init__(self, counts_by_substr: dict[str, int], existing: set[str]):
        self._counts = counts_by_substr
        self.tables: list[str] = []
        self.catalog = _FakeCatalog(existing)

    def table(self, ident: str):
        self.tables.append(ident)
        for substr, n in self._counts.items():
            if substr in ident:
                return _FakeFrame(n)
        return _FakeFrame(0)


def _fqn(table: str) -> str:
    return f"unity.bronze.{table}_stats"


def test_silver_evidence_passes_aggregates_across_tables():
    ds = "2026-05-11"
    existing = {_fqn("patients"), _fqn("encounters")}
    spark = _FakeSpark({"patients_stats": 4, "encounters_stats": 2}, existing=existing)

    evidence = recon.check_se_run_evidence(
        spark, ds=ds, tables=["patients", "encounters"], env=_ENV
    )

    assert evidence.passed is True
    assert evidence.stats_row_count == 6
    assert evidence.paths_checked == 2
    # 3-part managed FQN identifiers, never a path-table (delta.`...`) ident.
    assert all(ident.startswith("unity.bronze.") for ident in spark.tables)
    assert all(not ident.startswith("delta.`") for ident in spark.tables)


def test_silver_evidence_fails_closed_when_empty():
    ds = "2026-05-12"
    existing = {_fqn("patients")}
    spark = _FakeSpark({"patients_stats": 0}, existing=existing)

    with pytest.raises(recon.ReconciliationError) as exc:
        recon.check_se_run_evidence(spark, ds=ds, tables=["patients"], env=_ENV)

    assert f"SE_RUN_MISSING_FOR_DS={ds}" in str(exc.value)


# ---------------------------------------------------------------------------
# LLD §5.5 cross-table query_dq checks (row count, FK orphans, SCD2 sanity).
# A stubbed ``spark`` returns counts keyed by FQN substring (for ``.table``)
# and by SQL substring (for ``.sql``) so the checks run without live Spark.
# ---------------------------------------------------------------------------


class _QFrame:
    def __init__(self, n: int):
        self._n = n

    def where(self, _cond: str):
        return self

    def select(self, *_cols):
        return self

    def distinct(self):
        return self

    def count(self) -> int:
        return self._n


class _QSpark:
    """Returns counts keyed by table FQN and by SQL substring."""

    def __init__(self, table_counts: dict[str, int], sql_counts: dict[str, int] | None = None):
        self._table_counts = table_counts
        self._sql_counts = sql_counts or {}
        self.queries: list[str] = []

    def table(self, fqn: str):
        for substr, n in self._table_counts.items():
            if substr in fqn:
                return _QFrame(n)
        return _QFrame(0)

    def sql(self, q: str):
        self.queries.append(q)
        n = 0
        for substr, val in self._sql_counts.items():
            if substr in q:
                n = val
                break
        return _FakeSqlResult(n)


class _FakeSqlRow:
    def __init__(self, n: int):
        self._n = n

    def __getitem__(self, key):
        assert key == "n"
        return self._n


class _FakeSqlResult:
    def __init__(self, n: int):
        self._n = n

    def collect(self):
        return [_FakeSqlRow(self._n)]


def test_row_count_exact_match_passes():
    spark = _QSpark({"bronze.synthea_patients": 100, "silver.clinical_patients": 100})
    rule = recon.RowCountRule(
        "DQ-REC-002",
        "bronze.synthea_patients",
        "silver.clinical_patients",
        tolerance=0.0,
        target_filter="is_current = TRUE",
    )
    res = recon.check_row_count(spark, rule, ds="2026-05-11")
    assert res.passed is True
    assert res.rule_id == "DQ-REC-002"


def test_row_count_mismatch_fails():
    spark = _QSpark({"bronze.synthea_patients": 100, "silver.clinical_patients": 95})
    rule = recon.RowCountRule(
        "DQ-REC-002",
        "bronze.synthea_patients",
        "silver.clinical_patients",
        tolerance=0.0,
    )
    res = recon.check_row_count(spark, rule, ds="2026-05-11")
    assert res.passed is False


def test_fk_orphans_zero_passes():
    spark = _QSpark({}, sql_counts={"clinical_encounters": 0})
    rule = recon.FkOrphanRule(
        "DQ-REF-001",
        "silver.clinical_encounters",
        "patient_id",
        "silver.clinical_patients",
        "patient_id",
    )
    res = recon.check_fk_orphans(spark, rule)
    assert res.passed is True
    # query must use is_current parent filter (SCD2 dim) and NOT EXISTS shape.
    assert "is_current = TRUE" in spark.queries[0]
    assert "NOT EXISTS" in spark.queries[0]


def test_fk_orphans_nonzero_fails():
    spark = _QSpark({}, sql_counts={"clinical_encounters": 7})
    rule = recon.FkOrphanRule(
        "DQ-REF-001",
        "silver.clinical_encounters",
        "patient_id",
        "silver.clinical_patients",
        "patient_id",
    )
    res = recon.check_fk_orphans(spark, rule)
    assert res.passed is False
    assert "7" in res.detail


def test_scd2_versions_one_per_nk_passes():
    spark = _QSpark({"silver.reference_providers": 1080})
    rule = recon.Scd2VersionRule("DQ-FLD-185", "silver.reference_providers", "provider_id")
    res = recon.check_scd2_versions(spark, rule)
    assert res.passed is True


def test_run_query_dq_fails_closed_on_any_failure():
    spark = _QSpark(
        {"bronze.synthea_patients": 100, "silver.clinical_patients": 80},
        sql_counts={},
    )
    rc = [recon.RowCountRule("DQ-REC-002", "bronze.synthea_patients", "silver.clinical_patients")]
    with pytest.raises(recon.ReconciliationError) as exc:
        recon.run_query_dq(spark, ds="2026-05-11", row_count_rules=rc, fk_rules=[], scd2_rules=[])
    assert "DQ-REC-002" in str(exc.value)


def test_silver_query_dq_rules_default_set():
    row_count, fk, scd2 = recon.silver_query_dq_rules()
    assert any(r.rule_id == "DQ-REC-002" for r in row_count)
    assert len(fk) == 18  # DQ-REF-001..018
    assert len(scd2) == 3  # DQ-FLD-184..186
