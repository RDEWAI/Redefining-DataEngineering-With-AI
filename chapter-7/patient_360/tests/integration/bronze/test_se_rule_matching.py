"""STORY-02-010 AC5 — SE rule-matching & physical drop integration smoke.

Proves the LLD §2.3 (v1.17) "SE rule-matching & isolation contract" fix in
:func:`patient_360.utils.se_runner.run_dq` actually executes inline DQ:

1. **SE selects > 0 rules.** With the corrected identifier wiring
   (``product_id`` from the rules YAML, ``target_table`` from
   ``dq_env.<ENV>.table_name``), Spark Expectations matches the per-table rule
   set instead of silently selecting zero rules (the §13 Decision 16 silent-DQ
   no-op). We assert SE wrote >= 1 stats row for the run — empty stats means SE
   matched nothing.
2. **A ``row_dq`` ``drop`` rule physically removes the offending rows.** We feed
   one valid row and one rule-violating row through ``run_dq`` and assert the
   validated DataFrame drops the bad row.

This is a self-contained local-Spark smoke (no live Airflow/UC/Marquez stack):
it builds its own rules YAML with a known ``drop`` rule so the assertion is
independent of the shipped ``dq_rules/`` content (which is regenerated
separately). Marked ``integration`` because it spins up a real SparkSession with
Delta + Spark Expectations; skipped when ``pyspark`` / ``spark_expectations`` /
``delta`` are unavailable.
"""

from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path

import pytest

pytest.importorskip("pyspark", reason="pyspark not installed")
if importlib.util.find_spec("spark_expectations") is None:  # pragma: no cover
    pytest.skip("spark_expectations not installed", allow_module_level=True)

# `local_spark` opts this module out of the live-stack HTTP probe in
# tests/integration/conftest.py — it is a self-contained local-Spark smoke.
pytestmark = [pytest.mark.integration, pytest.mark.local_spark]


@pytest.fixture(scope="module")
def spark(tmp_path_factory):
    """Local SparkSession with Delta + a temp warehouse (no Unity Catalog)."""
    from pyspark.sql import SparkSession

    delta = pytest.importorskip("delta", reason="delta-spark not installed")

    warehouse = tmp_path_factory.mktemp("se-match-warehouse")
    builder = (
        SparkSession.builder.master("local[1]")
        .appName("se-rule-matching-smoke")
        .config("spark.sql.warehouse.dir", str(warehouse))
        .config(
            "spark.sql.extensions",
            "io.delta.sql.DeltaSparkSessionExtension",
        )
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
    )
    spark = delta.configure_spark_with_delta_pip(builder).getOrCreate()
    yield spark
    spark.stop()


# A rules YAML whose DEV env carries a BARE table_name (the value
# `generate-se-rules` now emits) and one row_dq rule with action_if_failed:
# drop. The product_id is intentionally DIFFERENT from the table param name so
# the test also proves run_dq reads product_id from the YAML (not the table arg).
_RULES_TEMPLATE = """\
product_id: patient-360
dq_env:
  DEV:
    table_name: {table}
    action_if_failed: drop
    enable_for_source_dq_validation: true
    enable_for_target_dq_validation: true
    is_active: true
    enable_error_drop_alert: false
    error_drop_threshold: 0
    priority: high
rules:
- rule: DQ_SMOKE_DROP_PATIENT_ID
  rule_type: row_dq
  column_name: patient_id
  expectation: patient_id IS NOT NULL
  action_if_failed: drop
  tag: field_validation
  description: drop rows with a null patient_id
  enable_for_source_dq_validation: false
  enable_for_target_dq_validation: true
  is_active: true
  enable_error_drop_alert: false
  error_drop_threshold: 0
  query_dq_delimiter: '@'
  enable_querydq_custom_output: false
  priority: high
"""


def _write_rules(tmp_path: Path, table: str) -> Path:
    """Write a per-test rules YAML. The ``table`` name is unique per test so
    SE's external error table (``<table>_error``) never collides across the
    module-scoped SparkSession."""
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / f"{table}.yml").write_text(_RULES_TEMPLATE.format(table=table))
    return rules_dir


