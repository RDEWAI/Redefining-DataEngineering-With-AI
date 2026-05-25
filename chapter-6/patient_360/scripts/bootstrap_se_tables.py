"""Pre-create the Spark-Expectations stats / errors Delta tables.

Why: SE writes per-run stats to a shared Delta table via
``saveAsTable("bronze.bronze_se_stats")`` with ``mode("append")``.
On a cold metastore the first task ends up in CREATE territory.
Any partial state (e.g. a transient OOM, a metastore restart, a Spark
crash) leaves orphan Delta files at the table path without a metastore
registration. The next task then fails with
``DELTA_CREATE_TABLE_WITH_NON_EMPTY_LOCATION`` and the failure
cascades to every retry.

This script pre-creates both SE tables as EXTERNAL Delta tables with
the exact schema SE expects (mirrored from
``spark_expectations/sinks/utils/writer.py``). After running it, every
SE invocation falls into the pure append path — no CREATE race.

Idempotent: ``CREATE SCHEMA IF NOT EXISTS`` + ``CREATE TABLE IF NOT
EXISTS`` are no-ops when the schema/tables already exist.

Per LLD v1.14 §13 Decision 12 (revised 2026-05-12), the runtime stack
is DeltaCatalog + embedded Derby Hive metastore — UC OSS is a UI demo
only. The table location is computed from ``spark.sql.warehouse.dir``
which `build_spark_session` anchors at
``${PATIENT360_PROJECT_ROOT}/warehouse/{env}/``.
"""

from __future__ import annotations

from pyspark.sql.types import (
    ArrayType,
    DateType,
    FloatType,
    IntegerType,
    LongType,
    MapType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from patient_360.utils.delta_helpers import build_spark_session
from patient_360.utils.se_runner import SE_ERROR_TABLE, SE_STATS_TABLE


# Mirrors `error_stats_schema` in
# spark_expectations/sinks/utils/writer.py (kept in lockstep with
# SE 2.6+). Column names come from SparkExpectationsContext defaults:
# `meta_dq_run_id`, `meta_dq_run_date`, `meta_dq_run_datetime`.
_SE_STATS_SCHEMA = StructType(
    [
        StructField("product_id", StringType(), True),
        StructField("table_name", StringType(), True),
        StructField("input_count", LongType(), True),
        StructField("error_count", LongType(), True),
        StructField("output_count", LongType(), True),
        StructField("output_percentage", FloatType(), True),
        StructField("success_percentage", FloatType(), True),
        StructField("error_percentage", FloatType(), True),
        StructField(
            "source_agg_dq_results",
            ArrayType(MapType(StringType(), StringType())),
            True,
        ),
        StructField(
            "final_agg_dq_results",
            ArrayType(MapType(StringType(), StringType())),
            True,
        ),
        StructField(
            "source_query_dq_results",
            ArrayType(MapType(StringType(), StringType())),
            True,
        ),
        StructField(
            "final_query_dq_results",
            ArrayType(MapType(StringType(), StringType())),
            True,
        ),
        StructField(
            "row_dq_res_summary",
            ArrayType(MapType(StringType(), StringType())),
            True,
        ),
        StructField(
            "row_dq_error_threshold",
            ArrayType(MapType(StringType(), StringType())),
            True,
        ),
        StructField("dq_status", MapType(StringType(), StringType()), True),
        StructField("dq_run_time", MapType(StringType(), FloatType()), True),
        StructField(
            "dq_rules",
            MapType(StringType(), MapType(StringType(), IntegerType())),
            True,
        ),
        StructField("meta_dq_run_id", StringType(), True),
        StructField("meta_dq_run_date", DateType(), True),
        StructField("meta_dq_run_datetime", TimestampType(), True),
    ]
)

# Errors table mirrors the input target schema + SE meta columns. We
# can't predict the input schema upfront (it varies per Bronze table),
# so register a sentinel schema with just the SE meta columns and rely
# on Delta `mergeSchema` to fold in target columns on first append.
_SE_ERRORS_SCHEMA = StructType(
    [
        StructField("meta_dq_run_id", StringType(), True),
        StructField("meta_dq_run_date", DateType(), True),
        StructField("meta_dq_run_datetime", TimestampType(), True),
    ]
)


def _ensure_table(spark, fqn: str, schema: StructType) -> None:
    """Create an empty external Delta table at the warehouse path.

    Uses the path+DDL pattern: write an empty Delta dataset to the
    location, then ``CREATE TABLE IF NOT EXISTS … USING DELTA
    LOCATION`` to register it in the Derby Hive metastore. Both steps
    are idempotent.
    """
    warehouse = spark.conf.get("spark.sql.warehouse.dir")
    parts = fqn.split(".")
    schema_name, table_name = parts[-2], parts[-1]
    location = f"{warehouse}/{schema_name}/{table_name}"

    empty_df = spark.createDataFrame([], schema)
    empty_df.write.format("delta").mode("ignore").save(location)
    spark.sql(
        f"CREATE TABLE IF NOT EXISTS {fqn} USING DELTA LOCATION '{location}'"
    )
    print(f"  ensured {fqn} → {location}")


def main() -> int:
    spark = build_spark_session(app_name="bootstrap_se_tables")
    spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")
    try:
        # CREATE SCHEMA IF NOT EXISTS is idempotent. The ingestion runner
        # does the same on every invocation; mirror it here so the
        # bootstrap can run against a cold metastore.
        for fqn in (SE_STATS_TABLE, SE_ERROR_TABLE):
            schema_name = fqn.split(".")[-2]
            spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
        _ensure_table(spark, SE_STATS_TABLE, _SE_STATS_SCHEMA)
        _ensure_table(spark, SE_ERROR_TABLE, _SE_ERRORS_SCHEMA)
    finally:
        spark.stop()
    print("SE bootstrap complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
