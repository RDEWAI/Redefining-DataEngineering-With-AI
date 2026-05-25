---
Version: 1.0
Status: Approved
Topic: Silver — SCD2 dimensions via Delta MERGE INTO, fact derivations
---

# Silver Transform Pattern

## Purpose

Silver is the **cleansed + conformed** layer: deduplicated, typed,
audit-complete. Dimensions are SCD Type 2 (history-preserving); facts
reference dimensions by both natural key (NK) and surrogate key (SK).
Every silver table is reproducible from bronze — no manual data fixes.

## Pattern

### SCD2 dimensions

- **Configuration over code** — each dimension is a row in a
  `SCD2_CONFIG` dict: `{dim_table: {source: ..., natural_keys: [...],
  tracked_columns: [...], scd1_columns: [...]}}`. Adding a new dim =
  add an entry; reuse one merge function.
- **Hash-based change detection** — `record_hash = sha2(concat(tracked
  cols), 256)`. Only a hash delta triggers a new version row.
- **Delta `MERGE INTO` with `WHEN MATCHED AND dim_is_current AND
  record_hash <> …`** — closes the current row (`end_ts = ds - 1`,
  `dim_is_current = false`) and inserts a new current row.
- **UUID surrogate keys** — `F.expr("uuid()")` at insert time; stable
  for the lifetime of that version row.
- **SCD1 inside SCD2** — columns marked `scd1` (e.g. `email`) update
  in place on the current row without creating a new version.
- **Metadata columns on every dim** — see `naming-conventions.md`
  §SCD2 metadata.

### Facts

- **Two keys per dimension reference** — `{entity}_nk` (natural key from
  source, joinable to bronze) and `{entity}_sk` (surrogate from silver
  dim, joinable to historical snapshots).
- **Point-in-time lookup** — join to
  `silver.dim_{entity}` on `dim_is_current = true` for current snapshots;
  on `start_ts ≤ event_ts < coalesce(end_ts, '9999-12-31')` for history.
- **Fact tables are append-only** — `write.mode=append` + partition by
  `ds`; no SCD, no late-arriving rewrites.

## Key APIs

- Delta 4.2.0 — `DeltaTable.forName(spark, "silver.dim_x").alias("t")
  .merge(source.alias("s"), "t.nk = s.nk")`.
- PySpark `F.sha2(F.concat_ws("|", *cols), 256)` for change hash.
- `F.expr("uuid()")` for surrogate keys.

## Illustrative snippet

```python
# src/{project}/silver/scd2.py
SCD2_CONFIG = {
    "dim_{entity}": {
        "source_table": "bronze.{entity}",
        "natural_keys": ["{entity}_id"],
        "tracked_columns": ["{col_a}", "{col_b}"],
        "scd1_columns": ["{mutable_col}"],
    },
}

def merge_scd2(spark, dim_name: str, ds: str) -> None:
    cfg = SCD2_CONFIG[dim_name]
    src = (spark.table(cfg["source_table"])
           .filter(F.col("ds") == ds)
           .withColumn("record_hash",
                       F.sha2(F.concat_ws("|", *cfg["tracked_columns"]), 256)))

    tgt = DeltaTable.forName(spark, f"silver.{dim_name}")
    nk_join = " AND ".join(f"t.{k} = s.{k}" for k in cfg["natural_keys"])

    (tgt.alias("t").merge(src.alias("s"), nk_join)
        .whenMatchedUpdate(
            condition="t.dim_is_current = true AND t.record_hash <> s.record_hash",
            set={"end_ts": F.date_sub(F.lit(ds), 1),
                 "dim_is_current": F.lit(False),
                 "dw_updated_at": F.current_timestamp()})
        .whenNotMatchedInsert(values=_insert_values(cfg, ds))
        .execute())

    _insert_new_versions(spark, dim_name, src, ds)  # closed-row -> new-row
```

## Common pitfalls

- Hashing **all** columns (including audit/SCD1) → every run flips
  every row. Hash only `tracked_columns`.
- `dim_is_current` as `0/1` integer — always boolean; keeps the filter
  expressive and indexable.
- Overwriting (`mode="overwrite"`) a dim — destroys history. Silver
  dims are MERGE-only.
- Joining fact → dim by NK alone — returns the wrong version for
  historical events. Always carry `{entity}_sk` on the fact, populated
  at silver-fact build time using a point-in-time join.
- Forgetting to close the old row before inserting the new one — two
  `dim_is_current = true` rows for the same NK.

## References

- `/mvp/src/patient_360/silver/scd2.py` (merge function)
- `/mvp/src/patient_360/silver/dims.py` (SCD2_CONFIG)
- `/mvp/src/patient_360/silver/facts.py` (NK+SK pattern)
- [`naming-conventions.md`](naming-conventions.md)
- Delta merge docs: https://docs.delta.io/latest/delta-update.html#upsert-into-a-table-using-merge
