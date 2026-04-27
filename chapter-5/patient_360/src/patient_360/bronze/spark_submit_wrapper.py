"""Thin SparkSubmitOperator wrapper for Bronze ingestion tasks.

Implements LLD §2.3 / Decision 9. Builds a SparkSubmitOperator that
delegates ingestion logic to a Spark cluster and passes ``--config-path``
to the runner module named in ``config-template.yaml`` /
``ingestion.spark_submit_class`` (default
``patient_360.bronze.ingestion_runner``).

Catalog wiring matches the runner: DeltaCatalog for `spark_catalog`.
``UCSingleCatalog`` is set inside the runner via ``_build_spark`` (so
local ``python -m`` runs work too); we forward UC env vars here so the
spark-submit JVM has the same view as the airflow worker.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Defaults — overridable by per-task kwargs / pipeline config (LLD §6.1, §7).  #
# --------------------------------------------------------------------------- #
DEFAULT_RUNNER_MODULE = "patient_360.bronze.ingestion_runner"
DEFAULT_DELTA_PACKAGES = "io.delta:delta-spark_2.13:4.0.0"

# Catalog config — matches `_build_spark` in ingestion_runner.py.
DEFAULT_SPARK_CONF = {
    "spark.sql.extensions": "io.delta.sql.DeltaSparkSessionExtension",
    "spark.sql.catalog.spark_catalog": "org.apache.spark.sql.delta.catalog.DeltaCatalog",
}


def build_spark_submit_task(
    *,
    task_id: str,
    config_path: str | Path,
    ds: str,
    env: str,
    dag,
    pipeline_config: dict[str, Any] | None = None,
    runner_module: str = DEFAULT_RUNNER_MODULE,
    application: str | None = None,
    extra_conf: dict[str, str] | None = None,
):
    """Construct a SparkSubmitOperator for one Bronze table ingestion.

    The lazy import lets unit tests run without the airflow Spark provider.
    """
    try:
        from airflow.providers.apache.spark.operators.spark_submit import (
            SparkSubmitOperator,
        )
    except ImportError as e:  # pragma: no cover -- guarded for unit tests
        raise RuntimeError(
            "airflow Spark provider not installed; install "
            "apache-airflow-providers-apache-spark>=4.0"
        ) from e

    pc = pipeline_config or {}

    spark_conf = dict(DEFAULT_SPARK_CONF)
    if extra_conf:
        spark_conf.update(extra_conf)
    # Forward UC OSS endpoint so the spark-submit JVM sees the same UC.
    if "UC_URI" in os.environ:
        spark_conf["spark.driverEnv.UC_URI"] = os.environ["UC_URI"]
        spark_conf["spark.executorEnv.UC_URI"] = os.environ["UC_URI"]

    # Resolve the application file. The runner is invoked as a module via
    # `python -m`; SparkSubmitOperator needs a file path, so we point at
    # the runner's __file__ if `application` is not supplied.
    if application is None:
        from patient_360.bronze import ingestion_runner as _runner  # noqa: F401

        application = ingestion_runner_path()

    return SparkSubmitOperator(
        task_id=task_id,
        application=str(application),
        name=f"bronze_ingest_{Path(str(config_path)).stem}",
        conn_id=pc.get("spark_conn_id", "spark_default"),
        conf=spark_conf,
        packages=pc.get("delta_packages", DEFAULT_DELTA_PACKAGES),
        driver_memory=pc.get("driver_memory", "2g"),
        executor_memory=pc.get("executor_memory", "2g"),
        executor_cores=int(pc.get("executor_cores", 1)),
        num_executors=int(pc.get("num_executors", 1)),
        application_args=[
            "--config-path",
            str(config_path),
            "--env",
            env,
            "--ds",
            ds,
        ],
        dag=dag,
    )


def ingestion_runner_path() -> Path:
    """Return the absolute path to the `ingestion_runner.py` file."""
    from patient_360.bronze import ingestion_runner

    return Path(ingestion_runner.__file__).resolve()
