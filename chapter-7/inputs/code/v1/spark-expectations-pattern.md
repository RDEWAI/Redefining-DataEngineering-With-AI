---
Version: 1.0
Status: Approved
Topic: Nike Spark Expectations — rule YAML + runner wiring
---

# Spark Expectations Pattern

## Purpose

Run declarative data-quality rules against every bronze/silver/gold
write. Rules live next to the table (`expectations/{layer}/{table}_expectations.yaml`),
the runner invokes Spark Expectations (SE) after the write, and
`action_if_failed` decides whether a failing rule drops the row, warns,
or fails the whole run. One library handles row-level, aggregate-level,
and query-level checks.

## Pattern

- **One YAML file per table** under `expectations/{layer}/`. File name
  matches the table (`{table}_expectations.yaml`).
- **Three rule types**:
  - `row_dq` — row-level predicate (`column_name IS NOT NULL`,
    `age > 0`).
  - `agg_dq` — aggregate predicate over the whole write
    (`count(*) > 0`, `avg(amount) < 1000`).
  - `query_dq` — arbitrary SQL that returns a boolean — useful for
    cross-table invariants.
- **Per-rule `action_if_failed`** — `fail` (raises; fails pipeline),
  `drop` (removes bad rows from the downstream dataset), `warn` (logs
  + counts but never blocks).
- **SE runner wrapper** — `src/{project}/utils/se_runner.py` builds the
  `WrappedDataFrame` and invokes `SparkExpectations.with_expectations`;
  skill-generated ingest/transform modules call the wrapper, never SE
  directly.
- **Statistics table** — SE writes per-run stats into
  `{catalog}.{schema}._se_stats` (configurable). Expose this in Marquez
  or a dashboard.
- **Rules are version-controlled code** — not DB config. PRs review
  rule changes; no UI.

## Key APIs

- Spark Expectations 2.10.0 — `from spark_expectations.core.expectations
  import SparkExpectations`; `.with_expectations(rule_yaml, target_and_error_table_writer, ...)`.
- Stats writer — `SparkExpectationsWriter` builds the stats sink config.

## Illustrative snippet

```yaml
# expectations/bronze/{table}_expectations.yaml
product_id: {project}
table_name: bronze.{table}
rules:
  - rule_type: row_dq
    rule: {table}_id_not_null
    column_name: {table}_id
    expectation: "{table}_id IS NOT NULL"
    action_if_failed: fail
    enable_for_source_dq_validation: false
    enable_for_target_dq_validation: true
    tag: completeness

  - rule_type: agg_dq
    rule: row_count_positive
    expectation: "count(*) > 0"
    action_if_failed: fail
    tag: volume

  - rule_type: row_dq
    rule: email_looks_like_email
    column_name: email
    expectation: "email RLIKE '^[^@]+@[^@]+\\.[^@]+$'"
    action_if_failed: drop
    tag: validity
```

```python
# src/{project}/utils/se_runner.py
def run_with_se(spark, df, table: str, rules_yaml: Path,
                target_table: str, ds: str) -> DataFrame:
    se = SparkExpectations(
        product_id="{project}",
        rules_df=spark.read.format("yaml").load(str(rules_yaml)),
        stats_table="spark_catalog.bronze._se_stats",
        debugger=False,
    )
    return se.with_expectations(
        target_and_error_table_writer={
            "mode": "overwrite",
            "format": "delta",
            "partitionBy": ["ds"],
            "options": {"replaceWhere": f"ds = '{ds}'"},
        },
        target_table=target_table,
    )(df)
```

## Common pitfalls

- Running SE **before** the bronze write — bronze should capture raw
  truth; SE runs against the DataFrame that's about to be written or
  against the persisted table, never replacing the write.
- Using `action_if_failed: fail` on every rule — one bad row stops the
  pipeline. Pick `drop` for row-level, `fail` for aggregate invariants.
- Encoding rules as Python (custom predicates) — defeats the
  declarative model. Stick to SQL in YAML; add a Python UDF only when
  SQL can't express it.
- Forgetting `enable_for_target_dq_validation: true` — rule is parsed
  but never executed; no errors, no stats.
- Writing stats to a non-partitioned table — grows unbounded. Partition
  `_se_stats` by `run_date`.

## References

- `/mvp/expectations/bronze/*.yaml`
- `/mvp/src/patient_360/utils/se_runner.py`
- [`bronze-ingestion-pattern.md`](bronze-ingestion-pattern.md)
- Spark Expectations docs: https://engineering.nike.com/spark-expectations/
  and GitHub: https://github.com/Nike-Inc/spark-expectations
