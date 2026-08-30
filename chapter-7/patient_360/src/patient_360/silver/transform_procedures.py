"""Silver transform: synthea_procedures -> clinical_procedures (cleansed fact).

LLD: §5.2 transform_procedures_silver (insertInto unity.silver.clinical_procedures;
     §13 Decision 12 + 15 — dynamic partition overwrite, never partition-predicate append,
     table-create, or path write), §5.4 (inline SE BEFORE write).
     Empty-input: Write empty (LLD §5.2).
STM: Tab:Bronze-to-Silver (procedures) rows 121-132.
DMS: §3.7 clinical_procedures schema.
DQS: DQ-FLD-084 .. DQ-FLD-087 (dq_rules/clinical_procedures.yml).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyspark.sql import functions as F

try:
    from patient_360.utils import se_runner
except ImportError as exc:  # pragma: no cover - import-contract guard
    import logging

    logging.getLogger(__name__).critical("se_runner import failed in transform_procedures: %s", exc)
    raise

from patient_360.utils.delta_helpers import read_bronze_delta

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import DataFrame, SparkSession

TABLE = "clinical_procedures"
DOMAIN = "clinical"
BRONZE_TABLE = "synthea_procedures"

EMPTY_INPUT_BEHAVIOR = "write_empty"
ACTION_IF_FAILED = "fail"

# DMS §3.7 has no STM _record_hash row shown — SHA256 of business cols.
HASH_COLUMNS = [
    "procedure_id",
    "patient_id",
    "snomed_code",
    "start_date",
]

# DMS §3.7 ordered columns. procedure_id is the STM synthetic composite PK
# (row 121) — not a DMS business column but used in the hash; kept transient.
OUTPUT_COLUMNS = [
    "patient_id",
    "encounter_id",
    "start_date",
    "stop_date",
    "code_system",
    "snomed_code",
    "procedure_description",
    "base_cost",
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
        # row 121 — synthetic composite PK (transient; feeds the hash)
        F.sha2(
            F.concat_ws(
                "|",
                F.col("PATIENT"),
                F.col("ENCOUNTER"),
                F.col("CODE").cast("string"),
                F.col("START").cast("string"),
            ),
            256,
        ).alias("procedure_id"),
        F.trim(F.col("PATIENT")).alias("patient_id"),  # row 122
        F.trim(F.col("ENCOUNTER")).alias("encounter_id"),  # row 123
        F.col("START").cast("timestamp").alias("start_date"),  # row 125
        F.col("STOP").cast("timestamp").alias("stop_date"),  # row 126
        F.trim(F.col("SYSTEM")).alias("code_system"),  # row 129
        F.col("CODE").cast("string").alias("snomed_code"),  # row 127
        F.trim(F.col("DESCRIPTION")).alias("procedure_description"),  # row 128
        F.coalesce(F.col("BASE_COST").cast("decimal(12,2)"), F.lit(0).cast("decimal(12,2)")).alias(
            "base_cost"
        ),  # row 130
        F.col("REASONCODE").cast("string").alias("reason_code"),  # row 131
        F.trim(F.col("REASONDESCRIPTION")).alias("reason_description"),  # row 132
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
