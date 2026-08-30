"""Integration tests for :mod:`patient_360.utils.reconciliation`.

Exercises LLD §8.6.1 v1.18 — the SE-RUN-EVIDENCE gate against the
**per-table path-based** SE stats Delta tables
(``warehouse/{env}/_se/<table>/stats``) introduced by §2.3 v1.17 / §13
Decision 16. Backed by a real SparkSession + temp Delta warehouse, so it
is marked ``integration`` and skipped when PySpark / Delta are not
installed.

The gate filters the SE ``_stats`` table on ``meta_dq_run_date`` = the SE
**wall-clock run date** (the date reconciliation runs in the same DAG
execution), NOT the data ``ds`` — gating on ``ds`` false-failed backfill /
replay of a past ``ds`` (2026-06-20 fix). The passing tests therefore stamp
their stats with the CURRENT run date so the gate finds them; the fails-closed
test stamps a non-current date so the gate correctly finds 0 rows.

Scenarios:

* ``test_se_run_evidence_passes_when_stats_present`` — at least one
  per-table stats path has rows for the current run date →
  :func:`check_se_run_evidence` returns evidence aggregated across paths.
* ``test_se_run_evidence_skips_absent_paths`` — tables whose stats path
  does not exist are skipped, not treated as zero/failure.
* ``test_se_run_evidence_fails_closed_when_empty`` — no per-table stats
  path has any row for the current run date → :class:`ReconciliationError`
  is raised with the ``SE_RUN_MISSING_FOR_DS`` marker. The pipeline MUST
  fail closed (LLD §13 Decision 14/16).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

pyspark = pytest.importorskip("pyspark")  # noqa: F401 — skip when Spark missing
delta = pytest.importorskip("delta")  # noqa: F401 — skip when Delta missing

from patient_360.utils import reconciliation as _recon  # noqa: E402
from patient_360.utils.reconciliation import (  # noqa: E402
    ReconciliationError,
    check_se_run_evidence,
)

pytestmark = pytest.mark.integration

_ENV = "DEV"

# Every logical table any test in this suite writes managed SE-stats for.
# The fixture drops these before AND after each test so managed UC tables
# (which persist in the shared module-scoped Spark session) cannot leak
# across cases — e.g. ``encounters_stats`` from an earlier test must not
# inflate ``paths_checked`` in ``test_se_run_evidence_skips_absent_paths``.
_SUITE_TABLES = ("patients", "encounters")


@pytest.fixture(scope="module")
def spark(tmp_path_factory):
    """Build a Delta-aware local SparkSession with a clean warehouse."""
    from delta import configure_spark_with_delta_pip
    from pyspark.sql import SparkSession

    warehouse = tmp_path_factory.mktemp("warehouse")
    builder = (
        SparkSession.builder.appName("test_reconciliation_integration")
        .master("local[2]")
        .config("spark.sql.warehouse.dir", str(warehouse))
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
    )
    session = configure_spark_with_delta_pip(builder).getOrCreate()
    try:
        yield session
    finally:
        session.stop()


@pytest.fixture
def se_root(spark, monkeypatch):
    """Qualify the managed SE-stats FQNs into the local DeltaCatalog.

    The managed SE-stats tables are addressed by 3-part FQN
    ``unity.bronze.<table>_stats`` (LLD §8.6.1 v1.20). There is no live UC
    server here, so point the catalog/schema overrides at ``spark_catalog``
    and pre-create the ``bronze`` schema.
    """
    monkeypatch.setenv("SE_UC_CATALOG", "spark_catalog")
    monkeypatch.setenv("SE_UC_BRONZE_SCHEMA", "bronze")
    spark.sql("CREATE SCHEMA IF NOT EXISTS spark_catalog.bronze")

    def _drop_suite_stats() -> None:
        # Managed UC tables persist in the shared module-scoped Spark
        # session, so drop every suite table's stats FQN to isolate the test.
        for t in _SUITE_TABLES:
            spark.sql("DROP TABLE IF EXISTS " + _recon._se_stats_fqn(t))

    _drop_suite_stats()
    yield None
    _drop_suite_stats()


def _run_date() -> str:
    """The SE wall-clock run date the gate filters on (current UTC date).

    Mirrors the ``datetime.now(timezone.utc)`` the production gate computes, so
    stats stamped with this value are the ones the gate will actually match.
    """
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _write_stats(spark, env: str, table: str, run_dates: list[str]) -> None:
    """Create a per-table MANAGED SE-stats UC table the evidence gate reads.

    ``run_dates`` are stamped into the ``meta_dq_run_date`` column — the SE
    wall-clock run date the gate filters on (NOT the data ds).
    """
    from pyspark.sql import Row

    fqn = _recon._se_stats_fqn(table)
    rows = [Row(meta_dq_run_date=rd, product_id=table, row_count=1) for rd in run_dates]
    spark.createDataFrame(rows).write.format("delta").mode("overwrite").saveAsTable(fqn)


def test_se_run_evidence_passes_when_stats_present(spark, se_root):
    # ds is a PAST date (a backfill/replay); stats are stamped with the
    # CURRENT run date — the gate must find them regardless of ds.
    ds = "2026-05-11"
    run_date = _run_date()
    _write_stats(spark, _ENV, "patients", [run_date, run_date])
    _write_stats(spark, _ENV, "encounters", [run_date])

    evidence = check_se_run_evidence(spark, ds=ds, tables=["patients", "encounters"], env=_ENV)

    assert evidence.passed is True
    assert evidence.stats_row_count == 3
    assert evidence.paths_checked == 2
    assert evidence.ds == ds


def test_se_run_evidence_skips_absent_paths(spark, se_root):
    """Tables with no stats path yet are skipped, not failed."""
    ds = "2026-05-12"
    _write_stats(spark, _ENV, "patients", [_run_date()])
    # "encounters" path intentionally never created.

    evidence = check_se_run_evidence(spark, ds=ds, tables=["patients", "encounters"], env=_ENV)

    assert evidence.passed is True
    assert evidence.stats_row_count == 1
    assert evidence.paths_checked == 1  # only the existing path was queried


def test_se_run_evidence_fails_closed_when_empty(spark, se_root):
    """LLD §13 Decision 14/16 — zero rows means SE never ran. Fail closed."""
    ds = "2026-05-13"
    # Stats exist but only for a NON-current run date → zero matching rows
    # for today's run date, so the gate must fail closed.
    _write_stats(spark, _ENV, "patients", ["2026-01-01"])

    with pytest.raises(ReconciliationError) as exc_info:
        check_se_run_evidence(spark, ds=ds, tables=["patients"], env=_ENV)

    assert "SE_RUN_MISSING_FOR_DS" in str(exc_info.value)
    assert ds in str(exc_info.value)
