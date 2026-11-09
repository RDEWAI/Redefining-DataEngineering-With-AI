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

In-place refresh contract (LLD v1.26 §2.3, §13 Decision 17): optional
``refresh_columns`` are copied from ``df`` onto the current version of an
unchanged-hash row, with no new version. The helper holds no business rule for
these values; the caller computes them.

Same-day overwrite contract (LLD v1.27 §2.3, §13 Decision 18, DMS v1.5 §6): a
hash change to a current version whose ``effective_from`` equals
``effective_date`` updates that version in place (``rows_overwritten``). A hash
change to a version that started earlier closes it and inserts a new version.

Backfill skip contract (LLD v1.28 §2.3, §13 Decision 19, DMS v1.6 §6): a
natural key whose current version has ``effective_from > effective_date`` is
not written at all (``rows_skipped_backfill``), and one warning logs the count.

Hash-list change contract (LLD v1.28 §2.3, §13 Decision 20, DMS v1.6 §6): the
incoming hash is compared with a hash recomputed from the target's stored
hash columns, and a stale stored ``_record_hash`` is rewritten in place in its
own MERGE (``rows_rehashed``), so a hash-list change creates no version.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import DataFrame

# DMS §6 sentinel for the open (current) version's end date.
OPEN_EFFECTIVE_TO = "9999-12-31"

# DMS §3 hash column name + STM `SHA256(CONCAT_WS('|', ...))` separator.
HASH_COLUMN = "_record_hash"
HASH_SEPARATOR = "|"

# LLD §2.3 in-place refresh: never refreshable, and the reduction order column.
_SCD2_METADATA_COLUMNS = ("effective_from", "effective_to", "is_current", HASH_COLUMN)
_INGESTED_AT_COLUMN = "_ingested_at"

# Working column names for the stored and recomputed target hashes.
_STORED_HASH = "_stored_hash"
_TARGET_REHASH = "_t_rehash"

logger = logging.getLogger(__name__)


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


def _validate_refresh_columns(
    refresh_columns: list[str],
    *,
    df_columns: list[str],
    target_columns: list[str],
    natural_keys: list[str],
    hash_columns: list[str],
) -> None:
    """LLD §2.3 refresh step 1: raise ``ValueError`` before any write."""
    for column in refresh_columns:
        if column in natural_keys:
            raise ValueError(f"refresh column {column!r} is a natural key")
        if column in hash_columns:
            raise ValueError(f"refresh column {column!r} is a hash column")
        if column in _SCD2_METADATA_COLUMNS:
            raise ValueError(f"refresh column {column!r} is an SCD2 metadata column")
        if column not in df_columns:
            raise ValueError(f"refresh column {column!r} is not in the source DataFrame")
        if column not in target_columns:
            raise ValueError(f"refresh column {column!r} is not in the target table")
    if _INGESTED_AT_COLUMN not in df_columns:
        raise ValueError(f"refresh_columns requires a {_INGESTED_AT_COLUMN!r} source column")


def _refresh_in_place(
    target: Any,
    staged: DataFrame,
    *,
    natural_keys: list[str],
    refresh_columns: list[str],
    not_skipped: str,
) -> int:
    """LLD §2.3 refresh steps 3-7. Return the change-set row count.

    ``not_skipped`` is the SQL predicate on the target alias ``t`` that excludes
    natural keys skipped by backfill case (s).
    """
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    match_keys = [*natural_keys, HASH_COLUMN]

    # Step 3: natural keys may repeat in df, and MERGE allows one source row per
    # target row. Keep the latest _ingested_at; refresh columns resolve ties.
    latest_first = Window.partitionBy(*match_keys).orderBy(
        F.col(_INGESTED_AT_COLUMN).desc_nulls_last(),
        *[F.col(c).desc_nulls_last() for c in refresh_columns],
    )
    reduced = (
        staged.withColumn("_refresh_rank", F.row_number().over(latest_first))
        .where("_refresh_rank = 1")
        .select(*match_keys, *refresh_columns)
    )

    # Step 4: only rows whose value differs under null-safe comparison. A key
    # skipped by case (s) is never refreshed.
    current = (
        target.toDF()
        .alias("t")
        .where(f"t.is_current = true AND {not_skipped}")
        .select(*match_keys, *refresh_columns)
    )
    value_differs = " OR ".join(f"NOT (t.{c} <=> s.{c})" for c in refresh_columns)
    change_set = (
        reduced.alias("s")
        .join(current.alias("t"), on=match_keys, how="inner")
        .where(value_differs)
        .select(*match_keys, *[F.col(f"s.{c}").alias(c) for c in refresh_columns])
        .persist()
    )
    try:
        rows_refreshed = change_set.count()
        # Step 5: an empty change set adds no Delta commit.
        if rows_refreshed:
            # Step 6: the is_current predicate keeps closed versions unmatched.
            match = " AND ".join(f"t.{k} = s.{k}" for k in match_keys)
            (
                target.alias("t")
                .merge(
                    change_set.alias("s"),
                    f"{match} AND t.is_current = true AND {not_skipped}",
                )
                .whenMatchedUpdate(set={c: f"s.{c}" for c in refresh_columns})
                .execute()
            )
    finally:
        change_set.unpersist()
    return rows_refreshed


