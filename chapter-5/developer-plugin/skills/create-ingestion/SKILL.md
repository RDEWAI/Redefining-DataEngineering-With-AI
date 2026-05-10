---
name: create-ingestion
description: >
  Generates the Bronze config-driven ingestion layer from the approved LLD,
  DMS, STM, DQS, and a given story. Modes:
  - Story mode: read a STORY-NN-NNN, extract backtick-quoted deliverables
    from its Acceptance Criteria, generate only those that fall under this
    skill's domain of ownership. ROUTE-OUT for others.
  - Full mode: process every un-Done story classified as `ingestion`,
    topo-sorted by Depends On.
  Project-agnostic: the table list, critical-table designation, per-table
  DQ rule filenames, and runner module names are ALL read from the current
  run's LLD / DMS / STM / DQS / stories at runtime. No project identifiers
  or story IDs are hardcoded.
  Use when the user asks to:
  - Generate or update Bronze ingestion code for a story
  - Build the ingestion runner / factory / SparkSubmit wrapper
  - Generate per-table ingestion configs
argument-hint: "[STORY-NN-NNN | 'full']"
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

## Domain of Ownership

This skill owns the project's **Bronze ingestion layer** — config-driven
code that reads raw sources and writes versioned Bronze Delta tables.
Specifically:

| Owned path pattern                                | What lives here                                                      |
|---------------------------------------------------|----------------------------------------------------------------------|
| `src/<project_name>/bronze/**`                    | Ingestion runner, factory, SparkSubmit wrapper, reconciliation task, DLQ writer — whatever LLD §2.3 + §5.1 name |
| `airflow/configs/**`                              | One YAML per Bronze table from LLD §5.1                              |
| `dq_rules/**`                                     | Synced from latest `{workspace_root}/../chapter-4/outputs/dqs/v*/se-rules/*.yaml` |
| `contracts/dq/**`                                 | Per-table DQ thresholds from DQS §5                                  |
| `ddl/liquibase/changelogs/**`                     | Bronze DDL from DMS §2                                               |
| `tests/bronze/**`                                 | Bronze unit + integration tests                                      |

It does **not** own: `src/<project_name>/utils/**` (create-scaffold),
`src/<project_name>/{silver,gold}/**` (future layer skills),
`airflow/dags/**` (create-dag), `contracts/*.yml` except `contracts/dq/**`
(create-scaffold; StructType contracts), `.github/workflows/**` +
`_infra/{ci,cd}/**` (create-pipeline).

## Deliverable Resolution Protocol

**No Story → Deliverable Map is hardcoded.** The current run's story file
is the single source of truth for which paths to emit.

1. **Story mode** (`STORY-NN-NNN`): read the story file. Parse Acceptance
   Criteria. For each backtick-quoted path or identifier:
   - Path matches an owned pattern above → generate it.
   - Path matches another skill's domain → print
     `ROUTE-TO: create-<kind> <path>` and exit cleanly.
   - Identifier (no path) → resolve via LLD §2.3 interface contracts; if
     the LLD places it under this skill's domain, generate; else ROUTE-OUT.

2. **Full / auto mode**: enumerate every un-Done story whose classifier
   kind is `ingestion` (`status_rollup.py --mode classify`), topo-sorted
   by `Depends On`, and run each through Story mode.

## Source-of-Truth Reads at Runtime

Project-specific facts are read each run — never hardcoded.

| Fact needed                          | Where to read                                                            |
|--------------------------------------|--------------------------------------------------------------------------|
| Bronze table list                    | LLD §5.1 (`Source → Bronze` task table)                                  |
| Source schema/format per table       | STM `Source-to-Bronze` tab                                               |
| Per-table `empty_input_behavior`     | LLD §5.1 column — the tables flagged `fail` ARE the critical tables     |
| Per-table SE rule file               | `ls {workspace_root}/../chapter-4/outputs/dqs/v*/se-rules/*.yaml` — discover filenames; do NOT assume any prefix like `se-rules-<domain>-<table>.yaml` |
| Per-table DQ thresholds              | DQS §5                                                                   |
| Runner/factory/wrapper module names  | LLD §2.3 Module Interface Contracts                                      |
| Compute knobs (shuffle, cores, mem)  | `config-template.yaml` + LLD §6.1/§6.3                                   |
| DAG name (for integration tests)     | LLD §4.1                                                                 |

