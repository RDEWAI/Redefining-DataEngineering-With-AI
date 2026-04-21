---
name: create-ingestion
description: >
  Generates the Bronze config-driven ingestion framework from the approved LLD.
  Produces the generic ingestion runner, TaskGroup factory, SparkSubmitOperator
  wrapper, and one per-table YAML config for every Bronze table listed in LLD §5.1.
  Also known as: bronze ingestion scaffolding, ingestion-runner generation,
  per-table config generation.
  Input formats: LLD markdown (inputs/lld/v{N}/LLD-*.md), STM xlsx, config-template.yaml.
  Output format: Python modules + YAML configs written under patient_360/.
  Use when the user asks to:
  - Create, generate, or scaffold the Bronze ingestion code
  - Build the ingestion runner / factory / SparkSubmit wrapper
  - Generate per-table ingestion configs from the LLD
  - "Write the ingestion framework from the LLD"
argument-hint: "[lld-path]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion, Skill
context: fork
---

# Create Bronze Ingestion Framework

You are a senior Data Engineer. Your job is to translate LLD §2.3 and §5.1 into
production-ready ingestion code: a generic runner, a TaskGroup factory, a
SparkSubmitOperator wrapper, and one YAML config per Bronze table.

The LLD is the single source of truth. Never invent paths or tables — every
module path, config file, and table name must already be named in the LLD.
Use `mvp/src/patient_360/bronze/ingest.py` as a reference only; the output
must be config-driven, not hard-coded like the MVP.

## Workflow

### Phase 0: Upstream Gate

Read the latest LLD and verify `Status: Approved` (or `Updated - Pending Review`
if the user explicitly opts to proceed with a draft).

```bash
LATEST_LLD_DIR=$(ls -d chapter-5/inputs/lld/v* | sort -V | tail -1)
ls -t "$LATEST_LLD_DIR"/LLD-*.md | grep -v '\.bak$' | head -1
```

If not approved, stop and inform the user.

### Phase 1: Read Inputs

- **LLD markdown**: read §2.3 (Module Interface Contracts), §5.1 (Bronze task
  table), §3 (storage layout), §7 (configuration schema). The LLD §5.1 task
  table lists every table to generate a config for.
- **Config template**: `chapter-5/inputs/lld/v{N}/config/config-template.yaml`
  — source of truth for default storage paths, ingestion knobs (`ingestion_config_dir`,
  `ingestion_dq_rules_dir`, `ingestion_default_empty_input_behavior`,
  `ingestion_spark_submit_class`), and compute defaults.
- **STM workbook** (reference only): `chapter-5/inputs/stm/v{N}/STM-*.xlsx` →
  `Source-to-Bronze` tab. Column lists inform the per-table YAML schema block.
- **Existing patient_360 tree**: `chapter-5/patient_360/` — confirm target
  directories (`src/patient_360/bronze/`, `airflow/configs/`, `contracts/`,
  `dq_rules/`) exist before writing. Never create new top-level folders.
- **MVP reference**: `mvp/src/patient_360/bronze/ingest.py` — use as a coding-style
  reference only. Do NOT copy its hard-coded `TABLE_REGISTRY`; the chapter-5
  runner is config-driven.
- **DQS SE rules** (source of truth for `dq_rules/`): latest
  `chapter-5/inputs/dqs/v{N}/se-rules/se-rules-synthea-{table}.yaml` files.
  These are Spark Expectations-formatted rule sets (`product_id`, `dq_env`,
  `rules[]`) produced by the upstream DQ Engineer plugin. Never hand-write
  stubs when a matching SE file exists.

### Phase 2: Clarify

Use `AskUserQuestion` to confirm (only where the LLD is silent):

- Which Bronze tables to include on this run (all 13 from §5.1, or a subset).
- Whether existing files should be overwritten or skipped.
- Source read format when STM leaves it ambiguous (CSV vs JDBC vs Delta).

Skip the question entirely if the LLD/config-template gives an unambiguous
answer.

### Phase 3: Generate Code

Write three Python modules to `chapter-5/patient_360/src/patient_360/bronze/`:

