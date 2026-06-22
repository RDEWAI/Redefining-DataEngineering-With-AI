---
Version: 1.0
Status: Approved
Topic: Spark Declarative Pipelines — spark-pipeline.yml + @dp decorators
---

# Spark Declarative Pipelines (SDP)

## Purpose

SDP is the **declarative** runtime for bronze/silver/gold pipelines —
`@dp.table` / `@dp.materialized_view` functions declare *what* each
table is, and the `dp` CLI resolves the DAG and executes in topological
order. This is the alternative to hand-rolled Airflow tasks for
layer-internal transforms; Airflow then triggers the `dp` run.

## Pattern

- **Root `spark-pipeline.yml`** declares the pipeline, catalog, schema,
  and root module (where decorated functions live).
- **`pipelines/{layer}.py`** hosts `@dp.table` definitions; the module
  is imported by the `dp` runtime.
- **One decorator per table** — `@dp.table(name=...)` for Delta tables,
  `@dp.materialized_view(...)` for queries materialized but not
  auto-refreshed.
- **Pure functions take `spark`** and return a `DataFrame`; all
  side-effects (writes) are handled by the runtime.
- **Run via `dp run --conf spark-pipeline.yml`** — packages under
  `pyspark[pipelines]` (the `[pipelines]` extra is mandatory).

## Key APIs

- `pyspark.pipelines as dp` (ships with PySpark 4.1.1 when installed
  with `pyspark[pipelines]`).
- `@dp.table(name, comment, table_properties, partition_cols)`
- `@dp.materialized_view(name)`
- CLI: `dp run --conf spark-pipeline.yml [--full-refresh]`

## Illustrative snippet

```yaml
# spark-pipeline.yml
name: {project}_pipeline
catalog: spark_catalog
schema: silver
root: pipelines
libraries:
  - glob:
      include: pipelines/**/*.py
```

```python
# pipelines/silver.py
import pyspark.pipelines as dp
from pyspark.sql import functions as F, SparkSession

@dp.table(
    name="silver.dim_{entity}_current",
    comment="Current snapshot of {entity} dimension",
    partition_cols=["ds"],
)
def dim_{entity}_current(spark: SparkSession):
    return (spark.table("silver.dim_{entity}")
                 .filter(F.col("dim_is_current") == True))

@dp.materialized_view(name="silver.mv_{entity}_daily_counts")
def mv_{entity}_daily_counts(spark: SparkSession):
    return (spark.table("silver.fct_{event}")
                 .groupBy("ds", "{entity}_sk")
                 .agg(F.count("*").alias("daily_count")))
```

## Common pitfalls

- Installing `pyspark` without the `[pipelines]` extra — `dp` CLI is
  absent; all runs fail with `command not found`.
- Side effects inside the decorated function (writes, `spark.sql(...)`
  DDL) — the runtime already handles persistence; side effects are
  re-run on every invocation and corrupt state.
- Cross-layer `spark-pipeline.yml` — one `dp` run per layer is the
  clearest model; mixing silver + gold tables in the same config makes
  failures harder to isolate.
- Forgetting `partition_cols` on `ds`-partitioned tables — the runtime
  creates an un-partitioned Delta table; silver/gold overwrite
  semantics break.

## References

- `/mvp/spark-pipeline.yml`
- `/mvp/pipelines/bronze.py`, `silver.py`, `gold.py`
- [`dependency-management.md`](dependency-management.md) (`pyspark[pipelines]`)
- PySpark SDP docs: https://spark.apache.org/docs/latest/api/python/
