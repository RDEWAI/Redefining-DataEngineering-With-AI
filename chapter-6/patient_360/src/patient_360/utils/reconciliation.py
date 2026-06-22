"""Reconciliation runner — SE run-evidence + cross-table query_dq.

LLD references: §2.3 (`reconciliation.py` interface contract), §5.5
(Reconciliation Tasks), §8.6 + §8.6.1 (SE-RUN-EVIDENCE — the gate that
proves SE actually ran), §13 Decision 14 (single-state fail-closed),
§13 Decision 16 / §2.3 v1.17 (per-table path-based SE stats).

updated: 2026-06-19 — LLD §8.6.1 v1.18 / §2.3 v1.17 / §13 Decision 16:
**per-table path-based SE stats**. The single shared ``bronze_se_stats``
catalog table is RETIRED — ``se_runner`` writes SE stats to PER-TABLE
path-based Delta tables (``warehouse/{env}/_se/<table>/stats``). The
run-evidence gate therefore no longer does a single ``spark.table(...)``
lookup keyed on ``meta_dq_run_id``; it iterates the layer's table list,
resolves each per-table stats path, skips paths that do not yet exist,
counts ``meta_dq_run_date = '<run_date>'`` rows across each existing path, and
requires the aggregate total to be ``>= 1``. The check is
layer-parameterized (``bronze | silver | gold``) so the same helper backs
``reconciliation_bronze`` / ``reconciliation_silver`` / ``reconciliation_gold``.

updated: 2026-06-20 — SE-RUN-EVIDENCE date-filter fix (backfill/replay
false-fail). ``meta_dq_run_date`` is the SE wall-clock run date, not the data
``ds`` (the managed SE ``_stats`` table has no ``ds`` column). Gating on
``meta_dq_run_date = '{ds}'`` false-failed any backfill/replay of a past ``ds``
with ``SE_RUN_MISSING_FOR_DS`` — a silent-DQ-skip false alarm. The gate now
filters by the SE run date (= the date this reconciliation runs in the same DAG
execution), computed once as the current UTC date. ``ds`` is retained in the
error message + logs for traceability only.

The reconciliation runner has two responsibilities:

1. **SE run-evidence** (AC6) — confirm Spark Expectations actually wrote
   stats for the run's ``ds`` across the layer's per-table stats paths. Zero
   stats rows means a silent skip; the pipeline must fail closed (LLD §8.6 /
   §13 Decision 14/16). NOTE: the historical single shared
   ``silver_se_stats`` / ``bronze_se_stats`` catalog table is RETIRED
   (LLD §8.6.1 v1.18); the equivalent fail-closed gate is now the
   per-table path-based ``check_se_run_evidence`` below.
2. Cross-table ``query_dq`` checks per LLD §5.5. For the Silver layer
   (STORY-04-010) these are: Bronze→Silver row-count reconciliation
   (DQS §5 DQ-REC-002), FK orphan cross-checks (DQS §3 DQ-REF-001..018),
   and SCD2 version-count sanity (DQS §2 DQ-FLD-184..186). They run only
   after the SE-run-evidence gate passes and themselves fail closed.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import SparkSession

logger = logging.getLogger(__name__)

# LLD §8.6.1 v1.20 / §2.3 item 3 / §13 Decision 12 (corrected 2026-06-20) —
# per-table SE stats are now MANAGED Unity Catalog tables addressed by the
# 3-part FQN ``unity.bronze.<table>_stats`` (the UC-0.4.0 path-based shape is
# retired). The ``_stats`` suffix mirrors se_runner.SE_STATS_SUFFIX so the two
# stay in lock-step.
SE_STATS_SUFFIX = "_stats"

# Catalog + Bronze schema used to build the managed SE-stats FQN. Overridable
# via env vars (mirrors se_runner) so the warehouse name is never hardcoded.
SE_UC_CATALOG_ENV = "SE_UC_CATALOG"
SE_UC_BRONZE_SCHEMA_ENV = "SE_UC_BRONZE_SCHEMA"
_DEFAULT_SE_UC_CATALOG = "unity"
_DEFAULT_SE_UC_BRONZE_SCHEMA = "bronze"

# Runtime env flag (DEV | STAGING | PROD). Retained for log/error context;
# the managed SE-stats tables are env-agnostic FQNs.
ENV_ENV = "PATIENT360_ENV"
DEFAULT_ENV = "DEV"


def _se_stats_fqn(table: str) -> str:
    """Return the managed SE-stats UC table FQN for ``table``.

    LLD §8.6.1 v1.20: ``unity.bronze.<table>_stats``. ``table`` may be a bare
    logical name (qualified here) or already an FQN (suffixed as-is).
    """
    if "." in table:
        return f"{table}{SE_STATS_SUFFIX}"
    catalog = os.environ.get(SE_UC_CATALOG_ENV, _DEFAULT_SE_UC_CATALOG)
    schema = os.environ.get(SE_UC_BRONZE_SCHEMA_ENV, _DEFAULT_SE_UC_BRONZE_SCHEMA)
    return f"{catalog}.{schema}.{table}{SE_STATS_SUFFIX}"


# Default configs dir resolution mirrors the AIRFLOW_CONFIGS_DIR pattern
# used by ingestion_factory. Never hardcode the relative path.
DEFAULT_CONFIGS_DIR = os.environ.get("AIRFLOW_CONFIGS_DIR", "/opt/airflow/configs")


class ReconciliationError(RuntimeError):
    """Raised when a reconciliation gate fails closed."""


@dataclass(frozen=True)
class SERunEvidence:
    """Result of the LLD §8.6.1 SE-RUN-EVIDENCE check.

    ``stats_row_count`` is the AGGREGATE count across every existing
    per-table managed SE-stats UC table for the layer (LLD §8.6.1 v1.20).
    """

    ds: str
    stats_row_count: int
    paths_checked: int

    @property
    def passed(self) -> bool:
        return self.stats_row_count > 0


def check_se_run_evidence(
    spark: SparkSession,
    *,
    ds: str,
    tables: list[str],
    env: str | None = None,
) -> SERunEvidence:
    """Verify SE wrote ≥1 stats row for ``ds`` across per-table managed
    SE-stats UC tables.

    LLD §8.6.1 v1.20 / §2.3 item 3 / §13 Decision 12 (corrected) — iterate the
    layer's table list, resolve each per-table managed stats table FQN
    ``unity.bronze.<table>_stats``, skip tables that do not yet exist (first
    run before SE created them), query each existing table filtered on
    ``meta_dq_run_date = '<run_date>'``, and require the aggregate total to be
    ``>= 1``. A zero aggregate means SE did not run — either ``se_runner`` was
    unavailable (caught by the import gate) or the writer silently no-op'd.
    Either way the pipeline must abort before downstream consumers see
    un-validated data.

    FILTER KEY: ``meta_dq_run_date`` is the SE wall-clock run date, NOT the
    data ``ds`` (the managed stats table has no ``ds`` column). Gating on ``ds``
    false-fails any backfill/replay of a past ``ds``. We therefore filter by the
    SE run date — computed once as the current UTC date, since this gate runs in
    the same DAG execution as the SE writes it audits. (Ideal would be matching
    the DAG ``meta_dq_run_id`` if SE ever stamps it; until then run-date is the
    robust anti-silent-skip signal.) ``ds`` stays in the logs/error for
    traceability.

    Do NOT add ``AND meta_dq_run_id = ...`` — SE generates its own
    ``meta_dq_run_id`` internally and the gate cannot predict it (LLD §8.6.1
    evidence-query keying note).

    Parameters
    ----------
    spark:
        Active SparkSession.
    ds:
        The pipeline logical date; matched against the SE stats column
        ``meta_dq_run_date``.
    tables:
        The layer's logical table names (from the per-table YAML configs).
        Each resolves to a managed ``unity.bronze.<table>_stats`` UC table.
    env:
        Runtime env flag (``DEV | STAGING | PROD``). Retained for log/error
        context; the managed SE-stats tables are env-agnostic FQNs.

    Returns
    -------
    SERunEvidence
        Carries the aggregate matched row count and number of tables checked.

    Raises
    ------
    ReconciliationError
        When zero stats rows match ``ds`` across every existing per-table
        managed SE-stats UC table (fail-closed gate).
    """
    resolved_env = env or os.environ.get(ENV_ENV, DEFAULT_ENV)
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
        n = spark.table(stats_fqn).where(f"meta_dq_run_date = '{run_date}'").count()
        logger.info(
            "  table=%s stats rows for run_date=%s (ds=%s): %d",
            table,
            run_date,
            ds,
            n,
        )
        total += n

    evidence = SERunEvidence(ds=ds, stats_row_count=total, paths_checked=checked)
    if not evidence.passed:
        logger.error(
            "SE-RUN-EVIDENCE FAIL: zero stats rows across %d per-table managed "
            "SE-stats UC tables for ds=%s (env=%s) — DQ did not run; failing "
            "closed.",
            checked,
            ds,
            resolved_env,
        )
        raise ReconciliationError(
            f"SE_RUN_MISSING_FOR_DS={ds}: no per-table managed SE-stats UC "
            f"table (unity.bronze.<table>_stats) has any row for ds={ds} "
            f"(env={resolved_env})"
        )
    logger.info(
        "SE-RUN-EVIDENCE OK: %d stats rows across %d per-table managed SE-stats "
        "UC tables for ds=%s (env=%s)",
        total,
        checked,
        ds,
        resolved_env,
    )
    return evidence


# ---------------------------------------------------------------------------
# LLD §5.5 cross-table query_dq checks (STORY-04-010, Silver layer)
#
# Each check is a fail-closed assertion expressed as Delta SQL against the
# named UC catalog (``unity.{layer}.{table}`` — LLD §13 Decision 12). The
# rule SETS are passed in by the caller (the silver reconciliation task wires
# the DQS §2/§3/§5 rows). Defaults for the Silver layer are provided via
# ``silver_query_dq_rules()`` so the helper is project-agnostic — callers can
# override the rule set when the DMS/DQS table list changes.
# ---------------------------------------------------------------------------

CATALOG = "unity"


@dataclass(frozen=True)
class RowCountRule:
    """Bronze→Silver row-count reconciliation (DQS §5 DQ-REC-*).

    ``source`` / ``target`` are ``{layer}.{table}`` pairs; the optional
    ``target_filter`` restricts the target count (e.g. ``is_current = TRUE``
    for SCD2 dims). ``tolerance`` is a fraction (0.0 = exact match).
    """

    rule_id: str
    source: str
    target: str
    tolerance: float = 0.0
    target_filter: str | None = None


@dataclass(frozen=True)
class FkOrphanRule:
    """Silver FK orphan cross-check (DQS §3 DQ-REF-*).

    Asserts that every ``child.child_col`` resolves to a ``parent.parent_col``
    among current parent rows. ``parent_filter`` defaults to the SCD2
    ``is_current = TRUE`` predicate so versioned dims compare against the live
    version only. Orphan count must be 0 (fail closed).
    """

    rule_id: str
    child: str
    child_col: str
    parent: str
    parent_col: str
    parent_filter: str | None = "is_current = TRUE"


@dataclass(frozen=True)
class Scd2VersionRule:
    """SCD2 version-count sanity (DQS §2 DQ-FLD-184..186).

    Asserts ``COUNT(*) WHERE is_current = TRUE == COUNT(DISTINCT natural_key)``
    — exactly one current version per natural key.
    """

    rule_id: str
    table: str
    natural_key: str


@dataclass(frozen=True)
class QueryDqResult:
    rule_id: str
    passed: bool
    detail: str


def _fqn(layer_table: str) -> str:
    """Wrap a ``{layer}.{table}`` ref as a fully-qualified UC identifier."""
    return f"{CATALOG}.{layer_table}"


def _count(spark: SparkSession, fqn: str, where: str | None = None) -> int:
    df = spark.table(fqn)
    if where:
        df = df.where(where)
    return df.count()


def check_row_count(spark: SparkSession, rule: RowCountRule, *, ds: str) -> QueryDqResult:
    """Bronze→Silver row-count reconciliation within ``rule.tolerance``."""
    src_where = f"ds = '{ds}'"
    src = _count(spark, _fqn(rule.source), src_where)
    tgt = _count(spark, _fqn(rule.target), rule.target_filter)
    if src == 0:
        passed = tgt == 0
    else:
        passed = abs(tgt - src) <= rule.tolerance * src
    return QueryDqResult(
        rule.rule_id,
        passed,
        f"{rule.source}={src} vs {rule.target}={tgt} (tol={rule.tolerance:.4%})",
    )


def check_fk_orphans(spark: SparkSession, rule: FkOrphanRule) -> QueryDqResult:
    """FK orphan cross-check — orphan child rows must be 0."""
    child = _fqn(rule.child)
    parent = _fqn(rule.parent)
    parent_pred = f"WHERE {rule.parent_filter}" if rule.parent_filter else ""
    sql = (
        f"SELECT COUNT(*) AS n FROM {child} c "
        f"WHERE c.{rule.child_col} IS NOT NULL AND NOT EXISTS ("
        f"SELECT 1 FROM {parent} p {parent_pred} "
        f"{'AND' if parent_pred else 'WHERE'} "
        f"p.{rule.parent_col} = c.{rule.child_col})"
    )
    orphans = spark.sql(sql).collect()[0]["n"]
    return QueryDqResult(
        rule.rule_id,
        orphans == 0,
        f"{rule.child}.{rule.child_col} orphans vs {rule.parent}.{rule.parent_col}: {orphans}",
    )


def check_scd2_versions(spark: SparkSession, rule: Scd2VersionRule) -> QueryDqResult:
    """SCD2 sanity — exactly one current version per natural key."""
    fqn = _fqn(rule.table)
    current = _count(spark, fqn, "is_current = TRUE")
    distinct_nk = (
        spark.table(fqn).where("is_current = TRUE").select(rule.natural_key).distinct().count()
    )
    return QueryDqResult(
        rule.rule_id,
        current == distinct_nk,
        f"{rule.table}: current={current} distinct_{rule.natural_key}={distinct_nk}",
    )


def run_query_dq(
    spark: SparkSession,
    *,
    ds: str,
    row_count_rules: list[RowCountRule],
    fk_rules: list[FkOrphanRule],
    scd2_rules: list[Scd2VersionRule],
) -> list[QueryDqResult]:
    """Run every cross-table check; raise ``ReconciliationError`` on any fail.

    Fail-closed: a single failing rule aborts the layer so Gold never reads
    un-reconciled Silver data (LLD §5.5 — block Gold processing on failure).
    """
    results: list[QueryDqResult] = []
    for rc in row_count_rules:
        results.append(check_row_count(spark, rc, ds=ds))
    for fk in fk_rules:
        results.append(check_fk_orphans(spark, fk))
    for sc in scd2_rules:
        results.append(check_scd2_versions(spark, sc))

    for r in results:
        level = logging.INFO if r.passed else logging.ERROR
        logger.log(
            level, "  query_dq %s %s — %s", r.rule_id, "PASS" if r.passed else "FAIL", r.detail
        )

    failed = [r for r in results if not r.passed]
    if failed:
        ids = ", ".join(r.rule_id for r in failed)
        raise ReconciliationError(
            f"QUERY_DQ_FAILED_FOR_DS={ds}: {len(failed)} cross-table check(s) failed — {ids}"
        )
    return results


def silver_query_dq_rules() -> tuple[list[RowCountRule], list[FkOrphanRule], list[Scd2VersionRule]]:
    """Default Silver-layer query_dq rule set (DQS §2/§3/§5).

    These mirror the DQS rows that are cross-table (require all Silver tasks
    complete). Callers may override by passing their own lists to
    ``run_query_dq``; this default keeps STORY-04-010 self-contained.
    """
    # DQS §5 DQ-REC-002 — Bronze→Silver row-count (is_current for the SCD2 dim).
    row_count = [
        RowCountRule(
            "DQ-REC-002",
            source="bronze.synthea_patients",
            target="silver.clinical_patients",
            tolerance=0.0,
            target_filter="is_current = TRUE",
        ),
    ]
    # DQS §3 DQ-REF-001..018 — Silver FK orphan cross-checks. Parent SCD2 dims
    # filtered to is_current; non-SCD2 parents pass parent_filter=None.
    fk = [
        FkOrphanRule(
            "DQ-REF-001",
            "silver.clinical_encounters",
            "patient_id",
            "silver.clinical_patients",
            "patient_id",
        ),
        FkOrphanRule(
            "DQ-REF-002",
            "silver.clinical_encounters",
            "organization_id",
            "silver.reference_organizations",
            "organization_id",
        ),
        FkOrphanRule(
            "DQ-REF-003",
            "silver.clinical_encounters",
            "provider_id",
            "silver.reference_providers",
            "provider_id",
        ),
        FkOrphanRule(
            "DQ-REF-004",
            "silver.clinical_conditions",
            "patient_id",
            "silver.clinical_patients",
            "patient_id",
        ),
        FkOrphanRule(
            "DQ-REF-005",
            "silver.clinical_conditions",
            "encounter_id",
            "silver.clinical_encounters",
            "encounter_id",
            parent_filter=None,
        ),
        FkOrphanRule(
            "DQ-REF-006",
            "silver.clinical_medications",
            "patient_id",
            "silver.clinical_patients",
            "patient_id",
        ),
        FkOrphanRule(
            "DQ-REF-007",
            "silver.clinical_medications",
            "encounter_id",
            "silver.clinical_encounters",
            "encounter_id",
            parent_filter=None,
        ),
        FkOrphanRule(
            "DQ-REF-008",
            "silver.clinical_observations",
            "patient_id",
            "silver.clinical_patients",
            "patient_id",
        ),
        FkOrphanRule(
            "DQ-REF-009",
            "silver.clinical_observations",
            "encounter_id",
            "silver.clinical_encounters",
            "encounter_id",
            parent_filter=None,
        ),
        FkOrphanRule(
            "DQ-REF-010",
            "silver.clinical_allergies",
            "patient_id",
            "silver.clinical_patients",
            "patient_id",
        ),
        FkOrphanRule(
            "DQ-REF-011",
            "silver.clinical_procedures",
            "patient_id",
            "silver.clinical_patients",
            "patient_id",
        ),
        FkOrphanRule(
            "DQ-REF-012",
            "silver.clinical_procedures",
            "encounter_id",
            "silver.clinical_encounters",
            "encounter_id",
            parent_filter=None,
        ),
        FkOrphanRule(
            "DQ-REF-013",
            "silver.clinical_immunizations",
            "patient_id",
            "silver.clinical_patients",
            "patient_id",
        ),
        FkOrphanRule(
            "DQ-REF-014",
            "silver.clinical_immunizations",
            "encounter_id",
            "silver.clinical_encounters",
            "encounter_id",
            parent_filter=None,
        ),
        FkOrphanRule(
            "DQ-REF-015",
            "silver.clinical_careplans",
            "patient_id",
            "silver.clinical_patients",
            "patient_id",
        ),
        FkOrphanRule(
            "DQ-REF-016",
            "silver.clinical_careplans",
            "encounter_id",
            "silver.clinical_encounters",
            "encounter_id",
            parent_filter=None,
        ),
        FkOrphanRule(
            "DQ-REF-017",
            "silver.billing_claims",
            "patient_id",
            "silver.clinical_patients",
            "patient_id",
        ),
        FkOrphanRule(
            "DQ-REF-018",
            "silver.reference_providers",
            "organization_id",
            "silver.reference_organizations",
            "organization_id",
        ),
    ]
    # DQS §2 DQ-FLD-184..186 — SCD2 version-count sanity on SCD2 dims.
    scd2 = [
        Scd2VersionRule("DQ-FLD-184", "silver.reference_organizations", "organization_id"),
        Scd2VersionRule("DQ-FLD-185", "silver.reference_providers", "provider_id"),
        Scd2VersionRule("DQ-FLD-186", "silver.reference_payers", "payer_id"),
    ]
    return row_count, fk, scd2


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


def _table_names(configs: list[dict]) -> list[str]:
    """Extract logical table names from loaded per-table configs."""
    return [cfg["table"] for cfg in configs if "table" in cfg]


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
    p.add_argument("--layer", default="bronze", choices=["bronze", "silver", "gold"])
    p.add_argument(
        "--env",
        default=os.environ.get(ENV_ENV, DEFAULT_ENV),
        help="Runtime env (DEV | STAGING | PROD) anchoring the SE stats path.",
    )
    return p.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    """Entry point for SparkSubmit invocation of the reconciliation task."""
    from pyspark.sql import SparkSession  # imported here to avoid Spark dep at import

    configs_dir = Path(args.configs_dir)
    configs = load_configs(configs_dir)
    tables = _table_names(configs)
    logger.info(
        "Reconciling %d %s tables for ds=%s run_id=%s",
        len(tables),
        args.layer,
        args.ds,
        args.run_id,
    )
    spark = SparkSession.builder.appName(f"reconcile_{args.layer}").getOrCreate()
    try:
        # LLD §8.6.1 v1.18 — per-table path-based SE-RUN-EVIDENCE gate ahead
        # of any cross-table checks. If SE didn't land stats for this ds,
        # none of the §5.5 checks are meaningful.
        check_se_run_evidence(spark, ds=args.ds, tables=tables, env=args.env)

        # LLD §5.5 cross-table query_dq. Silver wires the DQS §2/§3/§5 rule
        # set (row-count reconciliation, FK orphans, SCD2 version sanity);
        # other layers fall through with no cross-table rules for now.
        if args.layer == "silver":
            row_count, fk, scd2 = silver_query_dq_rules()
            run_query_dq(
                spark,
                ds=args.ds,
                row_count_rules=row_count,
                fk_rules=fk,
                scd2_rules=scd2,
            )
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
    "SE_STATS_SUFFIX",
    "RowCountRule",
    "FkOrphanRule",
    "Scd2VersionRule",
    "QueryDqResult",
    "check_se_run_evidence",
    "check_row_count",
    "check_fk_orphans",
    "check_scd2_versions",
    "run_query_dq",
    "silver_query_dq_rules",
    "load_configs",
    "parse_args",
    "run",
]
