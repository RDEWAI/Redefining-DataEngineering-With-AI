"""Spark Expectations runner — inline DQ for every Bronze write.

LLD references: §2.3 (`se_runner.py` interface contract), §5.4 (Inline SE
Validation), §8.2-§8.3 (error/stats tables + alerting), §8.6 + §13
Decision 14 (single-state fail-closed import contract).

Contract
--------
``run_dq(df, *, table, env, dq_rules_dir, action_if_failed=None,
quarantine_path=None)`` wraps Nike Spark Expectations
(``SparkExpectations.with_expectations``) around a DataFrame and returns the
validated frame. Failing rows are routed to the SE error table; aggregate
stats land in ``bronze_se_stats``. Both tables are managed Delta tables
(``se.enable.error.table=true``, ``se.enable.stats.table=true``).

Per-row failures honour ``action_if_failed`` resolution order:

1. The per-rule ``action_if_failed`` declared in the YAML rule.
2. The per-table fail-closed default passed in via ``action_if_failed``.

``env`` is the pipeline runtime flag and is mapped to the SE ``dq_env``
selector before rule load:

+----------------+----------------+
| runtime ``env``| SE ``dq_env``  |
+================+================+
| ``DEV``        | ``DEV``        |
| ``STAGING``    | ``QA``         |
| ``PROD``       | ``PROD``       |
+----------------+----------------+

The mapping lives in :data:`_DQ_ENV_MAP` so it is verifiable from tests.

Spark Expectations version requirement
--------------------------------------
This module requires ``spark-expectations >= 2.10.0`` for the YAML rule
loader and ``WrappedDataFrameWriter`` APIs. Earlier versions raise
``ModuleNotFoundError`` for ``spark_expectations.rules``.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from spark_expectations.core.expectations import (  # noqa: I001
    SparkExpectations,
    WrappedDataFrameWriter,
)
from spark_expectations.rules.plugins.yaml_loader import (
    SparkExpectationsYamlRuleLoaderImpl,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import DataFrame

logger = logging.getLogger(__name__)


# LLD §2.3 / §5.4 — runtime --env → SE dq_env selector. Exposed at module
# scope so unit tests can parametrise over it without re-importing.
_DQ_ENV_MAP: dict[str, str] = {
    "DEV": "DEV",
    "STAGING": "QA",
    "PROD": "PROD",
}

# Managed Delta tables that SE writes per-run stats and error rows into.
# Names are stable across environments; the catalog is selected by the
# Spark session, not by this module.
SE_STATS_TABLE = "bronze.bronze_se_stats"
SE_ERROR_TABLE = "bronze.bronze_se_errors"


def _ensure_stats_table(spark) -> None:
    """Register the SE stats Delta table in the active session catalog.

    SE's ``saveAsTable`` call fails on a fresh ``SparkSession`` if the
    managed table already exists on disk but is absent from the in-memory
    catalog — a common case during local pytest runs that reuse a warehouse
    directory across sessions. This helper is a no-op when the table is
    already known to the catalog.
    """
    warehouse = spark.conf.get("spark.sql.warehouse.dir", "spark-warehouse")
    stats_path = Path(warehouse.lstrip("file:")) / SE_STATS_TABLE
    if stats_path.exists() and not spark.catalog.tableExists(SE_STATS_TABLE):
        spark.sql(
            f"CREATE TABLE IF NOT EXISTS {SE_STATS_TABLE} "
            f"USING DELTA LOCATION '{stats_path}'"
        )


def _resolve_dq_rules_dir(dq_rules_dir: Path | str | None) -> Path:
    """Resolve the dq_rules directory using the AIRFLOW_CONFIGS_DIR pattern.

    Resolution order (LLD §2.3):

    1. Explicit argument passed by the caller.
    2. ``DQ_RULES_DIR`` environment variable — the canonical container path
       injected by the cookiecutter ``docker-compose.yml``.
    3. ``/opt/dq_rules`` as a last-resort fallback for non-container runs.

    The literal ``"airflow/configs"`` / relative paths are never hardcoded
    here — the env var is the single resolution mechanism (see
    ``validate-dag DAG-PATHS-002`` regression rule).
    """
    if dq_rules_dir is not None:
        return Path(dq_rules_dir)
    env_dir = os.environ.get("DQ_RULES_DIR")
    if env_dir:
        return Path(env_dir)
    return Path("/opt/dq_rules")


def run_dq(
    df: "DataFrame",
    *,
    table: str,
    env: str,
    dq_rules_dir: Path | str | None = None,
    action_if_failed: str | None = None,
    quarantine_path: str | None = None,
) -> "DataFrame":
    """Run inline Spark Expectations validation against ``df``.

    Parameters
    ----------
    df:
        Input DataFrame about to be written to Bronze.
    table:
        Logical table name. Used to locate ``dq_rules/{table}.yml`` and to
        scope SE stats rows via ``product_id``.
    env:
        Runtime environment flag (``DEV | STAGING | PROD``). Mapped to SE
        ``dq_env`` via :data:`_DQ_ENV_MAP`.
    dq_rules_dir:
        Optional override for the SE rules directory. Defaults to the
        ``DQ_RULES_DIR`` env var, then ``/opt/dq_rules``.
    action_if_failed:
        Per-table fail-closed default for any rule whose YAML omits its own
        ``action_if_failed`` (LLD §5.4). One of ``fail | drop | ignore``.
    quarantine_path:
        Filesystem path where SE writes its error/quarantine Delta table.
        Required so STORY-01-009's runner can wire LLD §3 quarantine paths
        through unchanged.

    Returns
    -------
    DataFrame
        The validated DataFrame ready to be written to the Bronze target.

    Raises
    ------
    KeyError
        If ``env`` is not one of ``DEV | STAGING | PROD``.
    FileNotFoundError
        If the resolved rules file does not exist.
    """
    if env not in _DQ_ENV_MAP:
        raise KeyError(
            f"Unknown env={env!r}; expected one of {sorted(_DQ_ENV_MAP)}"
        )
    dq_env = _DQ_ENV_MAP[env]

    rules_dir = _resolve_dq_rules_dir(dq_rules_dir)
    rules_yaml = rules_dir / f"{table}.yml"
    if not rules_yaml.exists():
        # Fall back to `.yaml` — both extensions are used in practice.
        alt = rules_dir / f"{table}.yaml"
        if alt.exists():
            rules_yaml = alt
        else:
            raise FileNotFoundError(
                f"SE rules file not found: {rules_yaml} (or {alt})"
            )

    spark = df.sparkSession
    _ensure_stats_table(spark)

    # Disable Kafka stats streaming + every notifier — required to keep
    # local (non-Databricks) runs free of Databricks-secret lookups.
    user_conf: dict[str, object] = {
        "se.enable.error.table": True,
        "se.streaming.enable": False,
        "spark.expectations.notifications.alert.flag.disable": True,
        "spark.expectations.notifications.email.enabled": False,
        "spark.expectations.notifications.slack.enabled": False,
        "spark.expectations.notifications.teams.enabled": False,
        "spark.expectations.notifications.pagerduty.enabled": False,
        "spark.expectations.notifications.zoom.enabled": False,
    }
    if action_if_failed:
        # Fail-closed per-table default; per-rule declarations still win
        # because SE consults the rule row first.
        user_conf["se.default_action_if_failed"] = action_if_failed

    rules_df = SparkExpectationsYamlRuleLoaderImpl().load_rules(
        str(rules_yaml),
        format="yaml",
        options={"dq_env": dq_env},
    )

    # MANAGED writers — UC owns the path via `spark.sql.warehouse.dir`.
    # No `.option("path", ...)` so saveAsTable creates standard managed
    # Delta tables (MVP-aligned pattern; works with UC OSS `main`).
    error_writer = (
        WrappedDataFrameWriter()
        .mode("append")
        .format("delta")
    )
    if quarantine_path:
        error_writer = error_writer.option("path", quarantine_path)
    stats_writer = (
        WrappedDataFrameWriter()
        .mode("append")
        .format("delta")
    )

    se = SparkExpectations(
        product_id=table,
        rules_df=rules_df,
        stats_table=SE_STATS_TABLE,
        stats_table_writer=stats_writer,
        target_and_error_table_writer=error_writer,
        debugger=False,
    )

    logger.info(
        "SE run_dq table=%s env=%s dq_env=%s action_if_failed=%s rules=%s",
        table,
        env,
        dq_env,
        action_if_failed,
        rules_yaml,
    )

    # spark-expectations' `with_expectations` is a decorator: it returns a
    # wrapper that expects a *function* producing a DataFrame, not a
    # DataFrame itself. Wrap `df` in a no-arg lambda, then invoke the
    # wrapped callable to get the validated DataFrame back.
    decorated = se.with_expectations(
        target_table=table,
        user_conf=user_conf,
        target_and_error_table_writer=error_writer,
    )(lambda: df)
    validated = decorated()
    return validated


__all__ = [
    "_DQ_ENV_MAP",
    "SE_STATS_TABLE",
    "SE_ERROR_TABLE",
    "run_dq",
]
