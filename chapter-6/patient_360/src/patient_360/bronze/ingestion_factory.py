"""Bronze TaskGroup factory — LLD §2.3, §4.2, §6.1, §13 Decision 8.

# created: 2026-05-11

Pattern
-------
At DAG parse time, scan ``airflow/configs/*.yml`` (deterministic order) and
emit one :class:`SparkSubmitOperator` per file inside a TaskGroup named
``bronze_ingestion``. Adding a 14th source table = one YAML drop; no DAG
edit (LLD §13 Decision 8 — TaskGroup with Factory).

Path resolution
---------------
``configs_dir`` is resolved in this order (matches the LLD §2.3 contract
and the ingestion runner's ``DQ_RULES_DIR`` pattern):

1. Explicit ``configs_dir`` kwarg.
2. ``AIRFLOW_CONFIGS_DIR`` env var (the canonical container path injected
   by the cookiecutter ``docker-compose.yml``).
Missing env raises ``RuntimeError`` (no source-baked default).

Never hardcode a relative path like ``airflow/configs`` -- when Airflow
parses DAGs from ``/opt/airflow/dags/``, a relative path resolves against
``/opt/airflow/`` and silently yields zero tasks. The validator's
``DAG-PATHS-002`` rule rejects DAG files containing
``configs_dir="airflow/configs"``.

Pipeline config (compute knobs)
-------------------------------
LLD §6.1 driver/executor memory/cores live in ``config-template.yaml``
under ``compute_spark_*``. The factory forwards the caller-supplied
``pipeline_cfg`` mapping straight to
:func:`spark_submit_wrapper.build_spark_submit_task`, which translates it
to SparkSubmit CLI flags. If the caller omits ``pipeline_cfg`` the
wrapper falls back to its built-in defaults (so a smoke DAG still parses).

Task id convention
------------------
``ingest_<stem>`` where ``<stem>`` is the YAML filename without
``.yml`` (e.g. ``patients.yml`` -> ``ingest_patients``). Stems are sorted
so task ids are stable across Airflow scheduler restarts (predictable
downstream wiring -- LLD §13 Decision 8 trade-off note).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# LLD §9.1 (post-v1.12) — paths come from the env / explicit args only.
# Source-baked absolute defaults are forbidden by the validator
# DAG-PATHS-001 rule because they silently work in one container layout
# and break in another.
CONFIGS_DIR_ENV = "AIRFLOW_CONFIGS_DIR"

# Airflow TaskGroup name (LLD §4.2). Downstream tasks reference this id
# in their ``depends_on`` lists; do not rename without updating the DAG.
TASKGROUP_ID = "bronze_ingestion"

# Per-table YAML extension. Both ``.yml`` and ``.yaml`` are accepted at
# parse time so a stray ``.yaml`` from a hand-written contract doesn't
# silently drop a table (LLD §5.1 mandates 13 tasks).
CONFIG_GLOBS: tuple[str, ...] = ("*.yml", "*.yaml")


def _resolve_configs_dir(configs_dir: str | os.PathLike[str] | None) -> Path:
    """Return the absolute configs directory per the LLD §9.1 contract.

    Resolution order:
      1. explicit kwarg
      2. ``AIRFLOW_CONFIGS_DIR`` env var

    Raises ``RuntimeError`` when neither is supplied — no source-baked
    default (DAG-PATHS-001).
    """
    if configs_dir is not None:
        return Path(configs_dir)

    env_val = os.environ.get(CONFIGS_DIR_ENV)
    if not env_val:
        raise RuntimeError(
            f"configs_dir not provided and {CONFIGS_DIR_ENV} is unset — "
            "set the env var in docker-compose / Airflow worker env"
        )
    return Path(env_val)


def _discover_config_files(configs_dir: Path) -> list[Path]:
    """Return the sorted list of per-table YAML configs.

    Sorted by filename stem so the resulting TaskGroup has deterministic
    task ids across DAG parses. Hidden files (``.``-prefixed) are
    ignored so editor scratch files cannot inject phantom tasks.
    """
    if not configs_dir.exists():
        logger.warning(
            "Bronze configs dir does not exist: %s — TaskGroup will be empty",
            configs_dir,
        )
        return []
    if not configs_dir.is_dir():
        raise NotADirectoryError(f"configs_dir must be a directory, got: {configs_dir}")

    found: dict[str, Path] = {}
    for pattern in CONFIG_GLOBS:
        for f in configs_dir.glob(pattern):
            if f.name.startswith("."):
                continue
            # Prefer .yml over .yaml when both exist for the same stem so
            # we never emit two tasks for the same table.
            if f.stem not in found or f.suffix == ".yml":
                found[f.stem] = f

    return [found[stem] for stem in sorted(found)]


def _task_id_for(config_file: Path) -> str:
    """Derive an Airflow task id from a per-table YAML filename."""
    return f"ingest_{config_file.stem}"


def build_bronze_taskgroup(
    dag: Any,
    configs_dir: str | os.PathLike[str] | None = None,
    *,
    pipeline_cfg: Mapping[str, Any] | None = None,
    spark_conn_id: str = "spark_default",
    operator_kwargs: Mapping[str, Any] | None = None,
) -> Any:
    """Build the ``bronze_ingestion`` TaskGroup for the given DAG.

    Parameters
    ----------
    dag
        Airflow DAG the TaskGroup attaches to.
    configs_dir
        Optional override for the per-table YAML directory. Defaults to
        ``$AIRFLOW_CONFIGS_DIR``; missing env raises ``RuntimeError``.
    pipeline_cfg
        LLD §7 pipeline config (compute knobs, ingestion entry point).
        Forwarded to :func:`spark_submit_wrapper.build_spark_submit_task`.
        ``None`` is accepted so a smoke DAG can parse before the runtime
        config exists; the wrapper applies safe defaults in that case.
    spark_conn_id
        Airflow Spark connection id. Per-env DAG factories override.
    operator_kwargs
        Optional passthrough for retries/timeout (LLD §4.2 / §8.1).
        Applied uniformly to every task. The wrapper drops any keys it
        owns (memory/cores/conf/application/...).

    Returns
    -------
    TaskGroup
        Airflow TaskGroup containing one SparkSubmitOperator per YAML.
        Empty TaskGroup is returned if ``configs_dir`` has no YAMLs
        (logged at WARNING level so the DAG still parses).
    """
    # Local imports so this module stays importable in non-Airflow
    # contexts (pure-Python unit tests).
    from airflow.sdk import TaskGroup  # type: ignore[import-not-found]

    from patient_360.bronze.spark_submit_wrapper import build_spark_submit_task

    resolved_dir = _resolve_configs_dir(configs_dir)
    config_files = _discover_config_files(resolved_dir)
    pipeline_cfg = pipeline_cfg or {}

    logger.info(
        "Building bronze_ingestion TaskGroup from %s (%d config(s))",
        resolved_dir,
        len(config_files),
    )

    with TaskGroup(group_id=TASKGROUP_ID, dag=dag) as tg:
        for config_file in config_files:
            build_spark_submit_task(
                task_id=_task_id_for(config_file),
                config_path=str(config_file),
                pipeline_cfg=pipeline_cfg,
                spark_conn_id=spark_conn_id,
                operator_kwargs=operator_kwargs,
            )

    return tg
