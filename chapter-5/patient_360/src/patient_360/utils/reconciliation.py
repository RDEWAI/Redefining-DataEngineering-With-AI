"""Reconciliation runner — SE run-evidence + cross-table query_dq.

LLD references: §2.3 (`reconciliation.py` interface contract), §5.5
(Reconciliation Tasks), §8.6 + §8.6.1 (SE-RUN-EVIDENCE — the gate that
proves SE actually ran), §13 Decision 14 (single-state fail-closed).

The reconciliation runner has two responsibilities:

1. **SE run-evidence** (this story, AC6) — confirm Spark Expectations
   actually wrote stats for ``run_id``. Zero stats rows means a silent
   skip; the pipeline must fail closed (LLD §8.6 / §13 Decision 14).
2. Cross-table ``query_dq`` checks per LLD §5.5 — row count
   reconciliation, freshness, completeness. These are sketched here and
   filled in by downstream stories.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import SparkSession

logger = logging.getLogger(__name__)

# LLD §8.6 + se_runner.SE_STATS_TABLE — single source of truth for the
# managed Delta table SE writes per-run aggregates into.
SE_STATS_TABLE = "bronze_se_stats"

# Default configs dir resolution mirrors the AIRFLOW_CONFIGS_DIR pattern
# used by ingestion_factory. Never hardcode the relative path.
DEFAULT_CONFIGS_DIR = os.environ.get("AIRFLOW_CONFIGS_DIR", "/opt/airflow/configs")


class ReconciliationError(RuntimeError):
    """Raised when a reconciliation gate fails closed."""


@dataclass(frozen=True)
class SERunEvidence:
    """Result of the LLD §8.6.1 SE-RUN-EVIDENCE check."""

    run_id: str
    stats_row_count: int

    @property
    def passed(self) -> bool:
        return self.stats_row_count > 0


def check_se_run_evidence(
    spark: "SparkSession",
    *,
    run_id: str,
    stats_table: str = SE_STATS_TABLE,
) -> SERunEvidence:
    """Verify SE wrote at least one stats row for ``run_id``.

    Queries ``stats_table`` filtered by ``meta_dq_run_id = run_id`` and
    fails closed when the count is zero (LLD §8.6.1). A zero count means
    SE did not run — either ``se_runner.py`` was unavailable (caught by
    STORY-01-009's import gate) or the writer silently no-op'd. Either
    way the pipeline must abort before Silver consumers see un-validated
    Bronze data.

    Parameters
    ----------
    spark:
        Active SparkSession; the catalog must already know
        ``stats_table``.
    run_id:
        The pipeline run identifier; matched against the SE stats column
        ``meta_dq_run_id``.
    stats_table:
        Override for the stats Delta table name. Defaults to
        :data:`SE_STATS_TABLE`.

    Returns
    -------
    SERunEvidence
        Carries the matched row count.

    Raises
    ------
    ReconciliationError
        When zero stats rows match ``run_id`` (fail-closed gate).
    """
    df = spark.table(stats_table).where(f"meta_dq_run_id = '{run_id}'")
    count = df.count()
    evidence = SERunEvidence(run_id=run_id, stats_row_count=count)
    if not evidence.passed:
        logger.error(
            "SE-RUN-EVIDENCE FAIL: zero rows in %s for meta_dq_run_id=%s — "
            "DQ did not run; failing closed.",
            stats_table,
            run_id,
        )
        raise ReconciliationError(
            f"SE-RUN-EVIDENCE: no stats rows for run_id={run_id} in {stats_table}"
        )
    logger.info(
        "SE-RUN-EVIDENCE OK: %d stats rows for run_id=%s", count, run_id
    )
    return evidence


def load_configs(configs_dir: Path) -> list[dict]:
    """Load every ``*.yml`` config under ``configs_dir`` for §5.5 checks."""
    if not configs_dir.is_dir():
        raise FileNotFoundError(
            f"configs_dir does not exist: {configs_dir}. Set AIRFLOW_CONFIGS_DIR "
            "or pass --configs-dir."
        )
    configs: list[dict] = []
    for yml in sorted(configs_dir.glob("*.yml")):
        configs.append(yaml.safe_load(yml.read_text()))
    return configs


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bronze/Silver/Gold reconciliation runner")
    p.add_argument("--ds", required=True, help="Logical date YYYY-MM-DD")
    p.add_argument("--run-id", required=True, help="Pipeline run identifier")
    p.add_argument(
        "--configs-dir",
        default=DEFAULT_CONFIGS_DIR,
        help=(
            "Directory containing per-table YAML configs. Defaults to "
            "AIRFLOW_CONFIGS_DIR or /opt/airflow/configs."
        ),
    )
    p.add_argument(
        "--layer", default="bronze", choices=["bronze", "silver", "gold"]
    )
    p.add_argument(
        "--stats-table",
        default=SE_STATS_TABLE,
        help="SE stats Delta table name (LLD §8.6.1).",
    )
    return p.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    """Entry point for SparkSubmit invocation of the reconciliation task."""
    from pyspark.sql import SparkSession  # imported here to avoid Spark dep at import

    configs_dir = Path(args.configs_dir)
    configs = load_configs(configs_dir)
    logger.info(
        "Reconciling %d %s tables for ds=%s run_id=%s",
        len(configs),
        args.layer,
        args.ds,
        args.run_id,
    )
    spark = SparkSession.builder.appName(f"reconcile_{args.layer}").getOrCreate()
    try:
        # LLD §8.6.1 — gate ahead of any cross-table checks. If SE didn't
        # land stats for this run, none of the §5.5 checks are meaningful.
        check_se_run_evidence(
            spark, run_id=args.run_id, stats_table=args.stats_table
        )

        for cfg in configs:
            target = f"unity.{args.layer}.{cfg['table']}"
            count = spark.table(target).where(f"ds = '{args.ds}'").count()
            logger.info("  %s rows=%d", target, count)
            # LLD §5.5 cross-table reconciliation lives here — populated by
            # downstream stories. Intentionally minimal in this story.
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":  # pragma: no cover - CLI entry
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    sys.exit(run(parse_args()))


__all__ = [
    "ReconciliationError",
    "SERunEvidence",
    "SE_STATS_TABLE",
    "check_se_run_evidence",
    "load_configs",
    "parse_args",
    "run",
]
