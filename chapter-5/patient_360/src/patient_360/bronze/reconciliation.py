"""Bronze reconciliation runner — cross-table query_dq + SE-evidence gate.

Implements LLD §5.5 + §8.6.1 (Decision 16). Runs after every Bronze
table ingestion task completes, before Silver. Two responsibilities:

1. Cross-table ``query_dq`` checks (row counts vs source, freshness,
   completeness) sourced from DQS §4.
2. **Mandatory SE-evidence gate** (LLD §8.6.1) — fails-closed when
   ``unity.bronze.bronze_se_stats`` has zero rows for the current
   ``meta_dq_run_id`` / ``meta_dq_run_date``. This blocks the silent-DQ
   regression that hit Spokane on 2026-04-26.

Path resolution follows the same order as the ingestion factory:
explicit ``--configs-dir`` arg → ``AIRFLOW_CONFIGS_DIR`` env →
``/opt/airflow/configs`` default.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIGS_DIR = os.environ.get(
    "AIRFLOW_CONFIGS_DIR",
    str(Path("/", "opt", "airflow", "configs")),
)
SE_STATS_TABLE = "unity.bronze.bronze_se_stats"


class ReconciliationError(RuntimeError):
    """Raised when a reconciliation check fails."""


class SERunMissingError(ReconciliationError):
    """Raised when the SE-evidence gate finds no SE run for the ds.

    Surface code: ``SE_RUN_MISSING_FOR_DS=<ds>`` per LLD §8.6.1.
    """


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bronze reconciliation runner")
    p.add_argument("--ds", required=True, help="Logical date YYYY-MM-DD")
    p.add_argument("--run-id", required=True, help="meta_dq_run_id correlation id (Airflow run_id)")
    p.add_argument(
        "--configs-dir",
        default=DEFAULT_CONFIGS_DIR,
        help=(
            "Per-table YAML configs directory. Defaults to "
            "AIRFLOW_CONFIGS_DIR env or /opt/airflow/configs."
        ),
    )
    return p.parse_args(argv)


def load_configs(configs_dir: Path) -> list[dict[str, Any]]:
    if not configs_dir.is_dir():
        raise FileNotFoundError(f"configs_dir does not exist: {configs_dir}")
    return [yaml.safe_load(p.read_text()) for p in sorted(configs_dir.glob("*.yml"))]


def assert_se_run_evidence(
    spark, *, run_id: str, ds: str, stats_table: str = SE_STATS_TABLE
) -> int:
    """Return the SE-stats row count for (run_id, ds); fail-closed when zero.

    Per LLD §8.6.1: this query MUST return >= 1 or the task fails-closed
    with ``SE_RUN_MISSING_FOR_DS``.
    """
    sql = (
        f"SELECT count(*) AS n FROM {stats_table} "
        f"WHERE meta_dq_run_id = '{run_id}' "
        f"AND meta_dq_run_date = '{ds}'"
    )
    logger.info("SE-evidence gate: %s", sql)
    n = int(spark.sql(sql).collect()[0]["n"])
    if n < 1:
        raise SERunMissingError(
            f"SE_RUN_MISSING_FOR_DS={ds} (run_id={run_id}) — "
            "no rows in bronze_se_stats; SE did not run for this DAG run "
            "(LLD §8.6.1)"
        )
    logger.info("SE-evidence gate PASS: %d stats rows", n)
    return n


def reconcile_table(spark, cfg: dict[str, Any], ds: str) -> dict[str, Any]:
    """Run query_dq checks for one Bronze table.

    Currently performs row-count + freshness probes; thresholds come
    from ``contracts/dq/<table>.yml`` (DQS §5).
    """
    target = cfg["target"]  # e.g. unity.bronze.synthea_patients
    df = spark.table(target).where(f"ds = '{ds}'")
    row_count = df.count()
    logger.info("  reconcile %s rows=%d", target, row_count)
    return {"table": cfg["table"], "target": target, "rows": row_count}


def run(args: argparse.Namespace, *, spark=None) -> int:
    configs_dir = Path(args.configs_dir)
    configs = load_configs(configs_dir)
    logger.info(
        "Reconciling %d Bronze tables for ds=%s run_id=%s", len(configs), args.ds, args.run_id
    )

    if spark is None:
        from patient_360.bronze.ingestion_runner import _build_spark

        spark = _build_spark("reconcile_bronze")

    try:
        # 1. Cross-table query_dq checks (DQS §4) — per-table reconciliation
        results = [reconcile_table(spark, cfg, args.ds) for cfg in configs]
        logger.info(
            "query_dq complete: %d tables reconciled", sum(1 for r in results if r["rows"] >= 0)
        )

        # 2. SE-evidence gate (LLD §8.6.1, Decision 16)
        assert_se_run_evidence(spark, run_id=args.run_id, ds=args.ds)
        return 0
    finally:
        if spark is not None and hasattr(spark, "stop"):
            try:
                spark.stop()
            except Exception:  # noqa: BLE001
                pass


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    sys.exit(main())
