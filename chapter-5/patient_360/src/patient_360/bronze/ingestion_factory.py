"""Bronze TaskGroup factory.

Scans ``airflow/configs/*.yml`` at DAG parse time and produces one
``SparkSubmitOperator`` per file, grouped into a ``bronze_ingestion``
TaskGroup. Per LLD §2.3 and §5.1.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable

import yaml

from patient_360.bronze.spark_submit_wrapper import (
    DEFAULT_ENTRY_POINT,
    build_spark_submit_task,
)

try:
    from airflow.utils.task_group import TaskGroup
except ImportError:  # pragma: no cover
    TaskGroup = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def _iter_config_files(configs_dir: Path) -> Iterable[Path]:
    return sorted(p for p in configs_dir.glob("*.yml") if p.stem != "table_name")


def build_bronze_taskgroup(
    *,
    dag: Any,
    configs_dir: Path,
    ds: str,
    env: str,
    compute: dict[str, Any],
    entry_point: str = DEFAULT_ENTRY_POINT,
    group_id: str = "bronze_ingestion",
    spark_conn_id: str = "spark_default",
) -> Any:
    """Return a TaskGroup with one SparkSubmitOperator per per-table config.

    Args:
        dag: Parent Airflow DAG.
        configs_dir: Directory containing per-table YAML configs.
        ds: Load date (Airflow ``{{ ds }}`` template).
        env: Target environment (DEV | STAGING | PROD).
        compute: Pipeline compute config (§7) — executor memory, cores, etc.
        entry_point: Python module name executed by spark-submit.
        group_id: Airflow TaskGroup name.
        spark_conn_id: Airflow connection ID for the Spark cluster.

    Returns:
        Airflow ``TaskGroup`` containing one task per YAML config file.
    """
    if TaskGroup is None:
        raise RuntimeError("Airflow is not installed — cannot build TaskGroup")

    configs = list(_iter_config_files(configs_dir))
    if not configs:
        raise FileNotFoundError(f"no per-table configs found under {configs_dir}")

    with TaskGroup(group_id=group_id, dag=dag) as group:
        for config_path in configs:
            table_cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            table = str(table_cfg.get("table") or config_path.stem)
            task_id = f"ingest_{table}"
            logger.info("registering bronze task %s from %s", task_id, config_path)
            build_spark_submit_task(
                task_id=task_id,
                config_path=str(config_path),
                ds=ds,
                env=env,
                compute=compute,
                retries=int(table_cfg.get("retries", 3)),
                retry_delay_seconds=int(table_cfg.get("retry_delay_seconds", 60)),
                timeout_minutes=int(table_cfg.get("timeout_minutes", 30)),
                entry_point=entry_point,
                conn_id=spark_conn_id,
            )
    return group
