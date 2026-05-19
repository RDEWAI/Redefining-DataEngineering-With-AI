"""Bronze ingestion runner — generic, config-driven entry point.

LLD references: §2.3 (module interface contract), §5.1 (per-table tasks),
§5.4 (inline SE), §7.1 (UC params), §13 Decision 15 (UC-managed writes).

# updated: 2026-05-11 (STORY-02-007 — honor optional `target_partitions` from
# per-table YAML to control output partition count before the Delta write,
# per LLD §6.5 Partition Tuning).

Pattern
-------
One runner drives all 13 Bronze tasks from per-table YAML in
``airflow/configs/{table}.yml``. The runner:

1. Boots a Spark session wired to Unity Catalog OSS via UCSingleCatalog
   (``UC_URI`` env var, LLD §7.1).
2. Loads the per-table YAML config and the matching ``contracts/{table}.yml``
   StructType (no schema inference at read time, LLD §2.3).
3. Reads the source declared in the YAML (DuckDB / Parquet / CSV).
4. Appends the three Bronze metadata columns -- ``ds`` (string
   ``YYYY-MM-DD``), ``_ingested_at`` (TimestampType), ``_source_batch_id``
   (StringType, deterministic ``{table}:{ds}``).
5. Calls :func:`patient_360.utils.se_runner.run_dq` inline so row_dq /
   agg_dq run inside the same Spark action.
6. Writes via ``saveAsTable(f"{catalog}.{schema}.{table}")`` with
   ``replaceWhere`` so a re-run of one ``ds`` is idempotent. The
   ``{catalog}.{schema}`` triple is composed at runtime from the
   ``catalog_bronze_catalog_name`` and ``catalog_bronze_schema`` config
   keys -- no hardcoded ``unity.bronze`` literals (validator
   ``validate-dag UC-WIRING-001``).

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


# LLD §7.1 — the UC service URI is sourced from the env var injected by
# the cookiecutter docker-compose `airflow` service. The literal default
# is the in-cluster service name; tests override via the env var.
UC_URI_ENV = "UC_URI"
DEFAULT_UC_URI = "http://unity-catalog:8080"

# LLD §2.3 — the three Bronze metadata columns. SE rules reference these
# names verbatim; renaming them requires a matching SE rules update.
METADATA_COL_DS = "ds"
METADATA_COL_INGESTED_AT = "_ingested_at"
METADATA_COL_SOURCE_BATCH_ID = "_source_batch_id"

# Project root for resolving relative `contracts_dir` / `dq_rules_dir`
# paths inside spark-submit (CWD is unreliable). Set by docker-compose
# (e.g. `/opt/patient_360`) and consumed by `_anchor_relative`.
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
    parser = argparse.ArgumentParser(
        description="Generic Bronze ingestion runner (LLD §2.3)"
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
# Config + contract loading
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


# LLD §2.3 / DMS §2 — minimal Spark-type vocabulary for the contract YAML.
# Kept narrow on purpose so a typo in a contract surfaces at read time.
_TYPE_MAP_LAZY: dict[str, Any] | None = None


def _type_map() -> dict[str, Any]:
    """Lazy import of pyspark.sql.types so unit tests stay PySpark-free."""
    global _TYPE_MAP_LAZY
    if _TYPE_MAP_LAZY is not None:
        return _TYPE_MAP_LAZY
    from pyspark.sql import types as T  # type: ignore[import-not-found]

    _TYPE_MAP_LAZY = {
        "string": T.StringType(),
        "int": T.IntegerType(),
        "integer": T.IntegerType(),
        "long": T.LongType(),
        "bigint": T.LongType(),
        "double": T.DoubleType(),
        "float": T.FloatType(),
        "boolean": T.BooleanType(),
        "bool": T.BooleanType(),
        "date": T.DateType(),
        "timestamp": T.TimestampType(),
    }
    return _TYPE_MAP_LAZY


def build_struct_type_from_contract(contract: dict[str, Any]) -> Any:
    """Build a ``StructType`` from a ``contracts/{table}.yml`` dict.

    Contract shape (LLD §2.3 / DMS §2):

    .. code-block:: yaml

        table: synthea_patients
        layer: bronze
        columns:
          - {name: id, type: string, nullable: false}
          - {name: birthdate, type: date, nullable: true}

    An empty ``columns:`` list raises -- schema enforcement is mandatory
    (no inference). The runner refuses to start if the contract is empty.
    """
    from pyspark.sql import types as T  # type: ignore[import-not-found]

    columns = contract.get("columns") or []
    if not columns:
        raise ValueError(
            f"contracts/{contract.get('table', '<unknown>')}.yml has no "
            "columns; schema enforcement is required (LLD §2.3)"
        )

    type_map = _type_map()
    fields: list[Any] = []
    for col in columns:
        name = col["name"]
        type_key = str(col["type"]).lower()
        if type_key not in type_map:
            raise ValueError(
                f"Unsupported type '{col['type']}' for column '{name}' "
                f"in contracts/{contract.get('table')}.yml"
            )
        nullable = bool(col.get("nullable", True))
        fields.append(T.StructField(name, type_map[type_key], nullable))
    return T.StructType(fields)


def load_contract_schema(contracts_dir: Path | str, table: str) -> Any:
    """Locate ``contracts/{table}.yml`` and return its StructType."""
    contract_path = Path(contracts_dir) / f"{table}.yml"
    return build_struct_type_from_contract(load_yaml(contract_path))


# ---------------------------------------------------------------------------
# Spark session
# ---------------------------------------------------------------------------
def build_spark(app_name: str, *, uc_uri: str | None = None) -> Any:
    """Build a Spark session wired to Unity Catalog OSS.

    The UC service URI is sourced from the ``UC_URI`` env var (LLD §7.1).
    The Spark session factory in ``patient_360.utils.delta_helpers`` is
    reused so Bronze / Silver / Gold share one wiring contract.
    """
    from patient_360.utils.delta_helpers import build_spark_session

    resolved_uri = uc_uri or os.environ.get(UC_URI_ENV, DEFAULT_UC_URI)
    return build_spark_session(app_name=app_name, uc_uri=resolved_uri)


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
# Source reader
# ---------------------------------------------------------------------------
def read_source(spark: Any, *, source_cfg: dict[str, Any], schema: Any) -> Any:
    """Read the configured source with the contract StructType applied.

    Supported source types (LLD §5.1 / STM Tab:Source-to-Bronze):

    * ``duckdb``  -- ``duckdb`` Python connector + ``spark.createDataFrame``.
    * ``parquet`` -- ``spark.read.format("parquet").schema(schema).load(path)``.
    * ``csv``     -- ``spark.read.format("csv").schema(schema).load(path)``.

    Schema is **always** enforced -- no ``inferSchema`` (LLD §2.3).
    """
    src_type = source_cfg.get("type", "duckdb").lower()
    if src_type == "duckdb":
        return _read_duckdb(spark, source_cfg=source_cfg, schema=schema)
    if src_type == "parquet":
        return (
            spark.read.format("parquet")
            .schema(schema)
            .load(str(_anchor_relative(source_cfg["path"])))
        )
    if src_type == "csv":
        reader = spark.read.format("csv").schema(schema)
        if source_cfg.get("header"):
            reader = reader.option("header", "true")
        return reader.load(str(_anchor_relative(source_cfg["path"])))
    raise ValueError(f"Unsupported source type: {src_type}")


def _read_duckdb(spark: Any, *, source_cfg: dict[str, Any], schema: Any) -> Any:
    """Read a DuckDB table via the ``duckdb`` Python connector.

    The connector returns an Arrow table that ``spark.createDataFrame``
    accepts directly. The contract StructType is applied so column types
    match Bronze expectations even when DuckDB's inferred types differ.
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
    # Apply contract schema explicitly -- enforces types over inference.
    return spark.createDataFrame(arrow_tbl.to_pylist(), schema=schema)


