---
name: create-ingestion
description: >
  Generates the Bronze config-driven ingestion framework from the approved LLD
  or from a specific Scrum story. Can run in two modes:
  - Full mode: generates the entire framework from an LLD file path.
  - Story mode: generates only the deliverables for a single story (e.g. STORY-02-002),
    validates against that story's acceptance criteria, and checks dependencies.
  Also known as: bronze ingestion scaffolding, ingestion-runner generation,
  per-table config generation.
  Input formats: LLD markdown (inputs/lld/v{N}/LLD-*.md) OR story ID (STORY-NN-NNN).
  Output format: Python modules + YAML configs written under the project root.
  Use when the user asks to:
  - Create, generate, or scaffold the Bronze ingestion code
  - Build the ingestion runner / factory / SparkSubmit wrapper
  - Generate per-table ingestion configs from the LLD
  - "Write the ingestion framework from the LLD"
  - "Implement story STORY-02-002" or "implement story 02 of epic 02"
argument-hint: "[lld-path | STORY-NN-NNN]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion, Skill
context: fork
---

# Create Bronze Ingestion Framework

You are a senior Data Engineer. Your job is to translate LLD §2.3 and §5.1 into
production-ready ingestion code: a generic runner, a TaskGroup factory, a
SparkSubmitOperator wrapper, and one YAML config per Bronze table.

The LLD is the single source of truth. Never invent paths or tables — every
module path, config file, and table name must already be named in the LLD.
the output must be config-driven, not hard-coded.

## Workspace Discovery

Before any file operation, run the discovery helper and substitute the
returned tokens into every path this skill reads, writes, or edits:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py --mode discover
```

The JSON output supplies `{workspace_root}`, `{project_root}`,
`{project_name}`, `{stories_dir}`, and `{learnings_queue}`. The plugin is
project-agnostic — never hardcode project or chapter names in edits.

## Coding Patterns & Libraries Handbook

Before any ingestion code is emitted, load the latest coding-patterns handbook:

```bash
PATTERNS_DIR=$(ls -d "{workspace_root}/inputs/code/v"* 2>/dev/null | sort -V | tail -1)
if [ -z "$PATTERNS_DIR" ] || [ ! -d "$PATTERNS_DIR" ]; then
  echo "CRITICAL: inputs/code/v*/ not found. Run /developer-plugin:refresh-libraries to initialize the library cache."
  exit 1
fi
LIBRARIES_FILE="$PATTERNS_DIR/LIBRARIES.md"
```

**Required pattern docs for this skill:**

- `$PATTERNS_DIR/bronze-ingestion-pattern.md` — registry → factory → runner shape
- `$PATTERNS_DIR/spark-expectations-pattern.md` — SE YAML rule shape + runner wrapper
- `$PATTERNS_DIR/naming-conventions.md` — audit columns, table names
- `$PATTERNS_DIR/logging-error-handling.md` — module logger + fail-fast
- `$PATTERNS_DIR/LIBRARIES.md` — pinned PySpark / Delta / SE versions

### Library freshness check

```bash
LAST_VERIFIED=$(grep '^last_verified:' "$LIBRARIES_FILE" | awk '{print $2}')
TODAY=$(date -u +%Y-%m-%d)
AGE_DAYS=$(python3 -c "from datetime import date; print((date.fromisoformat('$TODAY') - date.fromisoformat('$LAST_VERIFIED')).days")
```

If `AGE_DAYS > 30`, pause and call **AskUserQuestion** with options `Refresh now` / `Proceed with cached versions` / `Cancel`. On Refresh, invoke `/developer-plugin:refresh-libraries` then resume.

### References trailer (in output)

Emit a `### References` section citing consumed pattern docs + LIBRARIES.md vintage. Add a stale-cache warning if the user opted to proceed with cached versions.

## Story → Deliverable Map

Use this map in story mode to determine what to generate and what to skip.

