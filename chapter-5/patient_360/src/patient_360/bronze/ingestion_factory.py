"""TaskGroup factory for Bronze ingestion (LLD §2.3, §4.2).

``create_bronze_taskgroup`` scans ``airflow/configs/*.yml`` at DAG parse time
and returns an Airflow TaskGroup named ``bronze_ingestion`` with one
SparkSubmitOperator per file. Adding a new Bronze table requires only a new
YAML file in ``airflow/configs/`` — no code changes needed.

No Spark jobs are executed at DAG parse time (LLD §4.1).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from airflow.utils.task_group import TaskGroup

from patient_360.bronze.spark_submit_wrapper import create_spark_submit_task


def create_bronze_taskgroup(
    config_dir: str | Path,
    dag: Any,
    ds: str = "{{ ds }}",
    env: str = "DEV",
    pipeline_config: dict[str, Any] | None = None,
) -> TaskGroup:
    """Build the ``bronze_ingestion`` TaskGroup from per-table YAML configs.

    Scans ``config_dir`` for ``*.yml`` files at DAG parse time. Creates one
    SparkSubmitOperator per file with task ID ``bronze_ingestion.ingest_{table}``.
    All 13 tasks run in parallel within the TaskGroup (LLD §6.3).

    Args:
        config_dir: Path to ``airflow/configs/`` directory.
        dag: Airflow DAG instance.
        ds: Partition date template (default: Airflow ``{{ ds }}`` macro).
        env: Runtime environment (DEV/STAGING/PROD).
        pipeline_config: Parsed pipeline config dict for Spark resource params.
    """
    config_dir = Path(config_dir)
    pipeline_config = pipeline_config or {}

    with TaskGroup(group_id="bronze_ingestion", dag=dag) as tg:
        for config_path in sorted(config_dir.glob("*.yml")):
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            table = str(raw.get("table", config_path.stem))
            create_spark_submit_task(
                task_id=f"ingest_{table}",
                config_path=str(config_path),
                ds=ds,
                env=env,
                pipeline_config=pipeline_config,
                dag=dag,
            )
    return tg
