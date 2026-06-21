"""Silver transform: synthea_providers -> reference_providers (SCD2 dim).

LLD: §5.2 transform_providers_silver (Silver writes target the pre-created
     named UC table `unity.silver.reference_providers` — §13 Decision 12),
     §5.4 (inline SE BEFORE write). Empty-input: Fail task — FK dimension.
STM: Tab:Bronze-to-Silver (providers) — every rename/cast/derive below cites
     the source column it implements (STM v3 is authoritative for transforms
     and column names where it refines DMS §3.12).
DMS: §3.12 reference_providers schema; §6 SCD Type 2 strategy + hash columns.
DQS: DQ-FLD-097, DQ-FLD-098, DQ-FLD-099, DQ-FLD-185, DQ-REF-018
     (reference_providers).

reference_providers is reference (non-PHI) data — the Synthea providers source
has no PHI columns (SSN / DRIVERS / PASSPORT). The PHI-drop boundary (NFR-6,
story AC2) is therefore satisfied structurally: the projection below selects
ONLY the DMS §3.12 columns, so no PHI column can ever leak even if the bronze
source schema were to gain one.

Naming note: DMS §3.12 is authoritative for Silver *column names* and names this
column ``specialty`` (the source column ``SPECIALITY`` carries a typo that is
corrected at the Silver boundary — DMS Open Question #4). The STM v3 target_column
cell shows ``speciality`` (typo carried through), but column naming is owned by
the DMS, so this module emits ``specialty``. The STM remains authoritative for
the *transform* (TRIM(SPECIALITY)).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyspark.sql import functions as F

# LLD §8.6 + §13 Decision 14 — fail-closed diagnostic import wrapper (IL-010).
# NEVER swallow the ImportError; re-raise after logging.
try:
    from patient_360.utils import se_runner
except ImportError as exc:  # pragma: no cover - import-contract guard
    import logging

    logging.getLogger(__name__).critical("se_runner import failed in transform_providers: %s", exc)
    raise

from patient_360.utils.delta_helpers import read_bronze_delta
from patient_360.utils.scd2 import apply_scd2

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import DataFrame, SparkSession

# Identity / scope ----------------------------------------------------------
TABLE = "reference_providers"
DOMAIN = "reference"
BRONZE_TABLE = "synthea_providers"

# DMS §6 / STM `_record_hash` expression — natural (merge) key + SCD2-tracked
# hash columns. The list and order match the STM v3 Bronze-to-Silver
# SHA256(CONCAT_WS('|', COALESCE(TRIM(NAME),''), COALESCE(TRIM(SPECIALITY),''),
#                       COALESCE(TRIM(ORGANIZATION),''))) expression exactly,
# so the digest computed in apply_scd2 reproduces the contract:
# provider_name, then specialty, then organization_id (DMS §6 — provider_name,
# specialty, organization_id are the Type 2 tracked attributes).
NATURAL_KEYS = ["provider_id"]
HASH_COLUMNS = [
    "provider_name",
    "specialty",
    "organization_id",
]

# LLD §5.2 "DQ Check" / DQS PROD severity — providers is an FK dimension
# (reference_providers.organization_id -> reference_organizations); SE failures
# fail the task (DQS §2 PROD action_if_failed: fail; LLD §5.4).
ACTION_IF_FAILED = "fail"

# STM Bronze-to-Silver DEFAULT null-handling sentinel for provider_name/gender.
_UNKNOWN = "UNKNOWN"


def _cleanse(bronze_df: DataFrame) -> DataFrame:
    """Apply the STM Bronze-to-Silver transformations in source-row order.

    Every output column comes from DMS §3.12 reference_providers. Only DMS
    columns are selected; any non-DMS bronze column (incl. any future PHI) is
    dropped by omission.
    """
    return bronze_df.select(
        # STM: TRIM(Id) — PK natural key (REJECT -- PRIMARY KEY)
        F.trim(F.col("Id")).alias("provider_id"),
        # STM: TRIM(ORGANIZATION) PASS NULL — FK; SCD Type 2 tracked
        F.trim(F.col("ORGANIZATION")).alias("organization_id"),
        # STM: TRIM(NAME) DEFAULT 'UNKNOWN' — SCD Type 2 tracked
        F.coalesce(F.trim(F.col("NAME")), F.lit(_UNKNOWN)).alias("provider_name"),
        # STM: CASE UPPER(TRIM(GENDER)) 'M'->'MALE' 'F'->'FEMALE' ELSE 'UNKNOWN'
        # — HL7 gender standardization; DEFAULT 'UNKNOWN'.
        F.when(F.upper(F.trim(F.col("GENDER"))) == F.lit("M"), F.lit("MALE"))
        .when(F.upper(F.trim(F.col("GENDER"))) == F.lit("F"), F.lit("FEMALE"))
        .otherwise(F.lit(_UNKNOWN))
        .alias("gender"),
        # STM: TRIM(SPECIALITY) PASS NULL — SCD Type 2 tracked. DMS §3.12 names
        # the Silver column `specialty` (source typo corrected — DMS OQ #4).
        F.trim(F.col("SPECIALITY")).alias("specialty"),
        # STM: TRIM(ADDRESS) PASS NULL
        F.trim(F.col("ADDRESS")).alias("address"),
        # STM: TRIM(CITY) PASS NULL
        F.trim(F.col("CITY")).alias("city"),
        # STM: TRIM(STATE) PASS NULL
        F.trim(F.col("STATE")).alias("state"),
        # STM: TRIM(ZIP) PASS NULL
        F.trim(F.col("ZIP")).alias("zip"),
        # DMS §3.12: CAST(LAT AS DECIMAL(9,6))
        F.col("LAT").cast("decimal(9,6)").alias("lat"),
        # DMS §3.12: CAST(LON AS DECIMAL(9,6))
        F.col("LON").cast("decimal(9,6)").alias("lon"),
        # STM: CAST(ENCOUNTERS AS INTEGER) PASS NULL
        F.col("ENCOUNTERS").cast("int").alias("encounter_count"),
        # STM: CAST(PROCEDURES AS INTEGER) PASS NULL
        F.col("PROCEDURES").cast("int").alias("procedure_count"),
        # STM: PASS_THROUGH pipeline metadata
        F.col("_ingested_at"),
        F.col("_source_batch_id"),
    )


def transform(spark: SparkSession, env: str, ds: str) -> DataFrame:
    """Build the validated reference_providers open-version DataFrame and merge
    it into the SCD2 dimension.

    Returns the validated (post-SE, pre-merge) DataFrame so unit tests can
    assert on schema + row count independently of the Delta write.
    """
    bronze_df = read_bronze_delta(spark, table=BRONZE_TABLE, ds=ds, env=env)

    # LLD §5.2 empty-input policy: "Fail task -- FK dimension". This gate is
    # distinct from the SE action_if_failed gate (LLD-DEVIATIONS #3).
    if bronze_df.head(1) == []:
        raise ValueError(
            f"empty bronze input for {BRONZE_TABLE} at ds={ds}; "
            "providers is an FK dimension (LLD §5.2 — Fail task)"
        )

    silver_df = _cleanse(bronze_df)

    # Inline SE BEFORE the merge (LLD §5.4). The SCD2 helper trusts every row.
    validated_df = se_runner.run_dq(
        df=silver_df,
        table=TABLE,
        env=env,
        action_if_failed=ACTION_IF_FAILED,
        dq_rules_dir=None,  # let se_runner resolve via DQ_RULES_DIR (IL-005)
    )

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
