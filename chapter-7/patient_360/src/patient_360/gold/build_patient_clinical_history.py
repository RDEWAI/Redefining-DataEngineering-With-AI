"""Gold builder: clinical_encounters + current dims + per-encounter fact counts
-> unity.gold.patient_clinical_history.

LLD: §5.3 build_clinical_history_gold (insertInto unity.gold.patient_clinical_history;
     §3.3 / §13 Decision 12 & 15 — full-overwrite insertInto into the pre-created
     UC EXTERNAL Delta table, never a catalog table-create / path write / partitionBy).
     §5.4 (inline SE BEFORE write). §6.2 (current-state SCD2 dim join on natural key).
     Empty-input: Fail task -- consumer table must have data (LLD §5.3).
STM: Tab:Silver-to-Gold (patient_clinical_history) — 24 target columns, grain one
     row per encounter per patient.
DMS: §4 patient_clinical_history schema (24 columns, no `ds`; grain: one row per
     encounter).
DQS: §2 Gold (patient_clinical_history: DQ_REC_005, DQ_REC_006) via
     dq_rules/patient_clinical_history.yml.

Note on active_careplan_count: STM Tab:Silver-to-Gold (patient_clinical_history)
row filters `careplan_status = 'ACTIVE'`, but the silver clinical_careplans schema
(DMS §3.9) has no `careplan_status` column — DMS §3.9 models an active care plan as
`stop_date IS NULL` ("Care plan end date — NULL for active plans"). This builder
reconciles to the authoritative DMS silver schema (`stop_date IS NULL`); the STM row
should be corrected via mapping-analyst:update-stm.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyspark.sql import functions as F

try:
    from patient_360.utils import se_runner
except ImportError as exc:  # pragma: no cover - import-contract guard
    import logging

    logging.getLogger(__name__).critical(
        "se_runner import failed in build_patient_clinical_history: %s", exc
    )
    raise

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import DataFrame, SparkSession

TABLE = "patient_clinical_history"
SCHEMA = "gold"

# LLD §5.3 empty-input behavior for every Gold table = Fail task
# ("consumer table must have data"). A required Silver input with no rows raises.
EMPTY_INPUT_BEHAVIOR = "fail"
ACTION_IF_FAILED = "fail"

# DMS §4 `patient_clinical_history` ordered columns — the exact projection written
# to unity.gold.patient_clinical_history. Positional insertInto keeps DMS §4 order.
# NOTE: no `ds` column (DMS §4 grain is one row per encounter; full overwrite).
OUTPUT_COLUMNS = [
    "encounter_id",
    "patient_id",
    "first_name",
    "last_name",
    "birth_date",
    "encounter_class",
    "encounter_description",
    "start_date",
    "stop_date",
    "encounter_duration_hours",
    "los_days",
    "is_30_day_readmission",
    "provider_id",
    "provider_name",
    "organization_id",
    "organization_name",
    "reason_description",
    "condition_count",
    "procedure_count",
    "medication_count",
    "observation_count",
    "immunization_count",
    "active_careplan_count",
    "_ingested_at",
]

# Straight passthrough columns from clinical_encounters (STM src `ce.<col>`).
_ENCOUNTER_PASSTHROUGH = [
    "encounter_id",
    "patient_id",
    "encounter_class",
    "encounter_description",
    "start_date",
    "stop_date",
    "encounter_duration_hours",
    "los_days",
    "is_30_day_readmission",
    "provider_id",
    "organization_id",
    "reason_description",
]


def _read_current(spark: SparkSession, table: str) -> DataFrame:
    """Read a current-state SCD2 silver dimension (LLD §6.2 join strategy)."""
    return spark.table(f"unity.silver.{table}").filter(F.col("is_current") == True)  # noqa: E712


def _count_by_encounter(fact: DataFrame, alias: str) -> DataFrame:
    """Pre-aggregate a silver fact to one row per encounter (STM count subqueries)."""
    return fact.groupBy("encounter_id").agg(F.count(F.lit(1)).cast("int").alias(alias))


def build(spark: SparkSession, env: str, ds: str) -> DataFrame:
    # `ds` is part of the shared builder interface (SparkSubmitOperator passes it)
    # but patient_clinical_history carries no `ds` column (DMS §4) — `_ingested_at`
    # uses CURRENT_TIMESTAMP per the STM. Kept in the signature for DAG-wiring parity.
    del ds

    # 1. Read Silver inputs (LLD §5.3 Inputs). clinical_encounters is the base fact
    #    (grain: one row per encounter). clinical_patients / reference_providers /
    #    reference_organizations are current SCD2 dimensions, joined on their natural
    #    keys. The five clinical facts + care plans are pre-aggregated to per-encounter
    #    counts before joining.
    encounters = spark.table("unity.silver.clinical_encounters")
    patients = _read_current(spark, "clinical_patients")
    providers = _read_current(spark, "reference_providers")
    organizations = _read_current(spark, "reference_organizations")
    conditions = spark.table("unity.silver.clinical_conditions")
    procedures = spark.table("unity.silver.clinical_procedures")
    medications = spark.table("unity.silver.clinical_medications")
    observations = spark.table("unity.silver.clinical_observations")
    immunizations = spark.table("unity.silver.clinical_immunizations")
    careplans = spark.table("unity.silver.clinical_careplans")

    # LLD §5.3 empty-input = Fail: the required base fact with no rows halts the task
    # (do NOT write an empty consumer table).
    if encounters.head(1) == []:
        raise ValueError(
            f"Gold {TABLE}: required Silver input clinical_encounters is empty "
            "(LLD §5.3 empty-input = Fail task)."
        )

    # 2. STM Tab:Silver-to-Gold joins + aggregations, in row order.

    # Dimension slices — project each current dim to its natural key + denorm columns
    # so the encounter-grain joins stay unambiguous (STM cp./rprov./rorg. sources).
    patients_slim = patients.select("patient_id", "first_name", "last_name", "birth_date")
    providers_slim = providers.select("provider_id", "provider_name")
    organizations_slim = organizations.select("organization_id", "organization_name")

    # Per-encounter fact counts (STM count subqueries: COUNT(*) GROUP BY encounter_id).
    cond_cnt = _count_by_encounter(conditions, "condition_count")
    proc_cnt = _count_by_encounter(procedures, "procedure_count")
    med_cnt = _count_by_encounter(medications, "medication_count")
    obs_cnt = _count_by_encounter(observations, "observation_count")
    imm_cnt = _count_by_encounter(immunizations, "immunization_count")
    # active_careplan_count: STM filters careplan_status='ACTIVE'; that column is absent
    # from the silver schema (DMS §3.9) where an active plan = stop_date IS NULL.
    careplans_active = careplans.filter(F.col("stop_date").isNull())
    careplan_cnt = _count_by_encounter(careplans_active, "active_careplan_count")

    # STM row 31: encounters INNER JOIN current patients on patient_id. Rows 44/46:
    # LEFT JOIN current providers / organizations on their natural keys. Rows 48-53:
    # LEFT JOIN per-encounter counts on encounter_id.
    joined = (
        encounters.join(patients_slim, on="patient_id", how="inner")
        .join(providers_slim, on="provider_id", how="left")
        .join(organizations_slim, on="organization_id", how="left")
        .join(cond_cnt, on="encounter_id", how="left")
        .join(proc_cnt, on="encounter_id", how="left")
        .join(med_cnt, on="encounter_id", how="left")
        .join(obs_cnt, on="encounter_id", how="left")
        .join(imm_cnt, on="encounter_id", how="left")
        .join(careplan_cnt, on="encounter_id", how="left")
    )

    # 3. Project to DMS §4 order. COALESCE the non-nullable count columns so encounters
    #    with no matching facts land 0 (STM COALESCE(...,0)). _ingested_at =
    #    CURRENT_TIMESTAMP (STM).
    passthrough = [F.col(c).alias(c) for c in _ENCOUNTER_PASSTHROUGH]
    gold_df = joined.select(
        *passthrough,
        F.col("first_name"),
        F.col("last_name"),
        F.col("birth_date"),
        F.col("provider_name"),
        F.col("organization_name"),
        F.coalesce(F.col("condition_count"), F.lit(0)).cast("int").alias("condition_count"),
        F.coalesce(F.col("procedure_count"), F.lit(0)).cast("int").alias("procedure_count"),
        F.coalesce(F.col("medication_count"), F.lit(0)).cast("int").alias("medication_count"),
        F.coalesce(F.col("observation_count"), F.lit(0)).cast("int").alias("observation_count"),
        F.coalesce(F.col("immunization_count"), F.lit(0)).cast("int").alias("immunization_count"),
        F.coalesce(F.col("active_careplan_count"), F.lit(0))
        .cast("int")
        .alias("active_careplan_count"),
        F.current_timestamp().alias("_ingested_at"),
    ).select(*OUTPUT_COLUMNS)

    # 4. DQ gate BEFORE the write (LLD §5.4). Single validated DataFrame back;
    #    action resolves per env inside run_dq (DEV/QA=ignore, PROD=fail).
    validated_df = se_runner.run_dq(
        df=gold_df,
        table=TABLE,
        env=env,
        action_if_failed=ACTION_IF_FAILED,
        dq_rules_dir=None,  # convention discovery -> dq_rules/patient_clinical_history.yml
    )

    # 5. FULL OVERWRITE into the pre-created EXTERNAL Delta table. Positional insertInto
    #    against DMS §4 order; no partitioning, no catalog table-create at runtime.
    target_table = f"unity.{SCHEMA}.{TABLE}"
    validated_df.select(*OUTPUT_COLUMNS).write.mode("overwrite").insertInto(target_table)

    return validated_df


__all__ = ["build", "TABLE", "SCHEMA", "OUTPUT_COLUMNS"]