| Story ID     | Title                              | Deliverables to generate                                                      |
|--------------|------------------------------------|-------------------------------------------------------------------------------|
| STORY-02-001 | Per-Table YAML Ingestion Configs   | `airflow/configs/{table}.yml` × 13, `dq_rules/*.yml` sync                    |
| STORY-02-002 | Generic Ingestion Runner           | `src/{project_name}/bronze/ingestion_runner.py`                               |
| STORY-02-003 | SparkSubmitOperator Wrapper        | `src/{project_name}/bronze/spark_submit_wrapper.py`                           |
| STORY-02-004 | TaskGroup Factory                  | `src/{project_name}/bronze/ingestion_factory.py`                              |
| STORY-02-006 | SE Runner + Bronze DQ Rules        | `src/{project_name}/utils/se_runner.py`, `dq_rules/*.yml` sync               |
| STORY-02-009 | Unit Tests for Bronze              | `tests/bronze/test_ingestion_runner.py`, `tests/bronze/test_per_table_configs.py` |
| STORY-02-010 | Integration / Validate Tests       | `tests/bronze/test_validate_ingestion.py`                                     |

Stories not in this map belong to a different epic or are not implemented by this skill.

## Workflow

### Phase 0: Detect Input Mode and Upstream Gate

**Step 1 — Detect mode from the argument:**

- If the argument matches the pattern `STORY-NN-NNN` (e.g. `STORY-02-002`) or the user
  says something like "implement story 2 of epic 2" → **Story mode**. Normalize to
  `STORY-{EPIC:02d}-{NUM:03d}` format (e.g. "story 2 of epic 2" → `STORY-02-002`).
- If the argument is a file path (ends in `.md`) → **Full mode**. Skip to the LLD gate.
- If no argument is given → ask the user: "Provide an LLD file path for full generation,
  or a story ID (e.g. STORY-02-002) to implement a single story."

**Step 2 — Story mode: resolve and read the story file:**

```bash
STORY_ID="STORY-02-002"   # substitute actual ID
EPIC_NUM=$(echo "$STORY_ID" | cut -d- -f2)
STORY_FILE=$(ls {stories_dir}/v*/EPIC-${EPIC_NUM}-*/STORY-${STORY_ID}*.md \
             {stories_dir}/v*/${STORY_ID}*.md 2>/dev/null | head -1)
echo "$STORY_FILE"
```

Read the story file and extract:
- **Title** and **Story Points**
- **Sprint** number
- **Acceptance Criteria** (the numbered AC list)
- **Dependencies** (`Depends On:` lines)

If the story file is not found, stop and tell the user which path was searched.
If the story ID is not in the Story → Deliverable Map above, stop and tell the user
this skill does not implement that story (it may belong to a different skill).

**Step 3 — Story mode: dependency check:**

For each story listed under `Depends On:`, verify its deliverables exist on disk
using the map above. For example, STORY-02-002 depends on STORY-02-001
(configs must exist). If any dependency is unmet, stop and list what is missing:

```
Dependency check failed:
  STORY-02-002 depends on STORY-02-001
  Missing: {project_root}/airflow/configs/ (0 yml files found, 13 required)
Complete STORY-02-001 first, then re-run.
```

**Step 4 — Set GENERATION_SCOPE:**

In story mode, set `GENERATION_SCOPE` to only the deliverables for that story ID
per the map above. All Phase 3/4 generation blocks check this scope and skip
anything not in it.

In full mode, `GENERATION_SCOPE = all`.

**Step 5 — LLD gate (both modes):**

Read the latest LLD and verify `Status: Approved` (or `Updated - Pending Review`
if the user explicitly opts to proceed with a draft).

```bash
LATEST_LLD_DIR=$(ls -d {workspace_root}/inputs/lld/v* | sort -V | tail -1)
ls -t "$LATEST_LLD_DIR"/LLD-*.md | grep -v '\.bak$' | head -1
```

If not approved, stop and inform the user.

### Phase 1: Read Inputs

- **LLD markdown**: read §2.3 (Module Interface Contracts), §5.1 (Bronze task
  table), §3 (storage layout), §7 (configuration schema). The LLD §5.1 task
  table lists every table to generate a config for.
- **Config template**: `{workspace_root}/inputs/lld/v{N}/config/config-template.yaml`
  — source of truth for default storage paths, ingestion knobs (`ingestion_config_dir`,
  `ingestion_dq_rules_dir`, `ingestion_default_empty_input_behavior`,
  `ingestion_spark_submit_class`), and compute defaults.
