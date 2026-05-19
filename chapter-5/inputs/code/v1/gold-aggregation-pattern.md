---
Version: 1.0
Status: Approved
Topic: Gold — consumer-ready aggregates + wide joins over silver
---

# Gold Aggregation Pattern

## Purpose

Gold is the **consumer layer**: pre-joined, pre-aggregated datasets
optimized for a known access pattern (dashboard, export, API). One gold
table serves one consumer use-case; reuse comes from silver, not by
stretching a gold table across purposes.

## Pattern

- **Subject-centric naming** — `gold.{subject}_summary`,
  `gold.{subject}_metrics`; the name declares the consumer, not the
  source tables.
- **Join at current state by default** — `silver.dim_*` filtered to
  `dim_is_current = true`, joined to `silver.fct_*` via SK. Use
  point-in-time joins only when the consumer needs historical snapshots.
- **Aggregate once, expose once** — the aggregate logic lives in
  `src/{project}/gold/{subject}.py` and writes one Delta table. No
  downstream view that re-aggregates.
- **Partition by `ds`** — a gold rebuild per `ds` is cheap and keeps
  ad-hoc queries predictable.
- **Idempotent rebuilds** — `mode="overwrite"` + `replaceWhere` on
  `ds`; same `ds` can be rerun after a silver correction.
- **Tests assert consumer contract** — row counts, non-nullity of
  required fields, sum totals match silver — see `test-pattern.md`.

## Key APIs

- PySpark DataFrame API — `join`, `groupBy`, `agg`, `select`.
- Delta 4.2.0 — `replaceWhere` on the partition date.
- Unity Catalog — three-part names (`gold.{subject}_summary`) resolve
  via `UCSingleCatalog`.

## Illustrative snippet

```python
# src/{project}/gold/{subject}_summary.py
def build_summary(spark, ds: str) -> DataFrame:
    dim = (spark.table("silver.dim_{entity}")
                .filter(F.col("dim_is_current") == True)
                .select("{entity}_sk", "{entity}_id",
                        F.concat_ws(" ", "first_name", "last_name")
                         .alias("{entity}_full_name")))

    fct = (spark.table("silver.fct_{event}")
                .filter(F.col("ds") == ds)
                .groupBy("{entity}_sk")
                .agg(F.count("*").alias("total_{event}s"),
                     F.sum("{amount}").alias("total_{amount}")))

    summary = (dim.join(fct, "{entity}_sk", "left")
                  .withColumn("ds", F.lit(ds))
                  .withColumn("dw_built_at", F.current_timestamp()))

    (summary.write.format("delta").mode("overwrite")
            .option("replaceWhere", f"ds = '{ds}'")
            .partitionBy("ds")
            .saveAsTable("gold.{subject}_summary"))

    logger.info("Gold {subject}_summary: wrote %d rows (ds=%s)",
                summary.count(), ds)
    return summary
```

## Common pitfalls

- Joining silver facts on NK when SK is available — breaks historical
  reporting; always prefer SK.
- Rebuilding all partitions every run (`mode="overwrite"` without
  `replaceWhere`) — expensive and destructive if one silver run failed.
- A single `gold.everything` table serving multiple dashboards — becomes
  the union of every consumer's columns; split per use-case instead.
- Computing the aggregate in a BI-tool view — duplicates logic, drifts
  over time, and hides cost. Materialize in gold.
- Partitioning by high-cardinality keys (`{entity}_id`) — small-files
  explosion; partition by `ds` and let the `_sk` columns drive joins.

## References

- `/mvp/src/patient_360/gold/patient_summary.py`
- `/mvp/pipelines/gold.py`
- [`silver-transform-pattern.md`](silver-transform-pattern.md) (SK +
  point-in-time)
- [`naming-conventions.md`](naming-conventions.md) (subject naming)
