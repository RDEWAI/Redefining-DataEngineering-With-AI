"""Unit tests for :mod:`patient_360.bronze.reconciliation`.

Covers the LLD §8.6.1 v1.20 / §2.3 item 3 / §13 Decision 12 (corrected)
per-table MANAGED SE-stats UC-table SE-RUN-EVIDENCE contract WITHOUT a live
Spark session — a stubbed ``spark`` object records the SQL it is handed so the
test can assert the query shape (3-part managed FQN ``unity.bronze.<t>_stats``,
``meta_dq_run_date`` keyed on the SE wall-clock RUN DATE — not the data ds, so
backfill/replay no longer false-fails — NO ``meta_dq_run_id`` predicate) and
the fail-closed behaviour. ``spark.catalog.tableExists`` gates absent tables.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from patient_360.bronze import reconciliation as recon

_ENV = "DEV"


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


class _FakeCatalog:
    def __init__(self, existing: set[str]):
        self._existing = existing

    def tableExists(self, fqn: str) -> bool:  # noqa: N802 — Spark API name
        return fqn in self._existing


class _FakeSpark:
    """Records every SQL string; returns a per-table row count map.

    ``counts_by_substr`` maps a substring of the managed FQN (e.g.
    ``patients_stats``) to the row count returned for any query containing it.
    ``existing`` is the set of FQNs for which ``catalog.tableExists`` is True.
    """

    def __init__(self, counts_by_substr: dict[str, int], existing: set[str]):
        self._counts = counts_by_substr
        self.queries: list[str] = []
        self.catalog = _FakeCatalog(existing)

    def sql(self, q: str):
        self.queries.append(q)
        for substr, n in self._counts.items():
            if substr in q:
                return _FakeResult(n)
        return _FakeResult(0)


def _fqn(table: str) -> str:
    return f"unity.bronze.{table}_stats"


def test_list_layer_tables_reads_configs(tmp_path):
    cfg = tmp_path / "configs"
    cfg.mkdir()
    (cfg / "patients.yml").write_text("table: patients\n")
    (cfg / "encounters.yml").write_text("table: encounters\n")
    (cfg / "no_table_key.yml").write_text("source: foo\n")  # falls back to stem

    tables = recon.list_layer_tables(cfg)

    assert tables == ["encounters", "no_table_key", "patients"]


def test_se_stats_fqn_qualifies_and_passes_through(monkeypatch):
    monkeypatch.delenv("SE_UC_CATALOG", raising=False)
    monkeypatch.delenv("SE_UC_BRONZE_SCHEMA", raising=False)
    assert recon._se_stats_fqn("patients") == "unity.bronze.patients_stats"
    # already-qualified FQN just gets the suffix
    assert recon._se_stats_fqn("unity.bronze.patients") == "unity.bronze.patients_stats"


def test_assert_se_evidence_passes_and_query_shape():
    ds = "2026-05-11"
    existing = {_fqn("patients"), _fqn("encounters")}
    spark = _FakeSpark({"patients_stats": 2, "encounters_stats": 1}, existing=existing)

    n = recon.assert_se_evidence(
        spark,
        meta_dq_run_id="20260511T000000",
        ds=ds,
        env=_ENV,
        tables=["patients", "encounters"],
    )

    assert n == 3
    # Query shape: 3-part managed FQN + meta_dq_run_date keyed on the SE
    # wall-clock RUN DATE (current UTC date), NOT the data ds. Filtering on ds
    # false-failed backfill/replay of a past ds (2026-06-20 fix).
    run_date = datetime.now(UTC).strftime("%Y-%m-%d")
    joined = "\n".join(spark.queries)
    assert "unity.bronze.patients_stats" in joined
    assert "delta.`" not in joined  # no path-table syntax anymore
    assert f"meta_dq_run_date = '{run_date}'" in joined
    assert f"meta_dq_run_date = '{ds}'" not in joined  # NOT keyed on ds
    assert "meta_dq_run_id" not in joined  # SE owns run_id; gate cannot key on it


def test_assert_se_evidence_skips_absent_tables():
    ds = "2026-05-12"
    existing = {_fqn("patients")}  # only this one exists
    spark = _FakeSpark({"patients_stats": 1}, existing=existing)

    n = recon.assert_se_evidence(
        spark,
        meta_dq_run_id="run",
        ds=ds,
        env=_ENV,
        tables=["patients", "encounters"],  # encounters table absent
    )

    assert n == 1
    # Only the existing table was queried.
    assert len(spark.queries) == 1
    assert "unity.bronze.patients_stats" in spark.queries[0]


def test_assert_se_evidence_fails_closed_with_marker():
    ds = "2026-05-13"
    existing = {_fqn("patients")}
    spark = _FakeSpark({"patients_stats": 0}, existing=existing)  # zero rows

    with pytest.raises(recon.SEEvidenceMissingError) as exc:
        recon.assert_se_evidence(
            spark,
            meta_dq_run_id="run",
            ds=ds,
            env=_ENV,
            tables=["patients"],
        )

    assert f"SE_RUN_MISSING_FOR_DS={ds}" in str(exc.value)
