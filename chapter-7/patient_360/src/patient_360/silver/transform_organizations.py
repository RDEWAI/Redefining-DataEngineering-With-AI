"""Silver transform: synthea_organizations -> reference_organizations (SCD2 dim).

LLD: §5.2 transform_organizations_silver (Silver writes target the pre-created
     named UC table `unity.silver.reference_organizations` — §13 Decision 12),
     §5.4 (inline SE BEFORE write). Empty-input: Fail task — FK dimension.
STM: Tab:Bronze-to-Silver (organizations) — every rename/cast below cites the
     source column it implements.
DMS: §3.11 reference_organizations schema; §6 SCD Type 2 strategy + hash columns.
DQS: DQ-FLD-095, DQ-FLD-096, DQ-FLD-184 (reference_organizations).

reference_organizations is reference (non-PHI) data — the Synthea source has no
PHI columns (SSN / DRIVERS / PASSPORT). The PHI-drop boundary (NFR-6, story AC2)
is therefore satisfied structurally: the projection below selects ONLY the DMS
§3.11 columns, so no PHI column can ever leak even if the bronze source schema
were to gain one.
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

    logging.getLogger(__name__).critical(
        "se_runner import failed in transform_organizations: %s", exc
    )
    raise

from patient_360.utils.delta_helpers import read_bronze_delta
from patient_360.utils.scd2 import apply_scd2

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import DataFrame, SparkSession

# Identity / scope ----------------------------------------------------------
TABLE = "reference_organizations"
DOMAIN = "reference"
BRONZE_TABLE = "synthea_organizations"

# DMS §6 / STM `_record_hash` expression — natural (merge) key + SCD2-tracked
# hash columns. The hash column list and order match the STM
# SHA256(CONCAT_WS('|', COALESCE(TRIM(NAME),''), COALESCE(TRIM(ADDRESS),'')))
# expression exactly, so the digest computed in apply_scd2 reproduces the
# contract: organization_name then address.
NATURAL_KEYS = ["organization_id"]
HASH_COLUMNS = [
    "organization_name",
    "address",
]

# LLD §5.2 "DQ Check" / DQS PROD severity — organizations is an FK dimension;
# SE failures fail the task.
ACTION_IF_FAILED = "fail"

# STM DEFAULT null-handling sentinel for organization_name.
_UNKNOWN = "UNKNOWN"


def _cleanse(bronze_df: DataFrame) -> DataFrame:
    """Apply the STM Bronze-to-Silver transformations in source-row order.

    Every output column comes from DMS §3.11 reference_organizations. Only DMS
    columns are selected; any non-DMS bronze column (incl. any future PHI) is
    dropped by omission.
    """
    return bronze_df.select(
        # STM: TRIM(Id) — PK natural key
        F.trim(F.col("Id")).alias("organization_id"),
        # STM: TRIM(NAME) DEFAULT 'UNKNOWN' — SCD Type 2 tracked
        F.coalesce(F.trim(F.col("NAME")), F.lit(_UNKNOWN)).alias("organization_name"),
        # STM: TRIM(ADDRESS) PASS NULL — SCD Type 2 tracked
        F.trim(F.col("ADDRESS")).alias("address"),
        # STM: TRIM(CITY) PASS NULL
        F.trim(F.col("CITY")).alias("city"),
        # STM: TRIM(STATE) PASS NULL
        F.trim(F.col("STATE")).alias("state"),
        # STM: TRIM(ZIP) PASS NULL
        F.trim(F.col("ZIP")).alias("zip"),
        # DMS §3.11: CAST(LAT AS DECIMAL(9,6))
        F.col("LAT").cast("decimal(9,6)").alias("lat"),
        # DMS §3.11: CAST(LON AS DECIMAL(9,6))
        F.col("LON").cast("decimal(9,6)").alias("lon"),
        # STM: TRIM(PHONE) PASS NULL
        F.trim(F.col("PHONE")).alias("phone"),
        # STM v3: CAST(REVENUE AS DECIMAL(14,2)) PASS NULL  # Updated for STM v3
        # (STM Bronze-to-Silver is authoritative for the cast; DMS §3.11 still
        # reads DECIMAL(12,2) — flagged for an update-dms reconciliation cycle).
        F.col("REVENUE").cast("decimal(14,2)").alias("revenue"),
        # STM: CAST(UTILIZATION AS INTEGER) PASS NULL
        F.col("UTILIZATION").cast("int").alias("utilization"),
        # STM: PASS_THROUGH pipeline metadata
        F.col("_ingested_at"),
        F.col("_source_batch_id"),
    )


def transform(spark: SparkSession, env: str, ds: str) -> DataFrame:
    """Build the validated reference_organizations open-version DataFrame and
    merge it into the SCD2 dimension.

    Returns the validated (post-SE, pre-merge) DataFrame so unit tests can
    assert on schema + row count independently of the Delta write.
    """
    bronze_df = read_bronze_delta(spark, table=BRONZE_TABLE, ds=ds, env=env)

    # LLD §5.2 empty-input policy: "Fail task -- FK dimension". This gate is
    # distinct from the SE action_if_failed gate (LLD-DEVIATIONS #3).
    if bronze_df.head(1) == []:
        raise ValueError(
            f"empty bronze input for {BRONZE_TABLE} at ds={ds}; "
            "organizations is an FK dimension (LLD §5.2 — Fail task)"
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
