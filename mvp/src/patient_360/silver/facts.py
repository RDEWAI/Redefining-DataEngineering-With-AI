"""Silver fact tables — joins, surrogate key resolution, and transformations."""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from patient_360.utils.delta import save_as_delta_table
from patient_360.silver.transformations import (
    transform_allergy_fields,
    transform_claim_fields,
    transform_condition_fields,
    transform_encounter_fields,
    transform_medication_fields,
    transform_observation_fields,
)

# ── Surrogate key lookup helper ───────────────────────────────────────────────

def _resolve_patient_sk(df: DataFrame, spark: SparkSession, fk_col: str = "patient_nk") -> DataFrame:
    """
    Join fact DataFrame to current dim_patients to resolve patient surrogate key.
    Uses current record (dim_is_current = true) for simplicity.
    For point-in-time accuracy, join on effective_date <= event_date <= expiry_date.
    """
    patient_sk_map = (
        spark.table("silver.dim_patients")
        .filter(F.col("dim_is_current") == True)  # noqa: E712
        .select(F.col("patient_id"), F.col("surrogate_key").alias("patient_sk"))
    )
    return df.join(patient_sk_map, df[fk_col] == patient_sk_map["patient_id"], how="left").drop("patient_id")


# ── Fact transforms ───────────────────────────────────────────────────────────

def transform_encounters(spark: SparkSession, ds: str) -> DataFrame:
    """Bronze encounters → silver fct_encounters with surrogate keys and derived fields."""
    df = (
        spark.table("bronze.encounters")
        .filter(F.col("ds") == ds)
        .transform(transform_encounter_fields)
        .transform(_resolve_patient_sk, spark=spark)
    )

    save_as_delta_table(spark, df, "silver.fct_encounters", mode="overwrite", partition_by=["ds"], replace_where=f"ds = '{ds}'")
    return spark.table("silver.fct_encounters")


def transform_conditions(spark: SparkSession, ds: str) -> DataFrame:
    """Bronze conditions → silver fct_conditions."""
    df = (
        spark.table("bronze.conditions")
        .filter(F.col("ds") == ds)
        .transform(transform_condition_fields)
        .transform(_resolve_patient_sk, spark=spark)
    )

    save_as_delta_table(spark, df, "silver.fct_conditions", mode="overwrite", partition_by=["ds"], replace_where=f"ds = '{ds}'")
    return spark.table("silver.fct_conditions")


def transform_medications(spark: SparkSession, ds: str) -> DataFrame:
    """Bronze medications → silver fct_medications."""
    df = (
        spark.table("bronze.medications")
        .filter(F.col("ds") == ds)
        .transform(transform_medication_fields)
        .transform(_resolve_patient_sk, spark=spark)
    )

    save_as_delta_table(spark, df, "silver.fct_medications", mode="overwrite", partition_by=["ds"], replace_where=f"ds = '{ds}'")
    return spark.table("silver.fct_medications")


def transform_observations(spark: SparkSession, ds: str) -> DataFrame:
    """Bronze observations → silver fct_observations."""
    df = (
        spark.table("bronze.observations")
        .filter(F.col("ds") == ds)
        .transform(transform_observation_fields)
        .transform(_resolve_patient_sk, spark=spark)
        .repartition(16)
    )

    save_as_delta_table(spark, df, "silver.fct_observations", mode="overwrite", partition_by=["ds"], replace_where=f"ds = '{ds}'")
    return spark.table("silver.fct_observations")


def transform_allergies(spark: SparkSession, ds: str) -> DataFrame:
    """Bronze allergies → silver fct_allergies."""
    df = (
        spark.table("bronze.allergies")
        .filter(F.col("ds") == ds)
        .transform(transform_allergy_fields)
        .transform(_resolve_patient_sk, spark=spark)
    )

    save_as_delta_table(spark, df, "silver.fct_allergies", mode="overwrite", partition_by=["ds"], replace_where=f"ds = '{ds}'")
    return spark.table("silver.fct_allergies")


def transform_claims(spark: SparkSession, ds: str) -> DataFrame:
    """Bronze claims → silver fct_claims."""
    df = (
        spark.table("bronze.claims")
        .filter(F.col("ds") == ds)
        .transform(transform_claim_fields)
        .transform(_resolve_patient_sk, spark=spark, fk_col="patient_nk")
    )

    save_as_delta_table(spark, df, "silver.fct_claims", mode="overwrite", partition_by=["ds"], replace_where=f"ds = '{ds}'")
    return spark.table("silver.fct_claims")


def run_facts(spark: SparkSession, ds: str) -> None:
    """Run all fact transformations for the given load date."""
    transform_encounters(spark, ds=ds)
    transform_conditions(spark, ds=ds)
    transform_medications(spark, ds=ds)
    transform_observations(spark, ds=ds)
    transform_allergies(spark, ds=ds)
    transform_claims(spark, ds=ds)
