"""Silver transform: synthea_medications -> clinical_medications (cleansed fact).

LLD: §5.2 transform_medications_silver (insertInto unity.silver.clinical_medications;
     §13 Decision 12 + 15 — dynamic partition overwrite, never partition-predicate append,
     table-create, or path write), §5.4 (inline SE BEFORE write).
     Empty-input: Write empty (LLD §5.2).
STM: Tab:Bronze-to-Silver (medications) rows 70-87.
DMS: §3.4 clinical_medications schema.
DQS: DQ-FLD-071 .. DQ-FLD-076 (dq_rules/clinical_medications.yml).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyspark.sql import functions as F

try:
    from patient_360.utils import se_runner
except ImportError as exc:  # pragma: no cover - import-contract guard
    import logging

    logging.getLogger(__name__).critical(
        "se_runner import failed in transform_medications: %s", exc
    )
    raise

from patient_360.utils.delta_helpers import read_bronze_delta

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import DataFrame, SparkSession

TABLE = "clinical_medications"
DOMAIN = "clinical"
BRONZE_TABLE = "synthea_medications"

EMPTY_INPUT_BEHAVIOR = "write_empty"
ACTION_IF_FAILED = "fail"

# STM row 87 — SHA256 of business cols.
HASH_COLUMNS = [
    "medication_id",
    "patient_id",
    "rxnorm_code",
    "start_date",
    "medication_status",
]

# DMS §3.4 ordered columns. medication_id is the STM synthetic composite PK
# (row 70) — not a DMS business column but used in the hash; kept transient.
OUTPUT_COLUMNS = [
    "patient_id",
    "encounter_id",
    "payer_id",
    "start_date",
    "stop_date",
    "rxnorm_code",
    "medication_description",
    "base_cost",
    "payer_coverage",
    "dispenses",
    "total_cost",
    "reason_code",
    "reason_description",
    "medication_status",
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
        # row 70 — synthetic composite PK (transient; feeds the hash)
        F.sha2(
            F.concat_ws(
                "|",
                F.col("PATIENT"),
                F.col("ENCOUNTER"),
                F.col("CODE").cast("string"),
                F.col("START").cast("string"),
            ),
            256,
        ).alias("medication_id"),
        F.trim(F.col("PATIENT")).alias("patient_id"),  # row 71
        F.trim(F.col("ENCOUNTER")).alias("encounter_id"),  # row 72
        F.trim(F.col("PAYER")).alias("payer_id"),  # row 73
        F.col("START").cast("timestamp").alias("start_date"),  # row 74
        F.col("STOP").cast("timestamp").alias("stop_date"),  # row 75
        F.col("CODE").cast("string").alias("rxnorm_code"),  # row 76
        F.trim(F.col("DESCRIPTION")).alias("medication_description"),  # row 77
        F.coalesce(F.col("BASE_COST").cast("decimal(12,2)"), F.lit(0).cast("decimal(12,2)")).alias(
            "base_cost"
        ),  # row 78
        F.coalesce(
            F.col("PAYER_COVERAGE").cast("decimal(12,2)"), F.lit(0).cast("decimal(12,2)")
        ).alias("payer_coverage"),  # row 79
        F.col("DISPENSES").cast("int").alias("dispenses"),  # row 80
        F.coalesce(F.col("TOTALCOST").cast("decimal(12,2)"), F.lit(0).cast("decimal(12,2)")).alias(
            "total_cost"
        ),  # row 81
        F.col("REASONCODE").cast("string").alias("reason_code"),  # row 82
        F.trim(F.col("REASONDESCRIPTION")).alias("reason_description"),  # row 83
        # row 84 — derived status
        F.when(
            (F.col("STOP").isNull()) | (F.col("STOP").cast("timestamp") > F.current_timestamp()),
            F.lit("ACTIVE"),
        )
        .otherwise(F.lit("DISCONTINUED"))
        .alias("medication_status"),
        F.lit(ds).cast("date").alias("ds"),
        F.col("_ingested_at"),  # row 85
        F.col("_source_batch_id"),  # row 86
    )
    # row 87 — _record_hash recomputed on silver columns.
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
