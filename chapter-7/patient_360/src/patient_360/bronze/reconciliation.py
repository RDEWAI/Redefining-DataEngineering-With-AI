"""Bronze reconciliation runner — SE-RUN-EVIDENCE invariant (LLD §8.6.1).

updated: 2026-06-20 — LLD §8.6.1 v1.20 / §2.3 item 3 / §13 Decision 12
(corrected): **per-table MANAGED SE-stats UC tables**. The UC-0.4.0 per-table
path-based shape (``warehouse/{env}/_se/<table>/stats``) is RETIRED. On UC
0.5.0 ``se_runner`` writes SE stats as a per-table MANAGED ``catalogManaged``
Unity Catalog table addressed by the 3-part FQN ``unity.bronze.<table>_stats``
(a single shared stats table collides on each table's source schema, so the
per-table FQN derivation is mandatory). The evidence check **iterates the
layer's table list**, resolves each per-table managed stats FQN, skips tables
that do not yet exist, and counts ``meta_dq_run_date = '<run_date>'`` rows
across each existing per-table managed stats table, requiring the aggregate
total to be ``>= 1``.

updated: 2026-06-20 — SE-RUN-EVIDENCE date-filter fix (backfill/replay
false-fail). ``meta_dq_run_date`` in the managed SE ``_stats`` table is the
**wall-clock date spark-expectations actually ran**, NOT the data ``ds`` (the
managed stats table has no ``ds`` column). Gating on ``meta_dq_run_date =
'{ds}'`` only matched when the run happened on the same calendar day as ``ds``
(a normal scheduled hourly run) and FALSE-FAILED any backfill/replay of a past
``ds`` with ``SE_RUN_MISSING_FOR_DS`` — a silent-DQ-skip false alarm. The gate
now filters by the **SE run date** (= the date this reconciliation runs in the
same DAG execution), computed once as the current UTC date. ``ds`` is retained
in the error message + INFO logs for traceability only.

This module powers the ``reconciliation_bronze`` task in the
``patient360_hourly_v1`` DAG. Its job is **not** to re-run DQ; SE has
already validated row_dq / agg_dq inline during each Bronze ingestion
task. Instead, reconciliation asks the harder question:

    "Did SE actually run for this DAG run, or did the layer silently
    skip DQ?"

Zero rows across every per-table stats path means SE never wrote stats for
this run — i.e. ``with_expectations(...)`` was never invoked — which the
Spokane 2026-04-26 post-mortem (LLD §13 Decision 16) labels a silent-DQ-skip
failure. The task fails-closed in that case with ``SE_RUN_MISSING_FOR_DS=<ds>``.

Entry points:

* :func:`run_reconciliation_bronze` — Airflow PythonOperator callable.
  Accepts ``meta_dq_run_id`` + ``ds`` Jinja-templated kwargs, builds
  a SparkSession, iterates the per-table stats paths, and raises
  :class:`SEEvidenceMissingError` if the aggregate row count is zero.
* :func:`main` — argparse entry for the ``run_bronze_recon.py``
  spark-submit wrapper (LLD §4.2 task inventory). Used when the
  DAG factory routes reconciliation through SparkSubmitOperator.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


# Catalog + Bronze schema for the managed SE-stats FQN. Overridable via env
# vars (mirrors se_runner) so the warehouse name is never hardcoded.
SE_UC_CATALOG_ENV = "SE_UC_CATALOG"
SE_UC_BRONZE_SCHEMA_ENV = "SE_UC_BRONZE_SCHEMA"
_DEFAULT_SE_UC_CATALOG = "unity"
_DEFAULT_SE_UC_BRONZE_SCHEMA = "bronze"
SE_STATS_SUFFIX = "_stats"


def _se_stats_fqn(table: str) -> str:
    """Resolve the managed SE-stats UC table FQN (LLD §2.3 item 3 / §8.6.1
    v1.20 / §13 Decision 12 corrected): ``unity.bronze.<table>_stats``.

    The UC-0.4.0 per-table path-based shape is retired — SE now writes its
    stats as a MANAGED ``catalogManaged`` UC table addressed by a 3-part FQN.
    ``table`` may be a bare logical name (qualified here) or already an FQN.
    """
    if "." in table:
        return f"{table}{SE_STATS_SUFFIX}"
    catalog = os.environ.get(SE_UC_CATALOG_ENV, _DEFAULT_SE_UC_CATALOG)
    schema = os.environ.get(SE_UC_BRONZE_SCHEMA_ENV, _DEFAULT_SE_UC_BRONZE_SCHEMA)
    return f"{catalog}.{schema}.{table}{SE_STATS_SUFFIX}"


# ---------------------------------------------------------------------------
# Constants (LLD §8.6.1 v1.20)
# ---------------------------------------------------------------------------
# Layer whose per-table SE stats this runner audits. Bronze by default; the
# same module shape (and the layer-parameterized evidence helpers below) backs
# the Silver/Gold reconciliation tasks (LLD §5.5).
LAYER = "bronze"

# Runtime env flag (DEV | STAGING | PROD). Retained for log/error context; the
# managed SE-stats tables are env-agnostic FQNs (LLD §8.6.1 v1.20).
ENV_ENV = "PATIENT360_ENV"
DEFAULT_ENV = "DEV"

# Per-table YAML configs that enumerate the layer's table list. Mirrors the
# AIRFLOW_CONFIGS_DIR pattern used by ingestion_factory; never hardcode the
# relative path.
CONFIGS_DIR_ENV = "AIRFLOW_CONFIGS_DIR"
DEFAULT_CONFIGS_DIR = "/opt/airflow/configs"


class SEEvidenceMissingError(RuntimeError):
    """Raised when no per-table managed SE-stats table has rows for the run.

    Surfaces the Spokane silent-DQ-skip failure mode (LLD §13 Decision
    16). The Airflow task fails-closed and PagerDuty ``p360-critical``
    is alerted per LLD §5.5.
    """


# ---------------------------------------------------------------------------
# Layer table list (LLD §5.1 / per-table airflow/configs/<table>.yml)
# ---------------------------------------------------------------------------
def _resolve_env() -> str:
    return os.environ.get(ENV_ENV, DEFAULT_ENV)


def _resolve_configs_dir() -> Path:
    return Path(os.environ.get(CONFIGS_DIR_ENV, DEFAULT_CONFIGS_DIR))


def list_layer_tables(configs_dir: Path | None = None) -> list[str]:
    """Enumerate the layer's table names from the per-table YAML configs.

    LLD §8.6.1 v1.18 — the evidence check iterates the Bronze table list
    sourced from ``airflow/configs/<table>.yml`` (the same files the
    ingestion factory fans out over). Each config's ``table`` key (falling
    back to the filename stem) is the logical table name used to resolve the
    per-table stats path. Never hardcode the table list.
    """
    cfg_dir = configs_dir or _resolve_configs_dir()
    if not cfg_dir.is_dir():
        raise FileNotFoundError(
            f"configs_dir does not exist: {cfg_dir}. Set {CONFIGS_DIR_ENV} or pass configs_dir."
        )
    tables: list[str] = []
    for yml in sorted([*cfg_dir.glob("*.yml"), *cfg_dir.glob("*.yaml")]):
        doc = yaml.safe_load(yml.read_text()) or {}
        tables.append(doc.get("table") or yml.stem)
    # De-dupe while preserving order (a table may carry both .yml and .yaml).
    seen: set[str] = set()
    return [t for t in tables if not (t in seen or seen.add(t))]


# ---------------------------------------------------------------------------
# Core SE-RUN-EVIDENCE query (LLD §8.6.1 v1.20 — per-table managed UC tables)
# ---------------------------------------------------------------------------
def _count_se_stats_rows(
    spark: Any,
    *,
    ds: str,
    env: str,
    tables: list[str],
) -> int:
    """Sum ``meta_dq_run_date = '<run_date>'`` rows across per-table managed
    SE-stats UC tables.

    LLD §8.6.1 v1.20 / §2.3 item 3 — for each table resolve its managed stats
    FQN ``unity.bronze.<table>_stats``, **skip tables that do not yet exist**
    (a table SE has never written stats for), query each existing table, and
    return the aggregate count. Do NOT add ``AND meta_dq_run_id = ...`` — SE
    owns the run_id internally and the gate cannot predict it (LLD §8.6.1
    evidence-query keying note).

    FILTER KEY: ``meta_dq_run_date`` is the SE wall-clock run date, NOT the
    data ``ds`` (the managed stats table has no ``ds`` column). Gating on ``ds``
    false-fails any backfill/replay of a past ``ds``. We therefore filter by the
    SE run date — computed once as the current UTC date, since this gate runs in
    the same DAG execution as the SE writes it audits. (Ideal would be matching
    the DAG ``meta_dq_run_id`` if SE ever stamps it; until then run-date is the
    robust anti-silent-skip signal.) ``ds`` stays in the logs for traceability.
    """
    # SE run date = the date SE actually ran = the date this reconciliation
    # runs (same DAG execution). NOT the data ds — see docstring.
    run_date = datetime.now(UTC).strftime("%Y-%m-%d")
    total = 0
    checked = 0
    for table in tables:
        stats_fqn = _se_stats_fqn(table)
        try:
            exists = spark.catalog.tableExists(stats_fqn)
        except Exception:  # noqa: BLE001 — catalog may be cold/unavailable
            exists = False
        if not exists:
            logger.info(
                "SE-RUN-EVIDENCE: skipping absent stats table for table=%s (%s)",
                table,
                stats_fqn,
            )
            continue
        checked += 1
        sql = f"SELECT count(*) AS n FROM {stats_fqn} WHERE meta_dq_run_date = '{run_date}'"
        logger.info(
            "SE-RUN-EVIDENCE query [%s] (ds=%s run_date=%s): %s",
            table,
            ds,
            run_date,
            sql,
        )
        n = int(spark.sql(sql).collect()[0]["n"])
        logger.info(
            "  table=%s stats rows for run_date=%s (ds=%s): %d",
            table,
            run_date,
            ds,
            n,
        )
        total += n
    logger.info(
        "SE-RUN-EVIDENCE: checked %d/%d per-table managed stats tables; total "
        "rows for run_date=%s (ds=%s): %d",
        checked,
        len(tables),
        run_date,
        ds,
        total,
    )
    return total


def assert_se_evidence(
    spark: Any,
    *,
    meta_dq_run_id: str,
    ds: str,
    env: str | None = None,
    tables: list[str] | None = None,
    configs_dir: Path | None = None,
) -> int:
    """Assert ≥1 SE stats row exists across the layer's per-table managed
    SE-stats UC tables.

    Raises :class:`SEEvidenceMissingError` with the
    ``SE_RUN_MISSING_FOR_DS=<ds>`` marker (LLD §8.6.1) on failure so
    Airflow logs + PagerDuty bodies carry a greppable signal.
    """
    resolved_env = env or _resolve_env()
    resolved_tables = tables if tables is not None else list_layer_tables(configs_dir)
    n = _count_se_stats_rows(spark, ds=ds, env=resolved_env, tables=resolved_tables)
    if n == 0:
        raise SEEvidenceMissingError(
            f"SE_RUN_MISSING_FOR_DS={ds} meta_dq_run_id={meta_dq_run_id} "
            f"layer={LAYER} env={resolved_env} — no per-table managed SE-stats "
            f"UC table (unity.bronze.<table>_stats) has any row for ds={ds}; "
            "spark-expectations never wrote stats (silent-DQ-skip failure per "
            "LLD §8.6.1 / §13 Decision 16)."
        )
    logger.info(
        "SE-RUN-EVIDENCE OK: %d per-table stats rows for ds=%s meta_dq_run_id=%s (layer=%s env=%s)",
        n,
        ds,
        meta_dq_run_id,
        LAYER,
        resolved_env,
    )
    return n


# ---------------------------------------------------------------------------
# Airflow PythonOperator entry point
# ---------------------------------------------------------------------------
def run_reconciliation_bronze(
    *,
    ds: str,
    ts_nodash: str,
    uc_uri: str | None = None,
    **_: Any,
) -> int:
    """PythonOperator callable for the ``reconciliation_bronze`` task.

    Parameters
    ----------
    ds
        Airflow logical date (``{{ ds }}``); the partition value
        Bronze writes to. Matched against the SE stats column
        ``meta_dq_run_date``.
    ts_nodash
        Airflow run identifier (``{{ ts_nodash }}``); carried into the
        failure marker for traceability only. SE owns its internal
        ``meta_dq_run_id`` and the gate cannot key on it (LLD §8.6.1).
    uc_uri
        Optional Unity Catalog OSS URI override. Defaults to the
        ``UC_URI`` env var or LLD §7 default.

    Returns
    -------
    int
        Aggregate stats rows seen across per-table paths (always ≥1 —
        zero raises).
    """
    # Local import keeps this module importable in DAG-parse contexts
    # where pyspark is not on the path (Airflow's DAG parser).
    from patient_360.bronze.ingestion_runner import build_spark

    spark = build_spark(app_name="reconciliation_bronze", uc_uri=uc_uri)
    try:
        return assert_se_evidence(spark, meta_dq_run_id=ts_nodash, ds=ds)
    finally:
        spark.stop()


# ---------------------------------------------------------------------------
# spark-submit entry (used by run_bronze_recon.py wrapper)
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bronze reconciliation — SE-RUN-EVIDENCE (LLD §8.6.1)")
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


__all__ = [
    "LAYER",
    "SEEvidenceMissingError",
    "assert_se_evidence",
    "list_layer_tables",
    "main",
    "parse_args",
    "run_reconciliation_bronze",
]