## Workflow

### Phase 0: Detect Input Mode and Upstream Gate

**FIRST — resolve the effective argument. Do this before any other Phase 0 step.**

The conversational argument is NOT the only source of truth — a parent
orchestrator (e.g. `implement-stories`) may dispatch this skill via the
`Skill` tool and the forwarded argument may not reach this fork. Check
these sources in order; stop at the first non-empty hit:

1. `$SKILL_ARG` environment variable.
2. `{workspace_root}/.skill-arg` file — read its contents, then delete
   the file so it is consumed at most once.
3. The conversational argument supplied to the skill.
4. **Auto-mode default** — if `$CLAUDE_AUTO_MODE=1` OR
   `{workspace_root}/.auto-mode` exists → use the skill's full-mode default
   (**full LLD generation, no story ID**).
5. Only if ALL four above are empty, ask the user via `AskUserQuestion`.

You MUST NOT ask the user until sources 1–4 have been checked. Auto-mode
detection is a hard override — if the marker exists, proceed with the
full-mode default and do not ask.

Mechanical resolver (copy-paste; `$USER_ARG` is the conversational arg):

```bash
resolve_skill_arg() {
  if [ -n "$SKILL_ARG" ]; then echo "$SKILL_ARG"; return; fi
  if [ -f "{workspace_root}/.skill-arg" ]; then
    cat "{workspace_root}/.skill-arg"; rm -f "{workspace_root}/.skill-arg"; return
  fi
  # caller supplies conversational arg as $1
  if [ -n "$1" ]; then echo "$1"; return; fi
  if [ "$CLAUDE_AUTO_MODE" = "1" ] || [ -f "{workspace_root}/.auto-mode" ]; then
    echo "__AUTO__"; return
  fi
  echo ""
}
RESOLVED_ARG=$(resolve_skill_arg "$USER_ARG")
```

If `$RESOLVED_ARG` is `__AUTO__` or matches the full-mode pattern (empty or
an `.md` path), proceed without asking — treat it as **full mode**.

**Step 1 — Detect mode from the resolved argument:**

- If the argument matches the pattern `STORY-NN-NNN` (e.g. `STORY-02-002`) or the user
  says something like "implement story 2 of epic 2" → **Story mode**. Normalize to
  `STORY-{EPIC:02d}-{NUM:03d}` format (e.g. "story 2 of epic 2" → `STORY-02-002`).
- If the argument is a file path (ends in `.md`) → **Full mode**. Skip to the LLD gate.
- If `$RESOLVED_ARG` is `__AUTO__` (auto-mode default) → **Full mode**. Skip to the LLD gate.

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

Verify the story classifies to `ingestion` (run
`status_rollup.py --mode classify --story STORY-NN-NNN`). If the returned
`skill_kind` is anything other than `ingestion`, emit
`ROUTE-TO: create-<kind>` and exit cleanly so the orchestrator can dispatch
the correct skill. Do NOT raise an error.

If the story classifies to `ingestion` but is NOT listed in the Story →
Deliverable Map above, read its Acceptance Criteria at runtime and generate
every backtick-quoted deliverable path. The classifier is the gate, not the
map.

**Step 3 — Story mode: dependency check:**

For each story listed under `Depends On:`, open its story file and verify
each backtick-quoted deliverable path from **its** ACs exists on disk. If
any dependency's deliverables are missing, stop and list what is missing:

```
Dependency check failed:
  STORY-NN-NNN depends on STORY-NN-MMM
  Missing (declared in STORY-NN-MMM AC): {project_root}/<path>
Complete STORY-NN-MMM first, then re-run.
```

