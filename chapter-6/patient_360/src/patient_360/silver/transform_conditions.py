"""Silver transform: synthea_conditions -> clinical_conditions (cleansed fact).

LLD: §5.2 transform_conditions_silver (insertInto unity.silver.clinical_conditions;
     §13 Decision 12 + 15 — dynamic partition overwrite, never partition-predicate append,
     table-create, or path write), §5.4 (inline SE BEFORE write).
     Empty-input: Write empty (LLD §5.2).
STM: Tab:Bronze-to-Silver (conditions) rows 57-69.
DMS: §3.3 clinical_conditions schema.
DQS: DQ-FLD-066 .. DQ-FLD-070 (dq_rules/clinical_conditions.yml).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyspark.sql import functions as F

try:
    from patient_360.utils import se_runner
except ImportError as exc:  # pragma: no cover - import-contract guard
    import logging

    logging.getLogger(__name__).critical("se_runner import failed in transform_conditions: %s", exc)
    raise

from patient_360.utils.delta_helpers import read_bronze_delta

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import DataFrame, SparkSession

TABLE = "clinical_conditions"
DOMAIN = "clinical"
BRONZE_TABLE = "synthea_conditions"

EMPTY_INPUT_BEHAVIOR = "write_empty"
ACTION_IF_FAILED = "fail"

# STM row 69 — SHA256 of business cols.
HASH_COLUMNS = [
    "condition_id",
    "patient_id",
    "encounter_id",
    "onset_date",
    "snomed_code",
    "condition_status",
]

# DMS §3.3 ordered columns. condition_id is the STM synthetic composite PK
# (row 57) — not a DMS business column but used in the hash; kept transient.
OUTPUT_COLUMNS = [
    "patient_id",
    "encounter_id",
    "onset_date",
    "resolution_date",
    "code_system",
    "snomed_code",
    "condition_description",
    "condition_status",
    "condition_duration_days",
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
        # row 57 — synthetic composite PK (transient; feeds the hash)
        F.sha2(
            F.concat_ws(
                "|",
                F.col("PATIENT"),
                F.col("ENCOUNTER"),
                F.col("CODE").cast("string"),
                F.col("START").cast("string"),
            ),
            256,
        ).alias("condition_id"),
        F.trim(F.col("PATIENT")).alias("patient_id"),  # row 58
        F.trim(F.col("ENCOUNTER")).alias("encounter_id"),  # row 59
        F.col("START").cast("date").alias("onset_date"),  # row 60
        F.col("STOP").cast("date").alias("resolution_date"),  # row 61
        F.trim(F.col("SYSTEM")).alias("code_system"),  # row 64
        F.col("CODE").cast("string").alias("snomed_code"),  # row 62
        F.trim(F.col("DESCRIPTION")).alias("condition_description"),  # row 63
        # row 65 — derived status
        F.when(F.col("STOP").isNull(), F.lit("ACTIVE"))
        .otherwise(F.lit("RESOLVED"))
        .alias("condition_status"),
        # row 66 — duration days (NULL if ongoing)
        F.datediff(F.col("STOP").cast("date"), F.col("START").cast("date")).alias(
            "condition_duration_days"
        ),
        F.lit(ds).cast("date").alias("ds"),
        F.col("_ingested_at"),  # row 67
        F.col("_source_batch_id"),  # row 68
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
