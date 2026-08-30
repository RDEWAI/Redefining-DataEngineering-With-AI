"""Bronze ingestion runner — generic, config-driven entry point.

LLD references: §2.3 (module interface contract), §5.1 (per-table tasks +
source-selection rule), §5.4 (inline SE), §9.1 (path anchoring),
§13 Decision 12 (named UC side catalog) & Decision 15 (insertInto into the
Liquibase-pre-created UC EXTERNAL Delta table) — both re-adopted 2026-06-18.

# updated: 2026-06-19 (LLD §2.3 change log 1.19 — add_metadata_columns now
# emits four metadata columns: `_source_file` (per-table source.path) added
# for source lineage + Liquibase DDL arity parity)
# updated: 2026-06-18 (STORY-02-001 re-adoption — Bronze contract is now
# SOURCE-DERIVED, not schema-enforced from contracts/{table}.yml
# (Bronze is a permissive landing zone per LLD §2.3); the write targets the
# pre-created `unity.bronze.<table>` via
# `df.write.mode("overwrite").insertInto(...)` with idempotency from dynamic
# partition overwrite (`spark.sql.sources.partitionOverwriteMode=dynamic`) —
# NOT `replaceWhere`, which `insertInto` silently ignores (LLD §13 Decision
# 12/15, change log 1.14) — the runner NEVER creates the table (the named UC
# side catalog rejects CTAS/RTAS / create-table writes).

Pattern
-------
One runner drives all 13 Bronze tasks from per-table YAML in
``airflow/configs/{table}.yml``. The runner:

1. Boots a Spark session via :func:`patient_360.utils.delta_helpers.build_spark_session`,
   which wires ``spark.sql.catalog.spark_catalog=DeltaCatalog`` **plus** a
   named side catalog ``spark.sql.catalog.unity=UCSingleCatalog``
   (``.uri`` / ``.token`` / ``.warehouse``) with
   ``spark.sql.defaultCatalog=unity`` (LLD §13 Decision 12, re-adopted
   2026-06-18). The builtin ``spark_catalog`` stays bound to Delta — never to
   the UC catalog class. All paths anchor against ``PATIENT360_PROJECT_ROOT``
   (LLD §9.1).
2. Reads the source declared in the YAML. Per the LLD §5.1 source-selection
   rule, ``source.type=csv`` is the default; ``source.type=duckdb`` is
   reserved for the small reference tables whose raw CSV is < 100 MB.
3. Enforces a **source-derived** column contract — Bronze is a permissive
   landing zone (LLD §2.3). The column list comes from the source itself
   (DuckDB ``DESCRIBE`` / CSV header), NOT from a hand-written schema
   in ``contracts/{table}.yml``. The DMS owns Silver/Gold contracts only.
4. Appends the four Bronze metadata columns (LLD §2.3, change log 1.19) --
   ``ds`` (string ``YYYY-MM-DD``), ``_ingested_at`` (TimestampType),
   ``_source_batch_id`` (StringType, deterministic ``{table}:{ds}``), and
   ``_source_file`` (StringType, the per-table ``source.path`` for lineage —
   matches the ``_source_file STRING`` column in the Bronze Liquibase DDL).
5. Calls :func:`patient_360.utils.se_runner.run_dq` inline so row_dq /
   agg_dq run inside the same Spark action.
6. Writes via ``df.write.mode("overwrite").insertInto("unity.bronze.<table>")``;
   idempotency for a re-run of one ``ds`` comes from **dynamic partition
   overwrite** (``spark.sql.sources.partitionOverwriteMode=dynamic``, set on
   the session by ``build_spark_session``) — **NOT** ``replaceWhere``, which
   ``insertInto`` silently ignores (it appended/doubled data on re-run; LLD
   §13 Decision 15, change log 1.14). The ``unity.bronze.<table>`` table is
   pre-created as EXTERNAL Delta by Liquibase (``make ddl-apply``); the runner
   **never** creates it. Create-table writes (CTAS / RTAS) and path-based
   warehouse writes are forbidden (LLD §13 Decision 12/15; validator
   ``UC-WIRING-001``).

SE import diagnostic (LLD §8.6 / §13 Decision 14)
-------------------------------------------------
The ``se_runner`` import is wrapped in a ``try/except ImportError`` block
**purely for diagnostic logging**. On ImportError the runner logs a single
ERROR-level line containing ``se_runner not available`` and re-raises.
There is no soft-degradation path -- a missing SE module is a deploy
error, not a runtime condition.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# LLD §8.6 / §13 Decision 14 — fail-closed SE import wrapper. The
# ImportError is re-raised; the try/except exists so a deployment with a
# broken SE install surfaces a readable diagnostic above the stack trace.
try:
    from patient_360.utils import se_runner  # noqa: F401  — re-exported for callers
except ImportError as exc:
    logger.error(
        "se_runner not available — fail-closed; deployment is broken: %s",
        exc,
    )
    raise


# LLD §13 Decision 12 (re-adopted 2026-06-18) — catalog wiring class names.
# Referenced here (and in delta_helpers) so a reader / the validator can see
# the runner is built on the named-side-catalog contract: the builtin
# spark_catalog is bound to DeltaCatalog while the UC catalog class backs the
# named `unity` side catalog, with defaultCatalog=unity.
SPARK_CATALOG_CLASS = "org.apache.spark.sql.delta.catalog.DeltaCatalog"
UC_CATALOG_CLASS = "io.unitycatalog.spark.UCSingleCatalog"
UC_CATALOG_NAME = "unity"

# LLD §7.1 — the UC service URI is sourced from the env var injected by
# the cookiecutter docker-compose `airflow` service. The literal default
# is the in-cluster service name; tests override via the env var.
UC_URI_ENV = "UC_URI"
DEFAULT_UC_URI = "http://unity-catalog:8080"

# LLD §2.3 (change log 1.19, 2026-06-19) — the four Bronze metadata columns.
# SE rules reference these names verbatim; renaming them requires a matching
# SE rules update. `_source_file` carries the per-table source path/URI for
# lineage and matches the `_source_file STRING` column pre-created in the
# Bronze Liquibase changelog DDL (omitting it triggers
# DELTA_INSERT_COLUMN_ARITY_MISMATCH on insertInto).
METADATA_COL_DS = "ds"
METADATA_COL_INGESTED_AT = "_ingested_at"
METADATA_COL_SOURCE_BATCH_ID = "_source_batch_id"
METADATA_COL_SOURCE_FILE = "_source_file"

# LLD §9.1 — project root for resolving relative source / dq_rules paths
# inside spark-submit (CWD is unreliable). Set by docker-compose
# (e.g. `/opt/patient_360`) and consumed by `_anchor_relative`. The Spark
# session warehouse root (build_spark_session) anchors against the same var.
PROJECT_ROOT_ENV = "PATIENT360_PROJECT_ROOT"


def _anchor_relative(path_str: str) -> Path:
    """Resolve ``path_str``; if relative and ``PATIENT360_PROJECT_ROOT`` is
    set, anchor against it. Absolute paths are returned as-is. Falls back
    to CWD when the env var is unset (matches local-dev pytest behaviour).
    """
    p = Path(path_str)
    if p.is_absolute():
        return p
    root = os.environ.get(PROJECT_ROOT_ENV)
    if root:
        return Path(root) / p
    return p


# ---------------------------------------------------------------------------
# Argparse
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI args.

    The runner is invoked from a SparkSubmitOperator wrapper that always
    passes ``--config-path`` and ``--ds``. ``--env`` defaults to ``DEV``
    so local pytest runs work without extra wiring.
    """
    parser = argparse.ArgumentParser(description="Generic Bronze ingestion runner (LLD §2.3)")
    parser.add_argument(
        "--config-path",
        required=True,
        help="Per-table YAML config (e.g. airflow/configs/patients.yml)",
    )
    parser.add_argument(
        "--ds",
        required=True,
        help="Logical date YYYY-MM-DD; partition value for the write",
    )
    parser.add_argument(
        "--env",
        default=os.environ.get("PIPELINE_ENV", "DEV"),
        choices=["DEV", "STAGING", "PROD"],
        help="Pipeline environment; mapped to SE dq_env by se_runner",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------
def load_yaml(path: Path | str) -> dict[str, Any]:
    """Safe-load a YAML file into a dict; raise if the file is missing."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"YAML config not found: {p}")
    data = yaml.safe_load(p.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping at top-level of {p}, got {type(data)}")
    return data


# ---------------------------------------------------------------------------
# Spark session
# ---------------------------------------------------------------------------
def build_spark(app_name: str, *, uc_uri: str | None = None) -> Any:
    """Build a Spark session wired to Unity Catalog OSS as a named side catalog.

    Delegates to :func:`patient_360.utils.delta_helpers.build_spark_session`,
    which sets ``spark.sql.catalog.spark_catalog=DeltaCatalog`` plus a named
    ``spark.sql.catalog.unity=UCSingleCatalog`` side catalog (with
    ``.uri`` / ``.token`` / ``.warehouse``) and ``spark.sql.defaultCatalog=unity``
    per LLD §13 Decision 12 (re-adopted 2026-06-18). The UC service URI is
    sourced from the ``UC_URI`` env var; the warehouse root is anchored
    against ``PATIENT360_PROJECT_ROOT`` (LLD §9.1). ``spark_catalog`` is
    never bound to ``UCSingleCatalog``.
    """
    from patient_360.utils.delta_helpers import build_spark_session

    resolved_uri = uc_uri or os.environ.get(UC_URI_ENV, DEFAULT_UC_URI)
    return build_spark_session(app_name=app_name, uc_uri=resolved_uri)


# ---------------------------------------------------------------------------
# Metadata columns (LLD §2.3)
# ---------------------------------------------------------------------------
def add_metadata_columns(df: Any, *, table: str, ds: str, source_file: str | None = None) -> Any:
    """Append the four Bronze metadata columns before write (LLD §2.3, 1.19).

    ``ds`` is a string ``YYYY-MM-DD`` to match the partition column type.
    ``_ingested_at`` is the row-time timestamp.
    ``_source_batch_id`` is deterministic per ``(table, ds)`` so a re-run
    produces the same id and the SE error table dedupes cleanly.
    ``_source_file`` is the per-table ``source.path`` the rows were ingested
    from (source lineage). It matches the ``_source_file STRING`` column
    pre-created in the Bronze Liquibase changelog DDL — emitting only three
    columns triggers ``DELTA_INSERT_COLUMN_ARITY_MISMATCH`` on ``insertInto``.
    A ``None`` ``source_file`` is written as a SQL NULL so the column arity
    still matches the pre-created table.
    """
    from pyspark.sql import functions as F  # type: ignore[import-not-found]

    return (
        df.withColumn(METADATA_COL_DS, F.lit(ds))
        .withColumn(METADATA_COL_INGESTED_AT, F.current_timestamp())
        .withColumn(METADATA_COL_SOURCE_BATCH_ID, F.lit(f"{table}:{ds}"))
        .withColumn(
            METADATA_COL_SOURCE_FILE,
            F.lit(source_file).cast("string"),
        )
    )


# ---------------------------------------------------------------------------
# Source reader (LLD §2.3 — source-derived column contract, no hand schema)
# ---------------------------------------------------------------------------
def read_source(spark: Any, *, source_cfg: dict[str, Any]) -> Any:
    """Read the configured source — Bronze is a permissive landing zone.

    The column contract is **source-derived** (LLD §2.3): the runner reflects
    whatever columns the source emits rather than enforcing a hand-written
    schema. Supported source types (LLD §5.1 source-selection rule):

    * ``csv``  -- the default. Read via the CSV header so the column list is
      derived from the source; types are inferred then pinned by Spark.
    * ``duckdb`` -- reserved for small reference tables (< 100 MB raw CSV).
      The ``duckdb`` connector returns an Arrow table whose column set is
      derived from ``DESCRIBE``/``SELECT *``; ``spark.createDataFrame``
      preserves it.
    * ``parquet`` -- read via ``spark.read.parquet`` (schema-on-read).

    No fixed-schema enforcement is applied — that is the Silver/Gold contract
    layer's job, not Bronze's.
    """
    src_type = source_cfg.get("type", "csv").lower()
    if src_type == "csv":
        reader = spark.read.format("csv")
        # Header drives the source-derived column contract; inferSchema pins
        # types from a sample (Bronze landing zone — permissive).
        reader = reader.option("header", "true" if source_cfg.get("header", True) else "false")
        reader = reader.option("inferSchema", "true")
        return reader.load(str(_anchor_relative(source_cfg["path"])))
    if src_type == "duckdb":
        return _read_duckdb(spark, source_cfg=source_cfg)
    if src_type == "parquet":
        return spark.read.format("parquet").load(str(_anchor_relative(source_cfg["path"])))
    raise ValueError(f"Unsupported source type: {src_type}")


def _read_duckdb(spark: Any, *, source_cfg: dict[str, Any]) -> Any:
    """Read a DuckDB table via the ``duckdb`` Python connector.

    The column contract is source-derived: ``SELECT *`` (or an explicit
    ``query``) returns whatever the DuckDB source emits. The connector
    returns an Arrow table that ``spark.createDataFrame`` accepts directly —
    no fixed schema is imposed (LLD §2.3, Bronze landing zone).
    """
    import duckdb  # type: ignore[import-not-found]

    # Anchor relative DB paths against ``PATIENT360_PROJECT_ROOT`` so the
    # spark-submit subprocess (CWD = /opt/airflow) doesn't shadow the
    # actual mount under /opt/patient_360.
    db_path = str(_anchor_relative(source_cfg["database"]))
    sql = source_cfg.get("query") or f"SELECT * FROM {source_cfg['table']}"
    con = duckdb.connect(db_path, read_only=True)
    try:
        arrow_tbl = con.execute(sql).fetch_arrow_table()
    finally:
        con.close()
    # createDataFrame from Arrow → column contract is whatever the source
    # described; no fixed-schema enforcement (Bronze permissive landing zone).
    return spark.createDataFrame(arrow_tbl.to_pylist())


# ---------------------------------------------------------------------------
# Write (LLD §13 Decision 12/15 — insertInto the pre-created UC table)
# ---------------------------------------------------------------------------
def compose_target_table(cfg: dict[str, Any]) -> str:
    """Compose the 3-part UC table name ``unity.<schema>.<table>`` from config.

    The Spark session wires UC as a **named side catalog** (``unity``) with
    ``spark.sql.defaultCatalog=unity`` (LLD §13 Decision 12, re-adopted
    2026-06-18), so the fully-qualified ``unity.bronze.<table>`` name resolves
    through UC. The catalog/schema are read from config keys — no hardcoded
    ``unity.bronze`` literal — so an alternate catalog works without code
    changes (validator ``UC-WIRING-001``).
    """
    try:
        catalog = cfg["catalog_bronze_catalog_name"]
        schema = cfg["catalog_bronze_schema"]
        table = cfg["table"]
    except KeyError as exc:
        raise KeyError(
            "Per-table YAML must declare catalog_bronze_catalog_name, "
            "catalog_bronze_schema and table (LLD §7.1 / §13 Decision 12)"
        ) from exc
    return f"{catalog}.{schema}.{table}"


def write_bronze(df: Any, *, target_table: str, ds: str) -> None:
    """Write ``df`` into the pre-created ``target_table`` via ``insertInto``.

    The ``unity.bronze.<table>`` table is pre-created as EXTERNAL Delta by
    Liquibase (``make ddl-apply``); the runner **never** creates it. The
    write uses
    ``df.write.mode("overwrite").insertInto(target_table)`` and idempotency for
    a single ``ds`` comes from **dynamic partition overwrite**
    (``spark.sql.sources.partitionOverwriteMode=dynamic``, set on the Spark
    session by ``delta_helpers.build_spark_session``) — which replaces only the
    in-DataFrame ``ds`` partition(s) and preserves the rest (LLD §13 Decision
    15, re-adopted 2026-06-18).

    ``.option("replaceWhere", ...)`` is deliberately **NOT** used:
    ``insertInto`` silently ignores ``replaceWhere`` (it only applies to
    ``.save()`` / ``.saveAsTable()``), so combining them appended/doubled data
    on every re-run (empirically confirmed via Delta ``DESCRIBE HISTORY``); the
    two also cannot coexist (``DELTA_REPLACE_WHERE_WITH_DYNAMIC_PARTITION_OVERWRITE``).
    Create-table writes (CTAS / RTAS) are rejected by the named UC side
    catalog, and path-based warehouse writes are forbidden by
    ``validate-dag UC-WIRING-001``.
    """
    # ``ds`` is unused as a filter here: idempotency is provided solely by
    # dynamic partition overwrite, which targets the partition value carried in
    # the DataFrame's ``ds`` column (added by ``add_metadata_columns``).
    del ds
    df.write.mode("overwrite").insertInto(target_table)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run(args: argparse.Namespace) -> int:
    """Top-level orchestration -- read → metadata → SE → insertInto."""
    cfg = load_yaml(args.config_path)
    table = cfg["table"]

    spark = build_spark(app_name=f"bronze_ingest_{table}")
    try:
        # Source-derived contract (LLD §2.3): read whatever the source emits;
        # no fixed-schema enforcement — Bronze is a permissive landing zone.
        df = read_source(spark, source_cfg=cfg["source"])

        if df.rdd.isEmpty():
            behavior = cfg.get("empty_input_behavior", "write_empty")
            if behavior == "fail":
                raise RuntimeError(
                    f"Source for table={table!r} produced 0 rows and "
                    "empty_input_behavior=fail (LLD §2.3 / §5.1)"
                )
            logger.warning(
                "Source for table=%s produced 0 rows; behavior=%s",
                table,
                behavior,
            )

        # `_source_file` lineage column (LLD §2.3, 1.19) — read from the
        # per-table `source.path` (e.g. `data/raw_delta/patients.csv`). DuckDB
        # sources expose `database`/`table` instead of `path`; fall back to
        # those so the column is always populated, never silently NULL.
        source_cfg = cfg["source"]
        source_file = source_cfg.get("path") or source_cfg.get("database")
        df = add_metadata_columns(df, table=table, ds=args.ds, source_file=source_file)

        # Inline SE validation (LLD §5.1 / §5.4). action_if_failed and
        # quarantine_path are per-table fields in the YAML.
        dq_rules_dir_cfg = cfg.get("dq_rules_dir")
        df = se_runner.run_dq(
            df,
            table=table,
            env=args.env,
            dq_rules_dir=str(_anchor_relative(dq_rules_dir_cfg)) if dq_rules_dir_cfg else None,
            action_if_failed=cfg.get("action_if_failed") or cfg.get("se_action_if_failed"),
            quarantine_path=cfg.get("quarantine_path"),
        )

        # LLD §6.5 — optional `target_partitions` knob (per-table YAML).
        # When present, repartition before write so Delta lays down N files
        # per `ds`. `synthea_observations` uses 8; other tables default to
        # Spark's natural partitioning (no repartition).
        target_partitions = cfg.get("target_partitions")
        if target_partitions is not None:
            try:
                n_parts = int(target_partitions)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"target_partitions for table={table!r} must be an int, "
                    f"got {target_partitions!r}"
                ) from exc
            if n_parts < 1:
                raise ValueError(
                    f"target_partitions for table={table!r} must be >= 1, got {n_parts}"
                )
            df = df.repartition(n_parts)

        target_table = compose_target_table(cfg)
        write_bronze(df, target_table=target_table, ds=args.ds)
        logger.info(
            "Bronze ingest complete: table=%s target=%s ds=%s env=%s",
            table,
            target_table,
            args.ds,
            args.env,
        )
        return 0
    finally:
        spark.stop()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return run(parse_args(argv))


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
