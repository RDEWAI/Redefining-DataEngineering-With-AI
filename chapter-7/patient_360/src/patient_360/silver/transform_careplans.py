"""Silver transform: synthea_careplans -> clinical_careplans (cleansed fact).

LLD: §5.2 transform_careplans_silver (insertInto unity.silver.clinical_careplans;
     §13 Decision 12 + 15 — dynamic partition overwrite, never partition-predicate append,
     table-create, or path write), §5.4 (inline SE BEFORE write).
     Empty-input: Write empty (LLD §5.2).
STM: Tab:Bronze-to-Silver (careplans) rows 141-150.
DMS: §3.9 clinical_careplans schema.
DQS: DQ-FLD-091 .. DQ-FLD-092 (dq_rules/clinical_careplans.yml).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyspark.sql import functions as F

try:
    from patient_360.utils import se_runner
except ImportError as exc:  # pragma: no cover - import-contract guard
    import logging

    logging.getLogger(__name__).critical("se_runner import failed in transform_careplans: %s", exc)
    raise

from patient_360.utils.delta_helpers import read_bronze_delta

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import DataFrame, SparkSession

TABLE = "clinical_careplans"
DOMAIN = "clinical"
BRONZE_TABLE = "synthea_careplans"

EMPTY_INPUT_BEHAVIOR = "write_empty"
ACTION_IF_FAILED = "fail"

# SHA256 of business cols. careplan_id is a natural key (a real DMS §3.9
# business column), not a transient synthetic PK.
HASH_COLUMNS = [
    "careplan_id",
    "patient_id",
    "snomed_code",
    "start_date",
]

# DMS §3.9 ordered columns. careplan_id is a natural key business column.
# DMS §3.9 has NO is_active column (STM row 150 derives it) — omitted per DMS.
OUTPUT_COLUMNS = [
    "careplan_id",
    "patient_id",
    "encounter_id",
    "start_date",
    "stop_date",
    "snomed_code",
    "careplan_description",
    "reason_code",
    "reason_description",
    "ds",
    "_ingested_at",
    "_source_batch_id",
    "_record_hash",
]


def _record_hash(*cols) -> F.Column:
    parts = [F.coalesce(F.col(c).cast("string"), F.lit("")) for c in cols]
    return F.sha2(F.concat_ws("|", *parts), 256)


def _cleanse(bronze_df: DataFrame, ds: str) -> DataFrame:
    df = bronze_df.select(
        F.trim(F.col("Id")).alias("careplan_id"),  # row 141
        F.trim(F.col("PATIENT")).alias("patient_id"),  # row 142
        F.trim(F.col("ENCOUNTER")).alias("encounter_id"),  # row 143
        F.col("START").cast("date").alias("start_date"),  # row 144
        F.col("STOP").cast("date").alias("stop_date"),  # row 145
        F.col("CODE").cast("string").alias("snomed_code"),  # row 146
        F.trim(F.col("DESCRIPTION")).alias("careplan_description"),  # row 147
        F.col("REASONCODE").cast("string").alias("reason_code"),  # row 148
        F.trim(F.col("REASONDESCRIPTION")).alias("reason_description"),  # row 149
        F.lit(ds).cast("date").alias("ds"),
        F.col("_ingested_at"),
        F.col("_source_batch_id"),
    )
    return df.withColumn("_record_hash", _record_hash(*HASH_COLUMNS)).select(*OUTPUT_COLUMNS)


def transform(spark: SparkSession, env: str, ds: str) -> DataFrame:
    bronze_df = read_bronze_delta(spark, table=BRONZE_TABLE, ds=ds, env=env)

    # LLD §5.2 empty-input: Write empty. Emit a 0-row frame with the right
    # schema and continue (no SE, nothing to validate).
    if bronze_df.head(1) == []:
        empty = _cleanse(bronze_df, ds)
        (empty.select(*OUTPUT_COLUMNS).write.mode("overwrite").insertInto(f"unity.silver.{TABLE}"))
        return empty

    silver_df = _cleanse(bronze_df, ds)

    validated_df = se_runner.run_dq(
        df=silver_df,
        table=TABLE,
        env=env,
        action_if_failed=ACTION_IF_FAILED,
        dq_rules_dir=None,
    )

    target_table = f"unity.silver.{TABLE}"
    (validated_df.select(*OUTPUT_COLUMNS).write.mode("overwrite").insertInto(target_table))

    return validated_df


__all__ = ["transform", "TABLE", "DOMAIN", "HASH_COLUMNS", "OUTPUT_COLUMNS"]