**Step 4 — Set GENERATION_SCOPE:**

In story mode, set `GENERATION_SCOPE` to the subset of candidate
deliverables from the current story's AC that match this skill's owned
path patterns. Phase 3/4 generation blocks check this scope and skip
anything not in it; anything owned by another skill emits ROUTE-TO.

In full mode, `GENERATION_SCOPE = all`.

**Step 5 — LLD gate (both modes):**

Read the latest LLD and verify `Status: Approved` (or `Updated - Pending Review`
if the user explicitly opts to proceed with a draft).

```bash
# Prefer pinned versions from the dev-lock (written by implement-stories).
# Falls through to the legacy `ls … | tail -1` pattern when no lockfile.
eval "$(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/resolve_versions.py --export)"
LATEST_LLD_DIR="${LATEST_LLD_DIR:-$(ls -d {workspace_root}/../chapter-4/outputs/lld/v* | sort -V | tail -1)}"
ls -t "$LATEST_LLD_DIR"/LLD-*.md | grep -v '\.bak$' | head -1
```

If not approved, stop and inform the user.

### Phase 0.5: Path Scoping (optional, set by the orchestrator)

If `{workspace_root}/.skill-paths` exists, read it — each non-empty line
is a path in scope for THIS invocation. Process ONLY those paths; ignore
other paths the story AC names (they belong to other skills and the
orchestrator will dispatch them separately). Delete `.skill-paths` after
consuming it. When the file is absent (direct human invocation), fall
through to the standard phases that scan every candidate deliverable
against the Domain of Ownership.

### Phase 1: Read Inputs

- **LLD markdown**: read §2.3 (Module Interface Contracts), §5.1 (Bronze task
  table), §3 (storage layout), §7 (configuration schema). The LLD §5.1 task
  table lists every table to generate a config for.
- **Config template**: `{workspace_root}/../chapter-4/outputs/lld/v{N}/config/config-template.yaml`
  — source of truth for default storage paths, ingestion knobs (`ingestion_config_dir`,
  `ingestion_dq_rules_dir`, `ingestion_default_empty_input_behavior`,
  `ingestion_spark_submit_class`), and compute defaults.
- **STM workbook** (reference only): `{workspace_root}/../chapter-4/outputs/stm/v{N}/STM-*.xlsx` →
  `Source-to-Bronze` tab. Column lists inform the per-table YAML schema block.
- **Existing project tree**: `{project_root}/` — confirm target
  directories (`src/{project_name}/bronze/`, `airflow/configs/`, `contracts/`,
  `dq_rules/`) exist before writing. Never create new top-level folders.
- **Pattern handbook**: the canonical bronze-ingestion coding style lives
  in `$PATTERNS_DIR/bronze-ingestion-pattern.md`. Follow that; do NOT copy
  from any other example that might hard-code a `TABLE_REGISTRY` — the
  generated runner must be config-driven from `airflow/configs/*.yml`.
