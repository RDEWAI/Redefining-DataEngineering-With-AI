"""
Silver pipeline — Spark Declarative Pipeline.

Applies SCD Type 2 to dimension tables and transforms fact tables.
@dp.materialized_view for dims (recomputed from latest bronze snapshot).
@dp.table for facts (incremental streaming from bronze).

Run via:
    spark-pipelines run --spec spark-pipeline.yml
"""

from pyspark import pipelines as dp

from patient_360.silver.dims import (
    transform_organizations,
    transform_patients,
    transform_payers,
    transform_providers,
)
from patient_360.silver.facts import (
    transform_allergies,
    transform_claims,
    transform_conditions,
    transform_encounters,
    transform_medications,
    transform_observations,
)

DS = "2026-03-06"


# ── Dimensions (SCD Type 2 — materialized views recomputed each run) ──────────

@dp.materialized_view(comment="SCD Type 2 patient dimension — full history preserved")
def dim_patients():
    return transform_patients(spark, ds=DS)


@dp.materialized_view(comment="SCD Type 2 provider dimension")
def dim_providers():
    return transform_providers(spark, ds=DS)


@dp.materialized_view(comment="SCD Type 2 organization dimension")
def dim_organizations():
    return transform_organizations(spark, ds=DS)


@dp.materialized_view(comment="SCD Type 2 payer dimension")
def dim_payers():
    return transform_payers(spark, ds=DS)


# ── Facts (incremental streaming tables) ──────────────────────────────────────

@dp.table(comment="Encounter facts with surrogate keys, duration, readmission flag")
def fct_encounters():
    return transform_encounters(spark, ds=DS)


@dp.table(comment="Condition facts with active flag and SNOMED descriptions")
def fct_conditions():
    return transform_conditions(spark, ds=DS)


@dp.table(comment="Medication facts with active flag and RxNorm descriptions")
def fct_medications():
    return transform_medications(spark, ds=DS)


@dp.table(comment="Observation facts with result status and LOINC descriptions")
def fct_observations():
    return transform_observations(spark, ds=DS)


@dp.table(comment="Allergy facts with severity display and sort order")
def fct_allergies():
    return transform_allergies(spark, ds=DS)


@dp.table(comment="Claim facts with payer rank and service date")
def fct_claims():
    return transform_claims(spark, ds=DS)
