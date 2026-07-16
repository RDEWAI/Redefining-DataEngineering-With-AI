---
Version: 1.1
Status: Approved
Topic: Gold — consumer-ready aggregates + wide joins over silver
Changelog:
  - "1.1 (2026-07-12): Reconciled with the Patient 360 LLD/Decision 15 runtime
     stack — full-overwrite insertInto into pre-created UC EXTERNAL Delta
     (no saveAsTable / replaceWhere / partitionBy(ds)); natural-key
     current-state joins (no surrogate FK on this pipeline); run_dq gate
     before write. Illustrative snippet rewritten to match
     scripts/gold_builder.py.snippet."
  - "1.0: Initial MVP pattern (saveAsTable + replaceWhere + SK joins)."
---

# Gold Aggregation Pattern

## Purpose

Gold is the **consumer layer**: pre-joined, pre-aggregated datasets
optimized for a known access pattern (dashboard, export, API). One gold
table serves one consumer use-case; reuse comes from silver, not by
stretching a gold table across purposes.

## Pattern

- **Subject-centric naming** — `unity.gold.{subject}_summary`,
  `unity.gold.{subject}_history`; the name declares the consumer, not the
  source tables.
- **Join at current state on the natural key** — SCD2 silver dims filtered
  to `is_current = True` and joined on the business/natural key
  (`patient_id`, `provider_id`, `organization_id`, `payer_id`). This
  pipeline has **no surrogate FK** — never join on an `_sk`. Use a
  point-in-time (`effective_from`/`effective_to` overlap) join only when a
  consumer explicitly needs a historical snapshot.
- **Aggregate once, expose once** — the build logic lives in
  `src/{project}/gold/build_{subject}.py` and writes one Delta table. No
  downstream view that re-aggregates.
- **Full overwrite each run, no partition** — Gold tables are rebuilt
  wholesale every run (LLD §3.3: write = Full overwrite, partition = None).
  A `ds` column, if present, is a **build stamp only** — never a partition
  key.
- **Insert into the pre-created table** — write with
  `df.write.mode("overwrite").insertInto("unity.gold.{subject}_summary")`.
  The EXTERNAL Delta table is pre-created at deploy time (beeline DDL
  migration); the builder never creates tables. **Never** `saveAsTable`,
  `.save(path)`, `replaceWhere`, `partitionBy`, `CREATE TABLE`, or any
  catalog DDL at runtime (Decision 15; stories' `forbidden_grep`).
- **DQ gate before the write** — call `run_dq(...)` on the assembled frame
  and write the returned (single) validated DataFrame; never write the
  pre-validation frame.
- **Tests assert consumer contract** — row counts, non-nullity of required
  fields, sum totals match silver, cross-field safety invariants (e.g.
  allergy flag ↔ allergy array) — see `test-pattern.md`.

## Key APIs

- PySpark DataFrame API — `join`, `groupBy`, `agg`, `select`,
  `F.collect_list(F.struct(...))` for `ARRAY<STRUCT>` denormalization.
- `patient_360.utils.se_runner.run_dq(df, *, table, env, action_if_failed,
  dq_rules_dir)` — inline Spark Expectations; returns the validated frame.
- Unity Catalog — three-part names (`unity.gold.{subject}_summary`) resolve
  via the `unity` side-catalog (`UCSingleCatalog`); `insertInto` is the
  supported write op (`saveAsTable` is rejected by UCSingleCatalog).

## Illustrative snippet

The authoritative fill-in-the-blanks template is
[`scripts/gold_builder.py.snippet`](scripts/gold_builder.py.snippet). The
shape:

```python
# src/{project}/gold/build_{subject}.py
def build(spark, env: str, ds: str) -> DataFrame:
    # current-state SCD2 dim on the NATURAL key (no _sk)
    patients = (spark.table("unity.silver.clinical_patients")
                     .filter(F.col("is_current") == True))          # noqa: E712
    encounters = spark.table("unity.silver.clinical_encounters")

    if patients.head(1) == []:                                       # LLD §5.3
        raise ValueError("Gold {subject}: required silver input empty (Fail task).")

    summary = (patients.join(encounters, on="patient_id", how="left")
                       # ...STM Silver-to-Gold joins/aggregations, in row order
                       .withColumn("ds", F.lit(ds).cast("date")))    # build stamp, not a partition

    validated = se_runner.run_dq(df=summary, table="{subject}_summary",
                                 env=env, action_if_failed="fail", dq_rules_dir=None)

    (validated.select(*OUTPUT_COLUMNS)                               # DMS §4 order
              .write.mode("overwrite")
              .insertInto("unity.gold.{subject}_summary"))           # full overwrite, no partition
    return validated
```

## Common pitfalls

- Joining silver dims on an `_sk` — this pipeline has no surrogate key;
  join on the natural key and filter `is_current = True`.
- `saveAsTable` / `.save(path)` / `partitionBy(ds)` / `replaceWhere` — all
  rejected here: the table is pre-created EXTERNAL Delta and the write is a
  full-overwrite `insertInto` with no partition (UCSingleCatalog rejects
  `saveAsTable` outright).
- Writing the pre-validation frame — always write the DataFrame returned by
  `run_dq`, and call it before the write, not after.
- A single `unity.gold.everything` table serving multiple dashboards —
  becomes the union of every consumer's columns; split per use-case.
- Computing the aggregate in a BI-tool view — duplicates logic, drifts over
  time, hides cost. Materialize in gold.

## References

- [`scripts/gold_builder.py.snippet`](scripts/gold_builder.py.snippet) — the builder template
- [`silver-transform-pattern.md`](silver-transform-pattern.md) (SCD2 current-state reads)
- [`unity-catalog-pattern.md`](unity-catalog-pattern.md) (insertInto vs saveAsTable on UCSingleCatalog)
- [`naming-conventions.md`](naming-conventions.md) (subject naming)
