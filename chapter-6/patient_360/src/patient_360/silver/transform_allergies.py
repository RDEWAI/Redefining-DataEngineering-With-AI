"""Silver transform: synthea_allergies -> clinical_allergies (cleansed fact).

LLD: §5.2 transform_allergies_silver (insertInto unity.silver.clinical_allergies;
     §13 Decision 12 + 15 — dynamic partition overwrite, never partition-predicate append,
     table-create, or path write), §5.4 (inline SE BEFORE write).
     Empty-input: Fail task -- safety critical [DRD §1.3] (LLD §5.2 -- Fail task).
STM: Tab:Bronze-to-Silver (allergies) rows 102-120.
DMS: §3.6 clinical_allergies schema.
DQS: DQ-FLD-080 .. DQ-FLD-083 (dq_rules/clinical_allergies.yml).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyspark.sql import functions as F

try:
    from patient_360.utils import se_runner
except ImportError as exc:  # pragma: no cover - import-contract guard
    import logging

    logging.getLogger(__name__).critical("se_runner import failed in transform_allergies: %s", exc)
    raise

from patient_360.utils.delta_helpers import read_bronze_delta

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import DataFrame, SparkSession

TABLE = "clinical_allergies"
DOMAIN = "clinical"
BRONZE_TABLE = "synthea_allergies"

EMPTY_INPUT_BEHAVIOR = "fail"
ACTION_IF_FAILED = "fail"

# STM row 120 — SHA256 of business cols. allergy_code is the DMS §3.6 name for
# the SNOMED code column (STM row 120 references it as snomed_code).
HASH_COLUMNS = [
    "allergy_id",
    "patient_id",
    "allergy_code",
    "allergy_description",
]

# DMS §3.6 ordered columns. allergy_id is the STM synthetic composite PK
# (row 102) — not a DMS business column but used in the hash; kept transient.
OUTPUT_COLUMNS = [
    "patient_id",
    "encounter_id",
    "start_date",
    "stop_date",
    "allergy_code",
    "code_system",
    "allergy_description",
    "allergy_type",
    "allergy_category",
    "reaction1_code",
    "reaction1_description",
    "severity1",
    "reaction2_code",
    "reaction2_description",
    "severity2",
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
        # row 102 — synthetic composite PK (transient; feeds the hash)
        F.sha2(
            F.concat_ws(
                "|",
                F.col("PATIENT"),
                F.col("CODE").cast("string"),
                F.col("START").cast("string"),
            ),
            256,
        ).alias("allergy_id"),
        F.trim(F.col("PATIENT")).alias("patient_id"),  # row 103
        F.trim(F.col("ENCOUNTER")).alias("encounter_id"),  # row 104
        F.col("START").cast("date").alias("start_date"),  # row 105
        # row 106 — STOP is VARCHAR in source
        F.expr("try_cast(STOP as date)").alias("stop_date"),
        F.col("CODE").cast("string").alias("allergy_code"),  # row 107
        F.trim(F.col("SYSTEM")).alias("code_system"),  # row 108
        # row 109 — NOT NULL safety-critical
        F.trim(F.col("DESCRIPTION")).alias("allergy_description"),
        F.trim(F.col("TYPE")).alias("allergy_type"),  # row 110
        F.trim(F.col("CATEGORY")).alias("allergy_category"),  # row 111
        F.col("REACTION1").cast("string").alias("reaction1_code"),  # row 112
        F.trim(F.col("DESCRIPTION1")).alias("reaction1_description"),  # row 113
        # row 114 — DMS §3.6 COALESCE 'Unknown'
        F.coalesce(F.trim(F.col("SEVERITY1")), F.lit("Unknown")).alias("severity1"),
        F.col("REACTION2").cast("string").alias("reaction2_code"),  # row 115
        F.trim(F.col("DESCRIPTION2")).alias("reaction2_description"),  # row 116
        F.trim(F.col("SEVERITY2")).alias("severity2"),  # row 117
        F.lit(ds).cast("date").alias("ds"),
        F.col("_ingested_at"),  # row 118
        F.col("_source_batch_id"),  # row 119
    )
    # row 120 — _record_hash recomputed on silver columns.
    return df.withColumn("_record_hash", _record_hash(*HASH_COLUMNS)).select(*OUTPUT_COLUMNS)


def transform(spark: SparkSession, env: str, ds: str) -> DataFrame:
    bronze_df = read_bronze_delta(spark, table=BRONZE_TABLE, ds=ds, env=env)

    # LLD §5.2 empty-input: Fail task -- safety critical. Distinct from the
    # SE action_if_failed gate (LLD-DEVIATIONS #3).
    if bronze_df.head(1) == []:
        raise ValueError(
            f"empty bronze input for {BRONZE_TABLE} at ds={ds}; "
            "allergies is safety critical [DRD §1.3] (LLD §5.2 -- Fail task)"
        )

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
