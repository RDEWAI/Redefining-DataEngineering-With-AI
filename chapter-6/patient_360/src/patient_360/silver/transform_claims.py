"""Silver transform: synthea_claims -> billing_claims (cleansed fact).

LLD: §5.2 transform_claims_silver (insertInto unity.silver.billing_claims;
     §13 Decision 12 + 15 — dynamic partition overwrite, never partition-predicate append,
     table-create, or path write), §5.4 (inline SE BEFORE write).
     Empty-input: Write empty (LLD §5.2).
STM: Tab:Bronze-to-Silver (claims) rows 151-167.
DMS: §3.10 billing_claims schema (AUTHORITATIVE Silver column contract — note
     the DMS column names differ from the STM v3 target names; the DMS owns the
     Silver contract, so DMS names + the full DMS column set win. The extra DMS
     columns (diagnosis_code_3, referring/supervising_provider_id) map directly
     from the bronze source columns DIAGNOSIS3 / REFERRINGPROVIDERID /
     SUPERVISINGPROVIDERID present in synthea_claims).
DQS: DQ-FLD-093 .. DQ-FLD-094 (dq_rules/billing_claims.yml).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyspark.sql import functions as F

try:
    from patient_360.utils import se_runner
except ImportError as exc:  # pragma: no cover - import-contract guard
    import logging

    logging.getLogger(__name__).critical("se_runner import failed in transform_claims: %s", exc)
    raise

from patient_360.utils.delta_helpers import read_bronze_delta

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import DataFrame, SparkSession

TABLE = "billing_claims"
DOMAIN = "billing"
BRONZE_TABLE = "synthea_claims"

EMPTY_INPUT_BEHAVIOR = "write_empty"
ACTION_IF_FAILED = "fail"

# Business columns whose digest forms _record_hash (DMS §3.10 business cols).
HASH_COLUMNS = [
    "claim_id",
    "patient_id",
    "provider_id",
    "service_date",
    "outstanding_primary",
    "outstanding_secondary",
    "outstanding_patient",
]

# DMS §3.10 ordered column list (authoritative). insertInto is positional.
OUTPUT_COLUMNS = [
    "claim_id",
    "patient_id",
    "provider_id",
    "primary_insurance_id",
    "secondary_insurance_id",
    "diagnosis_code_1",
    "diagnosis_code_2",
    "diagnosis_code_3",
    "referring_provider_id",
    "supervising_provider_id",
    "service_date",
    "current_illness_date",
    "status_primary",
    "status_secondary",
    "status_patient",
    "outstanding_primary",
    "outstanding_secondary",
    "outstanding_patient",
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
        F.trim(F.col("Id")).alias("claim_id"),  # row 151
        F.trim(F.col("PATIENTID")).alias("patient_id"),  # row 152
        F.trim(F.col("PROVIDERID")).alias("provider_id"),  # row 153
        F.trim(F.col("PRIMARYPATIENTINSURANCEID")).alias("primary_insurance_id"),  # row 154
        F.trim(F.col("SECONDARYPATIENTINSURANCEID")).alias("secondary_insurance_id"),  # row 155
        F.col("DIAGNOSIS1").cast("string").alias("diagnosis_code_1"),  # row 159
        F.col("DIAGNOSIS2").cast("string").alias("diagnosis_code_2"),  # row 160
        # DMS §3.10 diagnosis_code_3 — maps from bronze DIAGNOSIS3 (present in
        # synthea_claims; not in the STM v3 subset, sourced per DMS).
        F.col("DIAGNOSIS3").cast("string").alias("diagnosis_code_3"),
        # DMS §3.10 referring_provider_id — bronze REFERRINGPROVIDERID.
        F.trim(F.col("REFERRINGPROVIDERID")).alias("referring_provider_id"),
        # DMS §3.10 supervising_provider_id — bronze SUPERVISINGPROVIDERID.
        F.trim(F.col("SUPERVISINGPROVIDERID")).alias("supervising_provider_id"),
        # DMS §3.10 service_date is TIMESTAMP (STM casts to DATE; DMS wins).
        F.col("SERVICEDATE").cast("timestamp").alias("service_date"),  # row 157
        F.col("CURRENTILLNESSDATE").cast("timestamp").alias("current_illness_date"),  # row 158
        F.trim(F.col("STATUS1")).alias("status_primary"),  # row 161
        F.trim(F.col("STATUS2")).alias("status_secondary"),  # row 162
        F.trim(F.col("STATUSP")).alias("status_patient"),  # row 163
        F.coalesce(
            F.col("OUTSTANDING1").cast("decimal(12,2)"), F.lit(0).cast("decimal(12,2)")
        ).alias("outstanding_primary"),  # row 164
        F.coalesce(
            F.col("OUTSTANDING2").cast("decimal(12,2)"), F.lit(0).cast("decimal(12,2)")
        ).alias("outstanding_secondary"),  # row 165
        F.coalesce(
            F.col("OUTSTANDINGP").cast("decimal(12,2)"), F.lit(0).cast("decimal(12,2)")
        ).alias("outstanding_patient"),  # row 166
        F.lit(ds).cast("date").alias("ds"),
        F.col("_ingested_at"),
        F.col("_source_batch_id"),
    )
    return df.withColumn("_record_hash", _record_hash(*HASH_COLUMNS)).select(*OUTPUT_COLUMNS)


def transform(spark: SparkSession, env: str, ds: str) -> DataFrame:
    bronze_df = read_bronze_delta(spark, table=BRONZE_TABLE, ds=ds, env=env)

    # LLD §5.2 empty-input: Write empty.
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
