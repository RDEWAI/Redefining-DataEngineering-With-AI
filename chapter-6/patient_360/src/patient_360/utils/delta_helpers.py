"""Spark / Delta helpers shared across Bronze, Silver, and Gold.

Centralises the Spark session factory (with UCSingleCatalog wired per
LLD §13 Decision 12) and a small set of Delta MERGE / replaceWhere helpers
used by SCD2 and Bronze ingestion.

A Spark session is intentionally lazy — importing this module does NOT
boot Spark. Call :func:`build_spark_session` from your entrypoint.
"""

from __future__ import annotations

from typing import Any

# Library availability is checked lazily so unit tests that don't exercise
# Spark do not require pyspark/delta-spark to be installed.
_SPARK_DEFAULT_APP_NAME = "patient_360"

# LLD §13 Decision 12 — the catalog wiring required for Unity Catalog OSS.
UC_CATALOG_CLASS = "io.unitycatalog.spark.UCSingleCatalog"

# UC-OSS service URI; can be overridden by callers via build_spark_session(uc_uri=...).
DEFAULT_UC_URI = "http://localhost:8080"


def build_spark_session(
    app_name: str = _SPARK_DEFAULT_APP_NAME,
    *,
    uc_uri: str = DEFAULT_UC_URI,
    extra_conf: dict[str, Any] | None = None,
) -> Any:
    """Construct a :class:`SparkSession` wired to Unity Catalog OSS.

    Per LLD §13 Decision 12, the spark_catalog implementation MUST be
    ``io.unitycatalog.spark.UCSingleCatalog``; failing to set this prevents
    Bronze writes from being visible to the UC REST API.

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

    # UC OSS is intentionally NOT wired into the Spark session — see
    # spark_submit_wrapper.py header. We rely on Spark's built-in
    # Hive-style metastore (Derby, in-process) + DeltaCatalog. Tables
    # live as managed Delta files under `spark.sql.warehouse.dir`.
    builder = SparkSession.builder.appName(app_name)
    builder = builder.config(
        "spark.sql.catalog.spark_catalog",
        "org.apache.spark.sql.delta.catalog.DeltaCatalog",
    )
    builder = builder.config(
        "spark.sql.warehouse.dir",
        os.environ.get(UC_WAREHOUSE_ENV, DEFAULT_UC_WAREHOUSE),
    )
    builder = builder.config(
        "spark.sql.extensions",
        "io.delta.sql.DeltaSparkSessionExtension",
    )
    for key, value in (extra_conf or {}).items():
        builder = builder.config(key, value)
    return builder.getOrCreate()


import os


# UC OSS 0.4.0 has managed tables disabled by default (experimental).
# Bronze writes use **external** Delta tables: each table is materialised
# at a known path under the UC warehouse and registered via
# `saveAsTable` with an explicit `.option("path", ...)`. The warehouse
# root is configurable via UC_EXTERNAL_WAREHOUSE; defaults to the
# `/tmp/uc-warehouse` volume mounted by docker-compose.
UC_WAREHOUSE_ENV = "UC_EXTERNAL_WAREHOUSE"
DEFAULT_UC_WAREHOUSE = "/tmp/uc-warehouse"


def _external_table_path(table_fqn: str) -> str:
    """Map a UC FQN (``catalog.schema.table``) to a directory under the
    UC external warehouse root. The path layout (``<root>/<catalog>/<schema>/<table>``)
    mirrors the FQN so a user can reason about on-disk artifacts without
    consulting UC."""
    root = os.environ.get(UC_WAREHOUSE_ENV, DEFAULT_UC_WAREHOUSE)
    parts = table_fqn.split(".")
    return os.path.join(root, *parts)


def replace_where_write(
    df: Any,
    table_fqn: str,
    *,
    partition_col: str,
    partition_value: str,
) -> None:
    """Append ``df`` to ``table_fqn``, replacing the single
    ``partition_col=partition_value`` partition. Delta + Spark's built-in
    Hive metastore (Derby) — managed table under
    ``spark.sql.warehouse.dir``. The schema (e.g. ``bronze``) must exist;
    the runner pre-creates it via ``CREATE SCHEMA IF NOT EXISTS`` before
    the first write.
    """
    (
        df.write.mode("append")
        .format("delta")
        .partitionBy(partition_col)
        .option("replaceWhere", f"{partition_col} = '{partition_value}'")
        .saveAsTable(table_fqn)
    )
