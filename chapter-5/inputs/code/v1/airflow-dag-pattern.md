---
Version: 1.0
Status: Approved
Topic: Airflow DAG shape — factory, task groups, SparkSubmitOperator
---

# Airflow DAG Pattern

## Purpose

One DAG per pipeline, one TaskGroup per source table (bronze) or
dimension/fact (silver) or consumer dataset (gold). Every task is a
`SparkSubmitOperator` that shells out to `pipelines/{layer}.py` with the
correct `--ds` and `--table` args. DAG files are generated from a
factory so 20 tables don't mean 20 copy-paste DAG files.

## Pattern

- **DAG file naming** — `dags/{project}_{schedule}_v{N}.py` (e.g.
  `{project}_hourly_v1.py`). One schedule per DAG file.
- **DAG factory** — `dags/_factory.py` exports
  `make_pipeline_dag(project, schedule, tables)` that constructs the
  DAG graph from the per-table YAML configs (same ones bronze reads).
- **TaskFlow API** (`@task`, `@dag`) preferred for orchestration; raw
  `SparkSubmitOperator` for the heavy Spark jobs themselves.
- **Sensible defaults**:
  - `retries=2`, `retry_delay=timedelta(minutes=5)`
  - `sla=timedelta(minutes=30)` per task (tuned per layer)
  - `catchup=False` — backfills are explicit via
    `airflow dags backfill`.
  - `depends_on_past=False` unless downstream semantics need it.
- **Pass `ds` via op_args/conf**, not env vars — Airflow's templating
  (`{{ ds }}`) expands at execute time and flows into `run_local.py`.
- **No business logic in DAG files** — DAG is pure orchestration; all
  transforms live in `src/{project}/`.
- **Shared-state bootstrap is its own task** — any pipeline whose tasks
  write to a SHARED downstream Delta table (e.g. Spark-Expectations
  `bronze_se_stats` / `bronze_se_errors`) MUST start with a one-shot
  `bootstrap_*` `SparkSubmitOperator` that idempotently pre-creates that
  table (`CREATE SCHEMA IF NOT EXISTS` + `CREATE TABLE IF NOT EXISTS …
  USING DELTA LOCATION`). Wire it as the root of the DAG, upstream of
  every TaskGroup that appends to the shared table. Without this, the
  first task races the CREATE on a cold metastore, and worse, after a
  container/metastore restart with on-disk Delta data still present,
  every task fails with `DELTA_CREATE_TABLE_WITH_NON_EMPTY_LOCATION`.

## Key APIs

- Airflow 3.2.1 — `@dag`, `@task`, `TaskGroup`, `SparkSubmitOperator`
  (from `airflow.providers.apache.spark`).
- Jinja-templated args: `{{ ds }}`, `{{ data_interval_end }}`.

## Illustrative snippet

```python
# dags/{project}_hourly_v1.py
import os
from datetime import datetime, timedelta
from airflow.decorators import dag, task_group
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator

# Env-driven paths — set by the cookiecutter docker-compose.yml.
# NEVER hardcode `airflow/configs` (relative) or `airflow/jobs` (relative).
CONFIGS_DIR = os.environ.get("AIRFLOW_CONFIGS_DIR", "/opt/airflow/configs")
BRONZE_RUNNER = os.environ.get("BRONZE_RUNNER_APP", "/opt/airflow/jobs/run_bronze_ingestion.py")
SE_BOOTSTRAP = os.environ.get("SE_BOOTSTRAP_APP", "/opt/patient_360/scripts/bootstrap_se_tables.py")

DEFAULT_ARGS = {
    "owner": "{project}",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "sla": timedelta(minutes=30),
}

@dag(
    dag_id="{project}_hourly_v1",
    schedule="@hourly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["{project}", "bronze-silver-gold"],
)
def {project}_pipeline():
    # Root task — pre-creates shared SE Delta tables so the bronze
    # TaskGroup can run at full concurrency without racing the CREATE.
    bootstrap_se = SparkSubmitOperator(
        task_id="bootstrap_se",
        application=SE_BOOTSTRAP,
        conn_id="spark_default",
        driver_memory="1g", executor_memory="1g",
        executor_cores=1, num_executors=1,
        retries=1, retry_delay=timedelta(seconds=60),
        execution_timeout=timedelta(minutes=5),
    )

    @task_group(group_id="bronze")
    def bronze_group():
        for table in BRONZE_TABLES:
            SparkSubmitOperator(
                task_id=f"ingest_{table}",
                # `application` is a path to a .py or .jar file — NEVER `-m module.path`.
                application=BRONZE_RUNNER,
                application_args=["--layer", "bronze",
                                  "--table", table,
                                  "--ds", "{{ ds }}",
                                  "--config-path", f"{CONFIGS_DIR}/{table}.yml"],
                conn_id="spark_default",
            )

    @task_group(group_id="silver")
    def silver_group(): ...

    @task_group(group_id="gold")
    def gold_group(): ...

    bootstrap_se >> bronze_group() >> silver_group() >> gold_group()

dag = {project}_pipeline()
```

