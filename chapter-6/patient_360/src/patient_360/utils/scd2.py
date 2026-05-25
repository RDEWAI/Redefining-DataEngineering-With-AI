"""Generic SCD Type 2 merge for Silver dimension tables.

Per LLD §5.2 / DMS §6, SCD2 uses SHA-256 hash comparison and Delta
``MERGE INTO`` with matched / unmatched semantics. The natural key plus a
column-hash uniquely identifies a row version; a hash change closes the
current row (sets ``effective_to`` + ``is_current = false``) and inserts a
new version.

Signature
---------
The helper signature follows LLD-DEVIATIONS row 1 (2026-05-19): the
published LLD §2.3 signature omits ``target_path``, without which the
function cannot locate which Delta table to MERGE INTO. We include
``target_path`` and derive the Spark session from ``df.sparkSession``.

::

    apply_scd2(
        df: DataFrame,
        target_path: str,
        natural_keys: list[str],
        hash_columns: list[str],
        effective_date: str,
    ) -> dict[str, int]

The returned metrics dict reports ``rows_inserted`` / ``rows_closed``
/ ``rows_unchanged`` — the caller emits these via OpenTelemetry per
LLD §5.4 step 8.

Contract
--------
The caller is responsible for running inline DQ via
``patient_360.utils.se_runner.run_dq`` BEFORE invoking this function;
the SCD2 helper trusts every row it receives.

Table visibility in Unity Catalog is established at deploy time via
``make bootstrap-uc`` (LLD v1.16 Decision 17). This helper performs
path-based Delta writes only — it MUST NOT issue any catalog DDL
(table-create / schema-create / save-as-table) at runtime.
"""

from __future__ import annotations

import hashlib
from typing import Any

# Sentinel "current" expiry per DMS §6 — Silver dim rows that are the
# active version write ``effective_to = 9999-12-31``.
SCD2_OPEN_EXPIRY = "9999-12-31"


def compute_record_hash_python(row: dict[str, Any], hash_columns: list[str]) -> str:
    """Return the SHA-256 hex digest used to detect attribute drift.

    Used by unit tests and by Python-side fixtures. The Spark-side
    implementation in :func:`apply_scd2` uses ``F.sha2(F.concat_ws(...))``
    over the same column ordering so the digests agree.
    """
    parts = [str(row.get(col, "")) for col in hash_columns]
    payload = "|".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def apply_scd2(
    df: Any,
    target_path: str,
    natural_keys: list[str],
    hash_columns: list[str],
    effective_date: str,
) -> dict[str, int]:
    """Apply a SCD Type 2 merge from ``df`` into the Delta table at
    ``target_path``.

    The MERGE runs directly against the path-based Delta target via
    ``delta.`<target_path>``` (LLD §3.2 path-based Delta + LLD v1.16
    Decision 17). Unity Catalog FQN visibility is established at deploy
    time by ``make bootstrap-uc`` — this helper performs path-based
    Delta writes only and MUST NOT issue any catalog DDL
    (table-create / schema-create / save-as-table) at runtime.

    Steps:
      1. Compute ``_record_hash`` on ``df`` rows over ``hash_columns``.
      2. Close current target rows whose ``natural_key`` matches and whose
         ``_record_hash`` differs: set ``is_current = false``,
         ``effective_to = effective_date - 1`` (one day before the new
         version becomes active).
      3. Insert the new version with ``is_current = true``,
         ``effective_from = effective_date``, ``effective_to = '9999-12-31'``.

    Returns a metrics dict ``{"rows_inserted", "rows_closed",
    "rows_unchanged"}``.
    """
    try:
        from pyspark.sql import functions as F  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - env-specific
        raise RuntimeError("pyspark required for apply_scd2") from exc

    spark = df.sparkSession

    nk_expr = F.concat_ws("||", *[F.col(c).cast("string") for c in natural_keys])
    hash_expr = F.sha2(
        F.concat_ws("||", *[F.coalesce(F.col(c).cast("string"), F.lit("")) for c in hash_columns]),
        256,
    )

    enriched = (
        df.withColumn("_natural_key", nk_expr)
        .withColumn("_record_hash", hash_expr)
        .withColumn("effective_from", F.to_date(F.lit(effective_date)))
        .withColumn("effective_to", F.to_date(F.lit(SCD2_OPEN_EXPIRY)))
        .withColumn("is_current", F.lit(True))
    )

    # First-run / cold-warehouse handling (LLD §3.2 path-based Delta +
    # LLD v1.16 Decision 17). Detect by checking for `_delta_log/` under
    # target_path. If absent, write the enriched DataFrame as the initial
    # Delta version (this establishes the schema) and return all-inserted
    # metrics. No MERGE on first run — every source row is by definition
    # new. No catalog DDL here: UC registration is a deploy-time concern
    # handled by `make bootstrap-uc`.
    from pathlib import Path as _Path

    if not (_Path(target_path) / "_delta_log").exists():
        enriched.write.format("delta").mode("overwrite").save(target_path)
        n_rows = len(source_pairs := [(r["_natural_key"], r["_record_hash"])
                                       for r in enriched.select(
                                           "_natural_key", "_record_hash"
                                       ).collect()])
        return {
            "rows_inserted": int(n_rows),
            "rows_closed": 0,
            "rows_unchanged": 0,
        }

    view_name = "_scd2_source_view"
    enriched.createOrReplaceTempView(view_name)

    # Snapshot the current source key+hash list to compute metrics
    # before/after the merge runs (Delta MERGE doesn't return counts in
    # all engines).
    source_rows = enriched.select("_natural_key", "_record_hash").collect()
    source_pairs = {(r["_natural_key"], r["_record_hash"]) for r in source_rows}

    rows_unchanged = 0
    rows_closed = 0
    rows_inserted = 0
    try:
        # Existing current rows in the target — addressed by path-based
        # Delta reference, never by FQN (LLD v1.16 Decision 17).
        existing = spark.sql(
            f"SELECT _natural_key, _record_hash FROM delta.`{target_path}` "
            f"WHERE is_current = TRUE"
        ).collect()
        existing_map = {r["_natural_key"]: r["_record_hash"] for r in existing}
    except Exception:  # noqa: BLE001 — first run, target empty / unregistered
        existing_map = {}

    for nk, h in source_pairs:
        if nk in existing_map:
            if existing_map[nk] == h:
                rows_unchanged += 1
            else:
                rows_closed += 1
                rows_inserted += 1
        else:
            rows_inserted += 1

    # Close out rows whose hash changed.
    spark.sql(
        f"""
        MERGE INTO delta.`{target_path}` t
        USING {view_name} s
        ON t._natural_key = s._natural_key AND t.is_current = TRUE
        WHEN MATCHED AND t._record_hash <> s._record_hash THEN
          UPDATE SET t.is_current = FALSE,
                     t.effective_to = date_sub(s.effective_from, 1)
        """
    )

    # Insert new versions (new natural keys + changed hashes).
    spark.sql(
        f"""
        INSERT INTO delta.`{target_path}`
        SELECT s.* FROM {view_name} s
        LEFT JOIN (
          SELECT _natural_key, _record_hash FROM delta.`{target_path}` WHERE is_current = TRUE
        ) t
        ON t._natural_key = s._natural_key
        WHERE t._natural_key IS NULL OR t._record_hash <> s._record_hash
        """
    )

    return {
        "rows_inserted": int(rows_inserted),
        "rows_closed": int(rows_closed),
        "rows_unchanged": int(rows_unchanged),
    }
