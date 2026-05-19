"""Integration tests for :mod:`patient_360.utils.reconciliation` (STORY-01-010).

Exercises LLD §8.6.1 — the SE-RUN-EVIDENCE gate. Backed by a real
SparkSession + temp Delta warehouse, so it is marked ``integration`` and
skipped when PySpark / Delta are not installed.

Two scenarios:

* ``test_se_run_evidence_passes_when_stats_present`` — stats Delta table
  has rows for ``run_id`` → :func:`check_se_run_evidence` returns and the
  reconciliation pipeline continues.
* ``test_se_run_evidence_fails_closed_when_empty`` — stats table is empty
  for ``run_id`` → :class:`ReconciliationError` is raised. The pipeline
  MUST fail closed (LLD §13 Decision 14).
"""

from __future__ import annotations

import pytest

pyspark = pytest.importorskip("pyspark")  # noqa: F401 — skip when Spark missing
delta = pytest.importorskip("delta")  # noqa: F401 — skip when Delta missing

from patient_360.utils.reconciliation import (  # noqa: E402
    ReconciliationError,
    SE_STATS_TABLE,
    check_se_run_evidence,
)

pytestmark = pytest.mark.integration


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
        .config(
            "spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension"
        )
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
def stats_table(spark):
    """Create (or recreate) the SE stats Delta table for the test session."""
    spark.sql(f"DROP TABLE IF EXISTS {SE_STATS_TABLE}")
    spark.sql(
        f"""
        CREATE TABLE {SE_STATS_TABLE} (
            meta_dq_run_id STRING,
            product_id STRING,
            row_count BIGINT
        ) USING DELTA
        """
    )
    yield SE_STATS_TABLE
    spark.sql(f"DROP TABLE IF EXISTS {SE_STATS_TABLE}")


def test_se_run_evidence_passes_when_stats_present(spark, stats_table):
    run_id = "run-2026-05-11-001"
    spark.sql(
        f"INSERT INTO {stats_table} VALUES "
        f"('{run_id}', 'patients', 5767), "
        f"('{run_id}', 'encounters', 340532)"
    )

    evidence = check_se_run_evidence(spark, run_id=run_id)

    assert evidence.passed is True
    assert evidence.stats_row_count == 2
    assert evidence.run_id == run_id


def test_se_run_evidence_fails_closed_when_empty(spark, stats_table):
    """LLD §13 Decision 14 — zero rows means SE never ran. Fail closed."""
    run_id = "run-that-never-happened"

    with pytest.raises(ReconciliationError) as exc_info:
        check_se_run_evidence(spark, run_id=run_id)

    assert "SE-RUN-EVIDENCE" in str(exc_info.value)
    assert run_id in str(exc_info.value)