## Bronze → Unity Catalog wiring (LLD §2.3)

Bronze writes MUST land in Unity Catalog OSS at write time via
`UCSingleCatalog` + `saveAsTable("unity.bronze.<table>")`. The earlier
"path-based Delta to `/tmp/uc-warehouse/...`" pattern leaves UC empty until
a manual `docker cp` + external-table registration — exactly the gap
spokane hit on its first green Bronze run. Validator rule
`UC-WIRING-001` rejects path-based Bronze writes.

```python
import os
from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .appName("bronze_ingest_<table>")
    .config("spark.sql.catalog.unity", "io.unitycatalog.spark.UCSingleCatalog")
    .config("spark.sql.catalog.unity.uri", os.environ["UC_URI"])
    .config("spark.sql.defaultCatalog", "unity")
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
    .config("spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    .getOrCreate()
)

# UC-managed write — appears in UC immediately, no manual registration.
(df.write.mode("append")
   .format("delta")
   .partitionBy("ds")
   .option("replaceWhere", f"ds = '{ds}'")
   .saveAsTable(f"unity.bronze.{table}"))
```

`UC_URI` comes from the airflow service env (`http://unity-catalog:8080`
in dev). See `inputs/code/v1/scripts/ingestion_runner.py.snippet` for the
full pattern.

## Common pitfalls

- Omitting the `bootstrap_se` root task — first bronze task races the
  CREATE of the shared SE stats Delta table; after a metastore restart
  every task fails with `DELTA_CREATE_TABLE_WITH_NON_EMPTY_LOCATION`.
  Workarounds like `max_active_tasks=1` are tech debt, not a fix.
- Hard-coding `ds` (`ds="2026-04-24"`) in the DAG — kills Airflow's
  scheduling model; always template.
- One DAG per table — turns the UI into thousands of DAGs and makes
  cross-table dependencies awkward. One DAG per pipeline, one TaskGroup
  per table.
- `catchup=True` on a fresh deploy — Airflow tries to backfill from
  `start_date` and floods the scheduler. Default `catchup=False`.
- Business logic in the DAG file (`if today.weekday() == 0: ...`) —
  moves logic out of version-controlled code into orchestration.
- `application="-m module.path"` — `SparkSubmitOperator.application`
  expects a path to a `.py` or `.jar` file, NOT a `-m module` spec.
  The wrapper has to be a real file under `airflow/jobs/run_<task_type>.py`.
  Spokane learned this the hard way after the wrapper failed with
  `PermissionError: [Errno 13] Permission denied: '-m'`.
- `application="run_local.py"` (relative path) — when Airflow runs from
  `/opt/airflow/` in the container, the relative path doesn't resolve.
  Always use an absolute path sourced from an env var
  (`os.environ["BRONZE_RUNNER_APP"]`, etc.).
- `configs_dir="airflow/configs"` (relative) — same issue. Always
  resolve via `os.environ.get("AIRFLOW_CONFIGS_DIR", "/opt/airflow/configs")`.
- `df.write.format("delta").save("/tmp/...")` for Bronze — writes
  path-based Delta that UC doesn't see. Use
  `saveAsTable("unity.bronze.<table>")` instead so the table is
  registered with UC at write time.
- Calling a SparkSession directly inside a `@task` — the Airflow worker
  holds it for the whole task; use `SparkSubmitOperator` so Spark runs
  in its own process.

## References

- [`spark-declarative-pipelines.md`](spark-declarative-pipelines.md)
- [`bronze-ingestion-pattern.md`](bronze-ingestion-pattern.md) (YAML
  configs that drive the factory)
- Airflow 3.x DAG authoring: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html
- SparkSubmitOperator: https://airflow.apache.org/docs/apache-airflow-providers-apache-spark/stable/operators.html