1. **`ingestion_runner.py`** — reads a per-table YAML, enforces `StructType`
   (no schema inference), adds metadata columns (`ds`, `_ingested_at`,
   `_source_batch_id`), calls `se_runner` inline for row_dq + agg_dq, writes
   Delta **partitioned by `ds`** with `replaceWhere ds = '{ds}'`, respects the
   per-table `empty_input_behavior`. `_source_batch_id` is deterministic
   (`{table}:{ds}`) so reruns are idempotent. Accepts a Spark session + config
   path via CLI (`--config-path`, `--ds`, `--env`).
   **Delta wiring**: `_build_spark()` must call
   `delta.configure_spark_with_delta_pip(builder)` and set
   `spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog`
   so local `python -m` runs work without `PYSPARK_SUBMIT_ARGS`. SparkSubmit
   production runs will pick up the same JAR via `--packages`.
   **Metadata column names** match the DQS SE rules in
   `chapter-5/inputs/dqs/v{N}/se-rules/` — underscore prefix is required.
   **`TableConfig` dataclass** must include a `quarantine_path_template` field
   (default `warehouse/{env}/quarantine/bronze/{table}/` per LLD §7) with a
   `resolved_quarantine_path(env)` method. Load it from the per-table YAML
   `quarantine_path` key; fall back to the default if absent.
   **`run_inline_dq`** signature: `(df, cfg, env, dq_rules_dir)`. Define
   `_DQ_ENV_MAP = {"DEV": "DEV", "STAGING": "QA", "PROD": "PROD"}` (LLD §2.3)
   and map `env` before calling `run_dq`. Derive `dq_rules_dir` in `ingest()`
   from the config path: `config_path.parent.parent.parent / "dq_rules"`.
   **`se_action_if_failed`** from the per-table YAML is the fail-closed default
   for rules that omit their own `action_if_failed`; per-rule declarations take
   precedence (LLD §5.4).
2. **`ingestion_factory.py`** — `build_bronze_taskgroup(dag, configs_dir)`
   scans `airflow/configs/*.yml` at DAG parse time, returns an Airflow
   TaskGroup named `bronze_ingestion` with one `SparkSubmitOperator` per file.
3. **`spark_submit_wrapper.py`** — thin helper that builds the
   `SparkSubmitOperator` with memory/cores/executors pulled from the
   pipeline config (§7) and passes `--config-path` to the runner module named
   by `ingestion_spark_submit_class` in `config-template.yaml`.
   **Catalog**: `spark.sql.catalog.spark_catalog` must be
   `org.apache.spark.sql.delta.catalog.DeltaCatalog` — same as the runner.
   Do not use `UCSingleCatalog` here; that belongs to Silver/Gold UC-wired tasks.

4. **`src/patient_360/utils/se_runner.py`** — implement `run_dq(df, *, table,
   env, dq_rules_dir, action_if_failed, quarantine_path)`. This module is the
   implementation of the LLD §2.3 `se_runner.py` interface contract. Pin the
   following wiring details exactly — they are **not** in the LLD but are
   required by SE 2.10 for local non-Databricks runs:

   ```python
   from spark_expectations.core.expectations import SparkExpectations, WrappedDataFrameWriter
   from spark_expectations.rules.plugins.yaml_loader import SparkExpectationsYamlRuleLoaderImpl

   SE_STATS_TABLE = "bronze_se_stats"

   # Pre-register the stats Delta table in the current session catalog.
   # saveAsTable fails on a fresh SparkSession if the managed table already
   # exists on disk but is absent from the in-memory catalog.
   def _ensure_stats_table(spark):
       warehouse = spark.conf.get("spark.sql.warehouse.dir", "spark-warehouse")
       stats_path = Path(warehouse.lstrip("file:")) / SE_STATS_TABLE
       if stats_path.exists() and not spark.catalog.tableExists(SE_STATS_TABLE):
           spark.sql(f"CREATE TABLE IF NOT EXISTS {SE_STATS_TABLE} "
                     f"USING DELTA LOCATION '{stats_path}'")

   # Disable Kafka streaming stats and all notifications — required to avoid
   # Databricks secrets errors in local (non-Databricks) environments.
   user_conf = {
       "se.enable.error.table": True,
       "se.streaming.enable": False,
       "spark.expectations.notifications.alert.flag.disable": True,
       "spark.expectations.notifications.email.enabled": False,
       "spark.expectations.notifications.slack.enabled": False,
       "spark.expectations.notifications.teams.enabled": False,
       "spark.expectations.notifications.pagerduty.enabled": False,
       "spark.expectations.notifications.zoom.enabled": False,
   }
   ```

   Load rules via `SparkExpectationsYamlRuleLoaderImpl.load_rules(path, format="yaml",
   options={"dq_env": dq_env})`. Pass `_quarantine` path via
   `WrappedDataFrameWriter().mode("append").format("delta").option("path", _quarantine)`
   as both `target_and_error_table_writer` at construction and in `with_expectations`.
   Stats writer: `WrappedDataFrameWriter().mode("append").format("delta")`.

### Phase 4: Generate Per-Table Configs

For every Bronze table named in LLD §5.1, write
`chapter-5/patient_360/airflow/configs/{table}.yml` with this shape:

```yaml
table: {table}                       # e.g. patients
source:
  schema: {pipeline_source_schema}   # from config-template §general
  table:  {source_table}             # e.g. synthea.patients
  format: csv                         # or jdbc / delta — per STM
  path: data/raw/{table}.csv          # required for format: csv
schema_ref: contracts/{table}.yml     # StructType derived from contract
output_path: warehouse/{env}/bronze/synthea_{table}/   # table ROOT; ds is a Delta partition
metadata_columns:
  - ds
  - _ingested_at            # underscore prefix — matches DQS SE rules
  - _source_batch_id        # deterministic {table}:{ds}, required by SE rules
empty_input_behavior: write_empty     # or `fail` for the critical tables
                                       # (patients, encounters, allergies,
                                       # organizations, providers, payers)
dq_rules_table: {table}               # resolves to dq_rules/{table}.yml
se_action_if_failed: fail|drop|ignore # per LLD §5.1 DQ Check column; fail-closed default
                                       # for rules without their own action_if_failed
quarantine_path: warehouse/{env}/quarantine/bronze/{table}/  # LLD §7; SE drop target
timeout_minutes: 30
retries: 3
retry_delay_seconds: 60
```

> **Do not include `ds={ds}/` in `output_path`** — the runner writes Delta
> partitioned by `ds`, so the output directory is the table root. Embedding
> `ds=` in the path creates a separate Delta table per partition and breaks
> `replaceWhere`.

Use the exact empty_input_behavior override from LLD §5.1 for the six critical
tables. Do not change thresholds or task IDs.

Do NOT rewrite `contracts/{table}.yml` here — contracts are owned by the Data
Modeler. If a contract is missing, flag it as a prerequisite the user must
resolve (offer to generate it from `docs/ERD.mmd` as a fallback).

For `dq_rules/{table}.yml`, sync from the DQS SE rules:

```bash
LATEST_DQS_DIR=$(ls -d chapter-5/inputs/dqs/v* | sort -V | tail -1)
cp "$LATEST_DQS_DIR/se-rules/se-rules-synthea-{table}.yaml" \
   chapter-5/patient_360/dq_rules/{table}.yml
```

Do this for every Bronze table in LLD §5.1. If a table has no matching SE
rule file, stop and ask the DQ Engineer to produce one — do NOT hand-write a
stub, because runtime loads expect the full SE schema (`product_id`,
`dq_env`, `rules[]`).

### Phase 4.5: Runtime Dependencies

The ingestion runner imports `pyspark`, writes Delta, and loads Spark
Expectations rules; the factory uses `SparkSubmitOperator`. Ensure
`chapter-5/patient_360/pyproject.toml` declares each of these — add any
that are missing:

| Section | Required entry |
|---------|---------------|
| `[project].dependencies` | `pyspark[sql]>=4.0` |
| `[project].dependencies` | `delta-spark>=4.0` |
| `[project].dependencies` | `spark-expectations>=2.6.0` |
| `[project.optional-dependencies].dev` | `apache-airflow-providers-apache-spark>=4.0` |
| `[project.optional-dependencies].dev` | `pytest-mock>=3.12` |

If the LLD §2.1 does not list these (current LLD v1 omits them), note the
drift in the change-set report so the Technical Lead can reconcile on the
next LLD revision.

### Phase 4.6: Generate Tests

Write three test modules under `chapter-5/patient_360/tests/bronze/` so the
generated code is exercised in CI. Use `pytest.importorskip("pyspark")` so
Spark-dependent tests skip cleanly when pyspark is not installed.

| Test module | Covers |
|-------------|--------|
| `test_ingestion_runner.py` | `load_table_config` (happy path + each `IngestionConfigError` branch), `_parse_spark_type` (every primitive + decimal + unsupported), `load_struct_type`, `add_metadata_columns` (asserts `_source_batch_id == "{table}:{ds}"` and that `_ingested_at` is present), the `fail` vs `write_empty` branches of `ingest()`, `resolved_quarantine_path` (default template + YAML override), `_DQ_ENV_MAP` (parametrized: DEV→DEV, STAGING→QA, PROD→PROD; exhaustiveness check for the three runtime envs). Requires pyspark — import-skip otherwise. |
| `test_per_table_configs.py` | Parametrized sweep over `airflow/configs/*.yml`: required keys present, `table:` matches filename, referenced `contracts/{t}.yml` + `dq_rules/{t}.yml` exist, critical tables use `fail`, SE rules declare `dq_env.{DEV,QA,PROD}`, exactly the 13 tables in LLD §5.1 are present. Pure YAML — no Spark. |
| `test_validate_ingestion.py` | Shells out to `validate-ingestion/scripts/validate_ingestion.py` against the real project (expect `Result: PASS`) and against a scaffolded project with only pyyaml declared (expect CRITICAL on pyspark / delta-spark / spark-expectations). |

Do not skip this phase — untested ingestion code is a CRITICAL finding in
`validate-ingestion`.

### Phase 5: Validate

Invoke `/developer-plugin:validate-ingestion` on the generated files. Fix any
CRITICAL findings before reporting completion. Report WARNING/INFO findings to
the user without blocking.

## Output Summary

At the end, print a table: `Module/Config | Path | Action (created|updated|skipped)`
so the user can see exactly what changed.