- **DQS SE rules** (source of truth for `dq_rules/`): discover files under
  `{workspace_root}/../chapter-4/outputs/dqs/v{N}/se-rules/*.yaml`. Match each file to a
  Bronze table by reading the file's `product_id` (or by filename stem, as
  a fallback). Do NOT assume any filename prefix like
  `se-rules-<domain>-<table>.yaml` — that naming is project-specific.
  These are Spark Expectations-formatted rule sets (`product_id`,
  `dq_env`, `rules[]`) produced by the upstream DQ Engineer plugin. Never
  hand-write stubs when a matching SE file exists.

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
   `{workspace_root}/../chapter-4/outputs/dqs/v{N}/se-rules/` — underscore prefix is required.
   **`TableConfig` dataclass** must include a `quarantine_path_template` field
   (default `warehouse/{env}/quarantine/bronze/{table}/` per LLD §7) with a
   `resolved_quarantine_path(env)` method. Load it from the per-table YAML
   `quarantine_path` key; fall back to the default if absent.
   **`run_inline_dq`** signature: `(df, cfg, env, dq_rules_dir)`. Define
   `_DQ_ENV_MAP = {"DEV": "DEV", "STAGING": "QA", "PROD": "PROD"}` (LLD §2.3)
   and map `env` before calling `run_dq`. **Derive `dq_rules_dir` in this order**
   (matches the `AIRFLOW_CONFIGS_DIR` pattern):
   1. Explicit kwarg passed by the caller.
   2. `os.environ.get("DQ_RULES_DIR")` — the canonical container path injected
      by the cookiecutter `docker-compose.yml`.
   3. Walk up from the config path: `config_path.parent.parent.parent / "dq_rules"`
      — only as a fallback for non-container runs (local pytest, etc.).
   Never hardcode `/opt/dq_rules` (relative or absolute) — spokane shipped a
   duplicate `dq_rules` bind mount because some generated code referenced
   that literal. The env var is the single resolution mechanism.
   **`se_action_if_failed`** from the per-table YAML is the fail-closed default
   for rules that omit their own `action_if_failed`; per-rule declarations take
   precedence (LLD §5.4).
**CRITICAL — UC-managed writes for Bronze (LLD §2.3 / Decision 12).**

The Bronze runner MUST land tables in Unity Catalog at write time using
`UCSingleCatalog` + `saveAsTable("unity.bronze.<table>")`. Path-based Delta
writes (`df.write.format("delta").save("/tmp/...")`) leave UC empty until
a manual `docker cp` + external-table registration — that's the gap spokane
hit on its first green run. The skill's Phase 3 generator MUST emit the
Spark session wiring shown in `inputs/code/v1/scripts/ingestion_runner.py.snippet`:

- `spark.sql.catalog.unity = io.unitycatalog.spark.UCSingleCatalog`
- `spark.sql.catalog.unity.uri = os.environ["UC_URI"]`
- `spark.sql.defaultCatalog = unity`
- Plus the Delta extensions / Delta catalog config.

Then the write becomes `df.write.mode(...).partitionBy("ds").option("replaceWhere", ...).saveAsTable(f"unity.bronze.{table}")`.

The validator (`validate-dag UC-WIRING-001`) rejects any generated
`src/**/bronze/**.py` file that calls `.save("/tmp/`, `.save("file://`,
or `.save(<warehouse_path_var>)` instead of `saveAsTable`. The
`tests/test_uc_wiring.py` regression scan blocks the same pattern from
being introduced into snippets.

2. **`ingestion_factory.py`** — `build_bronze_taskgroup(dag, configs_dir=None)`
   scans `<configs_dir>/*.yml` at DAG parse time, returns an Airflow
   TaskGroup named `bronze_ingestion` with one `SparkSubmitOperator` per file.
   **CRITICAL — env-driven path resolution.** The factory MUST resolve
   `configs_dir` in this order: explicit arg → `os.environ.get("AIRFLOW_CONFIGS_DIR")`
   → `/opt/airflow/configs`. Never hardcode `airflow/configs` (relative)
   or any other relative path — when Airflow runs from `/opt/airflow/` in
   the cookiecutter container, relative paths don't resolve. The
   `validate-dag DAG-PATHS-002` rule rejects DAG files containing the
   literal string `configs_dir="airflow/configs"`. The reconciliation
   runner under `airflow/jobs/run_<layer>_recon.py` follows the same
   pattern via `--configs-dir` argparse with the same default chain
   (see `inputs/code/v1/scripts/reconciliation.py.snippet`).
3. **`spark_submit_wrapper.py`** — thin helper that builds the
   `SparkSubmitOperator` with memory/cores/executors pulled from the
   pipeline config (§7) and passes `--config-path` to the runner module named
   by `ingestion_spark_submit_class` in `config-template.yaml`.
   **Catalog**: `spark.sql.catalog.spark_catalog` must be
   `org.apache.spark.sql.delta.catalog.DeltaCatalog` — same as the runner.
   Do not use `UCSingleCatalog` here; that belongs to Silver/Gold UC-wired tasks.

