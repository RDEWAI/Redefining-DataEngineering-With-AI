"""Generic SCD Type 2 merge for pre-created named Unity Catalog dimensions.

LLD references: §2.3 (`scd2.py` interface contract), §5.2 (SCD2 dimension
transforms), §5.4 (inline SE runs BEFORE this helper), §13 Decision 12 +
Decision 15 (Silver tables are pre-created as EXTERNAL Delta by Liquibase at
deploy-time and addressed at runtime by their named UC FQN
`unity.silver.<dim>`). DMS references: §3 (Silver dimension schemas), §6 (SCD
strategy — `effective_from`, `effective_to` default `9999-12-31`, `is_current`,
`_record_hash`).

Write-target contract (LLD §13 Decision 12 — Unity Catalog named tables):

* ``target_table`` is a NAMED Unity Catalog table FQN (3-part
  ``unity.silver.<dim>``). The helper resolves it via
  ``DeltaTable.forName(spark, target_table)`` and MERGEs into the existing
  (possibly empty) table. It issues NO runtime catalog DDL — no
  ``DeltaTable.forPath``, no ``.save(path)``, no ``saveAsTable``, no
  ``CREATE TABLE`` / ``CREATE SCHEMA``. Table creation is a deploy-time
  concern owned by Liquibase (IL-002, IL-003, IL-018).
* The SCD2 metadata columns follow DMS §3/§6 verbatim — ``effective_from``,
  ``effective_to`` (``9999-12-31`` sentinel for the open version),
  ``is_current``, ``_record_hash``. There is **no** ``surrogate_key``: the
  natural business key is the merge key (IL-006).

DQ contract (LLD §5.4): the caller MUST run inline Spark Expectations BEFORE
invoking this function. ``apply_scd2`` trusts every row it receives and
never calls ``run_dq``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import DataFrame

# DMS §6 sentinel for the open (current) version's end date.
OPEN_EFFECTIVE_TO = "9999-12-31"

# DMS §3 hash column name + STM `SHA256(CONCAT_WS('|', ...))` separator.
HASH_COLUMN = "_record_hash"
HASH_SEPARATOR = "|"


def compute_record_hash_python(row: Mapping[str, Any], hash_columns: list[str]) -> str:
    """Pure-Python twin of :func:`_compute_record_hash` (no Spark dependency).

    Returns the SHA-256 hex digest of
    ``CONCAT_WS('|', COALESCE(col, ''), ...)`` over ``hash_columns`` — the
    same expression the STM Bronze-to-Silver contract documents and that the
    Spark helper computes. A missing key or ``None`` value collapses to the
    empty string so a NULL never silently changes the digest across runs.

    This is the unit-testable surface for the SCD2 hash contract (LLD §2.4);
    :func:`apply_scd2` boots Spark and is covered by integration tests.
    """
    parts = ["" if (v := row.get(c)) is None else str(v) for c in hash_columns]
    payload = HASH_SEPARATOR.join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _compute_record_hash(df: DataFrame, hash_columns: list[str]) -> DataFrame:
    """Attach/overwrite ``_record_hash`` = SHA-256 of the SCD2 tracked columns.

    Mirrors the STM Bronze-to-Silver expression
    ``SHA256(CONCAT_WS('|', COALESCE(TRIM(col), ''), ...))`` so the hash
    computed here matches the one the contract documents. NULLs collapse to
    the empty string before concatenation so a NULL never silently changes
    the digest across runs.
    """
    from pyspark.sql import functions as F

    coalesced = [F.coalesce(F.col(c).cast("string"), F.lit("")) for c in hash_columns]
    return df.withColumn(
        HASH_COLUMN,
        F.sha2(F.concat_ws(HASH_SEPARATOR, *coalesced), 256),
    )


def apply_scd2(
    df: DataFrame,
    *,
    target_table: str,
    natural_keys: list[str],
    hash_columns: list[str],
    effective_date: str,
) -> dict[str, int]:
    """Apply an SCD Type 2 merge of ``df`` into the named UC dimension
    ``target_table``.

    Parameters
    ----------
    df:
        Validated incoming rows (DQ already run by the caller). Must carry
        every business column plus the natural-key column(s). The
        ``_record_hash`` column is computed here from ``hash_columns`` and
        overwrites any pre-existing value.
    target_table:
        NAMED Unity Catalog table FQN (3-part ``unity.silver.<dim>``) of the
        pre-created EXTERNAL Delta dimension to merge into. NOT a filesystem
        path — resolved via ``DeltaTable.forName`` (LLD §13 Decision 12).
    natural_keys:
        Business key column(s) used as the MERGE join key.
    hash_columns:
        SCD2-tracked columns (DMS §6) whose SHA-256 digest drives change
        detection.
    effective_date:
        ``YYYY-MM-DD`` version start date for new/changed rows; the closed
        version's ``effective_to`` is set to ``effective_date - 1 day``.

    Returns
    -------
    dict[str, int]
        ``{"rows_inserted", "rows_closed", "rows_unchanged"}`` read from the
        Delta ``MERGE`` operation metrics. The caller emits these via
        OpenTelemetry per LLD §5.4 step 8.
    """
    from delta.tables import DeltaTable
    from pyspark.sql import functions as F

    spark = df.sparkSession

    # 1. Stamp SCD2 metadata columns on the incoming (open) version.
    staged = (
        _compute_record_hash(df, hash_columns)
        .withColumn("effective_from", F.to_date(F.lit(effective_date)))
        .withColumn("effective_to", F.to_date(F.lit(OPEN_EFFECTIVE_TO)))
        .withColumn("is_current", F.lit(True))
    )

    # 2. Resolve the PRE-CREATED named UC table. Liquibase created it at
    #    deploy-time (LLD §13 Decision 12 / IL-002 / IL-018). The helper NEVER
    #    creates the table and NEVER issues runtime catalog DDL.
    target = DeltaTable.forName(spark, target_table)

    # Pre-merge counts for unchanged/closed accounting (small dims — max
    # 5,767 rows per DMS §6, so a count pass is cheap). On the first run the
    # pre-created table is empty, so both counts are 0 and every staged row
    # falls through to the insert branch below.
    join_cond = " AND ".join(f"t.{k} = s.{k}" for k in natural_keys)
    current_target = target.toDF().where("is_current = true")
    matched_current = (
        current_target.alias("t")
        .join(staged.alias("s"), on=natural_keys, how="inner")
        .select(
            *[F.col(f"t.{k}").alias(k) for k in natural_keys],
            F.col(f"t.{HASH_COLUMN}").alias("t_hash"),
            F.col(f"s.{HASH_COLUMN}").alias("s_hash"),
        )
    )
    rows_changed = matched_current.where("t_hash <> s_hash").count()
    rows_unchanged = matched_current.where("t_hash = s_hash").count()

    expiry = F.date_sub(F.to_date(F.lit(effective_date)), 1)

    # 3a. Close the current version of every changed natural key.
    (
        target.alias("t")
        .merge(
            staged.alias("s"),
            f"{join_cond} AND t.is_current = true AND t.{HASH_COLUMN} <> s.{HASH_COLUMN}",
        )
        .whenMatchedUpdate(
            set={
                "is_current": F.lit(False),
                "effective_to": expiry,
            }
        )
        .execute()
    )

    # 3b. Insert the new open version for new keys AND for changed keys whose
    #     current version we just closed. Anti-join against the still-open
    #     rows so unchanged keys are not re-inserted. The append targets the
    #     NAMED UC table (insertInto), never a filesystem path / saveAsTable.
    still_open = target.toDF().where("is_current = true").select(*natural_keys)
    to_insert = staged.join(still_open, on=natural_keys, how="left_anti")
    rows_inserted = to_insert.count()
    if rows_inserted:
        # Align column order to the pre-created table schema before insertInto
        # (positional API — the staged frame must match the target columns).
        target_cols = target.toDF().columns
        to_insert.select(*target_cols).write.mode("append").insertInto(target_table)

    return {
        "rows_inserted": rows_inserted,
        "rows_closed": rows_changed,
        "rows_unchanged": rows_unchanged,
    }


__all__ = [
    "apply_scd2",
    "compute_record_hash_python",
    "OPEN_EFFECTIVE_TO",
    "HASH_COLUMN",
]