- **STM workbook** (reference only): `{workspace_root}/inputs/stm/v{N}/STM-*.xlsx` →
  `Source-to-Bronze` tab. Column lists inform the per-table YAML schema block.
- **Existing project tree**: `{project_root}/` — confirm target
  directories (`src/{project_name}/bronze/`, `airflow/configs/`, `contracts/`,
  `dq_rules/`) exist before writing. Never create new top-level folders.
- **MVP reference**: `mvp/src/patient_360/bronze/ingest.py` — use as a coding-style
  reference only. Do NOT copy its hard-coded `TABLE_REGISTRY`; the generated
  runner is config-driven.
- **DQS SE rules** (source of truth for `dq_rules/`): latest
  `{workspace_root}/inputs/dqs/v{N}/se-rules/se-rules-synthea-{table}.yaml` files.
  These are Spark Expectations-formatted rule sets (`product_id`, `dq_env`,
  `rules[]`) produced by the upstream DQ Engineer plugin. Never hand-write
  stubs when a matching SE file exists.

### Phase 2: Clarify

**Story mode** — show a scope summary before generating anything:

```
Story:       STORY-02-002 — Generic Ingestion Runner (5 pts, Sprint 3)
Deliverable: {project_root}/src/{project_name}/bronze/ingestion_runner.py
Depends on:  ✓ STORY-02-001 (13 configs found)
LLD status:  Approved

Acceptance Criteria:
  1. Runner reads per-table YAML config
  2. Enforces StructType schema (no inference)
  3. Adds metadata columns: ds, _ingested_at, _source_batch_id
  4. Writes Delta partitioned by ds with replaceWhere ds = '{ds}'
  5. Respects empty_input_behavior (fail raises, write_empty proceeds)
```

Then use `AskUserQuestion` to ask: "Generate this story's deliverable now?
If a file already exists, overwrite or skip?"

**Full mode** — use `AskUserQuestion` to confirm (only where the LLD is silent):

- Which Bronze tables to include on this run (all 13 from §5.1, or a subset).
- Whether existing files should be overwritten or skipped.
- Source read format when STM leaves it ambiguous (CSV vs JDBC vs Delta).

Skip any question if the LLD/config-template gives an unambiguous answer.

### Phase 3: Generate Code

> **Scope gate**: In story mode, generate only the module(s) for the active story
> per the Story → Deliverable Map. Skip all others — do not create empty stubs.

Write Python modules to `{project_root}/src/{project_name}/bronze/`
(and `utils/` for se_runner). Only write a module if it is in `GENERATION_SCOPE`:

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
   `{workspace_root}/inputs/dqs/v{N}/se-rules/` — underscore prefix is required.
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

4. **`src/{project_name}/utils/se_runner.py`** — implement `run_dq(df, *, table,
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

> **Scope gate**: Skip this phase entirely in story mode unless `GENERATION_SCOPE`
> includes `configs` (STORY-02-001) or `dq_rules` (STORY-02-006).

For every Bronze table named in LLD §5.1, write
`{project_root}/airflow/configs/{table}.yml` with this shape:

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
LATEST_DQS_DIR=$(ls -d {workspace_root}/inputs/dqs/v* | sort -V | tail -1)
cp "$LATEST_DQS_DIR/se-rules/se-rules-synthea-{table}.yaml" \
   {project_root}/dq_rules/{table}.yml
```

Do this for every Bronze table in LLD §5.1. If a table has no matching SE
rule file, stop and ask the DQ Engineer to produce one — do NOT hand-write a
stub, because runtime loads expect the full SE schema (`product_id`,
`dq_env`, `rules[]`).

### Phase 4.5: Runtime Dependencies

> **Scope gate**: Always run this check — pyproject.toml deps are required regardless
> of which story is being implemented.

The ingestion runner imports `pyspark`, writes Delta, and loads Spark
Expectations rules; the factory uses `SparkSubmitOperator`. Ensure
`{project_root}/pyproject.toml` declares each of these — add any
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

