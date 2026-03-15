"""Silver dimension tables — SCD Type 2 applied via reusable apply_scd2()."""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from patient_360.silver.scd2 import apply_scd2
from patient_360.silver.transformations import transform_patient_fields

# ── SCD Type 2 config — one entry per dimension ───────────────────────────────
# natural_key:     business key, stable across versions
# tracked_columns: changes to these columns trigger a new SCD2 row

SCD2_CONFIG: dict[str, dict] = {
    "dim_patients": {
        "natural_key": "patient_id",
        "tracked_columns": [
            "address", "city", "state", "zip",
            "gender", "race", "ethnicity", "deceased_flag", "deathdate",
        ],
    },
    "dim_providers": {
        "natural_key": "provider_id",
        "tracked_columns": ["speciality", "address", "city", "state", "organization_id"],
    },
    "dim_organizations": {
        "natural_key": "org_id",
        "tracked_columns": ["name", "address", "city", "state", "zip", "phone"],
    },
    "dim_payers": {
        "natural_key": "payer_id",
        "tracked_columns": ["name", "member_months", "amount_covered"],
    },
}


# ── Individual dimension transforms ───────────────────────────────────────────

def transform_patients(spark: SparkSession, ds: str) -> DataFrame:
    """
    Read bronze.patients for ds, apply business rules, apply SCD Type 2.
    Returns the full silver.dim_patients table (all versions).
    """
    source = (
        spark.table("bronze.patients")
        .filter(F.col("ds") == ds)
        .transform(transform_patient_fields)
    )

    cfg = SCD2_CONFIG["dim_patients"]
    apply_scd2(
        spark=spark,
        source_df=source,
        target_table="silver.dim_patients",
        natural_key=cfg["natural_key"],
        tracked_columns=cfg["tracked_columns"],
        ds=ds,
    )

    return spark.table("silver.dim_patients")


def transform_providers(spark: SparkSession, ds: str) -> DataFrame:
    """Read bronze.providers for ds, apply SCD Type 2."""
    source = (
        spark.table("bronze.providers")
        .filter(F.col("ds") == ds)
        .withColumnRenamed("id", "provider_id")
        .withColumnRenamed("organization", "organization_id")
    )

    cfg = SCD2_CONFIG["dim_providers"]
    apply_scd2(
        spark=spark,
        source_df=source,
        target_table="silver.dim_providers",
        natural_key=cfg["natural_key"],
        tracked_columns=cfg["tracked_columns"],
        ds=ds,
    )

    return spark.table("silver.dim_providers")


def transform_organizations(spark: SparkSession, ds: str) -> DataFrame:
    """Read bronze.organizations for ds, apply SCD Type 2."""
    source = (
        spark.table("bronze.organizations")
        .filter(F.col("ds") == ds)
        .withColumnRenamed("id", "org_id")
    )

    cfg = SCD2_CONFIG["dim_organizations"]
    apply_scd2(
        spark=spark,
        source_df=source,
        target_table="silver.dim_organizations",
        natural_key=cfg["natural_key"],
        tracked_columns=cfg["tracked_columns"],
        ds=ds,
    )

    return spark.table("silver.dim_organizations")


def transform_payers(spark: SparkSession, ds: str) -> DataFrame:
    """Read bronze.payers for ds, apply SCD Type 2."""
    source = (
        spark.table("bronze.payers")
        .filter(F.col("ds") == ds)
        .withColumnRenamed("id", "payer_id")
    )

    cfg = SCD2_CONFIG["dim_payers"]
    apply_scd2(
        spark=spark,
        source_df=source,
        target_table="silver.dim_payers",
        natural_key=cfg["natural_key"],
        tracked_columns=cfg["tracked_columns"],
        ds=ds,
    )

    return spark.table("silver.dim_payers")


def run_dims(spark: SparkSession, ds: str) -> None:
    """Run all dimension SCD Type 2 merges for the given load date."""
    transform_patients(spark, ds=ds)
    transform_providers(spark, ds=ds)
    transform_organizations(spark, ds=ds)
    transform_payers(spark, ds=ds)
