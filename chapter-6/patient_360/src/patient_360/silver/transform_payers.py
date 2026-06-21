"""Silver transform: synthea_payers -> reference_payers (SCD2 dim).

LLD: §5.2 transform_payers_silver (Silver writes target the pre-created
     named UC table `unity.silver.reference_payers` — §13 Decision 12),
     §5.4 (inline SE BEFORE write). Empty-input: Fail task — FK dimension.
STM: Tab:Bronze-to-Silver (payers) — every rename/cast below cites the source
     column it implements (STM v3 is authoritative for transforms and column
     casts where it refines DMS §3.13).
DMS: §3.13 reference_payers schema; §6 SCD Type 2 strategy + hash columns.
DQS: DQ-FLD-100, DQ-FLD-101, DQ-FLD-186 (reference_payers).

reference_payers is reference (non-PHI) data — the Synthea payers source has no
PHI columns (SSN / DRIVERS / PASSPORT). The PHI-drop boundary (NFR-6, story AC2)
is therefore satisfied structurally: the projection below selects ONLY the DMS
§3.13 columns, so no PHI column can ever leak even if the bronze source schema
were to gain one.

Type-width note: STM v3 Bronze-to-Silver casts ``amount_covered`` /
``amount_uncovered`` to ``DECIMAL(14,2)`` while DMS §3.13 reads ``DECIMAL(12,2)``
— the STM is authoritative for the transform expression (same precedence as the
``reference_organizations.revenue`` case), so this module emits ``DECIMAL(14,2)``
for those two columns; the drift is flagged for an update-dms reconciliation
cycle. ``revenue``, ``covered_encounters`` and ``uncovered_encounters`` are in
the DMS §3.13 Silver contract but absent from the STM v3 payers rows; DMS §3 owns
the Silver column contract, so they are projected here using the cast documented
in their DMS §3.13 source descriptions (``DECIMAL(12,2)`` / ``INTEGER``).
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

    logging.getLogger(__name__).critical("se_runner import failed in transform_payers: %s", exc)
    raise

from patient_360.utils.delta_helpers import read_bronze_delta
from patient_360.utils.scd2 import apply_scd2

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import DataFrame, SparkSession

# Identity / scope ----------------------------------------------------------
TABLE = "reference_payers"
DOMAIN = "reference"
BRONZE_TABLE = "synthea_payers"

# DMS §6 / STM `_record_hash` expression — natural (merge) key + SCD2-tracked
# hash columns. The list and order match the STM v3 Bronze-to-Silver
# SHA256(CONCAT_WS('|', COALESCE(TRIM(NAME),''), COALESCE(TRIM(OWNERSHIP),'')))
# expression exactly, so the digest computed in apply_scd2 reproduces the
# contract: payer_name then ownership (DMS §6 — payer_name, ownership are the
# Type 2 tracked attributes).
NATURAL_KEYS = ["payer_id"]
HASH_COLUMNS = [
    "payer_name",
    "ownership",
]

# LLD §5.2 "DQ Check" / DQS PROD severity — payers is an FK dimension
# (clinical_encounters.payer_id / billing_claims.primary_payer_id ->
# reference_payers.payer_id); SE failures fail the task (DQS §2 reference_payers
# PROD action_if_failed: fail; LLD §5.4).
ACTION_IF_FAILED = "fail"

# STM Bronze-to-Silver DEFAULT null-handling sentinel for payer_name.
_UNKNOWN = "UNKNOWN"


def _cleanse(bronze_df: DataFrame) -> DataFrame:
    """Apply the STM Bronze-to-Silver transformations in source-row order.

    Every output column comes from DMS §3.13 reference_payers. Only DMS columns
    are selected; any non-DMS bronze column (incl. any future PHI) is dropped by
    omission.
    """
    return bronze_df.select(
        # STM: TRIM(Id) — PK natural key (REJECT -- PRIMARY KEY)
        F.trim(F.col("Id")).alias("payer_id"),
        # STM: TRIM(NAME) DEFAULT 'UNKNOWN' — SCD Type 2 tracked
        F.coalesce(F.trim(F.col("NAME")), F.lit(_UNKNOWN)).alias("payer_name"),
        # STM: TRIM(OWNERSHIP) PASS NULL — SCD Type 2 tracked
        F.trim(F.col("OWNERSHIP")).alias("ownership"),
        # STM: TRIM(ADDRESS) PASS NULL
        F.trim(F.col("ADDRESS")).alias("address"),
        # STM: TRIM(CITY) PASS NULL
        F.trim(F.col("CITY")).alias("city"),
        # STM: TRIM(STATE_HEADQUARTERED) PASS NULL — column renamed to `state`
        F.trim(F.col("STATE_HEADQUARTERED")).alias("state"),
        # STM: TRIM(ZIP) PASS NULL
        F.trim(F.col("ZIP")).alias("zip"),
        # STM: TRIM(PHONE) PASS NULL
        F.trim(F.col("PHONE")).alias("phone"),
        # STM v3: CAST(AMOUNT_COVERED AS DECIMAL(14,2)) PASS NULL  # STM v3 width
        F.col("AMOUNT_COVERED").cast("decimal(14,2)").alias("amount_covered"),
        # STM v3: CAST(AMOUNT_UNCOVERED AS DECIMAL(14,2)) PASS NULL  # STM v3 width
        F.col("AMOUNT_UNCOVERED").cast("decimal(14,2)").alias("amount_uncovered"),
        # DMS §3.13: CAST(REVENUE AS DECIMAL(12,2)) — DMS-only column (absent
        # from STM v3 payers rows); DMS §3 owns the Silver contract.
        F.col("REVENUE").cast("decimal(12,2)").alias("revenue"),
        # DMS §3.13: CAST(COVERED_ENCOUNTERS AS INTEGER) — DMS-only column.
        F.col("COVERED_ENCOUNTERS").cast("int").alias("covered_encounters"),
        # DMS §3.13: CAST(UNCOVERED_ENCOUNTERS AS INTEGER) — DMS-only column.
        F.col("UNCOVERED_ENCOUNTERS").cast("int").alias("uncovered_encounters"),
        # STM: CAST(UNIQUE_CUSTOMERS AS INTEGER) PASS NULL
        F.col("UNIQUE_CUSTOMERS").cast("int").alias("unique_customers"),
        # STM: CAST(MEMBER_MONTHS AS INTEGER) PASS NULL
        F.col("MEMBER_MONTHS").cast("int").alias("member_months"),
        # STM: PASS_THROUGH pipeline metadata
        F.col("_ingested_at"),
        F.col("_source_batch_id"),
    )


def transform(spark: SparkSession, env: str, ds: str) -> DataFrame:
    """Build the validated reference_payers open-version DataFrame and merge it
    into the SCD2 dimension.

    Returns the validated (post-SE, pre-merge) DataFrame so unit tests can
    assert on schema + row count independently of the Delta write.
    """
    bronze_df = read_bronze_delta(spark, table=BRONZE_TABLE, ds=ds, env=env)

    # LLD §5.2 empty-input policy: "Fail task -- FK dimension". This gate is
    # distinct from the SE action_if_failed gate (LLD-DEVIATIONS #3).
    if bronze_df.head(1) == []:
        raise ValueError(
            f"empty bronze input for {BRONZE_TABLE} at ds={ds}; "
            "payers is an FK dimension (LLD §5.2 — Fail task)"
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
