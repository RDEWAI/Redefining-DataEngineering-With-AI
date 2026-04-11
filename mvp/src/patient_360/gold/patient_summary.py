"""Gold layer — Patient 360 summary: one consumer-ready row per current patient."""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from patient_360.utils.delta import save_as_delta_table


# SCD2 metadata columns — stripped in gold (consumers don't need versioning internals)
_SCD2_COLS = [
    "start_ts", "end_ts",
    "dim_is_current", "record_hash", "dw_created_at", "dw_updated_at",
]


def _current_patients(spark: SparkSession) -> DataFrame:
    """Current-state dim_patients — keep surrogate_key for joining, drop other SCD2 cols."""
    return (
        spark.table("silver.dim_patients")
        .filter(F.col("dim_is_current") == True)  # noqa: E712
        .drop(*_SCD2_COLS)
    )


def _encounter_metrics(spark: SparkSession) -> DataFrame:
    """Per-patient encounter aggregates."""
    return (
        spark.table("silver.fct_encounters")
        .groupBy("patient_sk")
        .agg(
            F.count("*").alias("total_encounters"),
            F.sum(F.col("total_visit_cost")).alias("total_visit_cost"),
            F.max("start_datetime").alias("last_visit_date"),
            F.count(
                F.when(F.col("encounter_status") == "Ongoing", True)
            ).alias("active_encounters"),
        )
    )


def _condition_metrics(spark: SparkSession) -> DataFrame:
    """Per-patient condition aggregates."""
    return (
        spark.table("silver.fct_conditions")
        .groupBy("patient_sk")
        .agg(
            F.count("*").alias("total_conditions"),
            F.count(F.when(F.col("is_active") == True, True)).alias("active_conditions"),  # noqa: E712
        )
    )


def _medication_metrics(spark: SparkSession) -> DataFrame:
    """Per-patient medication aggregates."""
    return (
        spark.table("silver.fct_medications")
        .groupBy("patient_sk")
        .agg(
            F.count("*").alias("total_medications"),
            F.count(F.when(F.col("is_active") == True, True)).alias("active_medications"),  # noqa: E712
        )
    )


def _allergy_metrics(spark: SparkSession) -> DataFrame:
    """Per-patient allergy aggregates."""
    return (
        spark.table("silver.fct_allergies")
        .groupBy("patient_sk")
        .agg(
            F.count("*").alias("total_allergies"),
            F.count(
                F.when(F.upper(F.col("severity")) == "SEVERE", True)
            ).alias("severe_allergies"),
        )
    )


def transform_patient_summary(spark: SparkSession, ds: str) -> DataFrame:
    """
    Build the Patient 360 summary — one row per current patient.

    Joins current dim_patients with aggregated metrics from all fact tables.
    Consumers get a single wide table with demographics + clinical metrics.

    Args:
        spark: Active SparkSession.
        ds:    Load date string "YYYY-MM-DD" (written as partition).

    Returns:
        Patient 360 summary DataFrame.
    """
    patients = _current_patients(spark)
    encounters = _encounter_metrics(spark)
    conditions = _condition_metrics(spark)
    medications = _medication_metrics(spark)
    allergies = _allergy_metrics(spark)

    # Join dimension to all fact aggregates via surrogate key
    # Patients without any fact rows still appear (left joins → nulls → coalesced to 0)
    sk = "patient_sk"
    dim_sk = F.col("dim_patients.surrogate_key")

    summary = (
        patients.alias("dim_patients")
        .join(encounters.alias("enc"),   dim_sk == F.col(f"enc.{sk}"),  how="left")
        .join(conditions.alias("cond"),  dim_sk == F.col(f"cond.{sk}"), how="left")
        .join(medications.alias("med"),  dim_sk == F.col(f"med.{sk}"),  how="left")
        .join(allergies.alias("alg"),    dim_sk == F.col(f"alg.{sk}"),  how="left")
        .select(
            # ── Identity ──────────────────────────────────────────────────────
            F.col("dim_patients.patient_id"),
            F.col("dim_patients.full_name"),
            F.col("dim_patients.birthdate"),
            F.col("dim_patients.age_years"),
            F.col("dim_patients.gender"),
            F.col("dim_patients.race"),
            F.col("dim_patients.ethnicity"),
            F.col("dim_patients.ssn_masked"),
            F.col("dim_patients.address"),
            F.col("dim_patients.city"),
            F.col("dim_patients.state"),
            F.col("dim_patients.zip"),
            F.col("dim_patients.deceased_flag"),
            F.col("dim_patients.deathdate"),
            # ── Encounter metrics ─────────────────────────────────────────────
            F.coalesce(F.col("enc.total_encounters"),  F.lit(0)).alias("total_encounters"),
            F.coalesce(F.col("enc.active_encounters"), F.lit(0)).alias("active_encounters"),
            F.coalesce(F.col("enc.total_visit_cost"),  F.lit(0.0)).alias("total_visit_cost"),
            F.col("enc.last_visit_date"),
            # ── Condition metrics ─────────────────────────────────────────────
            F.coalesce(F.col("cond.total_conditions"),  F.lit(0)).alias("total_conditions"),
            F.coalesce(F.col("cond.active_conditions"), F.lit(0)).alias("active_conditions"),
            # ── Medication metrics ────────────────────────────────────────────
            F.coalesce(F.col("med.total_medications"),  F.lit(0)).alias("total_medications"),
            F.coalesce(F.col("med.active_medications"), F.lit(0)).alias("active_medications"),
            # ── Allergy metrics ───────────────────────────────────────────────
            F.coalesce(F.col("alg.total_allergies"),  F.lit(0)).alias("total_allergies"),
            F.coalesce(F.col("alg.severe_allergies"), F.lit(0)).alias("severe_allergies"),
            # ── Partition ────────────────────────────────────────────────────
            F.lit(ds).alias("ds"),
        )
    )

    return summary


def run_gold(spark: SparkSession, ds: str) -> None:
    """Write the Patient 360 summary to gold.patient_summary."""
    df = transform_patient_summary(spark, ds)
    save_as_delta_table(
        spark, df, "gold.patient_summary",
        mode="overwrite",
        partition_by=["ds"],
        replace_where=f"ds = '{ds}'",
    )