> **Scope gate**: In story mode, generate only the test module(s) for the active story
> per the Story → Deliverable Map. STORY-02-009 → `test_ingestion_runner.py` +
> `test_per_table_configs.py`. STORY-02-010 → `test_validate_ingestion.py`.
> Other stories do not trigger new test files (their code is covered by existing tests).

Write three test modules under `{project_root}/tests/bronze/` so the
generated code is exercised in CI. Use `pytest.importorskip("pyspark")` so
Spark-dependent tests skip cleanly when pyspark is not installed.

| Test module | Covers |
|-------------|--------|
| `test_ingestion_runner.py` | `load_table_config` (happy path + each `IngestionConfigError` branch), `_parse_spark_type` (every primitive + decimal + unsupported), `load_struct_type`, `add_metadata_columns` (asserts `_source_batch_id == "{table}:{ds}"` and that `_ingested_at` is present), the `fail` vs `write_empty` branches of `ingest()`, `resolved_quarantine_path` (default template + YAML override), `_DQ_ENV_MAP` (parametrized: DEV→DEV, STAGING→QA, PROD→PROD; exhaustiveness check for the three runtime envs). Requires pyspark — import-skip otherwise. |
| `test_per_table_configs.py` | Parametrized sweep over `{project_root}/airflow/configs/*.yml`: required keys present, `table:` matches filename, referenced `contracts/{t}.yml` + `dq_rules/{t}.yml` exist, critical tables use `fail`, SE rules declare `dq_env.{DEV,QA,PROD}`, exactly the 13 tables in LLD §5.1 are present. Pure YAML — no Spark. |
| `test_validate_ingestion.py` | Shells out to `validate-ingestion/scripts/validate_ingestion.py` against the real project (expect `Result: PASS`) and against a scaffolded project with only pyyaml declared (expect CRITICAL on pyspark / delta-spark / spark-expectations). |

Do not skip this phase — untested ingestion code is a CRITICAL finding in
`validate-ingestion`.

### Phase 5: Validate

Invoke `/developer-plugin:validate-ingestion` on the generated files. Fix any
CRITICAL findings before reporting completion. Report WARNING/INFO findings to
the user without blocking.

**Story mode only — Acceptance Criteria verification:**

After the validator passes, check each AC from the story file against the generated
code and report a pass/fail table. Use `Grep` to verify structural presence.
Examples for common ACs:

| Acceptance Criterion | Check |
|----------------------|-------|
| "Runner reads per-table YAML config" | `load_table_config` function exists in `ingestion_runner.py` |
| "Enforces StructType schema (no inference)" | `load_struct_type` + no `inferSchema` in runner |
| "Metadata columns ds, _ingested_at, _source_batch_id" | `add_metadata_columns` present; `_source_batch_id` in its body |
| "replaceWhere ds = '{ds}'" | `replaceWhere` string in `write_delta()` |
| "empty_input_behavior respected" | `EmptyInputError` class + `fail` branch in `ingest()` |
| "SE runner loads YAML rules" | `SparkExpectationsYamlRuleLoaderImpl` in `se_runner.py` |
| "action_if_failed: fail\|drop\|ignore" | validation in `load_table_config` checking those three values |
| "Critical tables use fail" | `test_per_table_configs.py::test_critical_tables_use_fail_behavior` or direct YAML check |

Print:
```
Story STORY-02-002 — Acceptance Criteria:
  AC 1: Runner reads per-table YAML config ................... PASS
  AC 2: Enforces StructType (no schema inference) ............ PASS
  AC 3: Metadata columns ds, _ingested_at, _source_batch_id .. PASS
  AC 4: replaceWhere ds = '{ds}' Delta write ................. PASS
  AC 5: empty_input_behavior respected ....................... PASS
  Result: 5/5 AC PASS
```

If any AC fails (code structure is absent), report it as a CRITICAL and fix before
declaring the story done.

## Output Summary

At the end, print a table: `Module/Config | Path | Action (created|updated|skipped)`
so the user can see exactly what changed.

In story mode, prefix the table with the story ID and AC result summary:
```
Story: STORY-02-002 — Generic Ingestion Runner | Result: 5/5 AC PASS

Module/Config             | Path                                              | Action
ingestion_runner.py       | src/{project_name}/bronze/ingestion_runner.py     | created
```
