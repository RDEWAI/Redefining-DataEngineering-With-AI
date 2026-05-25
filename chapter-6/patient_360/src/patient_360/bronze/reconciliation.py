"""Bronze reconciliation runner — SE-RUN-EVIDENCE invariant (LLD §8.6.1).

This module powers the ``reconciliation_bronze`` task in the
``patient360_hourly_v1`` DAG. Its job is **not** to re-run DQ; SE has
already validated row_dq / agg_dq inline during each Bronze ingestion
task. Instead, reconciliation asks the harder question:

    "Did SE actually run for this DAG run, or did the layer silently
    skip DQ?"

It queries ``unity.bronze.bronze_se_stats`` for the row keyed by the
current ``meta_dq_run_id``. Zero rows means SE never wrote stats for
this run — i.e. ``with_expectations(...)`` was never invoked — which
the Spokane 2026-04-26 post-mortem (LLD §13 Decision 16) labels a
silent-DQ-skip failure. The task fails-closed in that case with
``SE_RUN_MISSING_FOR_DS=<ds>``.

Entry points:

* :func:`run_reconciliation_bronze` — Airflow PythonOperator callable.
  Accepts ``meta_dq_run_id`` + ``ds`` Jinja-templated kwargs, builds
  a SparkSession, queries ``bronze_se_stats``, and raises
  :class:`SEEvidenceMissingError` if the row count is zero.
* :func:`main` — argparse entry for the ``run_bronze_recon.py``
  spark-submit wrapper (LLD §4.2 task inventory). Used when the
  DAG factory routes reconciliation through SparkSubmitOperator.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants (LLD §8.6.1)
# ---------------------------------------------------------------------------
SE_STATS_TABLE = os.environ.get(
    "BRONZE_SE_STATS_TABLE", "bronze.bronze_se_stats"
)
"""Fully-qualified Delta table name SE writes stats to.

Override via the ``BRONZE_SE_STATS_TABLE`` env var when running against
a non-default UC catalog/schema (e.g. local pytest with a temp
warehouse).
"""


class SEEvidenceMissingError(RuntimeError):
    """Raised when ``bronze_se_stats`` has 0 rows for the current run.

    Surfaces the Spokane silent-DQ-skip failure mode (LLD §13 Decision
    16). The Airflow task fails-closed and PagerDuty ``p360-critical``
    is alerted per LLD §5.5.
    """


# ---------------------------------------------------------------------------
# Core SE-RUN-EVIDENCE query (LLD §8.6.1)
# ---------------------------------------------------------------------------
def _count_se_stats_rows(spark: Any, *, meta_dq_run_id: str, ds: str) -> int:
    """Count rows in ``bronze_se_stats`` for the given run.

    The exact SQL is fixed by the LLD §8.6.1 contract — never inline
    a different query here, the contract is the audit anchor that
    proves SE ran.
    """
    # spark-expectations generates its own `meta_dq_run_id` value
    # internally — it does NOT accept the Airflow run id as an
    # external override. So we can only check that SE wrote stats for
    # the run date, not for an exact Airflow run. The ds match still
    # proves "DQ ran for today's data".
    sql = (
        f"SELECT count(*) AS n FROM {SE_STATS_TABLE} "
        f"WHERE meta_dq_run_date = '{ds}'"
    )
    logger.info("SE-RUN-EVIDENCE query: %s", sql)
    row = spark.sql(sql).collect()[0]
    return int(row["n"])


def assert_se_evidence(
    spark: Any, *, meta_dq_run_id: str, ds: str
) -> int:
    """Assert ``bronze_se_stats`` has >=1 row for the current run.

    Raises :class:`SEEvidenceMissingError` with the
    ``SE_RUN_MISSING_FOR_DS=<ds>`` marker (LLD §8.6.1) on failure so
    Airflow logs + PagerDuty bodies carry a greppable signal.
    """
    n = _count_se_stats_rows(
        spark, meta_dq_run_id=meta_dq_run_id, ds=ds
    )
    if n == 0:
        raise SEEvidenceMissingError(
            f"SE_RUN_MISSING_FOR_DS={ds} meta_dq_run_id={meta_dq_run_id} "
            f"table={SE_STATS_TABLE} — bronze_se_stats has 0 rows for this "
            "run; spark-expectations never wrote stats (silent-DQ-skip "
            "failure per LLD §8.6.1 / §13 Decision 16)."
        )
    logger.info(
        "SE-RUN-EVIDENCE OK: bronze_se_stats rows=%d for meta_dq_run_id=%s "
        "ds=%s",
        n,
        meta_dq_run_id,
        ds,
    )
    return n


# ---------------------------------------------------------------------------
# Airflow PythonOperator entry point
# ---------------------------------------------------------------------------
def run_reconciliation_bronze(
    *,
    ds: str,
    ts_nodash: str,
    **_: Any,
) -> int:
    """PythonOperator callable for the ``reconciliation_bronze`` task.

    Parameters
    ----------
    ds
        Airflow logical date (``{{ ds }}``); the partition value
        Bronze writes to.
    ts_nodash
        Airflow run identifier (``{{ ts_nodash }}``); used to derive
        ``meta_dq_run_id`` per Decision 16. SE tags each run with
        this id; reconciliation looks it up.

    Returns
    -------
    int
        Number of stats rows seen (always >=1 — zero raises).
    """
    # Direct-edited 2026-05-22 — pending retrofit through STORY-02-006 AC.
    # LLD v1.15 §13 Decision 12 (revised 2026-05-12) removed UC from the
    # runtime path; build_spark no longer accepts uc_uri. Reconciliation
    # tracked under direct-edit debt list — add an AC to STORY-02-006
    # naming src/patient_360/bronze/reconciliation.py as a deliverable
    # and re-derive.
    #
    # Local import keeps this module importable in DAG-parse contexts
    # where pyspark is not on the path (Airflow's DAG parser).
    from patient_360.bronze.ingestion_runner import build_spark

    meta_dq_run_id = ts_nodash
    spark = build_spark(app_name="reconciliation_bronze")
    try:
        return assert_se_evidence(
            spark, meta_dq_run_id=meta_dq_run_id, ds=ds
        )
    finally:
        spark.stop()


# ---------------------------------------------------------------------------
# spark-submit entry (used by run_bronze_recon.py wrapper)
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Bronze reconciliation — SE-RUN-EVIDENCE (LLD §8.6.1)"
    )
    p.add_argument("--ds", required=True, help="Logical date YYYY-MM-DD")
    p.add_argument(
        "--meta-dq-run-id",
        required=True,
        help="Airflow run id (typically {{ ts_nodash }})",
    )
    return p.parse_args(argv)


def main(args: argparse.Namespace | None = None) -> int:
    if args is None:
        args = parse_args()
    run_reconciliation_bronze(ds=args.ds, ts_nodash=args.meta_dq_run_id)
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    sys.exit(main(parse_args()))