def apply_scd2(
    df: DataFrame,
    *,
    target_table: str,
    natural_keys: list[str],
    hash_columns: list[str],
    effective_date: str,
    refresh_columns: list[str] | None = None,
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
        version's ``effective_to`` is set to ``effective_date - 1 day``. A
        changed current version that already started on ``effective_date`` is
        overwritten in place instead (LLD §2.3, Decision 18). A key whose
        current version started after ``effective_date`` is skipped (Decision
        19).
    refresh_columns:
        Columns outside ``hash_columns`` to update in place on the current
        version of an unchanged-hash row (LLD §2.3, Decision 17). Omitted,
        ``None``, or empty runs no refresh step.

    Returns
    -------
    dict[str, int]
        ``{"rows_inserted", "rows_closed", "rows_unchanged",
        "rows_overwritten", "rows_skipped_backfill", "rows_rehashed"}``, plus
        ``rows_refreshed`` only when ``refresh_columns`` is non-empty. Each
        incoming row counts in exactly one of ``rows_skipped_backfill``,
        ``rows_overwritten``, ``rows_closed``, ``rows_unchanged``, or (new keys)
        ``rows_inserted``. ``rows_refreshed`` and ``rows_rehashed`` are not
        buckets: a refreshed row also counts in ``rows_unchanged``, and
        ``rows_rehashed`` counts target rows. The caller emits these via
        OpenTelemetry per LLD §5.4 step 8.

    Raises
    ------
    ValueError
        Before any write, if ``refresh_columns`` is invalid (LLD §2.3 step 1).
    """
    from delta.tables import DeltaTable
    from pyspark.sql import functions as F

    spark = df.sparkSession
    run_date = f"to_date('{effective_date}')"

    # 1. Resolve the PRE-CREATED named UC table. Liquibase created it at
    #    deploy-time (LLD §13 Decision 12 / IL-002 / IL-018). The helper NEVER
    #    creates the table and NEVER issues runtime catalog DDL.
    target = DeltaTable.forName(spark, target_table)
    target_df = target.toDF()

    if refresh_columns:
        _validate_refresh_columns(
            refresh_columns,
            df_columns=df.columns,
            target_columns=target_df.columns,
            natural_keys=natural_keys,
            hash_columns=hash_columns,
        )

    # 2. Stamp SCD2 metadata columns on the incoming (open) version. Hash-list
    #    contract step 1: cast each incoming hash column to the target type
    #    first, so equal values give equal strings on both sides.
    target_types = {f.name: f.dataType for f in target_df.schema.fields}
    typed = df
    for column in hash_columns:
        if column in target_types and df.schema[column].dataType != target_types[column]:
            typed = typed.withColumn(column, F.col(column).cast(target_types[column]))
    staged = (
        _compute_record_hash(typed, hash_columns)
        .withColumn("effective_from", F.to_date(F.lit(effective_date)))
        .withColumn("effective_to", F.to_date(F.lit(OPEN_EFFECTIVE_TO)))
        .withColumn("is_current", F.lit(True))
    )

    # Hash-list contract step 1: recompute every target row's hash from its
    # stored hash columns with the same function and the current list.
    rehashed_target = _compute_record_hash(
        target_df.withColumnRenamed(HASH_COLUMN, _STORED_HASH), hash_columns
    ).withColumnRenamed(HASH_COLUMN, _TARGET_REHASH)
    current_target = rehashed_target.where("is_current = true")

    # Backfill contract: the skipped-key set is the current versions that start
    # after effective_date. No write in this call touches those versions, and
    # every version this call opens starts on effective_date, so this predicate
    # names the same keys before and after each write below.
    skipped_keys = current_target.where(f"effective_from > {run_date}").select(*natural_keys)
    not_skipped = f"t.effective_from <= {run_date}"

    # 3. Decide every case from the target state before any write (LLD §2.3
    #    same-day rule 1). Case (s) first, then (a), (b), (d) compare with the
    #    recomputed hash, not the stored one (hash-list contract step 2).
    #    Small dims (max 5,767 rows per DMS §6), so count passes are cheap.
    matched_current = (
        current_target.alias("t")
        .join(staged.alias("s"), on=natural_keys, how="inner")
        .select(
            F.col(f"t.{_TARGET_REHASH}").alias("t_hash"),
            F.col(f"s.{HASH_COLUMN}").alias("s_hash"),
            F.col("t.effective_from").alias("t_effective_from"),
        )
        .persist()
    )
    try:
        rows_skipped_backfill = matched_current.where(f"t_effective_from > {run_date}").count()
        decided = matched_current.where(f"t_effective_from <= {run_date}")
        changed = decided.where("t_hash <> s_hash")
        rows_overwritten = changed.where(f"t_effective_from = {run_date}").count()
        rows_changed = changed.where(f"t_effective_from < {run_date}").count()
        rows_unchanged = decided.where("t_hash = s_hash").count()
    finally:
        matched_current.unpersist()

    if rows_skipped_backfill:
        # Count only: clinical_patients natural keys are PHI-adjacent.
        logger.warning(
            "apply_scd2 %s: skipped %d natural keys whose current version starts after "
            "effective_date %s (backfill/replay)",
            target_table,
            rows_skipped_backfill,
            effective_date,
        )

    # 4. Rehash stale stored hashes in place, current and closed versions, as
    #    their own MERGE (hash-list contract steps 3-4). Only _record_hash
    #    changes. Nothing stale means no MERGE and no Delta commit.
    stale = (
        rehashed_target.join(skipped_keys, on=natural_keys, how="left_anti")
        .where(f"NOT ({_STORED_HASH} <=> {_TARGET_REHASH})")
        .select(*natural_keys, "effective_from", "is_current", _STORED_HASH, _TARGET_REHASH)
        .persist()
    )
    try:
        rows_rehashed = stale.count()
        if rows_rehashed:
            match = " AND ".join(
                f"t.{c} <=> s.{c}" for c in [*natural_keys, "effective_from", "is_current"]
            )
            (
                target.alias("t")
                .merge(
                    stale.alias("s"),
                    f"{match} AND t.{HASH_COLUMN} <=> s.{_STORED_HASH}",
                )
                .whenMatchedUpdate(set={HASH_COLUMN: f"s.{_TARGET_REHASH}"})
                .execute()
            )
    finally:
        stale.unpersist()

    expiry = F.date_sub(F.to_date(F.lit(effective_date)), 1)

    # 5. One MERGE over the changed current versions (LLD §2.3 same-day rule 3).
    #    After step 4 every non-skipped stored _record_hash equals its
    #    recomputed hash, so comparing with the stored value here is the
    #    comparison with t_rehash. Case (a): a version that started on
    #    effective_date is overwritten in place with every incoming column
    #    except the natural keys and the effective_from / effective_to /
    #    is_current versioning columns; it is never closed (rule 2). Case (b):
    #    a version that started earlier is closed. Skipped keys never match.
    #    Delta applies the first matching clause, so (a) precedes (b).
    join_cond = " AND ".join(f"t.{k} = s.{k}" for k in natural_keys)
    keep = {*natural_keys, "effective_from", "effective_to", "is_current"}
    overwrite_cols = [c for c in target_df.columns if c in staged.columns and c not in keep]
    (
        target.alias("t")
        .merge(
            staged.alias("s"),
            f"{join_cond} AND t.is_current = true AND {not_skipped} "
            f"AND t.{HASH_COLUMN} <> s.{HASH_COLUMN}",
        )
        .whenMatchedUpdate(
            condition=f"t.effective_from = {run_date}",
            set={c: f"s.{c}" for c in overwrite_cols},
        )
        .whenMatchedUpdate(
            set={
                "is_current": F.lit(False),
                "effective_to": expiry,
            }
        )
        .execute()
    )

    # 6. Insert the new open version for new keys AND for changed keys whose
    #    current version we just closed. Anti-join against the still-open
    #    rows so unchanged, overwritten, and skipped keys are not re-inserted.
    #    The append targets the NAMED UC table (insertInto), never a
    #    filesystem path / saveAsTable.
    still_open = target.toDF().where("is_current = true").select(*natural_keys)
    to_insert = staged.join(still_open, on=natural_keys, how="left_anti")
    rows_inserted = to_insert.count()
    if rows_inserted:
        # Align column order to the pre-created table schema before insertInto
        # (positional API — the staged frame must match the target columns).
        to_insert.select(*target_df.columns).write.mode("append").insertInto(target_table)

    metrics = {
        "rows_inserted": rows_inserted,
        "rows_closed": rows_changed,
        "rows_unchanged": rows_unchanged,
        "rows_overwritten": rows_overwritten,
        "rows_skipped_backfill": rows_skipped_backfill,
        "rows_rehashed": rows_rehashed,
    }

    # 7. Refresh in place last, as its own MERGE commit (LLD §2.3 step 2). It
    #    matches on the stored _record_hash, which step 4 already rehashed. An
    #    overwritten version already carries the incoming refresh values, so
    #    the change set skips it. Skipped keys are excluded.
    if refresh_columns:
        metrics["rows_refreshed"] = _refresh_in_place(
            target,
            staged,
            natural_keys=natural_keys,
            refresh_columns=refresh_columns,
            not_skipped=not_skipped,
        )

    return metrics


__all__ = [
    "apply_scd2",
    "compute_record_hash_python",
    "OPEN_EFFECTIVE_TO",
    "HASH_COLUMN",
]
