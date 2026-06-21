"""Silver transform: synthea_encounters -> clinical_encounters (cleansed fact).

LLD: §5.2 transform_encounters_silver (insertInto the pre-created UC table
     `unity.silver.clinical_encounters`; §13 Decision 12 + 15 — dynamic
     partition overwrite, never partition-predicate append, table-create, or path write),
     §5.4 (inline SE BEFORE write), §6.2 (broadcast is_current dim joins).
     Empty-input: Fail task -- encounters required (LLD §5.2).
STM: Tab:Bronze-to-Silver (encounters) rows 35-56.
DMS: §3.2 clinical_encounters schema (authoritative Silver column contract).
DQS: DQ-FLD-060 .. DQ-FLD-065 (dq_rules/clinical_encounters.yml).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyspark.sql import functions as F
from pyspark.sql.window import Window

# LLD §8.6 + §13 Decision 14 — fail-closed diagnostic import wrapper (IL-010).
try:
    from patient_360.utils import se_runner
except ImportError as exc:  # pragma: no cover - import-contract guard
    import logging

    logging.getLogger(__name__).critical("se_runner import failed in transform_encounters: %s", exc)
    raise

from patient_360.utils.delta_helpers import read_bronze_delta

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import DataFrame, SparkSession

TABLE = "clinical_encounters"
DOMAIN = "clinical"
BRONZE_TABLE = "synthea_encounters"

# LLD §5.2 empty-input policy for this fact.
EMPTY_INPUT_BEHAVIOR = "fail"
# DQS PROD severity for encounters (FK-critical fact).
ACTION_IF_FAILED = "fail"

# DMS §3.2 business columns whose digest forms _record_hash (STM row 56:
# SHA256(CONCAT_WS('|', encounter_id, patient_id, start_date, encounter_class,
# snomed_code, base_encounter_cost, total_claim_cost, payer_coverage))).
HASH_COLUMNS = [
    "encounter_id",
    "patient_id",
    "start_date",
    "encounter_class",
    "snomed_code",
    "base_encounter_cost",
    "total_claim_cost",
    "payer_coverage",
]

# DMS §3.2 ordered column list (business cols, then ds + pipeline metadata +
# _record_hash). insertInto is positional, so this order is the contract.
OUTPUT_COLUMNS = [
    "encounter_id",
    "patient_id",
    "organization_id",
    "provider_id",
    "payer_id",
    "encounter_class",
    "snomed_code",
    "encounter_description",
    "start_date",
    "stop_date",
    "encounter_duration_hours",
    "los_days",
    "base_encounter_cost",
    "total_claim_cost",
    "payer_coverage",
    "total_visit_cost",
    "reason_code",
    "reason_description",
    "is_30_day_readmission",
    "ds",
    "_ingested_at",
    "_source_batch_id",
    "_record_hash",
]


def _record_hash(*cols) -> F.Column:
    parts = [F.coalesce(F.col(c).cast("string"), F.lit("")) for c in cols]
    return F.sha2(F.concat_ws("|", *parts), 256)


def _cleanse(bronze_df: DataFrame, ds: str) -> DataFrame:
    """Apply STM Bronze-to-Silver (encounters) in source-row order.

    Only DMS §3.2 columns survive the final projection.
    """
    # STM row 53: 30-day inpatient readmission flag. Implemented as a window
    # over prior inpatient discharges per patient (avoids the correlated
    # EXISTS subquery in the STM expression — equivalent semantics).
    prev_stop = (
        Window.partitionBy("PATIENT")
        .orderBy(F.col("START").cast("timestamp"))
        .rowsBetween(Window.unboundedPreceding, -1)
    )
    df = bronze_df.withColumn("_enc_class", F.upper(F.trim(F.col("ENCOUNTERCLASS"))))
    df = df.withColumn(
        "_prev_inpatient_stop",
        F.max(
            F.when(
                F.col("_enc_class") == F.lit("INPATIENT"),
                F.col("STOP").cast("timestamp"),
            )
        ).over(prev_stop),
    )
    df = df.withColumn(
        "is_30_day_readmission",
        F.when(
            (F.col("_enc_class") == F.lit("INPATIENT"))
            & F.col("_prev_inpatient_stop").isNotNull()
            & (F.col("START").cast("timestamp") > F.col("_prev_inpatient_stop"))
            & (
                F.datediff(
                    F.col("START").cast("timestamp"),
                    F.col("_prev_inpatient_stop"),
                )
                <= 30
            ),
            F.lit(True),
        ).otherwise(F.lit(False)),
    )

    projected = df.select(
        F.trim(F.col("Id")).alias("encounter_id"),  # row 35
        F.trim(F.col("PATIENT")).alias("patient_id"),  # row 36
        F.trim(F.col("ORGANIZATION")).alias("organization_id"),  # row 38
        F.trim(F.col("PROVIDER")).alias("provider_id"),  # row 37
        F.trim(F.col("PAYER")).alias("payer_id"),  # row 39
        F.col("_enc_class").alias("encounter_class"),  # row 43
        F.col("CODE").cast("string").alias("snomed_code"),  # row 44
        F.trim(F.col("DESCRIPTION")).alias("encounter_description"),  # row 45
        F.col("START").cast("timestamp").alias("start_date"),  # row 40
        F.col("STOP").cast("timestamp").alias("stop_date"),  # row 41
        # row 51 — duration hours (NULL if STOP NULL)
        F.expr(
            "CAST(timestampdiff(HOUR, CAST(START AS TIMESTAMP), "
            "CAST(STOP AS TIMESTAMP)) AS DECIMAL(10,2))"
        ).alias("encounter_duration_hours"),
        # row 52 — length of stay days
        F.datediff(F.col("STOP").cast("timestamp"), F.col("START").cast("timestamp")).alias(
            "los_days"
        ),
        F.coalesce(
            F.col("BASE_ENCOUNTER_COST").cast("decimal(12,2)"), F.lit(0).cast("decimal(12,2)")
        ).alias("base_encounter_cost"),  # row 46
        F.coalesce(
            F.col("TOTAL_CLAIM_COST").cast("decimal(12,2)"), F.lit(0).cast("decimal(12,2)")
        ).alias("total_claim_cost"),  # row 47
        F.coalesce(
            F.col("PAYER_COVERAGE").cast("decimal(12,2)"), F.lit(0).cast("decimal(12,2)")
        ).alias("payer_coverage"),  # row 48
        # DMS §3.2 total_visit_cost: cross-table aggregate (procedures +
        # medications) computed downstream in Gold; emitted NULL here as no
        # join is available in the single-table Silver cleanse.
        F.lit(None).cast("decimal(12,2)").alias("total_visit_cost"),
        F.col("REASONCODE").cast("string").alias("reason_code"),  # row 49
        F.trim(F.col("REASONDESCRIPTION")).alias("reason_description"),  # row 50
        F.col("is_30_day_readmission"),  # row 53
        F.lit(ds).cast("date").alias("ds"),
        F.col("_ingested_at"),  # row 54
        F.col("_source_batch_id"),  # row 55
    )
    # row 56 — _record_hash recomputed on silver columns.
    return projected.withColumn("_record_hash", _record_hash(*HASH_COLUMNS)).select(*OUTPUT_COLUMNS)


def transform(spark: SparkSession, env: str, ds: str) -> DataFrame:
    """Build + write the validated clinical_encounters fact for ``ds``.

    Returns the validated (post-SE, pre-write) DataFrame for unit assertions.
    """
    bronze_df = read_bronze_delta(spark, table=BRONZE_TABLE, ds=ds, env=env)

    # LLD §5.2 empty-input: Fail task -- encounters required. Distinct from the
    # SE action_if_failed gate (LLD-DEVIATIONS #3).
    if bronze_df.head(1) == []:
        raise ValueError(
            f"empty bronze input for {BRONZE_TABLE} at ds={ds}; "
            "encounters is required downstream (LLD §5.2 -- Fail task)"
        )

    silver_df = _cleanse(bronze_df, ds)

    validated_df = se_runner.run_dq(
        df=silver_df,
        table=TABLE,
        env=env,
        action_if_failed=ACTION_IF_FAILED,
        dq_rules_dir=None,  # se_runner resolves via DQ_RULES_DIR (IL-005)
    )

    # LLD §13 Decision 12 + 15 — insertInto the pre-created UC table; dynamic
    # partition overwrite (spark.sql.sources.partitionOverwriteMode=dynamic)
    # makes per-ds re-runs idempotent. NO partition-predicate append (insertInto ignores it),
    # NO table-create write, NO path-based write.
    target_table = f"unity.silver.{TABLE}"
    (validated_df.select(*OUTPUT_COLUMNS).write.mode("overwrite").insertInto(target_table))

    return validated_df


__all__ = ["transform", "TABLE", "DOMAIN", "HASH_COLUMNS", "OUTPUT_COLUMNS"]
