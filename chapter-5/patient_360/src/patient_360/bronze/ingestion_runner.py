"""Generic Bronze ingestion runner — config-driven, UC-managed write.

Implements LLD §2.3 `src/patient_360/bronze/ingestion_runner.py`.
Single runner used by all 13 Bronze tables; per-table behaviour is
declared in `airflow/configs/<table>.yml`.

CRITICAL — UC-managed writes (LLD §2.3 / Decision 15).
Bronze tables MUST land in Unity Catalog at write time using
``UCSingleCatalog`` + ``saveAsTable("unity.bronze.<table>")``.
Path-based Delta writes (``df.write.format("delta").save("/tmp/...")``)
leave UC empty until manual registration; the validator
``validate-dag UC-WIRING-001`` rejects any such pattern.

Story coverage:
- STORY-02-001 — runner with `--config-path`, `--env`, `--ds`,
  soft-import of `se_runner` (bootstrap mode), per-table empty-input
  override, DuckDB read, Delta write to `unity.bronze.<table>`.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Soft-import: spark-expectations runner (bootstrap mode per LLD §8.6).       #
# STORY-02-004 supersedes this with a fail-closed import.                     #
# --------------------------------------------------------------------------- #
try:
    from patient_360.utils.se_runner import run_dq as _se_run_dq  # type: ignore

    _SE_AVAILABLE = True
except ImportError:  # noqa: BLE001 -- soft-import is a documented bootstrap state
    logger.warning("WARNING: se_runner not available — bootstrap mode (LLD §8.6)")
    _se_run_dq = None
    _SE_AVAILABLE = False


# --------------------------------------------------------------------------- #
# Config dataclass                                                            #
# --------------------------------------------------------------------------- #


class EmptyInputError(RuntimeError):
    """Raised when a critical Bronze table received zero source rows."""


class ConfigError(ValueError):
    """Raised on invalid per-table YAML config."""


_VALID_EMPTY_INPUT = {"fail", "write_empty"}
_VALID_SE_ACTIONS = {"fail", "drop", "ignore"}

# Map runtime --env values to spark-expectations dq_env names (LLD §2.3, §5.4).
_DQ_ENV_MAP = {"DEV": "DEV", "STAGING": "QA", "PROD": "PROD"}


@dataclass(frozen=True)
class TableConfig:
    table: str
    target: str
    source: dict[str, Any]
    schema_ref: str
    metadata_columns: list[str]
    empty_input_behavior: str
    dq_rules_table: str
    se_action_if_failed: str
    quarantine_path_template: str = "warehouse/{env}/quarantine/bronze/{table}/"
    timeout_minutes: int = 60
    retries: int = 3
    retry_delay_seconds: int = 60
    raw: dict[str, Any] = field(default_factory=dict)

    def resolved_quarantine_path(self, env: str) -> str:
        return self.quarantine_path_template.format(env=env, table=self.table)


def load_table_config(config_path: Path) -> TableConfig:
    """Read and validate a per-table YAML config.

    Validates: presence of required keys, ``empty_input_behavior`` in
    {fail, write_empty}, ``se_action_if_failed`` in {fail, drop, ignore}.
    """
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")
    cfg = yaml.safe_load(config_path.read_text())
    if not isinstance(cfg, dict):
        raise ConfigError(f"Config root must be a mapping: {config_path}")

    required = [
        "table",
        "target",
        "source",
        "schema_ref",
        "empty_input_behavior",
        "dq_rules_table",
        "se_action_if_failed",
    ]
    missing = [k for k in required if k not in cfg]
    if missing:
        raise ConfigError(f"Missing required keys {missing} in {config_path}")

    if cfg["empty_input_behavior"] not in _VALID_EMPTY_INPUT:
        raise ConfigError(
            f"empty_input_behavior must be one of {_VALID_EMPTY_INPUT}, "
            f"got {cfg['empty_input_behavior']!r}"
        )
    if cfg["se_action_if_failed"] not in _VALID_SE_ACTIONS:
        raise ConfigError(
            f"se_action_if_failed must be one of {_VALID_SE_ACTIONS}, "
            f"got {cfg['se_action_if_failed']!r}"
        )

    return TableConfig(
        table=cfg["table"],
        target=cfg["target"],
        source=cfg["source"],
        schema_ref=cfg["schema_ref"],
        metadata_columns=cfg.get("metadata_columns", ["ds", "_ingested_at", "_source_batch_id"]),
        empty_input_behavior=cfg["empty_input_behavior"],
        dq_rules_table=cfg["dq_rules_table"],
        se_action_if_failed=cfg["se_action_if_failed"],
        quarantine_path_template=cfg.get(
            "quarantine_path",
            "warehouse/{env}/quarantine/bronze/{table}/",
        ),
        timeout_minutes=int(cfg.get("timeout_minutes", 60)),
        retries=int(cfg.get("retries", 3)),
        retry_delay_seconds=int(cfg.get("retry_delay_seconds", 60)),
        raw=cfg,
    )


# --------------------------------------------------------------------------- #
# Schema loader (StructType from contract YAML — no inference).                #
# --------------------------------------------------------------------------- #


def _parse_spark_type(type_str: str):
    """Map a contract type string to a PySpark DataType.

    Supports: VARCHAR/STRING, INT/INTEGER, BIGINT/LONG, DOUBLE/FLOAT,
    BOOLEAN, DATE, TIMESTAMP, DECIMAL(p,s).
    """
    from pyspark.sql import types as T

    s = type_str.strip().upper()
    if s.startswith("DECIMAL"):
        # DECIMAL(p,s)
        inner = s[s.find("(") + 1 : s.find(")")]
        p, sc = (int(x) for x in inner.split(","))
        return T.DecimalType(p, sc)

    primitives = {
        "STRING": T.StringType(),
        "VARCHAR": T.StringType(),
        "TEXT": T.StringType(),
        "INT": T.IntegerType(),
        "INTEGER": T.IntegerType(),
        "BIGINT": T.LongType(),
        "LONG": T.LongType(),
        "DOUBLE": T.DoubleType(),
        "FLOAT": T.FloatType(),
        "BOOLEAN": T.BooleanType(),
        "BOOL": T.BooleanType(),
        "DATE": T.DateType(),
        "TIMESTAMP": T.TimestampType(),
    }
    if s in primitives:
        return primitives[s]
    raise ConfigError(f"Unsupported contract type: {type_str!r}")


def load_struct_type(contract_path: Path):
    """Load a `StructType` from a `contracts/<table>.yml` file."""
    from pyspark.sql import types as T

    if not contract_path.exists():
        raise ConfigError(f"Contract not found: {contract_path}")
    raw = yaml.safe_load(contract_path.read_text())
    fields = []
    for col in raw.get("columns", []):
        fields.append(
            T.StructField(
                col["name"],
                _parse_spark_type(col["type"]),
                bool(col.get("nullable", True)),
            )
        )
    return T.StructType(fields)


# --------------------------------------------------------------------------- #
# Spark + UC wiring (LLD §2.3 / Decision 15).                                  #
# --------------------------------------------------------------------------- #


def _build_spark(app_name: str):
    """Build a Spark session wired to UC OSS via UCSingleCatalog + Delta.

    UC_URI is sourced from the env (set by the cookiecutter docker-compose
    `airflow` service); falling back to the in-cluster default. Delta is
    configured via ``configure_spark_with_delta_pip`` so local
    ``python -m`` runs work without ``PYSPARK_SUBMIT_ARGS``.
    """
    from pyspark.sql import SparkSession

    try:
        from delta import configure_spark_with_delta_pip  # type: ignore
    except ImportError:
        configure_spark_with_delta_pip = None  # delta optional in tests

    uc_uri = os.environ.get("UC_URI", "http://unity-catalog:8080")
    builder = (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.catalog.unity", "io.unitycatalog.spark.UCSingleCatalog")
        .config("spark.sql.catalog.unity.uri", uc_uri)
        .config("spark.sql.defaultCatalog", "unity")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog"
        )
    )
    if configure_spark_with_delta_pip is not None:
        builder = configure_spark_with_delta_pip(builder)
    return builder.getOrCreate()


# --------------------------------------------------------------------------- #
# Source readers (config-driven).                                              #
# --------------------------------------------------------------------------- #


def _read_source(spark, cfg: TableConfig, schema):
    """Read source data per ``cfg.source.format`` (duckdb / csv / jdbc / delta).

    DuckDB is read via JDBC into pandas-on-spark using the duckdb jdbc URL
    or via the local duckdb python driver materialised through
    ``spark.createDataFrame``. The implementation chooses the local-driver
    path so the runner works in the cookiecutter dev container without an
    extra JDBC jar.
    """
    fmt = cfg.source.get("format", "csv").lower()

    if fmt == "duckdb":
        import duckdb  # local driver path

        db_path = cfg.source.get("path") or os.environ.get("DUCKDB_PATH", "data/duckdb/raw.db")
        schema_name = cfg.source.get("schema", "synthea")
        src_table = cfg.source["table"]
        con = duckdb.connect(db_path, read_only=True)
        try:
            pdf = con.execute(f'SELECT * FROM "{schema_name}"."{src_table}"').fetchdf()
        finally:
            con.close()
        # Normalise column names to match contract (case-sensitive Spark).
        return spark.createDataFrame(pdf, schema=schema)

    if fmt == "csv":
        path = cfg.source["path"]
        return spark.read.format("csv").option("header", "true").schema(schema).load(path)

    if fmt == "jdbc":
        opts = cfg.source.get("options", {})
        return spark.read.format("jdbc").options(**opts).load()

    if fmt == "delta":
        return spark.read.format("delta").load(cfg.source["path"])

    raise ConfigError(f"Unsupported source format: {fmt!r}")


# --------------------------------------------------------------------------- #
# Metadata columns + DQ + write.                                               #
# --------------------------------------------------------------------------- #


def add_metadata_columns(df, *, table: str, ds: str):
    """Append the 3 audit columns required by every Bronze table.

    `_source_batch_id` is deterministic (`{table}:{ds}`) so reruns are
    idempotent under `replaceWhere ds = '<ds>'`.
    """
    from pyspark.sql import functions as F

    return (
        df.withColumn("ds", F.lit(ds))
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source_batch_id", F.lit(f"{table}:{ds}"))
    )


def _resolve_dq_rules_dir(config_path: Path, dq_rules_dir: Path | str | None = None) -> Path:
    """Resolve the dq_rules directory in the canonical order.

    1. Explicit kwarg.
    2. ``DQ_RULES_DIR`` env var (set by the docker-compose airflow service).
    3. Fallback for non-container runs: walk up to the project root.
    """
    if dq_rules_dir is not None:
        return Path(dq_rules_dir)
    env_value = os.environ.get("DQ_RULES_DIR")
    if env_value:
        return Path(env_value)
    # config_path = <project>/airflow/configs/<table>.yml → project_root/dq_rules
    return config_path.parent.parent.parent / "dq_rules"


def run_inline_dq(df, cfg: TableConfig, env: str, dq_rules_dir: Path | str | None = None):
    """Apply spark-expectations row_dq + agg_dq inline, in bootstrap mode.

    When `_SE_AVAILABLE` is False, returns the input DataFrame unchanged
    (LLD §8.6 bootstrap behaviour). STORY-02-004 turns this fail-closed.
    """
    if not _SE_AVAILABLE or _se_run_dq is None:
        logger.warning(
            "WARNING: se_runner not available — bootstrap mode passes "
            "DataFrame for table=%s through unchanged",
            cfg.table,
        )
        return df

    rules_dir = _resolve_dq_rules_dir(_LAST_CONFIG_PATH or Path("."), dq_rules_dir)
    dq_env = _DQ_ENV_MAP.get(env.upper(), "DEV")
    return _se_run_dq(  # type: ignore[misc]
        df,
        table=cfg.dq_rules_table,
        env=dq_env,
        dq_rules_dir=rules_dir,
        action_if_failed=cfg.se_action_if_failed,
        quarantine_path=cfg.resolved_quarantine_path(env),
    )


def write_delta(df, cfg: TableConfig, ds: str) -> None:
    """Write to ``unity.bronze.<table>`` via ``saveAsTable`` per Decision 15.

    NEVER ``df.write.format("delta").save(<path>)`` — UC-WIRING-001.
    Partitioned by `ds` with ``replaceWhere`` for idempotent reruns.
    """
    (
        df.write.mode("append")
        .format("delta")
        .partitionBy("ds")
        .option("replaceWhere", f"ds = '{ds}'")
        .saveAsTable(cfg.target)
    )
    logger.info("Wrote %s for ds=%s", cfg.target, ds)


# Module-level holder so `run_inline_dq` can resolve dq_rules_dir from
# the active config file when called by `ingest()`.
_LAST_CONFIG_PATH: Path | None = None


def ingest(spark, cfg: TableConfig, *, env: str, ds: str, contracts_dir: Path | None = None) -> int:
    """Execute the standard Bronze ingestion pattern for one table.

    Returns the number of rows written.
    """
    contracts_dir = contracts_dir or (Path.cwd() / "contracts")
    schema = load_struct_type(
        Path(cfg.schema_ref)
        if Path(cfg.schema_ref).is_absolute()
        else contracts_dir.parent / cfg.schema_ref
    )

    df = _read_source(spark, cfg, schema)
    row_count = df.count()
    logger.info("Read %d source rows for table=%s", row_count, cfg.table)

    if row_count == 0:
        if cfg.empty_input_behavior == "fail":
            raise EmptyInputError(
                f"Source returned 0 rows for critical table {cfg.table!r} "
                f"and empty_input_behavior=fail (LLD §5.1)"
            )
        logger.warning("Empty input for %s — writing empty partition (ds=%s)", cfg.table, ds)

    df = add_metadata_columns(df, table=cfg.table, ds=ds)
    df = run_inline_dq(df, cfg, env=env)
    write_delta(df, cfg, ds=ds)
    return row_count


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bronze ingestion runner")
    p.add_argument("--config-path", required=True, help="Per-table YAML config path")
    p.add_argument(
        "--env", required=True, choices=["DEV", "STAGING", "PROD", "dev", "staging", "prod"]
    )
    p.add_argument("--ds", required=True, help="Logical date YYYY-MM-DD")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = Path(args.config_path).resolve()

    global _LAST_CONFIG_PATH
    _LAST_CONFIG_PATH = config_path

    cfg = load_table_config(config_path)
    spark = _build_spark(f"bronze_ingest_{cfg.table}")
    try:
        rows = ingest(
            spark,
            cfg,
            env=args.env.upper(),
            ds=args.ds,
            contracts_dir=config_path.parent.parent.parent / "contracts",
        )
        logger.info("ingest_runner: wrote %d rows to %s (ds=%s)", rows, cfg.target, args.ds)
        return 0
    finally:
        spark.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    sys.exit(main())
