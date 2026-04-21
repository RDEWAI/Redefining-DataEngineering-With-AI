"""Generic Bronze ingestion runner.

Reads a per-table YAML config from ``airflow/configs/``, enforces a StructType
schema resolved from ``contracts/{table}.yml``, adds ``ds``, ``_ingested_at``,
and ``_source_batch_id`` metadata columns (names match the DQS SE rules under
``chapter-5/inputs/dqs/vN/se-rules/``), runs inline Spark Expectations
row_dq/agg_dq checks, and writes Delta partitioned by ``ds`` with
``replaceWhere ds = '{ds}'``.

Per LLD §2.3 and §5.1. Intended to be launched via SparkSubmitOperator with::

    python -m patient_360.bronze.ingestion_runner \\
        --config-path airflow/configs/patients.yml \\
        --ds 2026-04-17 \\
        --env DEV
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType,
    DataType,
    DateType,
    DecimalType,
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

logger = logging.getLogger(__name__)


_TYPE_MAP: dict[str, DataType] = {
    "string": StringType(),
    "varchar": StringType(),
    "text": StringType(),
    "int": IntegerType(),
    "integer": IntegerType(),
    "bigint": LongType(),
    "long": LongType(),
    "double": DoubleType(),
    "float": DoubleType(),
    "boolean": BooleanType(),
    "bool": BooleanType(),
    "date": DateType(),
    "timestamp": TimestampType(),
}


class IngestionConfigError(ValueError):
    """Raised when the per-table YAML config is malformed or inconsistent."""


class EmptyInputError(RuntimeError):
    """Raised when the source has zero rows and empty_input_behavior is ``fail``."""


@dataclass(frozen=True)
class TableConfig:
    table: str
    source_schema: str
    source_table: str
    source_format: str
    source_path: str | None
    schema_ref: Path
    output_path_template: str
    metadata_columns: tuple[str, ...]
    empty_input_behavior: str
    dq_rules_table: str
    se_action_if_failed: str
    quarantine_path_template: str = "warehouse/{env}/quarantine/bronze/{table}/"

    def resolved_output_path(self, env: str, ds: str) -> str:
        return (
            self.output_path_template
            .replace("{env}", env)
            .replace("{ds}", ds)
        )

    def resolved_quarantine_path(self, env: str) -> str:
        return (
            self.quarantine_path_template
            .replace("{env}", env)
            .replace("{table}", self.table)
        )


def load_table_config(config_path: Path) -> TableConfig:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise IngestionConfigError(f"{config_path}: top-level YAML must be a mapping")

    try:
        table = str(raw["table"])
        source = raw["source"]
        source_schema = str(source["schema"])
        source_table = str(source["table"])
        source_format = str(source.get("format", "csv")).lower()
        source_path = source.get("path")
        schema_ref = Path(raw["schema_ref"])
        output_path = str(raw["output_path"])
        empty_behavior = str(raw.get("empty_input_behavior", "write_empty")).lower()
        dq_rules_table = str(raw.get("dq_rules_table", table))
        se_action = str(raw.get("se_action_if_failed", "drop")).lower()
        quarantine_path = str(
            raw.get("quarantine_path", f"warehouse/{{env}}/quarantine/bronze/{table}/")
        )
    except KeyError as exc:
        raise IngestionConfigError(f"{config_path}: missing required key {exc.args[0]!r}") from exc

    metadata_columns = tuple(
        raw.get("metadata_columns", ("ds", "_ingested_at", "_source_batch_id"))
    )
    if empty_behavior not in {"fail", "write_empty"}:
        raise IngestionConfigError(
            f"{config_path}: empty_input_behavior must be 'fail' or 'write_empty'"
        )
    if se_action not in {"fail", "drop", "ignore"}:
        raise IngestionConfigError(
            f"{config_path}: se_action_if_failed must be 'fail', 'drop', or 'ignore'"
        )

    return TableConfig(
        table=table,
        source_schema=source_schema,
        source_table=source_table,
        source_format=source_format,
        source_path=str(source_path) if source_path else None,
        schema_ref=schema_ref,
        output_path_template=output_path,
        metadata_columns=metadata_columns,
        empty_input_behavior=empty_behavior,
        dq_rules_table=dq_rules_table,
        se_action_if_failed=se_action,
        quarantine_path_template=quarantine_path,
    )


def load_struct_type(contract_path: Path) -> StructType:
    """Build a ``StructType`` from ``contracts/{table}.yml``.

    The contract's ``columns`` list is the source of truth; each entry must
    have ``name``, ``type``, and ``nullable`` (default True). DECIMAL types
    are written as ``decimal(18, 2)``.
    """
    if not contract_path.exists():
        raise IngestionConfigError(f"contract file not found: {contract_path}")

    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8")) or {}
    columns = contract.get("columns")
    if not columns:
        raise IngestionConfigError(f"{contract_path}: contract has no `columns` block")

    fields: list[StructField] = []
    for col in columns:
        name = col["name"]
        type_name = str(col["type"]).strip().lower()
        nullable = bool(col.get("nullable", True))
        fields.append(StructField(name, _parse_spark_type(type_name), nullable=nullable))
    return StructType(fields)


def _parse_spark_type(type_name: str) -> DataType:
    if type_name.startswith("decimal"):
        precision, scale = 18, 2
        if "(" in type_name:
            inside = type_name[type_name.index("(") + 1 : type_name.index(")")]
            parts = [p.strip() for p in inside.split(",")]
            if len(parts) == 2:
                precision, scale = int(parts[0]), int(parts[1])
        return DecimalType(precision, scale)
    if type_name in _TYPE_MAP:
        return _TYPE_MAP[type_name]
    raise IngestionConfigError(f"unsupported column type: {type_name!r}")


def read_source(spark: SparkSession, cfg: TableConfig) -> DataFrame:
    schema = load_struct_type(cfg.schema_ref)
    fmt = cfg.source_format
    if fmt == "csv":
        if not cfg.source_path:
            raise IngestionConfigError(
                f"{cfg.table}: source.format=csv requires source.path"
            )
        reader = (
            spark.read.format("csv")
            .option("header", "true")
            .option("timestampFormat", "yyyy-MM-dd'T'HH:mm:ssZ")
            .schema(schema)
        )
        return reader.load(cfg.source_path)
    if fmt == "delta":
        return spark.read.format("delta").load(cfg.source_path or cfg.source_table)
    if fmt == "jdbc":
        # Expects source.path = JDBC URL; connection properties provided via Spark conf.
        if not cfg.source_path:
            raise IngestionConfigError(
                f"{cfg.table}: source.format=jdbc requires source.path (JDBC URL)"
            )
        return (
            spark.read.format("jdbc")
            .option("url", cfg.source_path)
            .option("dbtable", f"{cfg.source_schema}.{cfg.source_table}")
            .load()
        )
    raise IngestionConfigError(f"{cfg.table}: unsupported source.format={fmt!r}")


def add_metadata_columns(
    df: DataFrame,
    ds: str,
    columns: tuple[str, ...],
    table: str | None = None,
) -> DataFrame:
    """Attach Bronze metadata columns expected by DQS SE rules.

    ``_source_batch_id`` is deterministic (``{table}:{ds}``) so reruns of the
    same ds for the same table resolve to the same batch id — required for
    idempotent ``replaceWhere`` writes.
    """
    out = df
    if "ds" in columns:
        out = out.withColumn("ds", F.lit(ds))
    if "_ingested_at" in columns:
        out = out.withColumn("_ingested_at", F.current_timestamp())
    if "_source_batch_id" in columns:
        batch_id = f"{table or 'unknown'}:{ds}"
        out = out.withColumn("_source_batch_id", F.lit(batch_id))
    return out


_DQ_ENV_MAP = {"DEV": "DEV", "STAGING": "QA", "PROD": "PROD"}


def run_inline_dq(
    df: DataFrame,
    cfg: TableConfig,
    env: str,
    dq_rules_dir: Path,
) -> DataFrame:
    """Call spark-expectations inline for row_dq + agg_dq.

    ``env`` is the runtime environment (DEV/STAGING/PROD); it is mapped to the
    SE ``dq_env`` key (DEV/QA/PROD) per LLD §2.3 before passing to run_dq.

    Bootstrap mode: if ``patient_360.utils.se_runner`` is not yet available,
    logs a WARNING and returns the DataFrame unchanged. Remove this fallback
    once se_runner.py is implemented — per LLD §2.3, ingestion must fail closed
    if SE is unavailable post-implementation.
    """
    try:
        from patient_360.utils.se_runner import run_dq  # type: ignore[import-not-found]
    except ImportError:
        logger.warning(
            "se_runner not available — skipping inline DQ for %s (action=%s)",
            cfg.table,
            cfg.se_action_if_failed,
        )
        return df
    dq_env = _DQ_ENV_MAP.get(env.upper(), env)
    return run_dq(
        df,
        table=cfg.dq_rules_table,
        env=dq_env,
        dq_rules_dir=dq_rules_dir,
        action_if_failed=cfg.se_action_if_failed,
    )


def write_delta(df: DataFrame, output_path: str, ds: str) -> None:
    """Write Delta to the table root, partitioned by ``ds``.

    ``output_path`` is the table directory (no ``ds=`` suffix); the ``ds``
    column is materialized as a true Delta partition so ``replaceWhere`` can
    overwrite just the target partition on rerun.
    """
    (
        df.write.format("delta")
        .mode("overwrite")
        .option("replaceWhere", f"ds = '{ds}'")
        .option("mergeSchema", "false")
        .partitionBy("ds")
        .save(output_path)
    )


def ingest(
    spark: SparkSession,
    config_path: Path,
    ds: str,
    env: str,
) -> dict[str, Any]:
    cfg = load_table_config(config_path)
    output_path = cfg.resolved_output_path(env, ds)
    logger.info(
        "ingesting table=%s source=%s.%s -> %s (ds=%s, env=%s)",
        cfg.table,
        cfg.source_schema,
        cfg.source_table,
        output_path,
        ds,
        env,
    )

    raw = read_source(spark, cfg)
    row_count = raw.count()
    logger.info("read %d rows from %s", row_count, cfg.source_table)

    if row_count == 0:
        if cfg.empty_input_behavior == "fail":
            raise EmptyInputError(
                f"{cfg.table}: source returned 0 rows and empty_input_behavior=fail"
            )
        logger.warning("%s: source empty — writing empty partition (ds=%s)", cfg.table, ds)

    enriched = add_metadata_columns(raw, ds, cfg.metadata_columns, table=cfg.table)
    dq_rules_dir = config_path.parent.parent.parent / "dq_rules"
    validated = run_inline_dq(enriched, cfg, env=env, dq_rules_dir=dq_rules_dir)
    write_delta(validated, output_path, ds)

    final_count = validated.count() if row_count else 0
    logger.info("wrote %d rows to %s (ds=%s)", final_count, output_path, ds)
    return {"table": cfg.table, "ds": ds, "env": env, "rows": final_count, "output": output_path}


def _build_spark(app_name: str) -> SparkSession:
    """Build a SparkSession with Delta Lake wired up for local `python -m` and
    SparkSubmit runs. Uses ``configure_spark_with_delta_pip`` so the Delta JAR
    bundled with ``delta-spark`` is added to ``spark.jars.packages`` — the
    same JAR SparkSubmit would otherwise need via ``--packages``.
    """
    from delta import configure_spark_with_delta_pip  # local import: optional dep

    builder = (
        SparkSession.builder
        .appName(app_name)
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
    )
    return configure_spark_with_delta_pip(builder).getOrCreate()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-path", type=Path, required=True, help="Per-table YAML config")
    parser.add_argument("--ds", required=True, help="Load date YYYY-MM-DD")
    parser.add_argument("--env", required=True, choices=("DEV", "STAGING", "PROD"))
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    spark = _build_spark(app_name=f"bronze_ingest_{args.config_path.stem}_{args.ds}")
    try:
        ingest(spark, args.config_path, args.ds, args.env)
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
