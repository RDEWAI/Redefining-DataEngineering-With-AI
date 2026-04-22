"""SparkSubmitOperator wrapper for Bronze ingestion tasks (LLD §2.3, §6.1, §8.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator


def create_spark_submit_task(
    task_id: str,
    config_path: str,
    ds: str,
    env: str,
    pipeline_config: dict[str, Any],
    dag: Any,
) -> SparkSubmitOperator:
    """Build a SparkSubmitOperator that invokes the ingestion runner.

    Spark resource parameters are sourced from the pipeline config compute
    section (LLD §6.1). Timeout and retry settings come from the per-table
    YAML config via pipeline_config (LLD §8.1).
    """
    compute = pipeline_config.get("environments", {}).get(env, {}).get("compute", {})

    return SparkSubmitOperator(
        task_id=task_id,
        application="patient_360.bronze.ingestion_runner",
        application_args=["--config-path", config_path, "--ds", ds, "--env", env],
        conf={
            "spark.sql.extensions": "io.delta.sql.DeltaSparkSessionExtension",
            "spark.sql.catalog.spark_catalog": (
                "org.apache.spark.sql.delta.catalog.DeltaCatalog"
            ),
        },
        driver_memory=compute.get("compute_spark_driver_memory", "2g"),
        executor_memory=compute.get("compute_spark_executor_memory", "2g"),
        executor_cores=int(compute.get("compute_spark_executor_cores", 1)),
        num_executors=int(compute.get("compute_spark_num_executors", 1)),
        dag=dag,
    )
