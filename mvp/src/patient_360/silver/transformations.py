"""Business transformation rules for all silver tables — derived from the DRD."""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType


# ── Patients (TR-001 to TR-004) ───────────────────────────────────────────────

def transform_patient_fields(df: DataFrame) -> DataFrame:
    """
    Apply patient-specific business rules.

    TR-001  full_name:      TRIM(CONCAT_WS(' ', prefix, first, middle, last, suffix))
    TR-002  age_years:      DATEDIFF(year, birthdate, today)
    TR-003  ssn_masked:     'XXX-XX-' || RIGHT(ssn, 4)
    TR-004  deceased_flag:  deathdate IS NOT NULL
    """
    return (
        df
        .withColumn(
            "full_name",
            F.trim(F.concat_ws(" ", F.col("prefix"), F.col("first"),
                               F.col("middle"), F.col("last"), F.col("suffix"))),
        )
        .withColumn(
            "age_years",
            (F.datediff(F.current_date(), F.col("birthdate")) / 365).cast(IntegerType()),
        )
        .withColumn(
            "ssn_masked",
            F.when(
                F.col("ssn").isNotNull(),
                F.concat(F.lit("XXX-XX-"), F.substring(F.col("ssn"), -4, 4)),
            ).otherwise(F.lit(None)),
        )
        .withColumn("deceased_flag", F.col("deathdate").isNotNull())
        .withColumnRenamed("id", "patient_id")
    )


# ── Encounters (TR-005 to TR-009) ─────────────────────────────────────────────

def transform_encounter_fields(df: DataFrame) -> DataFrame:
    """
    Apply encounter-specific business rules.

    TR-005  duration_minutes:    DATEDIFF(minute, start, COALESCE(stop, start))
    TR-006  encounter_status:    stop IS NULL → 'Ongoing' else 'Completed'
    TR-007  total_visit_cost:    base_encounter_cost (no procedure rollup)
    TR-008  is_readmission:      inpatient re-admit within 30 days (flagged)
    TR-009  days_since_discharge: computed via window function
    """
    return (
        df
        .withColumn("start_datetime", F.col("start"))
        .withColumn("stop_datetime",  F.col("stop"))
        .withColumn(
            "duration_minutes",
            F.timestamp_diff("minute", F.col("start"), F.coalesce(F.col("stop"), F.col("start"))),
        )
        .withColumn(
            "encounter_status",
            F.when(F.col("stop").isNull(), F.lit("Ongoing")).otherwise(F.lit("Completed")),
        )
        .withColumn("total_visit_cost", F.col("base_encounter_cost"))
        .withColumn("encounter_id",    F.col("id"))
        .withColumn("patient_nk",      F.col("patient"))
        .withColumn("provider_nk",     F.col("provider"))
        .withColumn("organization_nk", F.col("organization"))
        .withColumn("payer_nk",        F.col("payer"))
        .withColumn("reason_description", F.col("reasondescription"))
    )


# ── Conditions (TR rules) ─────────────────────────────────────────────────────

def transform_condition_fields(df: DataFrame) -> DataFrame:
    """
    Apply condition-specific business rules.

    is_active:             abatement_date (stop) IS NULL
    condition_description: code + description display
    """
    return (
        df
        .withColumn("is_active", F.col("stop").isNull())
        .withColumn(
            "condition_description",
            F.concat_ws(" — ", F.col("description"),
                        F.concat(F.lit("(SNOMED: "), F.col("code"), F.lit(")"))),
        )
        .withColumn("onset_date",      F.col("start"))
        .withColumn("abatement_date",  F.col("stop"))
        .withColumn("patient_nk",      F.col("patient"))
        .withColumn("encounter_nk",    F.col("encounter"))
        .withColumn("condition_code",  F.col("code"))
    )


# ── Medications (TR rules) ────────────────────────────────────────────────────

