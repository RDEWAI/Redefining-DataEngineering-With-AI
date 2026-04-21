"""SparkSubmitOperator wrapper for Bronze ingestion tasks.

Builds an Airflow ``SparkSubmitOperator`` that invokes the module named by
``ingestion_spark_submit_class`` (defaults to ``patient_360.bronze.ingestion_runner``)
with ``--config-path``, ``--ds``, and ``--env`` flags. Compute sizing comes
from the pipeline config (§7 Configuration Schema); timeout and retries
come from the per-table YAML.
"""

from __future__ import annotations

from typing import Any

try:
    from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
except ImportError:  # pragma: no cover
    SparkSubmitOperator = None  # type: ignore[assignment]


DEFAULT_ENTRY_POINT = "patient_360.bronze.ingestion_runner"


def build_spark_submit_task(
    *,
    task_id: str,
    config_path: str,
    ds: str,
    env: str,
    compute: dict[str, Any],
    retries: int,
    retry_delay_seconds: int,
    timeout_minutes: int,
    entry_point: str = DEFAULT_ENTRY_POINT,
    conn_id: str = "spark_default",
) -> Any:
    """Return a configured ``SparkSubmitOperator`` for one Bronze table."""
    if SparkSubmitOperator is None:
        raise RuntimeError(
            "airflow.providers.apache.spark is not installed — add it to dev extras"
        )

    import datetime

    application_args = [
        "--config-path", config_path,
        "--ds", ds,
        "--env", env,
    ]

    spark_conf = {
        "spark.sql.extensions": "io.delta.sql.DeltaSparkSessionExtension",
        "spark.sql.catalog.spark_catalog": "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        "spark.sql.shuffle.partitions": str(compute.get("compute_spark_shuffle_partitions", 8)),
    }

    return SparkSubmitOperator(
        task_id=task_id,
        conn_id=conn_id,
        application=f"-m {entry_point}",
        application_args=application_args,
        driver_memory=str(compute.get("compute_spark_driver_memory", "2g")),
        executor_memory=str(compute.get("compute_spark_executor_memory", "2g")),
        executor_cores=int(compute.get("compute_spark_executor_cores", 1)),
        num_executors=int(compute.get("compute_spark_num_executors", 1)),
        conf=spark_conf,
        retries=retries,
        retry_delay=datetime.timedelta(seconds=retry_delay_seconds),
        execution_timeout=datetime.timedelta(minutes=timeout_minutes),
    )
