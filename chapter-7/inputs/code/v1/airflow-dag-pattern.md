---
Version: 1.1
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

## Key APIs

- Airflow 3.2.1 — `@dag`, `@task`, `TaskGroup`, `SparkSubmitOperator`
  (from `airflow.providers.apache.spark`).
- Jinja-templated args: `{{ ds }}`, `{{ data_interval_end }}`.

## Resource sizing (env-tiered — source of truth is LLD §6.1)

Spark memory, executor count, and shuffle partitions are **environment-tiered
and MUST be resolved from `PATIENT360_ENV`** — never hardcode a single literal
across all deployments. The values come from **LLD §6.1** (Resource Sizing),
*not* from §4.2. The §4.2 task-inventory table has no memory column: the small
integers there are the **retries** count and the `execution_timeout`; wiring a
`driver_memory="2g"` off a "§4.2 sizing" reading is a citation error.

Why this matters: on the single-laptop DEV compose stack (8 GB Docker VM shared
by UC OSS, Marquez, Postgres, otel, and the Airflow scheduler/webserver), a
`2g` driver JVM's resident set exceeds the free VM headroom and the kernel
**SIGKILLs spark-submit (`Error code is: -9`)** — an *OS/cgroup* OOM, not a JVM
heap error. A smaller `-Xmx1g` keeps RSS bounded, lets Spark spill to disk, and
survives. LLD §6.1 (revised 2026-05-12) sets the DEV default to `1g/1g`
precisely for this reason.

Resolve once, near the top of the DAG (alongside the `max_active_tasks` /
`catchup` env resolution), and reference the map in **every**
`SparkSubmitOperator` — bronze factory, silver dims/facts, and gold builders:

```python
DEPLOY_ENV = os.environ.get("PATIENT360_ENV", "DEV").upper()

# Spark resource sizing per LLD §6.1 (env-tiered). DEV=1g avoids the OS
# OOM-kill on the 8 GB co-resident compose stack. Shuffle partitions per
# §6.1 (DEV 8 / STAGING 16 / PROD 32). §4.2 has NO memory column — do not
# source memory from it.
SPARK_SIZING = {
    "DEV":     {"driver_memory": "1g", "executor_memory": "1g", "shuffle_partitions": 8},
    "STAGING": {"driver_memory": "4g", "executor_memory": "4g", "shuffle_partitions": 16},
    "PROD":    {"driver_memory": "8g", "executor_memory": "8g", "shuffle_partitions": 32},
}[DEPLOY_ENV]

SparkSubmitOperator(
    task_id=f"transform_{table}_silver",
    application=silver_transform_app,
    driver_memory=SPARK_SIZING["driver_memory"],      # LLD §6.1 (env-tiered)
    executor_memory=SPARK_SIZING["executor_memory"],  # LLD §6.1 (env-tiered)
    conf=build_spark_conf({"spark.sql.shuffle.partitions": str(SPARK_SIZING["shuffle_partitions"])}),
    retries=2,                                         # LLD §4.2 (retries — NOT memory)
    execution_timeout=timedelta(minutes=45),          # LLD §4.2
    ...
)
```

`executor_memory` / `executor_cores` / `num_executors` are no-ops under a
`local[N]` master (the executor runs inside the driver JVM) — keep them for
STAGING/PROD parity but understand that in DEV only `driver_memory` bounds the
process. This is why the DEV OOM is fixed by lowering the **driver** heap.

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

    bronze_group() >> silver_group() >> gold_group()

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
- Hardcoding `driver_memory="2g"` (or any single memory literal) across
  all tasks/envs, or sourcing memory from LLD §4.2 — §4.2 has no memory
  column (its integers are retries/timeouts). Memory is env-tiered per
  §6.1; resolve it from `PATIENT360_ENV` via `SPARK_SIZING`. A `2g` driver
  OOM-kills spark-submit (`Error code is: -9`) on the 8 GB DEV compose
  stack; DEV must be `1g`.

## References

- [`spark-declarative-pipelines.md`](spark-declarative-pipelines.md)
- [`bronze-ingestion-pattern.md`](bronze-ingestion-pattern.md) (YAML
  configs that drive the factory)
- Airflow 3.x DAG authoring: https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html
- SparkSubmitOperator: https://airflow.apache.org/docs/apache-airflow-providers-apache-spark/stable/operators.html
