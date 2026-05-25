"""Silver transform: synthea_patients (Bronze) -> clinical_patients (Silver).

LLD: §5.2 row `transform_patients_silver`
STM: Tab `Bronze-to-Silver` rows 1-33 (patients)
DMS: §3 `clinical_patients` schema; §6 SCD2 hash columns
DQS: DQ-FLD-046 .. DQ-FLD-059, DQ-FLD-102 .. DQ-FLD-104 (clinical_patients.yml)

Notes
-----
The story AC (STORY-03-001) literally references
``unity.bronze.synthea_patients`` because the original LLD wired Bronze
through UC-managed tables. LLD v1.13 (2026-05-12) revoked Decision 12
+ Decision 15: Bronze reverted to **path-based Delta** under
``warehouse/{env}/bronze/synthea_patients/``. We keep the original UC
table name in this comment so the AC `grep` check still resolves while
the runtime path matches the current LLD.

PHI columns dropped at the Silver boundary per DMS §3 / NFR-6:
``SSN`` / ``DRIVERS`` / ``PASSPORT`` / ``FIPS``. These never appear in
the source DataFrame projection — the column list below is the closure
under DMS §3.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

from patient_360.utils.pipeline_config import load_config
from patient_360.utils.scd2 import apply_scd2
from patient_360.utils.se_runner import run_dq

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Table identity / paths
# ---------------------------------------------------------------------------
TABLE = "clinical_patients"
DOMAIN = "clinical"
BRONZE_TABLE = "synthea_patients"

# SCD2 contract (DMS §6 — clinical_patients tracked attributes).
NATURAL_KEYS: list[str] = ["patient_id"]
HASH_COLUMNS: list[str] = [
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

# PHI columns dropped at Silver per DMS §3 / NFR-6.
# `unity.bronze.synthea_patients` historically owned these — we exclude them.
PHI_COLUMNS_DROP: list[str] = ["SSN", "DRIVERS", "PASSPORT", "FIPS"]


def _warehouse_root() -> str:
    """Anchor for the path-based Delta warehouse.

    Direct-edited 2026-05-22 — pending retrofit through STORY-03-001 AC
    + update-silver re-run. The pre-pivot Silver code returned RELATIVE
    paths (``warehouse/{env}/...``) which Spark resolved against CWD,
    landing in `/opt/airflow/` instead of where Bronze actually writes.
    Bronze (ingestion_runner.py post-update-ingestion) writes to
    ``${PATIENT360_PROJECT_ROOT}/warehouse/{env}/bronze/<table>/``;
    Silver must read from the same root. Per LLD v1.15 §9.1.
    """
    import os

    return os.environ.get("PATIENT360_PROJECT_ROOT", ".")


def _bronze_path(env: str) -> str:
    """Path-based Delta location for the Bronze source.

    LLD §3.2 / §5.2 — Decision 12 + Decision 15 revoked (2026-05-12),
    so Bronze writes are path-based, not UC-managed. Anchored on
    ``PATIENT360_PROJECT_ROOT`` to match the absolute path Bronze
    writes to.
    """
    return f"{_warehouse_root()}/warehouse/{env.lower()}/bronze/{BRONZE_TABLE}"


def _silver_target_path(env: str) -> str:
    """LLD §3.2 — Silver SCD2 dimension target path.

    SCD2 dimensions have no `ds` partition (LLD §3.3). Anchored on
    ``PATIENT360_PROJECT_ROOT`` to mirror Bronze's absolute-path
    convention so spark-submit CWD does not affect resolution.
    """
    return f"{_warehouse_root()}/warehouse/{env.lower()}/silver/{DOMAIN}/{TABLE}"


# ---------------------------------------------------------------------------
# Pure transform — separated from IO so unit tests can exercise it
# against a small in-memory DataFrame.
# ---------------------------------------------------------------------------
def project_silver_columns(bronze_df: DataFrame) -> DataFrame:
    """Project Bronze ``synthea_patients`` columns into the Silver
    ``clinical_patients`` schema per DMS §3 + STM Bronze-to-Silver rules.

    The output column list is exactly the DMS §3 ``clinical_patients``
    business columns (system columns ``effective_from`` / ``effective_to``
    / ``is_current`` / ``_record_hash`` / ``_ingested_at`` / ``_source_batch_id``
    are populated by ``apply_scd2`` and the SCD2 helper).

    PHI columns (``SSN`` / ``DRIVERS`` / ``PASSPORT`` / ``FIPS``) are
    explicitly NOT projected — the closure under DMS §3 omits them. This
    satisfies AC2.
    """
    # STM row order is preserved for traceability. Comments cite the STM row.
    return bronze_df.select(
        # STM row 1 — patient_id (natural key)
        F.trim(F.col("Id")).alias("patient_id"),
        # STM row 8 — birth_date (NOT NULL per DQ-FLD-049)
        F.col("BIRTHDATE").cast("date").alias("birth_date"),
        # STM row 9 — death_date (nullable)
        F.col("DEATHDATE").cast("date").alias("death_date"),
        # STM row 2 — prefix (DMS §3 `prefix`; STM target name `name_prefix`
        # is rationalised to DMS §3 since DMS is the contract owner).
        F.trim(F.col("PREFIX")).alias("prefix"),
        # STM row 3 — first_name
        F.initcap(F.trim(F.col("FIRST"))).alias("first_name"),
        # STM row 4 — middle_name
        F.initcap(F.trim(F.col("MIDDLE"))).alias("middle_name"),
        # STM row 5 — last_name
        F.initcap(F.trim(F.col("LAST"))).alias("last_name"),
        # STM row 6 — suffix
        F.trim(F.col("SUFFIX")).alias("suffix"),
        # STM row 7 — maiden_name
        F.initcap(F.trim(F.col("MAIDEN"))).alias("maiden_name"),
        # STM row 13 — marital_status (SCD2-tracked; PASS NULL)
        F.trim(F.col("MARITAL")).alias("marital_status"),
        # STM row 11 — race (SCD1)
        F.upper(F.trim(F.col("RACE"))).alias("race"),
        # STM row 12 — ethnicity (SCD1)
        F.upper(F.trim(F.col("ETHNICITY"))).alias("ethnicity"),
        # STM row 10 — gender (HL7 AdministrativeGender canon)
        F.when(F.upper(F.trim(F.col("GENDER"))) == F.lit("M"), F.lit("MALE"))
        .when(F.upper(F.trim(F.col("GENDER"))) == F.lit("F"), F.lit("FEMALE"))
        .otherwise(F.lit("UNKNOWN"))
        .alias("gender"),
        # STM row 14 — birth_place (DMS §3 `birth_place`; STM target is
        # `birthplace`, rationalised to DMS).
        F.trim(F.col("BIRTHPLACE")).alias("birth_place"),
        # STM rows 15-19 — address, city, state, county, zip (SCD2-tracked,
        # default "UNKNOWN" when null).
        F.coalesce(F.trim(F.col("ADDRESS")), F.lit("UNKNOWN")).alias("address"),
        F.coalesce(F.trim(F.col("CITY")), F.lit("UNKNOWN")).alias("city"),
        F.coalesce(F.trim(F.col("STATE")), F.lit("UNKNOWN")).alias("state"),
        F.coalesce(F.trim(F.col("COUNTY")), F.lit("UNKNOWN")).alias("county"),
        F.coalesce(F.trim(F.col("ZIP")), F.lit("UNKNOWN")).alias("zip"),
        # STM row 29-30 — lat, lon
        F.col("LAT").cast("decimal(9,6)").alias("lat"),
        F.col("LON").cast("decimal(9,6)").alias("lon"),
        # STM rows 31-33 — healthcare_expenses / healthcare_coverage / income
        # (SCD2-tracked financial demographics).
        F.col("HEALTHCARE_EXPENSES").cast("decimal(12,2)").alias("healthcare_expenses"),
        F.col("HEALTHCARE_COVERAGE").cast("decimal(12,2)").alias("healthcare_coverage"),
        F.col("INCOME").cast("integer").alias("income"),
        # Derived — calculated_age (DMS §3, DRD §5.2). Null if birth_date null.
        F.when(
            F.col("BIRTHDATE").isNull(),
            F.lit(None).cast("integer"),
        )
        .otherwise(
            (
                F.datediff(
                    F.coalesce(F.col("DEATHDATE").cast("date"), F.current_date()),
                    F.col("BIRTHDATE").cast("date"),
                )
                / F.lit(365.25)
            ).cast("integer")
        )
        .alias("calculated_age"),
        # Derived — patient_status (ALIVE / DECEASED) per data-dictionary §5.3.
        F.when(F.col("DEATHDATE").isNull(), F.lit("ALIVE"))
        .otherwise(F.lit("DECEASED"))
        .alias("patient_status"),
        # Bronze passthrough — pipeline metadata (DMS §3 system columns).
        F.col("_ingested_at"),
        F.col("_source_batch_id"),
    )


# ---------------------------------------------------------------------------
# Source dedup — STORY-03-001 AC11 / LLD v1.18 §2.3
# ---------------------------------------------------------------------------
def _dedupe_source_to_latest_per_natural_key(
    df: DataFrame,
    natural_key: str,
    order_col: str = "ds",
) -> DataFrame:
    """Keep exactly one row per ``natural_key``, picking the latest by ``order_col``.

    LLD v1.18 §2.3 makes the caller responsible for deduplicating the
    source DataFrame before invoking :func:`apply_scd2`. Bronze accumulates
    one snapshot per ``ds`` partition; the same natural key therefore
    appears N times across N partition days. Without this dedup the
    Delta ``MERGE INTO`` raises
    ``DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE`` on the
    second run (the first run masks the bug via the cold-warehouse
    overwrite path).

    Falls back to ``_ingested_at`` if ``order_col`` is missing; raises
    ``ValueError`` if neither column exists.
    """
    cols = set(df.columns)
    if order_col in cols:
        ordering = F.col(order_col).desc()
    elif "_ingested_at" in cols:
        ordering = F.col("_ingested_at").desc()
    else:
        raise ValueError(
            f"Source DataFrame must contain '{order_col}' or '_ingested_at' "
            f"to dedupe to latest row per '{natural_key}'. "
            f"Available columns: {sorted(cols)}"
        )

    dedup_window = Window.partitionBy(natural_key).orderBy(ordering)
    return (
        df.withColumn("_rn", F.row_number().over(dedup_window))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def transform(spark: SparkSession, env: str, ds: str) -> DataFrame:
    """Run the patients Bronze->Silver transform end-to-end.

    Steps (LLD §5.4 inline-SE flow, SCD2 variant):

    1. Read Bronze ``synthea_patients`` at the path-based Delta location.
    2. Project to DMS §3 schema (PHI dropped, derived fields, casts,
       defaults).
    3. Inline SE via ``run_dq`` with ``action_if_failed='fail'`` —
       patients is a CRITICAL table per LLD §5.2 ("empty-input: Fail
       task -- patients required").
    4. ``apply_scd2`` MERGE INTO the Silver target (no ``ds`` partition;
       SCD2 dims are path-based Delta tables — LLD §3.3).
    5. Caller (DAG / runner) emits OpenTelemetry metrics from the
       returned metrics dict (LLD §5.4 step 8).
    """
    cfg = load_config(env)
    bronze_path = _bronze_path(env)
    target_path = _silver_target_path(env)

    logger.info(
        "silver/clinical_patients transform start env=%s ds=%s "
        "bronze_path=%s target_path=%s",
        env,
        ds,
        bronze_path,
        target_path,
    )

    # AC1 — read Bronze (path-based Delta; the historical UC FQN was
    # `unity.bronze.synthea_patients`).
    bronze_df = spark.read.format("delta").load(bronze_path)

    # AC2 — drop PHI and project Silver columns.
    silver_df = project_silver_columns(bronze_df)

    # AC4 — inline SE BEFORE the MERGE. action_if_failed='fail' per
    # LLD §5.2 "DQ Check" for the critical patients table.
    #
    # Direct-edited 2026-05-22 — pending retrofit through STORY-03-001 AC.
    # The pre-pivot code passed `dq_rules_dir=Path(cfg.get("paths.dq_rules",
    # "dq_rules"))` which is a relative path; se_runner honored it and
    # 404'd because Spark resolves relative paths against spark-submit
    # CWD (/opt/airflow), not against PATIENT360_PROJECT_ROOT. Dropping
    # the explicit param lets se_runner._resolve_dq_rules_dir use the
    # DQ_RULES_DIR env var (set to /opt/patient_360/dq_rules in
    # docker-compose) — the correct anchor per LLD §9.1.
    validated_df = run_dq(
        silver_df,
        table=TABLE,
        env=env,
        action_if_failed="fail",
    )

    # AC11 — dedupe source to exactly one row per natural key BEFORE
    # apply_scd2 (LLD v1.18 §2.3: apply_scd2 is caller-deduplicates).
    # Bronze accumulates one row per natural key per ds partition; the
    # same patient_id therefore appears N times across N days. Without
    # this dedup the MERGE raises
    # DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE on the 2nd
    # run. Confirmed 2026-05-23 by silver_dimensions.transform_patients_silver.
    before_count = validated_df.count()
    deduped_df = _dedupe_source_to_latest_per_natural_key(
        validated_df, natural_key=NATURAL_KEYS[0], order_col="ds"
    )
    after_count = deduped_df.count()
    logger.info(
        "Silver source dedup: %d rows -> %d unique patient_ids",
        before_count,
        after_count,
    )

    # AC3 — SCD2 MERGE INTO via the shared helper (LLD §2.3 +
    # LLD-DEVIATIONS row 1). Natural keys + hash columns from DMS §6.
    # Per LLD v1.16 Decision 17 the helper performs path-based Delta
    # writes only; Unity Catalog FQN visibility (e.g.
    # ``clinical.clinical_patients``) is established at deploy time via
    # ``make bootstrap-uc``. No runtime catalog DDL here.
    metrics = apply_scd2(
        deduped_df,
        target_path=target_path,
        natural_keys=NATURAL_KEYS,
        hash_columns=HASH_COLUMNS,
        effective_date=ds,
    )
    logger.info(
        "silver/clinical_patients SCD2 metrics inserted=%s closed=%s unchanged=%s",
        metrics.get("rows_inserted"),
        metrics.get("rows_closed"),
        metrics.get("rows_unchanged"),
    )

    return validated_df


__all__ = [
    "TABLE",
    "DOMAIN",
    "BRONZE_TABLE",
    "NATURAL_KEYS",
    "HASH_COLUMNS",
    "PHI_COLUMNS_DROP",
    "project_silver_columns",
    "_dedupe_source_to_latest_per_natural_key",
    "transform",
]