# ---------------------------------------------------------------------------
# Write (LLD §13 Decision 15)
# ---------------------------------------------------------------------------
def compose_target_table(cfg: dict[str, Any]) -> str:
    """Compose the 2-part UC table name (``<schema>.<table>``) from config.

    The Spark session wires ``spark_catalog`` to UCSingleCatalog and
    sets it as the default catalog, so 2-part names resolve through UC
    automatically. The per-table YAML key
    ``catalog_bronze_catalog_name`` is read for documentation but no
    longer required.
    """
    try:
        schema = cfg["catalog_bronze_schema"]
        table = cfg["table"]
    except KeyError as exc:
        raise KeyError(
            "Per-table YAML must declare catalog_bronze_schema and table "
            "(LLD §7.1)"
        ) from exc
    return f"{schema}.{table}"


def write_bronze(df: Any, *, target_table: str, ds: str) -> None:
    """Write ``df`` to ``target_table`` with ``replaceWhere ds = '<ds>'``.

    Delegates to :func:`patient_360.utils.delta_helpers.replace_where_write`
    so Silver / Gold share the same primitive. Path-based writes
    (``.save("/tmp/...")``) are explicitly forbidden by LLD §13 Decision
    15 and rejected by ``validate-dag UC-WIRING-001``.
    """
    from patient_360.utils.delta_helpers import replace_where_write

    replace_where_write(
        df,
        target_table,
        partition_col=METADATA_COL_DS,
        partition_value=ds,
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run(args: argparse.Namespace) -> int:
    """Top-level orchestration -- read → schema → metadata → SE → write."""
    cfg = load_yaml(args.config_path)
    table = cfg["table"]

    # Resolve contract path. Default is `contracts/` under PROJECT_ROOT;
    # override via the `contracts_dir` config key. `_anchor_relative`
    # joins relative paths against ``PATIENT360_PROJECT_ROOT`` so spark
    # workers don't depend on CWD.
    contracts_dir = _anchor_relative(cfg.get("contracts_dir", "contracts"))
    schema = load_contract_schema(contracts_dir, table)

    spark = build_spark(app_name=f"bronze_ingest_{table}")
    # Spark's built-in Hive metastore (Derby) ships with no schemas; SE
    # and saveAsTable both need `bronze` to exist before the first
    # write. CREATE SCHEMA IF NOT EXISTS is idempotent.
    schema_name = cfg.get("catalog_bronze_schema", "bronze")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
    try:
        df = read_source(
            spark,
            source_cfg=cfg["source"],
            schema=schema,
        )

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
            action_if_failed=cfg.get("action_if_failed"),
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
                    f"target_partitions for table={table!r} must be >= 1, "
                    f"got {n_parts}"
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
