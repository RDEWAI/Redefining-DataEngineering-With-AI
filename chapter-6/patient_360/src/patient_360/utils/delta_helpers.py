"""Spark / Delta helpers shared across Bronze, Silver, and Gold.

Centralises the Spark session factory (DeltaCatalog + embedded Derby
Hive metastore per LLD §13 Decision 12, 2026-05-12 pivot) and a small
set of Delta MERGE / replaceWhere helpers used by SCD2 and Bronze
ingestion.

A Spark session is intentionally lazy — importing this module does NOT
boot Spark. Call :func:`build_spark_session` from your entrypoint.

# updated: 2026-05-20 — UCSingleCatalog removed from the runtime path;
# Spark catalog now wires ``DeltaCatalog`` + Derby Hive metastore anchored
# at ``${PATIENT360_PROJECT_ROOT}/warehouse/{env}/`` per LLD §13 Decision
# 12 (revoked & replaced 2026-05-12).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_SPARK_DEFAULT_APP_NAME = "patient_360"

# LLD §13 Decision 12 (2026-05-12) — DeltaCatalog backed by an embedded
# Derby Hive metastore. UCSingleCatalog is intentionally absent from the
# runtime path; UC OSS is a UI demo only.
DELTA_CATALOG_CLASS = "org.apache.spark.sql.delta.catalog.DeltaCatalog"
DELTA_SQL_EXTENSIONS = "io.delta.sql.DeltaSparkSessionExtension"

# LLD §9.1 — every path is anchored against this env var at runtime.
PROJECT_ROOT_ENV = "PATIENT360_PROJECT_ROOT"


def _project_root() -> Path:
    """Return ``PATIENT360_PROJECT_ROOT`` as a Path; fall back to CWD."""
    root = os.environ.get(PROJECT_ROOT_ENV)
    return Path(root) if root else Path.cwd()


def _derby_jdo_url(env: str) -> str:
    """Compose the embedded Derby connection URL for the env's metastore."""
    metastore_dir = _project_root() / "warehouse" / env.lower() / "metastore_db"
    return f"jdbc:derby:{metastore_dir};create=true"


def _warehouse_dir(env: str) -> str:
    """Hive warehouse directory for ``env``."""
    return str(_project_root() / "warehouse" / env.lower())


def build_spark_session(
    app_name: str = _SPARK_DEFAULT_APP_NAME,
    *,
    env: str = "DEV",
    extra_conf: dict[str, Any] | None = None,
) -> Any:
    """Construct a :class:`SparkSession` wired to DeltaCatalog + Derby.

    Per LLD §13 Decision 12 (revoked & replaced 2026-05-12):

    * ``spark.sql.catalog.spark_catalog`` = ``DeltaCatalog``
    * ``spark.sql.extensions`` = ``DeltaSparkSessionExtension``
    * ``javax.jdo.option.ConnectionURL`` = embedded Derby URL anchored
      at ``${PATIENT360_PROJECT_ROOT}/warehouse/{env}/metastore_db``
    * ``spark.sql.warehouse.dir`` = ``${PATIENT360_PROJECT_ROOT}/warehouse/{env}/``

    Returns:
        A configured ``SparkSession``.

    Raises:
        RuntimeError: if pyspark is not importable.
    """
    try:
        from pyspark.sql import SparkSession  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - env-specific
        raise RuntimeError(
            "pyspark is required for build_spark_session(); "
            "install via `uv sync --all-extras`"
        ) from exc

    builder = SparkSession.builder.appName(app_name)
    builder = builder.config("spark.sql.catalog.spark_catalog", DELTA_CATALOG_CLASS)
    builder = builder.config("spark.sql.extensions", DELTA_SQL_EXTENSIONS)
    builder = builder.config("spark.sql.warehouse.dir", _warehouse_dir(env))
    builder = builder.config("javax.jdo.option.ConnectionURL", _derby_jdo_url(env))
    for key, value in (extra_conf or {}).items():
        builder = builder.config(key, value)
    return builder.getOrCreate()


def replace_where_write(
    df: Any,
    output_path: str,
    *,
    partition_col: str,
    partition_value: str,
) -> None:
    """Append ``df`` to ``output_path``, replacing the single
    ``partition_col=partition_value`` partition via path-based Delta.

    Path-based writes per LLD §13 Decision 15 (2026-05-12) — no
    ``saveAsTable``. The caller composes the absolute path under
    ``${PATIENT360_PROJECT_ROOT}/warehouse/{env}/<layer>/<table>/``.
    """
    (
        df.write.mode("append")
        .format("delta")
        .partitionBy(partition_col)
        .option("replaceWhere", f"{partition_col} = '{partition_value}'")
        .save(output_path)
    )
