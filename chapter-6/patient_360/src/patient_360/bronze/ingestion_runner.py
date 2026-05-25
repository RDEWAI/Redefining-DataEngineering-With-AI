"""Bronze ingestion runner — generic, config-driven entry point.

LLD references: §2.3 (module interface contract, 2026-05-12 pivot),
§5.1 (per-table tasks + source-selection rule),
§5.4 (inline SE), §9.1 (project-root anchoring),
§13 Decision 12 (revoked & replaced 2026-05-12 — DeltaCatalog + Hive/Derby),
§13 Decision 15 (revoked 2026-05-12 — path-based Delta writes).

# updated: 2026-05-20 (STORY-02-001 — applies the 2026-05-12 architectural
# pivot: source-derived column contract, path-based Delta writes,
# DeltaCatalog + Derby Hive metastore).

Pattern
-------
One runner drives all 13 Bronze tasks from per-table YAML in
``airflow/configs/{table}.yml``. The runner:

1. Boots a Spark session with the default ``spark_catalog`` backed by
   ``org.apache.spark.sql.delta.catalog.DeltaCatalog`` and an embedded
   Hive metastore on Derby at
   ``jdbc:derby:${P360_ROOT}/warehouse/{env}/metastore_db;create=true``
   (LLD §13 Decision 12, 2026-05-12). UC OSS is not in the write path —
   it is a UI demo only.
2. Loads the per-table YAML config and derives the column contract
   directly from the source itself: ``DESCRIBE synthea.<table>`` for
   DuckDB sources, or the CSV header for CSV sources. Bronze is a
   permissive landing zone (LLD §2.3, 2026-05-12 pivot); the DMS owns
   Silver/Gold contracts only.
3. Reads the source declared in the YAML. ``source.type=csv`` is the
   default; ``source.type=duckdb`` is allowed only for the six small
   reference tables (organizations, providers, payers, careplans,
   allergies, immunizations) whose raw CSV is < 100 MB (LLD §5.1).
4. Appends the three Bronze metadata columns — ``ds``,
   ``_ingested_at``, ``_source_batch_id`` (deterministic
   ``{table}:{ds}``).
5. Calls :func:`patient_360.utils.se_runner.run_dq` inline so row_dq /
   agg_dq run inside the same Spark action.
6. Writes via path-based Delta at
   ``${P360_ROOT}/warehouse/{env}/bronze/{table}/``
   with ``replaceWhere ds = '<ds>'`` so a re-run of one ``ds`` is
   idempotent (LLD §13 Decision 15, 2026-05-12).

SE import diagnostic (LLD §8.6 / §13 Decision 14)
-------------------------------------------------
The ``se_runner`` import is wrapped in a ``try/except ImportError`` block
purely for diagnostic logging. On ImportError the runner logs a single
ERROR-level line containing ``se_runner not available`` and re-raises.
There is no soft-degradation path — a missing SE module is a deploy
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


# LLD §2.3 — the three Bronze metadata columns. SE rules reference these
# names verbatim; renaming them requires a matching SE rules update.
METADATA_COL_DS = "ds"
METADATA_COL_INGESTED_AT = "_ingested_at"
METADATA_COL_SOURCE_BATCH_ID = "_source_batch_id"

# LLD §9.1 — Project root for resolving every relative path at runtime.
# Set by docker-compose (e.g. ``/opt/patient_360``) and consumed by
# ``_anchor_relative`` and by warehouse / metastore path construction.
PROJECT_ROOT_ENV = "PATIENT360_PROJECT_ROOT"

# Tables permitted to declare ``source.type: duckdb`` per LLD §5.1
# source-selection rule (raw CSV < 100 MB).
DUCKDB_ALLOWED_TABLES: frozenset[str] = frozenset(
    {
        "synthea_organizations",
        "synthea_providers",
        "synthea_payers",
        "synthea_careplans",
        "synthea_allergies",
        "synthea_immunizations",
    }
)


def _project_root() -> Path:
    """Return ``PATIENT360_PROJECT_ROOT`` as a Path; fall back to CWD."""
    root = os.environ.get(PROJECT_ROOT_ENV)
    return Path(root) if root else Path.cwd()


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
    parser = argparse.ArgumentParser(
        description="Generic Bronze ingestion runner (LLD §2.3, 2026-05-12 pivot)"
    )
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
# YAML loading
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
# Source-derived column contract (LLD §2.3, 2026-05-12 pivot)
# ---------------------------------------------------------------------------
def describe_duckdb_columns(
    *, database: str, query: str | None = None, table: str | None = None
) -> list[str]:
    """Return the ordered column list for a DuckDB source.

    Used purely for the source-derived Bronze column contract: we run
    ``DESCRIBE <subquery>`` against DuckDB and read back the column-name
    column. The Spark read still goes through
    :func:`spark.createDataFrame`, but the contract — what columns Bronze
    expects to land — is captured here for traceability and logging.
    """
    sql = query or (f"SELECT * FROM {table}" if table else None)
    if not sql:
        raise ValueError(
            "describe_duckdb_columns requires either `query` or `table`"
        )

    import duckdb  # type: ignore[import-not-found]

    con = duckdb.connect(database, read_only=True)
    try:
        rows = con.execute(f"DESCRIBE {sql}").fetchall()
    finally:
        con.close()
    # DuckDB DESCRIBE returns (column_name, column_type, null, key, default, extra).
    return [r[0] for r in rows]


def csv_header_columns(*, path: Path | str) -> list[str]:
    """Return the column list from a CSV header row.

    Bronze CSV sources are header-delimited; the header is the source of
    truth for the Bronze landing-zone column contract (LLD §2.3, 2026-05-12
    pivot). The read still uses ``spark.read.csv(header=True)`` so type
    inference is Spark's responsibility — Bronze does not enforce types.
    """
    import csv

    p = Path(path)
    with p.open("r", newline="") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError(f"CSV at {p} is empty; no header row") from exc
    return [h.strip() for h in header]


# ---------------------------------------------------------------------------
# Spark session — DeltaCatalog + Derby Hive metastore (LLD §13 Decision 12,
# 2026-05-12 pivot)
# ---------------------------------------------------------------------------
def build_spark(app_name: str, *, env: str = "DEV") -> Any:
    """Build a Spark session wired to DeltaCatalog + an embedded Derby
    Hive metastore.

    Per LLD §13 Decision 12 (revoked & replaced 2026-05-12):

    * ``spark.sql.catalog.spark_catalog`` =
      ``org.apache.spark.sql.delta.catalog.DeltaCatalog``
    * ``javax.jdo.option.ConnectionURL`` =
      ``jdbc:derby:${PATIENT360_PROJECT_ROOT}/warehouse/{env}/metastore_db;create=true``

    The legacy UC single-catalog wiring is intentionally absent — it is
    incompatible with Airflow 3.x embedded Spark on local FS.
    """
    from patient_360.utils.delta_helpers import build_spark_session

    return build_spark_session(app_name=app_name, env=env)


# ---------------------------------------------------------------------------
# Warehouse path (LLD §13 Decision 15, 2026-05-12 pivot)
# ---------------------------------------------------------------------------
def bronze_output_path(*, env: str, table: str) -> str:
    """Compose the path-based Delta output for a Bronze table.

    Layout per LLD §13 Decision 15 (2026-05-12):

    ``${PATIENT360_PROJECT_ROOT}/warehouse/{env}/bronze/{table}/``

    The partition (``ds=<ds>``) is NOT included in this path — partitioning
    is handled by ``partitionBy("ds")`` on the writer, and idempotency by
    ``replaceWhere``.
    """
    root = _project_root()
    return str(root / "warehouse" / env.lower() / "bronze" / table)


# ---------------------------------------------------------------------------
# Metadata columns (LLD §2.3)
# ---------------------------------------------------------------------------
def add_metadata_columns(df: Any, *, table: str, ds: str) -> Any:
    """Append the three Bronze metadata columns before write.

    ``ds`` is a string ``YYYY-MM-DD`` to match the partition column type.
    ``_ingested_at`` is the row-time timestamp.
    ``_source_batch_id`` is deterministic per ``(table, ds)`` so a re-run
    produces the same id and the SE error table dedupes cleanly.
    """
    from pyspark.sql import functions as F  # type: ignore[import-not-found]

    return (
        df.withColumn(METADATA_COL_DS, F.lit(ds))
        .withColumn(METADATA_COL_INGESTED_AT, F.current_timestamp())
        .withColumn(METADATA_COL_SOURCE_BATCH_ID, F.lit(f"{table}:{ds}"))
    )


# ---------------------------------------------------------------------------
# Source reader (LLD §5.1 source-selection rule)
# ---------------------------------------------------------------------------
def read_source(spark: Any, *, source_cfg: dict[str, Any], table: str) -> Any:
    """Read the configured source.

    Supported source types (LLD §5.1):

    * ``csv``    — DEFAULT. ``spark.read.csv(path, header=True)`` — no
      ``inferSchema``; Spark's natural string-typed read suffices for
      Bronze (permissive landing zone).
    * ``duckdb`` — only allowed for the six small reference tables listed
      in :data:`DUCKDB_ALLOWED_TABLES`. Uses the ``duckdb`` Python
      connector + ``spark.createDataFrame``.
    """
    src_type = str(source_cfg.get("type", "csv")).lower()
    if src_type == "duckdb":
        if table not in DUCKDB_ALLOWED_TABLES:
            raise ValueError(
                f"table={table!r} declares source.type=duckdb but is not in "
                f"the LLD §5.1 allow-list (raw CSV must be < 100 MB). "
                f"Allowed: {sorted(DUCKDB_ALLOWED_TABLES)}"
            )
        return _read_duckdb(spark, source_cfg=source_cfg)
    if src_type == "csv":
        path = str(_anchor_relative(source_cfg["path"]))
        header = bool(source_cfg.get("header", True))
        reader = spark.read.format("csv").option("header", "true" if header else "false")
        return reader.load(path)
    raise ValueError(f"Unsupported source type: {src_type}")


def _read_duckdb(spark: Any, *, source_cfg: dict[str, Any]) -> Any:
    """Read a DuckDB source via the ``duckdb`` Python connector.

    Returns a Spark DataFrame whose column list matches DuckDB's natural
    output (Bronze is a permissive landing zone — types are not enforced
    here per LLD §2.3 pivot).
    """
    import duckdb  # type: ignore[import-not-found]

    db_path = str(_anchor_relative(source_cfg["database"]))
    sql = source_cfg.get("query") or f"SELECT * FROM {source_cfg['table']}"
    con = duckdb.connect(db_path, read_only=True)
    try:
        arrow_tbl = con.execute(sql).fetch_arrow_table()
    finally:
        con.close()
    return spark.createDataFrame(arrow_tbl.to_pylist())


# ---------------------------------------------------------------------------
# Write — path-based Delta (LLD §13 Decision 15, 2026-05-12 pivot)
# ---------------------------------------------------------------------------
def write_bronze(df: Any, *, output_path: str, ds: str) -> None:
    """Write ``df`` to ``output_path`` with ``replaceWhere ds = '<ds>'``.

    Path-based Delta only — table-name based writes and 3-part FQNs are
    explicitly forbidden by LLD §13 Decision 15 (2026-05-12).
    """
    (
        df.write.mode("append")
        .format("delta")
        .partitionBy(METADATA_COL_DS)
        .option("replaceWhere", f"{METADATA_COL_DS} = '{ds}'")
        .save(output_path)
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run(args: argparse.Namespace) -> int:
    """Top-level orchestration — read → metadata → SE → path-based write."""
    cfg = load_yaml(args.config_path)
    table = cfg["table"]

    # Source-derived column contract (LLD §2.3 pivot). Logged for
    # traceability only; no schema enforcement — Bronze accepts whatever
    # the source emits.
    src = cfg["source"]
    src_type = str(src.get("type", "csv")).lower()
    try:
        if src_type == "duckdb":
            db_path = str(_anchor_relative(src["database"]))
            source_columns = describe_duckdb_columns(
                database=db_path,
                query=src.get("query"),
                table=src.get("table"),
            )
        else:
            source_columns = csv_header_columns(path=_anchor_relative(src["path"]))
        logger.info(
            "Source-derived contract for table=%s: %d columns: %s",
            table,
            len(source_columns),
            source_columns,
        )
    except Exception as exc:  # pragma: no cover - introspection diagnostic only
        logger.warning(
            "Could not derive source contract for table=%s: %s", table, exc
        )

    spark = build_spark(app_name=f"bronze_ingest_{table}", env=args.env)
    # Pre-create the bronze schema so any reconciliation queries that
    # reference the bronze namespace via the Hive metastore resolve.
    schema_name = cfg.get("catalog_bronze_schema", "bronze")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
    try:
        df = read_source(spark, source_cfg=src, table=table)

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

        df = add_metadata_columns(df, table=table, ds=args.ds)

        # Inline SE validation (LLD §5.1 / §5.4). action_if_failed and
        # quarantine_path are per-table fields in the YAML.
        dq_rules_dir_cfg = cfg.get("dq_rules_dir")
        df = se_runner.run_dq(
            df,
            table=table,
            env=args.env,
            dq_rules_dir=str(_anchor_relative(dq_rules_dir_cfg))
            if dq_rules_dir_cfg
            else None,
            action_if_failed=cfg.get("se_action_if_failed")
            or cfg.get("action_if_failed"),
            quarantine_path=cfg.get("quarantine_path"),
        )

        # LLD §6.5 — optional `target_partitions` knob (per-table YAML).
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
                    f"target_partitions for table={table!r} must be >= 1, "
                    f"got {n_parts}"
                )
            df = df.repartition(n_parts)

        output_path = bronze_output_path(env=args.env, table=table)
        write_bronze(df, output_path=output_path, ds=args.ds)
        logger.info(
            "Bronze ingest complete: table=%s output=%s ds=%s env=%s",
            table,
            output_path,
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
