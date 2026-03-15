"""
Bronze pipeline — Spark Declarative Pipeline.

Each @dp.table function reads a raw CSV and returns a DataFrame.
SDP handles writing to the target Delta table partitioned by ds.

Run via:
    spark-pipelines run --spec spark-pipeline.yml
"""

from pathlib import Path

from pyspark import pipelines as dp
from pyspark.sql import functions as F

from patient_360.bronze.schemas import (
    ALLERGIES,
    CLAIMS,
    CONDITIONS,
    ENCOUNTERS,
    MEDICATIONS,
    OBSERVATIONS,
    ORGANIZATIONS,
    PATIENTS,
    PAYERS,
    PROVIDERS,
)

DS       = "2026-03-06"
RAW_PATH = str(Path(__file__).parents[1] / "data" / "raw")


def _read_csv(schema, filename: str):
    """Read a Synthea CSV, enforce schema, and add audit columns."""
    return (
        spark.read.format("csv")
        .option("header", "true")
        .option("timestampFormat", "yyyy-MM-dd'T'HH:mm:ssZ")
        .schema(schema)
        .load(f"{RAW_PATH}/{filename}")
        .withColumn("ds", F.lit(DS))
        .withColumn("ingested_at", F.current_timestamp())
    )


@dp.table(comment="Raw patients — Synthea CSV, partitioned by ds")
def bronze_patients():
    return _read_csv(PATIENTS, "patients.csv")


@dp.table(comment="Raw encounters — Synthea CSV, partitioned by ds")
def bronze_encounters():
    return _read_csv(ENCOUNTERS, "encounters.csv")


@dp.table(comment="Raw conditions — Synthea CSV, partitioned by ds")
def bronze_conditions():
    return _read_csv(CONDITIONS, "conditions.csv")


@dp.table(comment="Raw medications — Synthea CSV, partitioned by ds")
def bronze_medications():
    return _read_csv(MEDICATIONS, "medications.csv")


@dp.table(comment="Raw observations — Synthea CSV, partitioned by ds")
def bronze_observations():
    return _read_csv(OBSERVATIONS, "observations.csv")


@dp.table(comment="Raw allergies — Synthea CSV, partitioned by ds")
def bronze_allergies():
    return _read_csv(ALLERGIES, "allergies.csv")


@dp.table(comment="Raw claims — Synthea CSV, partitioned by ds")
def bronze_claims():
    return _read_csv(CLAIMS, "claims.csv")


@dp.table(comment="Raw organizations — Synthea CSV, partitioned by ds")
def bronze_organizations():
    return _read_csv(ORGANIZATIONS, "organizations.csv")


@dp.table(comment="Raw providers — Synthea CSV, partitioned by ds")
def bronze_providers():
    return _read_csv(PROVIDERS, "providers.csv")


@dp.table(comment="Raw payers — Synthea CSV, partitioned by ds")
def bronze_payers():
    return _read_csv(PAYERS, "payers.csv")
