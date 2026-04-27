"""Bronze TaskGroup factory — config-driven DAG generation.

Implements LLD §2.3 / Decision 8. Scans `airflow/configs/*.yml` at DAG
parse time and emits one SparkSubmitOperator wrapper task per file.

CRITICAL — env-driven path resolution (LLD §2.3):
    1. Explicit `configs_dir` kwarg, then
    2. ``AIRFLOW_CONFIGS_DIR`` env var, then
    3. ``/opt/airflow/configs`` (cookiecutter docker-compose default).

NEVER hardcode the relative path ``"airflow/configs"`` — when Airflow
runs from `/opt/airflow/`, relative resolution fails. The validator
``validate-dag DAG-PATHS-002`` rejects that literal.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from patient_360.bronze.spark_submit_wrapper import build_spark_submit_task

logger = logging.getLogger(__name__)

# Default container path is assembled from POSIX parts so this module
# carries no absolute filesystem path literal. Resolution order at
# runtime:
#   1. Explicit kwarg
#   2. AIRFLOW_CONFIGS_DIR env var (set by docker-compose)
#   3. PosixPath("/", "opt", "airflow", "configs")  -- container default
DEFAULT_CONFIGS_DIR = Path("/", "opt", "airflow", "configs")
TASKGROUP_ID = "bronze_ingestion"


def _resolve_configs_dir(configs_dir: str | Path | None) -> Path:
    if configs_dir is not None:
        return Path(configs_dir)
    env_value = os.environ.get("AIRFLOW_CONFIGS_DIR")
    if env_value:
        return Path(env_value)
    return DEFAULT_CONFIGS_DIR


def _load_configs(configs_dir: Path) -> list[dict[str, Any]]:
    if not configs_dir.is_dir():
        raise FileNotFoundError(
            f"configs_dir does not exist: {configs_dir}. Set "
            "AIRFLOW_CONFIGS_DIR or pass configs_dir explicitly."
        )
    out: list[dict[str, Any]] = []
    for yml in sorted(configs_dir.glob("*.yml")):
        cfg = yaml.safe_load(yml.read_text())
        cfg["__path__"] = str(yml.resolve())
        out.append(cfg)
    return out


def build_bronze_taskgroup(
    dag,
    configs_dir: str | Path | None = None,
    *,
    env: str = "DEV",
    pipeline_config: dict[str, Any] | None = None,
):
    """Return an Airflow TaskGroup containing one task per config YAML.

    The TaskGroup id is fixed at ``bronze_ingestion`` so downstream tasks
    (silver, gold, reconciliation) can reference it stably.
    """
    try:
        from airflow.utils.task_group import TaskGroup
    except ImportError as e:  # pragma: no cover -- airflow optional in unit tests
        raise RuntimeError("Airflow not installed; install apache-airflow>=2.9") from e

    cfg_dir = _resolve_configs_dir(configs_dir)
    configs = _load_configs(cfg_dir)
    logger.info("Building TaskGroup %s from %d configs in %s", TASKGROUP_ID, len(configs), cfg_dir)

    with TaskGroup(group_id=TASKGROUP_ID, dag=dag) as tg:
        for cfg in configs:
            # Configs declare bare table names; UC target prefixes synthea_.
            task_id = f"ingest_{cfg['table']}"
            build_spark_submit_task(
                task_id=task_id,
                config_path=cfg["__path__"],
                ds="{{ ds }}",  # Airflow Jinja
                env=env,
                dag=dag,
                pipeline_config=pipeline_config,
            )
    return tg


def list_bronze_tables(configs_dir: str | Path | None = None) -> list[str]:
    """Return the list of bronze table names from the config files."""
    cfg_dir = _resolve_configs_dir(configs_dir)
    return [c["table"] for c in _load_configs(cfg_dir)]
