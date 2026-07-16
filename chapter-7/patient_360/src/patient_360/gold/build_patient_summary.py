"""Gold builder: clinical_patients (current) + clinical facts -> unity.gold.patient_summary.

LLD: §5.3 build_patient_summary_gold (insertInto unity.gold.patient_summary;
     §3.3 / §13 Decision 12 & 15 — full-overwrite insertInto into the pre-created
     UC EXTERNAL Delta table, never a catalog table-create / path write / partitionBy).
     §5.4 (inline SE BEFORE write). §6.2 (current-state SCD2 join on natural key).
     Empty-input: Fail task -- consumer table must have data (LLD §5.3).
STM: Tab:Silver-to-Gold (patient_summary) — 29 target columns.
DMS: §4 patient_summary schema (29 columns, no `ds`; grain: one row per patient,
     current SCD2 version only).
DQS: §2 Gold (DQ-FLD-105 .. DQ-FLD-140) via dq_rules/patient_summary.yml.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyspark.sql import functions as F

try:
    from patient_360.utils import se_runner
except ImportError as exc:  # pragma: no cover - import-contract guard
    import logging

    logging.getLogger(__name__).critical(
        "se_runner import failed in build_patient_summary: %s", exc
    )
    raise

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import DataFrame, SparkSession

TABLE = "patient_summary"
SCHEMA = "gold"

# LLD §5.3 empty-input behavior for every Gold table = Fail task
# ("consumer table must have data"). A required Silver input with no rows raises.
EMPTY_INPUT_BEHAVIOR = "fail"
ACTION_IF_FAILED = "fail"

# DMS §4 `patient_summary` ordered columns — the exact projection written to
# unity.gold.patient_summary. Positional insertInto keeps DMS §4 order. NOTE:
# no `ds` column (DMS §4 grain is one current row per patient; full overwrite).
OUTPUT_COLUMNS = [
    "patient_id",
    "first_name",
    "middle_name",
    "last_name",
    "prefix",
    "suffix",
    "birth_date",
    "death_date",
    "patient_status",
    "calculated_age",
    "gender",
    "race",
    "ethnicity",
    "marital_status",
    "address",
    "city",
    "state",
    "zip",
    "active_condition_count",
    "active_medication_count",
    "has_allergy",
    "allergies",
    "conditions",
    "medications",
    "recent_encounter_date",
    "recent_encounter_class",
    "encounter_count",
    "has_30day_readmission_history",
    "_ingested_at",
]

# Straight passthrough columns from clinical_patients (STM src `cp.<col>`).
_PATIENT_PASSTHROUGH = [
    "patient_id",
    "first_name",
    "middle_name",
    "last_name",
    "prefix",
    "suffix",
    "birth_date",
    "death_date",
    "patient_status",
    "calculated_age",
    "gender",
    "race",
    "ethnicity",
    "marital_status",
    "address",
    "city",
    "state",
    "zip",
]


def _read_current(spark: SparkSession, table: str) -> DataFrame:
    """Read a current-state SCD2 silver dimension (LLD §6.2 join strategy)."""
    return spark.table(f"unity.silver.{table}").filter(F.col("is_current") == True)  # noqa: E712


def build(spark: SparkSession, env: str, ds: str) -> DataFrame:
    # `ds` is part of the shared builder interface (SparkSubmitOperator passes it)
    # but patient_summary carries no `ds` column (DMS §4) — `_ingested_at` uses
    # CURRENT_TIMESTAMP per the STM. Kept in the signature for DAG-wiring parity.
    del ds

    # 1. Read Silver inputs (LLD §5.3 Inputs). clinical_patients is the current
    #    SCD2 dimension (natural key patient_id); the four fact tables are read
    #    plainly and pre-aggregated to one row per patient before the join.
    patients = _read_current(spark, "clinical_patients")
    conditions = spark.table("unity.silver.clinical_conditions")
    medications = spark.table("unity.silver.clinical_medications")
    allergies = spark.table("unity.silver.clinical_allergies")
    encounters = spark.table("unity.silver.clinical_encounters")

    # LLD §5.3 empty-input = Fail: the required base dimension with no rows halts
    # the task (do NOT write an empty consumer table).
    if patients.head(1) == []:
        raise ValueError(
            f"Gold {TABLE}: required Silver input clinical_patients is empty "
            "(LLD §5.3 empty-input = Fail task)."
        )

    # 2. STM Tab:Silver-to-Gold aggregations, in row order. Each fact is
    #    aggregated to one row per patient_id, then LEFT joined onto the current
    #    patient dimension (natural-key join; grain preserved as one row/patient).

    # STM rows active_condition_count + conditions: active conditions only
    # (condition_status = 'ACTIVE'). ARRAY<STRUCT<snomed_code, description,
    # onset_date>> via collect_list(struct(...)) — DMS §4 field names.
    conditions_active = conditions.filter(F.col("condition_status") == "ACTIVE")
    cond_agg = conditions_active.groupBy("patient_id").agg(
        F.count(F.lit(1)).cast("int").alias("active_condition_count"),
        F.collect_list(
            F.struct(
                F.col("snomed_code").alias("snomed_code"),
                F.col("condition_description").alias("description"),
                F.col("onset_date").alias("onset_date"),
            )
        ).alias("conditions"),
    )

    # STM rows active_medication_count + medications: active medications only
    # (medication_status = 'Active'). ARRAY<STRUCT<rxnorm_code, description,
    # status>>.
    medications_active = medications.filter(F.col("medication_status") == "Active")
    med_agg = medications_active.groupBy("patient_id").agg(
        F.count(F.lit(1)).cast("int").alias("active_medication_count"),
        F.collect_list(
            F.struct(
                F.col("rxnorm_code").alias("rxnorm_code"),
                F.col("medication_description").alias("description"),
                F.col("medication_status").alias("status"),
            )
        ).alias("medications"),
    )

    # STM rows has_allergy + allergies: all allergies (no status filter). NULL
    # severity1 shown as 'Unknown' per DRD §5.1/§5.4. ARRAY<STRUCT<description,
    # severity>>.
    allergy_agg = allergies.groupBy("patient_id").agg(
        F.count(F.lit(1)).alias("_allergy_count"),
        F.collect_list(
            F.struct(
                F.col("allergy_description").alias("description"),
                F.coalesce(F.col("severity1"), F.lit("Unknown")).alias("severity"),
            )
        ).alias("allergies"),
    )

    # STM rows recent_encounter_date / recent_encounter_class / encounter_count /
    # has_30day_readmission_history: per-patient encounter aggregate.
    #   recent_encounter_date  = MAX(start_date::DATE)
    #   recent_encounter_class = class of the most-recent encounter
    #                            (FIRST_VALUE ORDER BY start_date DESC)
    #   encounter_count        = COUNT(*)
    #   has_30day_readmission  = BOOL_OR(is_30_day_readmission)
    # The most-recent class is taken via MAX(struct(start_date, encounter_class)),
    # which resolves to the encounter_class carried by the max start_date.
    enc_agg = encounters.groupBy("patient_id").agg(
        F.max(F.to_date(F.col("start_date"))).alias("recent_encounter_date"),
        F.count(F.lit(1)).cast("int").alias("encounter_count"),
        F.max(F.col("is_30_day_readmission").cast("boolean")).alias(
            "_has_30day_readmission_history"
        ),
        F.max(
            F.struct(
                F.col("start_date").alias("_start_date"),
                F.col("encounter_class").alias("_encounter_class"),
            )
        ).alias("_recent_encounter"),
    )

    joined = (
        patients.join(cond_agg, on="patient_id", how="left")
        .join(med_agg, on="patient_id", how="left")
        .join(allergy_agg, on="patient_id", how="left")
        .join(enc_agg, on="patient_id", how="left")
    )

    # 3. Project to DMS §4 order. COALESCE the non-nullable count/flag columns so
    #    patients with no matching facts land 0 / False (STM COALESCE(...,0) and
    #    COALESCE(...,FALSE)). _ingested_at = CURRENT_TIMESTAMP (STM).
    passthrough = [F.col(c).alias(c) for c in _PATIENT_PASSTHROUGH]
    gold_df = joined.select(
        *passthrough,
        F.coalesce(F.col("active_condition_count"), F.lit(0)).cast("int").alias(
            "active_condition_count"
        ),
        F.coalesce(F.col("active_medication_count"), F.lit(0)).cast("int").alias(
            "active_medication_count"
        ),
        (F.coalesce(F.col("_allergy_count"), F.lit(0)) > 0).alias("has_allergy"),
        F.col("allergies"),
        F.col("conditions"),
        F.col("medications"),
        F.col("recent_encounter_date"),
        F.col("_recent_encounter._encounter_class").alias("recent_encounter_class"),
        F.coalesce(F.col("encounter_count"), F.lit(0)).cast("int").alias("encounter_count"),
        F.coalesce(F.col("_has_30day_readmission_history"), F.lit(False)).alias(
            "has_30day_readmission_history"
        ),
        F.current_timestamp().alias("_ingested_at"),
    )

    # 4. DQ gate BEFORE the write (LLD §5.4). Single validated DataFrame back;
    #    action resolves per env inside run_dq (DEV/QA=ignore, PROD=fail).
    validated_df = se_runner.run_dq(
        df=gold_df,
        table=TABLE,
        env=env,
        action_if_failed=ACTION_IF_FAILED,
        dq_rules_dir=None,  # convention discovery -> dq_rules/patient_summary.yml
    )

    # 5. FULL OVERWRITE into the pre-created EXTERNAL Delta table. Positional
    #    insertInto against DMS §4 order; no partitionBy, no catalog table-create.
    target_table = f"unity.{SCHEMA}.{TABLE}"
    validated_df.select(*OUTPUT_COLUMNS).write.mode("overwrite").insertInto(target_table)

    return validated_df


__all__ = ["build", "TABLE", "SCHEMA", "OUTPUT_COLUMNS"]
