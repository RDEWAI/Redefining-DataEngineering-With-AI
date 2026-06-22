"""Spark / Delta helpers shared across Bronze, Silver, and Gold.

Centralises the Spark session factory (with Unity Catalog OSS wired as a
**named side catalog** per LLD §13 Decision 12, re-adopted 2026-06-18) and
a small set of Delta MERGE / replaceWhere helpers used by SCD2 and Bronze
ingestion.

A Spark session is intentionally lazy — importing this module does NOT
boot Spark. Call :func:`build_spark_session` from your entrypoint.
"""

from __future__ import annotations

import os
from typing import Any

# Library availability is checked lazily so unit tests that don't exercise
# Spark do not require pyspark/delta-spark to be installed.
_SPARK_DEFAULT_APP_NAME = "patient_360"

# LLD §13 Decision 12 (re-adopted 2026-06-18) — the catalog wiring required
# for Unity Catalog OSS. UC is a NAMED side catalog (`unity`); the builtin
# `spark_catalog` stays bound to DeltaCatalog. UC-as-spark_catalog does NOT
# work — the named side-catalog wiring is the proven configuration.
DELTA_CATALOG_CLASS = "org.apache.spark.sql.delta.catalog.DeltaCatalog"
UC_CATALOG_CLASS = "io.unitycatalog.spark.UCSingleCatalog"
DELTA_EXTENSION_CLASS = "io.delta.sql.DeltaSparkSessionExtension"

# Name of the UC side catalog and the session default catalog.
UC_CATALOG_NAME = "unity"

# UC-OSS connection params. Env vars override the defaults so SDP / Airflow
# can point at a non-local UC in STAGING/PROD (LLD §7.1 keys
# `catalog_uc_uri`, `catalog_uc_token`, `catalog_warehouse_path`).
UC_URI_ENV = "UC_URI"
UC_TOKEN_ENV = "UC_TOKEN"
UC_WAREHOUSE_ENV = "UC_WAREHOUSE"

DEFAULT_UC_URI = "http://localhost:8080"
DEFAULT_UC_TOKEN = ""
# All path resolution is anchored to ${PATIENT360_PROJECT_ROOT} per LLD §9.1.
PROJECT_ROOT_ENV = "PATIENT360_PROJECT_ROOT"
DEFAULT_UC_WAREHOUSE_REL = "warehouse/dev"


def _resolve_uc_warehouse() -> str:
    """Resolve the UC EXTERNAL Delta warehouse path.

    Honours ``UC_WAREHOUSE`` if set (absolute or relative); otherwise
    anchors the default relative warehouse under
    ``${PATIENT360_PROJECT_ROOT}`` per LLD §9.1, falling back to CWD when
    the project-root env var is unset.
    """
    warehouse = os.environ.get(UC_WAREHOUSE_ENV)
    if warehouse:
        return warehouse
    project_root = os.environ.get(PROJECT_ROOT_ENV, os.getcwd())
    return os.path.join(project_root, DEFAULT_UC_WAREHOUSE_REL)


def build_spark_session(
    app_name: str = _SPARK_DEFAULT_APP_NAME,
    *,
    uc_uri: str | None = None,
    uc_token: str | None = None,
    uc_warehouse: str | None = None,
    extra_conf: dict[str, Any] | None = None,
) -> Any:
    """Construct a :class:`SparkSession` wired to Unity Catalog OSS.

    Per LLD §13 Decision 12 (re-adopted 2026-06-18), the builtin
    ``spark_catalog`` stays bound to ``DeltaCatalog`` and UC is added as a
    **named side catalog** ``unity`` backed by ``UCSingleCatalog`` (with
    ``.uri`` / ``.token`` / ``.warehouse``), with
    ``spark.sql.defaultCatalog=unity``. ``spark_catalog`` is **never** bound
    to ``UCSingleCatalog`` and there is **no** Derby JDBC metastore.
    ``spark.sql.sources.partitionOverwriteMode=dynamic`` is set as the
    idempotency mechanism for Bronze / Silver-fact ``insertInto`` writes
    (LLD §13 Decision 15).

    Args:
        app_name: Spark application name.
        uc_uri: UC OSS service URI; defaults to ``$UC_URI`` then localhost.
        uc_token: UC auth token; defaults to ``$UC_TOKEN`` (empty for OSS).
        uc_warehouse: EXTERNAL Delta warehouse path; defaults to
            ``$UC_WAREHOUSE`` then ``${PATIENT360_PROJECT_ROOT}/warehouse/dev``.
        extra_conf: Additional Spark conf entries applied last.

    Returns:
        A configured ``SparkSession``.

    Raises:
        RuntimeError: if pyspark is not importable.
    """
    try:
        from pyspark.sql import SparkSession  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - env-specific
        raise RuntimeError(
            "pyspark is required for build_spark_session(); install via `uv sync --all-extras`"
        ) from exc

    resolved_uri = uc_uri or os.environ.get(UC_URI_ENV, DEFAULT_UC_URI)
    resolved_token = (
        uc_token if uc_token is not None else os.environ.get(UC_TOKEN_ENV, DEFAULT_UC_TOKEN)
    )
    resolved_warehouse = uc_warehouse or _resolve_uc_warehouse()

    builder = SparkSession.builder.appName(app_name)
    # Delta is the engine catalog for the builtin namespace.
    builder = builder.config("spark.sql.catalog.spark_catalog", DELTA_CATALOG_CLASS)
    builder = builder.config("spark.sql.extensions", DELTA_EXTENSION_CLASS)
    # Unity Catalog OSS as a NAMED side catalog (never spark_catalog).
    builder = builder.config(f"spark.sql.catalog.{UC_CATALOG_NAME}", UC_CATALOG_CLASS)
    builder = builder.config(f"spark.sql.catalog.{UC_CATALOG_NAME}.uri", resolved_uri)
    builder = builder.config(f"spark.sql.catalog.{UC_CATALOG_NAME}.token", resolved_token)
    builder = builder.config(f"spark.sql.catalog.{UC_CATALOG_NAME}.warehouse", resolved_warehouse)
    builder = builder.config("spark.sql.defaultCatalog", UC_CATALOG_NAME)
    # Idempotency mechanism for Bronze / Silver-fact `insertInto` writes
    # (LLD §13 Decision 15): dynamic partition overwrite replaces only the
    # `ds` partition(s) present in the DataFrame. Never combined with
    # `replaceWhere`.
    builder = builder.config("spark.sql.sources.partitionOverwriteMode", "dynamic")
    for key, value in (extra_conf or {}).items():
        builder = builder.config(key, value)
    return builder.getOrCreate()


def read_bronze_delta(spark: Any, *, table: str, ds: str, env: str = "DEV") -> Any:
    """Read a Bronze Delta table partition for ``ds`` via UC FQN.

    Silver transforms consume Bronze through the Unity Catalog OSS ``unity``
    side catalog the Bronze writer registers into
    (``unity.bronze.<table>``); reading by FQN keeps the read path
    catalog-driven, never path-based (LLD §13 Decision 12). The ``ds`` filter
    pushes down to a single-partition scan.

    A bare ``table`` is qualified to ``unity.bronze.<table>``; a name that
    already contains dots is passed through unchanged. ``env`` is accepted
    for signature symmetry with the writers; the catalog is selected by the
    active Spark session, not by this helper.
    """
    fqn = table if "." in table else f"{UC_CATALOG_NAME}.bronze.{table}"
    return spark.read.table(fqn).where(f"ds = '{ds}'")