def test_se_selects_rules_and_drop_removes_rows(spark, tmp_path, monkeypatch):
    """AC5 — SE evaluates > 0 rules and a row_dq drop rule physically drops
    the offending row from the validated DataFrame."""
    from patient_360.utils import se_runner

    table = "se_match_drop"
    rules_dir = _write_rules(tmp_path, table)
    # UC 0.5.0 managed SE audit tables (LLD §2.3 item 3). No live UC server in
    # this local smoke, so qualify the SE target into the local DeltaCatalog
    # (`spark_catalog`) and pre-create the `bronze` schema so SE's managed
    # `saveAsTable` for `<target>_stats` / `<target>_error` resolves.
    monkeypatch.setenv("SE_UC_CATALOG", "spark_catalog")
    monkeypatch.setenv("SE_UC_BRONZE_SCHEMA", "bronze")
    spark.sql("CREATE SCHEMA IF NOT EXISTS spark_catalog.bronze")

    now = datetime.utcnow()
    # One valid row + one rule-violating row (null patient_id).
    df = spark.createDataFrame(
        [
            ("p-good", now, "batch-0001"),
            (None, now, "batch-0001"),
        ],
        schema="patient_id string, _ingested_at timestamp, _source_batch_id string",
    )
    assert df.count() == 2

    validated = se_runner.run_dq(
        df,
        table=table,
        env="DEV",
        dq_rules_dir=rules_dir,
    )

    rows = validated.collect()
    pids = {r["patient_id"] for r in rows}
    # The drop rule physically removed the null-patient_id row.
    assert None not in pids, (
        "row_dq drop rule did not remove the offending row — SE either "
        "matched zero rules (silent no-op) or the drop action did not apply"
    )
    assert "p-good" in pids
    assert len(rows) == 1

    # SE selected > 0 rules → it wrote >= 1 stats row to the per-table MANAGED
    # stats UC table `<catalog>.bronze.<table>_stats` (LLD §2.3 item 3 v1.20).
    stats_fqn = f"spark_catalog.bronze.{table}_stats"
    assert spark.catalog.tableExists(stats_fqn), (
        f"SE did not create the managed stats table {stats_fqn} — the rule "
        "set matched zero rules (LLD §13 Decision 16 silent-DQ no-op)"
    )
    assert spark.table(stats_fqn).count() >= 1, (
        "SE wrote no stats rows — the rule set matched zero rules "
        "(LLD §13 Decision 16 silent-DQ no-op)"
    )


def test_se_stats_error_tables_are_per_table_managed(spark, tmp_path, monkeypatch):
    """AC4 — the SE stats AND error tables are per-table MANAGED UC tables
    addressed by 3-part FQN (`<catalog>.bronze.<table>_stats` /
    `_error`), isolated from other tables. The error table is now ENABLED (UC
    0.5.0 / §13 Decision 12 corrected) and the row_dq `drop` removes failing
    rows AND persists them to the managed `_error` table."""
    from patient_360.utils import se_runner

    table = "se_match_managed"
    rules_dir = _write_rules(tmp_path, table)
    monkeypatch.setenv("SE_UC_CATALOG", "spark_catalog")
    monkeypatch.setenv("SE_UC_BRONZE_SCHEMA", "bronze")
    spark.sql("CREATE SCHEMA IF NOT EXISTS spark_catalog.bronze")

    now = datetime.utcnow()
    # Include a violating row so SE's drop action fires.
    df = spark.createDataFrame(
        [("p-good", now, "batch-0001"), (None, now, "batch-0001")],
        schema="patient_id string, _ingested_at timestamp, _source_batch_id string",
    )
    se_runner.run_dq(df, table=table, env="DEV", dq_rules_dir=rules_dir)

    stats_fqn = f"spark_catalog.bronze.{table}_stats"
    error_fqn = f"spark_catalog.bronze.{table}_error"
    # Per-table MANAGED stats table exists.
    assert spark.catalog.tableExists(stats_fqn), (
        f"managed per-table stats table missing: {stats_fqn}"
    )
    # The managed _error table is created (error table re-enabled on UC 0.5.0)
    # and captures the dropped null-patient_id row.
    assert spark.catalog.tableExists(error_fqn), (
        f"managed per-table error table missing: {error_fqn} "
        "(se.enable.error.table should be True on UC 0.5.0)"
    )
    assert spark.table(error_fqn).count() >= 1, (
        "managed _error table has no rejected rows — the row_dq drop did not "
        "persist the offending row"
    )