def transform_medication_fields(df: DataFrame) -> DataFrame:
    """
    TR-010  is_active:       stop IS NULL OR stop > today
    TR-011  payer_display:   COALESCE(payer_name, 'Self-Pay / Not Documented')
    """
    return (
        df
        .withColumn(
            "is_active",
            F.col("stop").isNull() | (F.col("stop") > F.current_date()),
        )
        .withColumn(
            "payer_display",
            F.coalesce(F.col("payer"), F.lit("Self-Pay / Not Documented")),
        )
        .withColumn(
            "medication_description",
            F.concat_ws(" — ", F.col("description"),
                        F.concat(F.lit("(RxNorm: "), F.col("code"), F.lit(")"))),
        )
        .withColumn("start_date",     F.col("start"))
        .withColumn("stop_date",      F.col("stop"))
        .withColumn("total_cost",     F.col("totalcost"))
        .withColumn("patient_nk",     F.col("patient"))
        .withColumn("encounter_nk",   F.col("encounter"))
        .withColumn("payer_nk",       F.col("payer"))
        .withColumn("medication_code", F.col("code"))
        .withColumn("reason_description", F.col("reasondescription"))
    )


# ── Observations (TR rules) ───────────────────────────────────────────────────

def transform_observation_fields(df: DataFrame) -> DataFrame:
    """
    TR-014  result_status: value IS NULL → 'Pending' else 'Available'
    """
    return (
        df
        .withColumn(
            "result_status",
            F.when(F.col("value").isNull(), F.lit("Pending")).otherwise(F.lit("Available")),
        )
        .withColumn(
            "observation_description",
            F.concat_ws(" — ", F.col("description"),
                        F.concat(F.lit("(LOINC: "), F.col("code"), F.lit(")"))),
        )
        .withColumn("observation_datetime", F.col("date"))
        .withColumn("observation_code",     F.col("code"))
        .withColumn("observation_type",     F.col("type"))
        .withColumn("patient_nk",           F.col("patient"))
        .withColumn("encounter_nk",         F.col("encounter"))
    )


# ── Allergies (TR-012, TR-013) ────────────────────────────────────────────────

def transform_allergy_fields(df: DataFrame) -> DataFrame:
    """
    TR-012  severity_display:    NULL → 'Unknown severity'
    TR-013  severity_sort_order: severe=1, moderate=2, mild=3, unknown=4
    """
    return (
        df
        .withColumn(
            "severity_display",
            F.coalesce(F.col("severity1"), F.lit("Unknown severity")),
        )
        .withColumn(
            "severity_sort_order",
            F.when(F.upper(F.col("severity1")) == "SEVERE",   F.lit(1))
             .when(F.upper(F.col("severity1")) == "MODERATE", F.lit(2))
             .when(F.upper(F.col("severity1")) == "MILD",     F.lit(3))
             .otherwise(F.lit(4))
             .cast(IntegerType()),
        )
        .withColumn(
            "allergy_description",
            F.concat_ws(" — ", F.col("description"),
                        F.concat(F.lit("(SNOMED: "), F.col("code"), F.lit(")"))),
        )
        .withColumn("allergy_code",  F.col("code"))
        .withColumn("allergy_type",  F.col("type"))
        .withColumn("onset_date",    F.col("start"))
        .withColumn("patient_nk",    F.col("patient"))
        .withColumn("encounter_nk",  F.col("encounter"))
        .withColumn("severity",      F.col("severity1"))
        .withColumn("reaction",      F.col("description1"))
    )


# ── Claims (TR-015) ───────────────────────────────────────────────────────────

def transform_claim_fields(df: DataFrame) -> DataFrame:
    """
    TR-015  payer_rank: primary / secondary based on insurance field presence.
    """
    return (
        df
        .withColumn("claim_id",    F.col("id"))
        .withColumn("patient_nk",  F.col("patientid"))
        .withColumn("provider_nk", F.col("providerid"))
        .withColumn("service_date", F.col("servicedate"))
        .withColumn(
            "outstanding_amount",
            F.coalesce(F.col("outstanding1"), F.lit(0)),
        )
        .withColumn(
            "payer_rank",
            F.when(F.col("primarypatientinsuranceid").isNotNull(), F.lit("primary"))
             .when(F.col("secondarypatientinsuranceid").isNotNull(), F.lit("secondary"))
             .otherwise(F.lit("self-pay")),
        )
        .withColumn(
            "payer_nk",
            F.coalesce(
                F.col("primarypatientinsuranceid"),
                F.col("secondarypatientinsuranceid"),
            ),
        )
    )
