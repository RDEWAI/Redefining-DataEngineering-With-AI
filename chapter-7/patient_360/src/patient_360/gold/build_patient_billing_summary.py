"""Gold builder: clinical_encounters + clinical_patients (current) + billing_claims
+ reference_payers (current) + reference_providers (current)
-> unity.gold.patient_billing_summary.

LLD: §5.3 build_billing_summary_gold (insertInto unity.gold.patient_billing_summary;
     §3.3 / §13 Decision 12 & 15 — full-overwrite insertInto into the pre-created
     UC EXTERNAL Delta table, never a catalog table-create / path write / partitionBy).
     §5.4 (inline SE BEFORE write). §6.2 (current-state SCD2 join on natural key).
     Empty-input: Fail task -- consumer table must have data (LLD §5.3).
STM: Tab:Silver-to-Gold (patient_billing_summary) — 21 target columns; encounter grain
     (one row per encounter per patient). Plain joins; the LLD §6.2/§6.4 broadcast +
     cache of the small reference_payers dim is deferred to STORY-05-004.
DMS: §4 patient_billing_summary schema (21 columns, no `ds`; cost fields isolated to
     this table only per DRD §5.5).
DQS: §2 Gold (DQ-FLD-163 .. DQ-FLD-189, DQ_REF_020, DQ_STA_019) via
     dq_rules/patient_billing_summary.yml.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyspark.sql import functions as F

try:
    from patient_360.utils import se_runner
except ImportError as exc:  # pragma: no cover - import-contract guard
    import logging

    logging.getLogger(__name__).critical(
        "se_runner import failed in build_patient_billing_summary: %s", exc
    )
    raise

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import DataFrame, SparkSession

TABLE = "patient_billing_summary"
SCHEMA = "gold"

# LLD §5.3 empty-input behavior for every Gold table = Fail task
# ("consumer table must have data"). A required Silver input with no rows raises.
EMPTY_INPUT_BEHAVIOR = "fail"
ACTION_IF_FAILED = "fail"

# DMS §4 `patient_billing_summary` ordered columns — the exact projection written to
# unity.gold.patient_billing_summary. Positional insertInto keeps DMS §4 order. NOTE:
# no `ds` column (DMS §4 grain is one row per encounter per patient; full overwrite).
OUTPUT_COLUMNS = [
    "encounter_id",
    "patient_id",
    "first_name",
    "last_name",
    "birth_date",
    "encounter_class",
    "service_date",
    "base_encounter_cost",
    "total_claim_cost",
    "payer_coverage",
    "total_visit_cost",
    "claim_id",
    "primary_payer_id",
    "primary_payer_name",
    "secondary_payer_id",
    "secondary_payer_name",
    "claim_status",
    "outstanding_amount",
    "provider_id",
    "provider_name",
    "_ingested_at",
]

_COST = "decimal(12,2)"


def _read_current(spark: SparkSession, table: str) -> DataFrame:
    """Read a current-state SCD2 silver dimension (LLD §6.2 join strategy)."""
    return spark.table(f"unity.silver.{table}").filter(F.col("is_current") == True)  # noqa: E712


def build(spark: SparkSession, env: str, ds: str) -> DataFrame:
    # `ds` is part of the shared builder interface (SparkSubmitOperator passes it)
    # but patient_billing_summary carries no `ds` column (DMS §4) — `_ingested_at`
    # uses CURRENT_TIMESTAMP per the STM. Kept in the signature for DAG-wiring parity.
    del ds

    # 1. Read Silver inputs (LLD §5.3 Inputs). clinical_encounters is the grain
    #    driver (one row per encounter); clinical_patients / reference_payers /
    #    reference_providers are current SCD2 dimensions read on their natural key.
    #    billing_claims is a plain Silver fact LEFT-joined on the encounter linkage.
    #    Each source is aliased so the multi-join projection is unambiguous.
    encounters = spark.table("unity.silver.clinical_encounters").alias("ce")
    patients = _read_current(spark, "clinical_patients").alias("cp")
    claims = spark.table("unity.silver.billing_claims").alias("bc")
    payers_primary = _read_current(spark, "reference_payers").alias("rpay")
    payers_secondary = _read_current(spark, "reference_payers").alias("rpay2")
    providers = _read_current(spark, "reference_providers").alias("rprov")

    # LLD §5.3 empty-input = Fail: the encounter grain driver with no rows halts the
    # task (do NOT write an empty consumer table).
    if encounters.head(1) == []:
        raise ValueError(
            f"Gold {TABLE}: required Silver input clinical_encounters is empty "
            "(LLD §5.3 empty-input = Fail task)."
        )

    # 2. STM Tab:Silver-to-Gold joins, IN STM ROW ORDER (encounter grain preserved):
    #    ce INNER JOIN cp (is_current) ON patient_id
    #       LEFT JOIN bc ON bc.appointment_id = ce.encounter_id
    #       LEFT JOIN rpay  (is_current) ON rpay.payer_id  = bc.primary_payer_id
    #       LEFT JOIN rpay2 (is_current) ON rpay2.payer_id = bc.secondary_payer_id
    #       LEFT JOIN rprov (is_current) ON rprov.provider_id = ce.provider_id
    joined = (
        encounters.join(patients, F.col("cp.patient_id") == F.col("ce.patient_id"), "inner")
        .join(claims, F.col("bc.appointment_id") == F.col("ce.encounter_id"), "left")
        .join(payers_primary, F.col("rpay.payer_id") == F.col("bc.primary_payer_id"), "left")
        .join(
            payers_secondary,
            F.col("rpay2.payer_id") == F.col("bc.secondary_payer_id"),
            "left",
        )
        .join(providers, F.col("rprov.provider_id") == F.col("ce.provider_id"), "left")
    )

    # 3. Project to DMS §4 order. Cost fields COALESCE to 0 (STM / DRD §5.1); the
    #    payer/provider names are the denormalized dimension pulls. outstanding_amount
    #    sums the three per-responsibility outstanding balances (STM expression).
    #    _ingested_at = CURRENT_TIMESTAMP (STM).
    gold_df = joined.select(
        F.col("ce.encounter_id").alias("encounter_id"),
        F.col("ce.patient_id").alias("patient_id"),
        F.col("cp.first_name").alias("first_name"),
        F.col("cp.last_name").alias("last_name"),
        F.col("cp.birth_date").alias("birth_date"),
        F.col("ce.encounter_class").alias("encounter_class"),
        F.col("bc.service_date").cast("date").alias("service_date"),
        F.coalesce(F.col("ce.base_encounter_cost"), F.lit(0)).cast(_COST).alias(
            "base_encounter_cost"
        ),
        F.coalesce(F.col("ce.total_claim_cost"), F.lit(0)).cast(_COST).alias("total_claim_cost"),
        F.coalesce(F.col("ce.payer_coverage"), F.lit(0)).cast(_COST).alias("payer_coverage"),
        F.coalesce(F.col("ce.total_visit_cost"), F.lit(0)).cast(_COST).alias("total_visit_cost"),
        F.col("bc.claim_id").alias("claim_id"),
        F.col("bc.primary_payer_id").alias("primary_payer_id"),
        F.col("rpay.payer_name").alias("primary_payer_name"),
        F.col("bc.secondary_payer_id").alias("secondary_payer_id"),
        F.col("rpay2.payer_name").alias("secondary_payer_name"),
        F.col("bc.status_primary").alias("claim_status"),
        (
            F.coalesce(F.col("bc.outstanding_primary"), F.lit(0))
            + F.coalesce(F.col("bc.outstanding_secondary"), F.lit(0))
            + F.coalesce(F.col("bc.outstanding_patient"), F.lit(0))
        )
        .cast(_COST)
        .alias("outstanding_amount"),
        F.col("ce.provider_id").alias("provider_id"),
        F.col("rprov.provider_name").alias("provider_name"),
        F.current_timestamp().alias("_ingested_at"),
    )

    # 4. DQ gate BEFORE the write (LLD §5.4). Single validated DataFrame back;
    #    action resolves per env inside run_dq (DEV/QA=ignore, PROD=fail).
    validated_df = se_runner.run_dq(
        df=gold_df,
        table=TABLE,
        env=env,
        action_if_failed=ACTION_IF_FAILED,
        dq_rules_dir=None,  # convention discovery -> dq_rules/patient_billing_summary.yml
    )

    # 5. FULL OVERWRITE into the pre-created EXTERNAL Delta table. Positional
    #    insertInto against DMS §4 order; no partitioning, no catalog table-create.
    target_table = f"unity.{SCHEMA}.{TABLE}"
    validated_df.select(*OUTPUT_COLUMNS).write.mode("overwrite").insertInto(target_table)

    return validated_df


__all__ = ["build", "TABLE", "SCHEMA", "OUTPUT_COLUMNS"]
