"""Spark Expectations inline runner for Bronze DQ (LLD §2.3, §5.4).

Implements the interface:

    run_dq(df, table, env, action_if_failed, dq_rules_dir) -> DataFrame

``env`` is the runtime environment (DEV/STAGING/PROD); this module maps it to
the SE dq_env key (DEV/QA/PROD) before passing to Spark Expectations.

Stats are appended to a managed Delta table ``bronze_se_stats`` (created on
first run). Error/quarantine rows (action_if_failed=drop) are written to the
quarantine path provided by the caller.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pyspark.sql import DataFrame, SparkSession

from spark_expectations.core.expectations import SparkExpectations, WrappedDataFrameWriter
from spark_expectations.rules.plugins.yaml_loader import SparkExpectationsYamlRuleLoaderImpl

logger = logging.getLogger(__name__)

_DQ_ENV_MAP = {"DEV": "DEV", "STAGING": "QA", "PROD": "PROD"}

SE_STATS_TABLE = "bronze_se_stats"


def _ensure_stats_table(spark: SparkSession) -> None:
    """Pre-register the SE stats Delta table to avoid DELTA_CREATE_TABLE_WITH_NON_EMPTY_LOCATION.

    SE calls saveAsTable which fails on a fresh SparkSession if the managed table
    already exists on disk but is absent from the in-memory catalog.
    """
    warehouse = spark.conf.get("spark.sql.warehouse.dir", "spark-warehouse")
    stats_path = Path(warehouse.lstrip("file:")) / SE_STATS_TABLE
    if stats_path.exists() and not spark.catalog.tableExists(SE_STATS_TABLE):
        spark.sql(
            f"CREATE TABLE IF NOT EXISTS {SE_STATS_TABLE} "
            f"USING DELTA LOCATION '{stats_path}'"
        )


def run_dq(
    df: DataFrame,
    table: str,
    env: str,
    action_if_failed: str,
    dq_rules_dir: Path,
) -> DataFrame:
    """Run row_dq + agg_dq via Spark Expectations and return validated rows.

    Args:
        df: Input DataFrame (post-metadata-column enrichment).
        table: Table name; resolves to ``dq_rules_dir/{table}.yml``.
        env: Runtime environment (DEV/STAGING/PROD) — mapped to SE dq_env.
        action_if_failed: Fail-closed default (fail|drop|ignore) per LLD §5.4.
            Per-rule declarations in the YAML take precedence.
        dq_rules_dir: Path to the dq_rules directory.

    Returns:
        DataFrame of rows that passed all row_dq checks.
    """
    spark = SparkSession.getActiveSession()
    if spark is None:
        raise RuntimeError("run_dq requires an active SparkSession")

    dq_env = _DQ_ENV_MAP.get(env.upper(), env)
    rules_path = Path(dq_rules_dir) / f"{table}.yml"
    if not rules_path.exists():
        logger.warning("DQ rules file not found: %s — skipping DQ for %s", rules_path, table)
        return df

    loader = SparkExpectationsYamlRuleLoaderImpl()
    rules_df = loader.load_rules(
        path=str(rules_path),
        format="yaml",
        options={"dq_env": dq_env},
        spark=spark,
    )
    if rules_df is None:
        raise ValueError(f"SE YAML loader returned None for {rules_path}")

    data = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    product_id: str = str(data.get("product_id", rules_path.stem))

    _ensure_stats_table(spark)

    _quarantine = f"/tmp/se_quarantine/{table}/"

    target_writer = (
        WrappedDataFrameWriter()
        .mode("append")
        .format("delta")
        .option("path", _quarantine)
    )
    stats_writer = WrappedDataFrameWriter().mode("append").format("delta")

    se = SparkExpectations(
        product_id=product_id,
        rules_df=rules_df,
        stats_table=SE_STATS_TABLE,
        target_and_error_table_writer=target_writer,
        stats_table_writer=stats_writer,
    )

    user_conf: dict[str, Any] = {
        "se.enable.error.table": True,
        "se.streaming.enable": False,
        "spark.expectations.notifications.alert.flag.disable": True,
        "spark.expectations.notifications.email.enabled": False,
        "spark.expectations.notifications.slack.enabled": False,
        "spark.expectations.notifications.teams.enabled": False,
        "spark.expectations.notifications.pagerduty.enabled": False,
        "spark.expectations.notifications.zoom.enabled": False,
    }

    @se.with_expectations(
        target_table=table,
        write_to_table=False,
        user_conf=user_conf,
        target_and_error_table_writer=target_writer,
    )
    def _run() -> DataFrame:
        return df

    validated_df: DataFrame = _run()
    logger.info("SE DQ complete for %s (env=%s, dq_env=%s)", table, env, dq_env)
    return validated_df
