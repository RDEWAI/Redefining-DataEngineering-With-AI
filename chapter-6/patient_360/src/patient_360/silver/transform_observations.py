"""Silver transform: synthea_observations -> clinical_observations (cleansed fact).

LLD: §5.2 transform_observations_silver (insertInto unity.silver.clinical_observations;
     §13 Decision 12 + 15 — dynamic partition overwrite, never partition-predicate append,
     table-create, or path write), §5.4 (inline SE BEFORE write).
     Empty-input: Write empty (LLD §5.2).
STM: Tab:Bronze-to-Silver (observations) rows 88-101.
DMS: §3.5 clinical_observations schema.
DQS: DQ-FLD-077 .. DQ-FLD-079 (dq_rules/clinical_observations.yml).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyspark.sql import functions as F

try:
    from patient_360.utils import se_runner
except ImportError as exc:  # pragma: no cover - import-contract guard
    import logging

    logging.getLogger(__name__).critical(
        "se_runner import failed in transform_observations: %s", exc
    )
    raise

from patient_360.utils.delta_helpers import read_bronze_delta

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import DataFrame, SparkSession

TABLE = "clinical_observations"
DOMAIN = "clinical"
BRONZE_TABLE = "synthea_observations"

EMPTY_INPUT_BEHAVIOR = "write_empty"
ACTION_IF_FAILED = "fail"

# STM row 101 — SHA256 of business cols.
HASH_COLUMNS = [
    "observation_id",
    "patient_id",
    "loinc_code",
    "observation_date",
    "observation_value",
]

# DMS §3.5 ordered columns. observation_id is the STM synthetic composite PK
# (row 88) — not a DMS business column but used in the hash; kept transient.
OUTPUT_COLUMNS = [
    "patient_id",
    "encounter_id",
    "observation_date",
    "category",
    "loinc_code",
    "observation_description",
    "observation_value",
    "units",
    "value_type",
    "ds",
    "_ingested_at",
    "_source_batch_id",
    "_record_hash",
]


def _record_hash(*cols) -> F.Column:
    parts = [F.coalesce(F.col(c).cast("string"), F.lit("")) for c in cols]
    return F.sha2(F.concat_ws("|", *parts), 256)


def _cleanse(bronze_df: DataFrame, ds: str) -> DataFrame:
    df = bronze_df.select(
        # row 88 — synthetic composite PK (transient; feeds the hash)
        F.sha2(
            F.concat_ws(
                "|",
                F.col("PATIENT"),
                F.col("ENCOUNTER"),
                F.col("CODE"),
                F.col("DATE").cast("string"),
            ),
            256,
        ).alias("observation_id"),
        F.trim(F.col("PATIENT")).alias("patient_id"),  # row 89
        F.trim(F.col("ENCOUNTER")).alias("encounter_id"),  # row 90
        # DMS §3.5 observation_date is TIMESTAMP (rows 91-92 collapse to one).
        F.col("DATE").cast("timestamp").alias("observation_date"),
        F.trim(F.col("CATEGORY")).alias("category"),  # row 93
        F.trim(F.col("CODE")).alias("loinc_code"),  # row 94
        F.trim(F.col("DESCRIPTION")).alias("observation_description"),  # row 95
        F.trim(F.col("VALUE")).alias("observation_value"),  # row 96
        F.trim(F.col("UNITS")).alias("units"),  # row 97
        F.trim(F.col("TYPE")).alias("value_type"),  # row 98 (DMS value_type)
        F.lit(ds).cast("date").alias("ds"),
        F.col("_ingested_at"),  # row 99
        F.col("_source_batch_id"),  # row 100
    )
    # row 101 — _record_hash recomputed on silver columns.
    return df.withColumn("_record_hash", _record_hash(*HASH_COLUMNS)).select(*OUTPUT_COLUMNS)


def transform(spark: SparkSession, env: str, ds: str) -> DataFrame:
    bronze_df = read_bronze_delta(spark, table=BRONZE_TABLE, ds=ds, env=env)

    # LLD §5.2 empty-input: Write empty. Emit a 0-row frame with the right
    # schema and continue (no SE, nothing to validate).
    if bronze_df.head(1) == []:
        empty = _cleanse(bronze_df, ds)
        (empty.select(*OUTPUT_COLUMNS).write.mode("overwrite").insertInto(f"unity.silver.{TABLE}"))
        return empty

    silver_df = _cleanse(bronze_df, ds)

    validated_df = se_runner.run_dq(
        df=silver_df,
        table=TABLE,
        env=env,
        action_if_failed=ACTION_IF_FAILED,
        dq_rules_dir=None,
    )

    target_table = f"unity.silver.{TABLE}"
    (validated_df.select(*OUTPUT_COLUMNS).write.mode("overwrite").insertInto(target_table))

    return validated_df


__all__ = ["transform", "TABLE", "DOMAIN", "HASH_COLUMNS", "OUTPUT_COLUMNS"]
