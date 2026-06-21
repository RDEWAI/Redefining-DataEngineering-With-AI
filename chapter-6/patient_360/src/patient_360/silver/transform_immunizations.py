"""Silver transform: synthea_immunizations -> clinical_immunizations (cleansed fact).

LLD: §5.2 transform_immunizations_silver (insertInto unity.silver.clinical_immunizations;
     §13 Decision 12 + 15 — dynamic partition overwrite, never partition-predicate append,
     table-create, or path write), §5.4 (inline SE BEFORE write).
     Empty-input: Write empty (LLD §5.2).
STM: Tab:Bronze-to-Silver (immunizations) rows 133-140.
DMS: §3.8 clinical_immunizations schema.
DQS: DQ-FLD-088 .. DQ-FLD-090 (dq_rules/clinical_immunizations.yml).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyspark.sql import functions as F

try:
    from patient_360.utils import se_runner
except ImportError as exc:  # pragma: no cover - import-contract guard
    import logging

    logging.getLogger(__name__).critical(
        "se_runner import failed in transform_immunizations: %s", exc
    )
    raise

from patient_360.utils.delta_helpers import read_bronze_delta

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import DataFrame, SparkSession

TABLE = "clinical_immunizations"
DOMAIN = "clinical"
BRONZE_TABLE = "synthea_immunizations"

EMPTY_INPUT_BEHAVIOR = "write_empty"
ACTION_IF_FAILED = "fail"

# DMS §3.8 shows no _record_hash business-col STM row; use the deterministic
# business-key set as the hash input.
HASH_COLUMNS = [
    "immunization_id",
    "patient_id",
    "cvx_code",
    "immunization_date",
]

# DMS §3.8 ordered columns. immunization_id is the STM synthetic composite PK
# (row 133) — not a DMS business column but used in the hash; kept transient.
OUTPUT_COLUMNS = [
    "patient_id",
    "encounter_id",
    "immunization_date",
    "cvx_code",
    "immunization_description",
    "base_cost",
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
        # row 133 — synthetic composite PK (transient; feeds the hash)
        F.sha2(
            F.concat_ws(
                "|",
                F.col("PATIENT"),
                F.col("ENCOUNTER"),
                F.col("CODE"),
                F.col("DATE").cast("string"),
            ),
            256,
        ).alias("immunization_id"),
        F.trim(F.col("PATIENT")).alias("patient_id"),  # row 134
        F.trim(F.col("ENCOUNTER")).alias("encounter_id"),  # row 135
        # DMS §3.8 immunization_date is TIMESTAMP.
        F.col("DATE").cast("timestamp").alias("immunization_date"),
        F.trim(F.col("CODE")).alias("cvx_code"),  # row 138
        F.trim(F.col("DESCRIPTION")).alias("immunization_description"),  # row 139
        F.coalesce(F.col("BASE_COST").cast("decimal(12,2)"), F.lit(0).cast("decimal(12,2)")).alias(
            "base_cost"
        ),  # row 140
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
