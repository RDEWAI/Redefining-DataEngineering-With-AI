"""Silver transform: synthea_patients -> clinical_patients (SCD2 dimension).

LLD: §5.2 transform_patients_silver (Silver writes target the pre-created
     named UC table `unity.silver.clinical_patients` — §13 Decision 12), §5.4
     (inline SE BEFORE write).
STM: Tab:Bronze-to-Silver (patients) — every rename/cast/derive below cites
     the source column it implements.
DMS: §3 clinical_patients schema; §6 SCD Type 2 strategy + hash columns.
DQS: DQ-FLD-046 .. DQ-FLD-059, DQ-FLD-102 .. DQ-FLD-104 (clinical_patients).

PHI columns SSN / DRIVERS / PASSPORT are dropped at this Silver boundary
(STM `EXCLUDED -- PHI`, NFR-6). They are never selected into the projection,
so they cannot leak downstream.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pyspark.sql import functions as F

# LLD §8.6 + §13 Decision 14 — fail-closed diagnostic import wrapper (IL-010).
# NEVER swallow the ImportError; re-raise after logging.
try:
    from patient_360.utils import se_runner
except ImportError as exc:  # pragma: no cover - import-contract guard
    import logging

    logging.getLogger(__name__).critical("se_runner import failed in transform_patients: %s", exc)
    raise

from patient_360.utils.delta_helpers import read_bronze_delta
from patient_360.utils.pipeline_config import load_config
from patient_360.utils.scd2 import apply_scd2

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import DataFrame, SparkSession

# Identity / scope ----------------------------------------------------------
TABLE = "clinical_patients"
DOMAIN = "clinical"
BRONZE_TABLE = "synthea_patients"

# DMS §6 — natural (merge) key + SCD2-tracked hash columns. The hash column
# list and order match the STM `_record_hash` CONCAT_WS expression exactly so
# the digest computed in apply_scd2 reproduces the contract. Bronze source
# columns are uppercase; we hash the cleansed Silver columns (same business
# values, trimmed) in the same logical order.
NATURAL_KEYS = ["patient_id"]
HASH_COLUMNS = [
    "first_name",
    "last_name",
    "maiden_name",
    "address",
    "city",
    "state",
    "county",
    "zip",
    "marital_status",
    "healthcare_expenses",
    "healthcare_coverage",
    "income",
]

# LLD §5.2 "DQ Check" — patients are required; SE failures fail the task.
ACTION_IF_FAILED = "fail"

# STM DEFAULT null-handling sentinel for SCD2-tracked address fields.
_UNKNOWN = "UNKNOWN"


def _cleanse(bronze_df: DataFrame) -> DataFrame:
    """Apply the STM Bronze-to-Silver transformations in source-row order.

    PHI (SSN, DRIVERS, PASSPORT) and non-clinical FIPS are dropped simply by
    not selecting them. Every output column is from DMS §3 clinical_patients.
    """
    return bronze_df.select(
        # STM: TRIM(Id) — PK natural key
        F.trim(F.col("Id")).alias("patient_id"),
        # STM: CAST(BIRTHDATE AS DATE)
        F.col("BIRTHDATE").cast("date").alias("birth_date"),
        # STM: CAST(DEATHDATE AS DATE)
        F.col("DEATHDATE").cast("date").alias("death_date"),
        # STM: TRIM(PREFIX)
        F.trim(F.col("PREFIX")).alias("prefix"),
        # STM: INITCAP(TRIM(FIRST))
        F.initcap(F.trim(F.col("FIRST"))).alias("first_name"),
        # STM: INITCAP(TRIM(MIDDLE))
        F.initcap(F.trim(F.col("MIDDLE"))).alias("middle_name"),
        # STM: INITCAP(TRIM(LAST))
        F.initcap(F.trim(F.col("LAST"))).alias("last_name"),
        # STM: TRIM(SUFFIX)
        F.trim(F.col("SUFFIX")).alias("suffix"),
        # STM: INITCAP(TRIM(MAIDEN))
        F.initcap(F.trim(F.col("MAIDEN"))).alias("maiden_name"),
        # STM: TRIM(MARITAL)
        F.trim(F.col("MARITAL")).alias("marital_status"),
        # STM: UPPER(TRIM(RACE)) — SCD Type 1
        F.upper(F.trim(F.col("RACE"))).alias("race"),
        # STM: UPPER(TRIM(ETHNICITY)) — SCD Type 1
        F.upper(F.trim(F.col("ETHNICITY"))).alias("ethnicity"),
        # STM: CASE UPPER(TRIM(GENDER)) WHEN 'M'->MALE WHEN 'F'->FEMALE ELSE UNKNOWN
        F.when(F.upper(F.trim(F.col("GENDER"))) == "M", F.lit("MALE"))
        .when(F.upper(F.trim(F.col("GENDER"))) == "F", F.lit("FEMALE"))
        .otherwise(F.lit("UNKNOWN"))
        .alias("gender"),
        # STM: TRIM(BIRTHPLACE)
        F.trim(F.col("BIRTHPLACE")).alias("birth_place"),
        # STM: TRIM(ADDRESS) DEFAULT 'UNKNOWN'
        F.coalesce(F.trim(F.col("ADDRESS")), F.lit(_UNKNOWN)).alias("address"),
        # STM: TRIM(CITY) DEFAULT 'UNKNOWN'
        F.coalesce(F.trim(F.col("CITY")), F.lit(_UNKNOWN)).alias("city"),
        # STM: TRIM(STATE) DEFAULT 'UNKNOWN'
        F.coalesce(F.trim(F.col("STATE")), F.lit(_UNKNOWN)).alias("state"),
        # STM: TRIM(COUNTY) DEFAULT 'UNKNOWN'
        F.coalesce(F.trim(F.col("COUNTY")), F.lit(_UNKNOWN)).alias("county"),
        # STM: TRIM(ZIP) DEFAULT 'UNKNOWN'
        F.coalesce(F.trim(F.col("ZIP")), F.lit(_UNKNOWN)).alias("zip"),
        # STM: CAST(LAT AS DECIMAL(9,6))
        F.col("LAT").cast("decimal(9,6)").alias("lat"),
        # STM: CAST(LON AS DECIMAL(9,6))
        F.col("LON").cast("decimal(9,6)").alias("lon"),
        # STM: CAST(HEALTHCARE_EXPENSES AS DECIMAL(12,2)) — SCD2 tracked
        F.col("HEALTHCARE_EXPENSES").cast("decimal(12,2)").alias("healthcare_expenses"),
        # STM: CAST(HEALTHCARE_COVERAGE AS DECIMAL(12,2)) — SCD2 tracked
        F.col("HEALTHCARE_COVERAGE").cast("decimal(12,2)").alias("healthcare_coverage"),
        # STM: CAST(INCOME AS INTEGER) — SCD2 tracked
        F.col("INCOME").cast("int").alias("income"),
        # STM: DATEDIFF('year', BIRTHDATE, COALESCE(DEATHDATE, CURRENT_DATE))
        F.when(F.col("BIRTHDATE").isNull(), F.lit(None).cast("int"))
        .otherwise(
            (
                F.year(F.coalesce(F.col("DEATHDATE").cast("date"), F.current_date()))
                - F.year(F.col("BIRTHDATE").cast("date"))
            ).cast("int")
        )
        .alias("calculated_age"),
        # STM: CASE WHEN DEATHDATE IS NULL THEN 'ALIVE' ELSE 'DECEASED' END
        F.when(F.col("DEATHDATE").isNull(), F.lit("ALIVE"))
        .otherwise(F.lit("DECEASED"))
        .alias("patient_status"),
        # STM: PASS_THROUGH pipeline metadata
        F.col("_ingested_at"),
        F.col("_source_batch_id"),
    )


def transform(spark: SparkSession, env: str, ds: str) -> DataFrame:
    """Build the validated clinical_patients open-version DataFrame and merge
    it into the SCD2 dimension.

    Returns the validated (post-SE, pre-merge) DataFrame so unit tests can
    assert on schema + row count independently of the Delta write.
    """
    cfg = load_config(env)

    bronze_df = read_bronze_delta(spark, table=BRONZE_TABLE, ds=ds, env=env)

    # LLD §5.2 empty-input policy: "Fail task -- patients required". This gate
    # is distinct from the SE action_if_failed gate (LLD-DEVIATIONS #3).
    if bronze_df.head(1) == []:
        raise ValueError(
            f"empty bronze input for {BRONZE_TABLE} at ds={ds}; "
            "patients are required (LLD §5.2 — Fail task)"
        )

    silver_df = _cleanse(bronze_df)

    # Inline SE BEFORE the merge (LLD §5.4). The SCD2 helper trusts every row.
    base_path = cfg.get("storage.storage_base_path", f"warehouse/{env.lower()}")
    dq_rules_dir = Path(base_path).parent / "dq_rules"
    # The dq_rules dir is resolved by se_runner via DQ_RULES_DIR env when
    # unset here; pass the project-relative location as the explicit default.
    validated_df = se_runner.run_dq(
        df=silver_df,
        table=TABLE,
        env=env,
        action_if_failed=ACTION_IF_FAILED,
        dq_rules_dir=None,  # let se_runner resolve via DQ_RULES_DIR (IL-005)
    )
    del dq_rules_dir  # documented above; resolution is env-var driven

    # SCD2 dimension: MERGE INTO the pre-created named UC table (LLD §13
    # Decision 12). No ds partition (DMS §6 / LLD §3.3). apply_scd2 resolves
    # the table via DeltaTable.forName and is the ONLY write path.
    target_table = f"unity.silver.{TABLE}"
    metrics = apply_scd2(
        df=validated_df,
        target_table=target_table,
        natural_keys=NATURAL_KEYS,
        hash_columns=HASH_COLUMNS,
        effective_date=ds,
    )
    # metrics: {"rows_inserted", "rows_closed", "rows_unchanged"} — caller
    # emits via OpenTelemetry per LLD §5.4 step 8.
    import logging

    logging.getLogger(__name__).info("scd2 merge %s metrics=%s", TABLE, metrics)

    return validated_df


__all__ = ["transform", "TABLE", "DOMAIN", "NATURAL_KEYS", "HASH_COLUMNS"]
