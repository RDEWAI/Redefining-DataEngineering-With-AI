"""
Gold pipeline — Spark Declarative Pipeline.

Consumer-ready layer: current-state dims, full-history facts,
and a pre-aggregated patient_summary for the search UI.

Run via:
    spark-pipelines run --spec spark-pipeline.yml
"""

from pyspark import pipelines as dp

from patient_360.gold.patient_summary import (
    transform_gold_dims,
    transform_gold_facts,
    transform_patient_summary,
)


# ── Gold dimensions (current state only — SCD columns stripped) ───────────────

@dp.materialized_view(comment="Current-state patient dim for consumers — no SCD columns")
def gold_dim_patients():
    return transform_gold_dims(spark, dim="dim_patients")


@dp.materialized_view(comment="Current-state provider dim for consumers")
def gold_dim_providers():
    return transform_gold_dims(spark, dim="dim_providers")


@dp.materialized_view(comment="Current-state organization dim for consumers")
def gold_dim_organizations():
    return transform_gold_dims(spark, dim="dim_organizations")


@dp.materialized_view(comment="Current-state payer dim for consumers")
def gold_dim_payers():
    return transform_gold_dims(spark, dim="dim_payers")


# ── Gold facts (surrogate keys resolved back to natural keys) ─────────────────

@dp.materialized_view(comment="Gold encounters — natural keys for consumers")
def gold_fct_encounters():
    return transform_gold_facts(spark, fact="fct_encounters")


@dp.materialized_view(comment="Gold conditions — natural keys for consumers")
def gold_fct_conditions():
    return transform_gold_facts(spark, fact="fct_conditions")


@dp.materialized_view(comment="Gold medications — natural keys for consumers")
def gold_fct_medications():
    return transform_gold_facts(spark, fact="fct_medications")


@dp.materialized_view(comment="Gold observations — natural keys for consumers")
def gold_fct_observations():
    return transform_gold_facts(spark, fact="fct_observations")


@dp.materialized_view(comment="Gold allergies — natural keys for consumers")
def gold_fct_allergies():
    return transform_gold_facts(spark, fact="fct_allergies")


@dp.materialized_view(comment="Gold claims — natural keys for consumers")
def gold_fct_claims():
    return transform_gold_facts(spark, fact="fct_claims")


# ── Patient summary (one row per patient, search-optimised) ───────────────────

@dp.materialized_view(comment="Aggregated patient 360 summary — one row per patient, p90 < 2s SLA")
def patient_summary():
    return transform_patient_summary(spark)
