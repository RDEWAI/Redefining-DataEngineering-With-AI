---
Version: 1.0
Status: Approved
Topic: Config-driven Bronze ingestion — registry → factory → runner
---

# Bronze Ingestion Pattern

## Purpose

Ingest N source tables with one runner, not N scripts. Every table is
declared as YAML (source file, schema, DQ rules, partitioning) and a
single `run_bronze(table)` dispatcher resolves the right ingestor from a
registry. Adding a new table = add a YAML + (optionally) an entry in the
registry; no new module.

## Pattern

- **Per-table YAML config** in `airflow/configs/{table}.yml` with the
  shape: `table`, `source.{type, path}`, `schema_module`, `dq.rules_file`,
  `write.{mode, partition_by, replace_where_template}`.
- **Schema registry** — `src/{project}/bronze/schemas.py` exposes a
  `REGISTRY: dict[str, StructType]` keyed by source table name. No schema
  is inferred at read time.
- **Ingestion factory** — `src/{project}/bronze/ingest.py` exports
  `ingest(spark, config, ds)` that reads CSV/JSON/Parquet per config,
  applies schema, appends audit columns (`ds`, `ingested_at`), and writes
  to the bronze Delta table with `replace_where` (idempotent by `ds`).
- **Runner** — `run_local.py --layer bronze --ds {ds}` loops over all
  configs in `airflow/configs/*.yml`, invokes `ingest()`, and reports
  per-table success/failure.
- **Fail-fast validation** — missing source file, missing schema in
  registry, or schema mismatch raises before any write.
- **Dead-letter path (optional)** — rows that fail schema enforcement
  land in `bronze.{table}_dead_letter` with a `rejection_reason` column;
  runner logs counts.

## Key APIs

- PySpark 4.1.1 — `spark.read.format("csv").schema(schema).load(path)`
- Delta 4.2.0 — `df.write.format("delta").mode("append")
  .partitionBy("ds").option("path", external_path)
  .option("replaceWhere", "ds = '2026-04-24'").saveAsTable(table)`
  — `.option("path", ...)` is **mandatory**: it makes the table external,
  so re-runs after an embedded-metastore reset re-register from the
  existing `_delta_log` instead of failing with
  `DELTA_CREATE_TABLE_WITH_NON_EMPTY_LOCATION`. Compute `external_path`
  via a shared helper (e.g. `_external_table_path(fqn)`) so the path
  layout is consistent across Bronze / Silver / Gold.
- Spark Expectations 2.10.0 — wrapped in runner (see
  `spark-expectations-pattern.md`); invoked after the write, not before,
  so bronze always captures raw data first.

## Illustrative snippet

```yaml
# airflow/configs/{table}.yml
table: {table}
source:
  type: csv
  path: data/raw/{table}.csv
  header: true
schema_module: {project}.bronze.schemas:REGISTRY
dq:
  rules_file: expectations/bronze/{table}_expectations.yaml
write:
  mode: overwrite
  database: bronze
  partition_by: [ds]
  replace_where_template: "ds = '{ds}'"
```

```python
# src/{project}/bronze/ingest.py
def ingest(spark, config: dict, ds: str) -> DataFrame:
    schema = resolve_schema(config["schema_module"], config["table"])
    src = Path(config["source"]["path"])
    if not src.exists():
        raise FileNotFoundError(f"Source not found: {src}")

    df = (spark.read.format(config["source"]["type"])
          .option("header", config["source"].get("header", False))
          .schema(schema).load(str(src))
          .withColumn("ds", F.lit(ds))
          .withColumn("ingested_at", F.current_timestamp()))

    replace_where = config["write"]["replace_where_template"].format(ds=ds)
    table_fqn = f'{config["write"]["database"]}.{config["table"]}'
    external_path = _external_table_path(table_fqn)  # see utils/delta_helpers
    (df.write.format("delta").mode(config["write"]["mode"])
       .partitionBy(*config["write"]["partition_by"])
       .option("path", external_path)        # MUST — external Delta; survives metastore reset
       .option("replaceWhere", replace_where)
       .saveAsTable(table_fqn))

    logger.info("Bronze %s: wrote %d rows (ds=%s)",
                config["table"], df.count(), ds)
    return df
```

## Common pitfalls

- Skipping `replaceWhere` → overwrite nukes all partitions; a re-run of
  one date silently deletes history.
- Inferring schema at read (`.option("inferSchema", "true")`) — changes
  on every input batch; breaks downstream silver merges.
- Writing audit columns (`ds`, `ingested_at`) as the last step of silver
  instead of bronze — violates "bronze = raw + provenance".
- Putting per-table logic in the factory — every `if table == "..."`
  belongs in the YAML or a table-specific transform module, not the
  generic runner.
- Running SE rules before the write — bronze should always capture raw
  truth; SE runs after and either quarantines or flags, never blocks.
- Omitting `.option("path", external_path)` on `saveAsTable` — creates a
  *managed* Delta table under Spark's default warehouse dir. After a
  container/metastore restart, Derby forgets the table while the on-disk
  Delta data remains, and the next run fails with
  `DELTA_CREATE_TABLE_WITH_NON_EMPTY_LOCATION`. Always pass `.option(
  "path", ...)` so the table is external and the location is the source
  of truth.

## References

- `/mvp/src/patient_360/bronze/ingest.py`, `schemas.py`
- `/mvp/pipelines/bronze.py`
- `/mvp/airflow/configs/*.yml`
- [`spark-expectations-pattern.md`](spark-expectations-pattern.md)
- [`naming-conventions.md`](naming-conventions.md) (audit columns)
- Delta `replaceWhere` docs: https://docs.delta.io/latest/delta-update.html