4. **`src/{project_name}/utils/se_runner.py`** — implement `run_dq(df, *, table,
   env, dq_rules_dir, action_if_failed, quarantine_path)`. This module is the
   implementation of the LLD §2.3 `se_runner.py` interface contract.

   **Version requirement (CRITICAL):** these imports require
   `spark-expectations >= 2.10.0`. The YAML rule loader and
   `WrappedDataFrameWriter` were added in v2.10.0
   (https://github.com/Nike-Inc/spark-expectations/releases/tag/v2.10.0). If
   the LIBRARIES.md catalogue ever pins SE below 2.10 these imports raise
   `ModuleNotFoundError: No module named 'spark_expectations.rules'` at
   runtime — the developer plugin's `validate-dag SE-IMPORTS-001` rule and
   `tests/test_se_runner_imports.py` regression test gate against that
   downgrade. Pin the wiring details exactly:

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

> **Scope gate**: Skip this phase unless a deliverable under
> `airflow/configs/**`, `dq_rules/**`, `contracts/dq/**`, or
> `ddl/liquibase/changelogs/**` was extracted from the story's AC.

For every Bronze table enumerated in LLD §5.1 (count and names read at
runtime — never hardcoded), write
`{project_root}/airflow/configs/<table>.yml` with this shape (substitute
`<table>` and replace other bracketed placeholders with values read from
LLD / STM / `config-template.yaml`):

```yaml
table: <table>                       # LLD §5.1 table name
source:
  schema: <pipeline_source_schema>   # from config-template §general
  table:  <source_table>             # STM Source-to-Bronze tab
  format: <csv|jdbc|delta>           # STM Source-to-Bronze tab
  path: <path-if-file-format>        # STM Source-to-Bronze tab
schema_ref: contracts/<table>.yml
output_path: warehouse/<env>/bronze/<bronze_table_name>/   # table ROOT — see note
metadata_columns:
  - ds
  - _ingested_at
  - _source_batch_id
empty_input_behavior: <fail|write_empty>  # from LLD §5.1 Empty Input column
dq_rules_table: <table>
se_action_if_failed: <fail|drop|ignore>   # from LLD §5.1 DQ Check column
quarantine_path: warehouse/<env>/quarantine/bronze/<table>/
timeout_minutes: <from LLD §4.2>
retries: <from LLD §4.2>
retry_delay_seconds: <from LLD §4.2>
```

Notes:
- `<bronze_table_name>` follows the DMS Bronze naming convention (DMS §3
  or wherever naming is declared). Do NOT hardcode a source-system prefix
  (e.g. `synthea_`) — read the DMS.
- `empty_input_behavior` per table comes from LLD §5.1. Tables flagged
  `fail` are the "critical" tables for this project — there is no
  hardcoded list.
- Do NOT include `ds={ds}/` in `output_path` — the runner writes Delta
  partitioned by `ds`, so the output directory is the table root.
- Do NOT rewrite `contracts/<table>.yml` here (owned by create-scaffold
  via DMS). If a contract is missing, flag it as a prerequisite.

For `dq_rules/<table>.yml`, sync from the DQS SE rules by discovery:

```bash
LATEST_DQS_DIR=$(ls -d {workspace_root}/../chapter-4/outputs/dqs/v* | sort -V | tail -1)
# For each Bronze table from LLD §5.1, locate its SE rule file by reading
# product_id from each candidate YAML; fall back to filename-stem match.
for SE_FILE in "$LATEST_DQS_DIR"/se-rules/*.yaml; do
  PID=$(python3 -c "import yaml,sys; print(yaml.safe_load(open('$SE_FILE')).get('product_id',''))")
  # match PID (or filename stem) to a Bronze table name from LLD §5.1
  cp "$SE_FILE" "{project_root}/dq_rules/${TABLE}.yml"
done
```

If a Bronze table has no matching SE rule file, stop and ask the DQ
Engineer to produce one. Do NOT hand-write stubs — runtime loads expect
the full SE schema (`product_id`, `dq_env`, `rules[]`).

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

> **Scope gate**: In story mode, generate a test module only when a test
> path under `tests/bronze/**` was extracted from the story's AC (or when
> the story's AC explicitly calls for "unit tests covering <X>"). Tests
> for modules emitted by this skill MUST accompany the module; do not
> ship untested ingestion code.

Write test modules under `{project_root}/tests/bronze/` so the generated
code is exercised in CI. Use `pytest.importorskip("pyspark")` so Spark-
dependent tests skip cleanly when pyspark is not installed.

The exact set of test modules is driven by what this skill just generated,
not by a hardcoded table. General guidance:

| If you generated … | Write tests covering … |
|--------------------|------------------------|
| `ingestion_runner.py` | `load_table_config` (happy + each config-error branch), `_parse_spark_type` (every primitive + decimal + unsupported), `load_struct_type`, `add_metadata_columns` (assert `_source_batch_id` is deterministic + `_ingested_at` present), empty-input branches of `ingest()`, `resolved_quarantine_path`, `_DQ_ENV_MAP` (parametrised over runtime envs). Requires pyspark — import-skip otherwise. |
| `airflow/configs/*.yml` (per-table configs) | Parametrised sweep over `{project_root}/airflow/configs/*.yml`: required keys present, `table:` matches filename, referenced `contracts/<t>.yml` + `dq_rules/<t>.yml` exist, tables flagged `fail` in LLD §5.1 use `fail`, SE rules declare every `dq_env` value, the table count matches LLD §5.1 exactly. Pure YAML — no Spark. |
| `ingestion_factory.py` / DAG integration | Shells out to `validate-ingestion/scripts/validate_ingestion.py` against the project (expect PASS) and against a minimal scaffold missing runtime deps (expect CRITICAL on the missing libs). |

Read the AC text of the active story verbatim — the story tells you
*which* behaviour needs test coverage. Do not skip this phase.

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

### Phase 5.5: Verification Compliance Self-Check (MANDATORY before reporting OK)

The story's `## Verification` block is the contract. After every prior
phase has emitted its files, run the AC verifier against the target
story and refuse to declare OK if any mechanical verifier still fails.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/../scripts/verify_acs.py STORY-NN-NNN --json
```

(For batch / multi-story dispatch, run once per story.)

Parse the JSON output. For each AC in `acs[]`:

- `status == "FAIL"` and at least one check has a non-`manual` kind
  that failed → emit one CRITICAL line per failing check:
  `CRITICAL STORY-NN-NNN AC<N>: <check.spec> — <check.detail>`
  Then **stop**. Do NOT mark the plan task `done`. Do NOT print the
  OK trailer. The orchestrator's Phase 2 Step 3.5 reads this and halts
  the story.
- `status == "FAIL"` but every failing check is `manual:` → INFO only
  (manual checks can't fail mechanically; treat as author note).
- `status == "PASS"` / `INDETERMINATE` → continue.
- `has_verification == false` → emit one WARNING line
  `STORY-NN-NNN: no Verification block — generation completed without
  AC compliance check.` Then continue.

This phase is the **only** place this skill flips its overall result
from OK to FAILED. Skills that ignore it leave gaps the orchestrator
cannot see.

## Output Summary

At the end, print a table: `Module/Config | Path | Action (created|updated|skipped)`
so the user can see exactly what changed.

In story mode, prefix the table with the story ID and AC result summary:
```
Story: STORY-02-002 — Generic Ingestion Runner | Result: 5/5 AC PASS

Module/Config             | Path                                              | Action
ingestion_runner.py       | src/{project_name}/bronze/ingestion_runner.py     | created
```
