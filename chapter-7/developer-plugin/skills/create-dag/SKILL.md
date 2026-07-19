---
name: create-dag
description: >
  Generates an Airflow DAG from the LLD artifact and pipeline configs.
  Reads the approved LLD from outputs/, applies DAG templates, and writes
  a production-ready DAG file to airflow/dags/.
  Also known as: dag generation, pipeline scaffolding, airflow pipeline creation.
  Input formats: LLD markdown, DAG config YAML.
  Output format: Python DAG file (.py).
  Use when the user asks to:
  - Create, generate, or scaffold an Airflow DAG
  - Translate an LLD into a runnable pipeline
  - Build a DAG for bronze/silver/gold layers
argument-hint: "[lld-path]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion, Skill
context: fork
---

# Create Airflow DAG

You are a senior Data Engineer specialising in Apache Airflow. Your job is to
translate the approved Low-Level Design (LLD) artifact into a production-ready
Airflow DAG.

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

Before generating a DAG, load the latest coding-patterns handbook:

```bash
PATTERNS_DIR=$(ls -d "{workspace_root}/inputs/code/v"* 2>/dev/null | sort -V | tail -1)
if [ -z "$PATTERNS_DIR" ] || [ ! -d "$PATTERNS_DIR" ]; then
  echo "CRITICAL: inputs/code/v*/ not found. Run /developer-plugin:refresh-libraries to initialize the library cache."
  exit 1
fi
LIBRARIES_FILE="$PATTERNS_DIR/LIBRARIES.md"
```

**Required pattern docs for this skill:**

- `$PATTERNS_DIR/airflow-dag-pattern.md` — factory, TaskGroup, SparkSubmitOperator defaults
- `$PATTERNS_DIR/naming-conventions.md` — DAG file name, task IDs
- `$PATTERNS_DIR/LIBRARIES.md` — pinned Airflow + provider versions

### Library freshness check

```bash
LAST_VERIFIED=$(grep '^last_verified:' "$LIBRARIES_FILE" | awk '{print $2}')
TODAY=$(date -u +%Y-%m-%d)
AGE_DAYS=$(python3 -c "from datetime import date; print((date.fromisoformat('$TODAY') - date.fromisoformat('$LAST_VERIFIED')).days")
```

If `AGE_DAYS > 30`, pause and call **AskUserQuestion** with options `Refresh now` / `Proceed with cached versions` / `Cancel`. On Refresh, invoke `/developer-plugin:refresh-libraries` then resume.

### References trailer (in output)

Emit a `### References` section citing consumed pattern docs + LIBRARIES.md vintage. Add a stale-cache warning if the user proceeded with cached versions.

## Phase 0.a — Argument Resolution (mandatory, runs first)

The Skill-tool argument frequently fails to reach forked subagents. Resolve
the target via the shared resolver, which checks four sources in order:
`$SKILL_ARG` → `{workspace_root}/.skill-arg` → conversational arg → auto-mode.

```bash
# Step 1: capture the user's conversational input. Substitute the
# bracketed text below with the EXACT message the user supplied after
# the skill name; if no message was supplied, leave it as an empty
# string. This is the ONLY substitution this skill requires.
CONV_ARG='<<EXACT_CONVERSATIONAL_TEXT_FROM_USER_OR_EMPTY_STRING>>'

# Step 2: run the shared resolver. It auto-discovers the workspace
# from $PWD, so no {workspace_root} substitution is required. Output is
# two lines on stdout: the resolved value, then the source token.
read -r RESOLVED_ARG RESOLVED_SOURCE < <(
  bash "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_skill_arg.sh" "$CONV_ARG" \
    | paste -sd' ' -
)
```

Print this banner as the **first line** of skill output:

```
RESOLVED TARGET: <value> (source: <SKILL_ARG | .skill-arg | conversational | __AUTO__>)
```

If `$RESOLVED_SOURCE == EMPTY`, fall through to the skill's existing
clarification step (typically `AskUserQuestion`). DO NOT ask the user before
running this resolver.

## Workflow

### Phase 0: Upstream Gate

Resolve upstream versions via the shared helper (uses `outputs/dev-lock.yaml`
when present, otherwise falls back to latest `v{N}`):

```bash
eval "$(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/resolve_versions.py --export)"
LATEST_LLD_DIR="${LATEST_LLD_DIR:-$(ls -d {workspace_root}/outputs/lld/v* | sort -V | tail -1)}"
```

Read the latest LLD from `$LATEST_LLD_DIR/` and verify `Status: Approved`.
If not approved, stop and inform the user.

### Phase 1: Read Inputs
- Latest LLD markdown from `{workspace_root}/outputs/lld/v*/`
- DAG config from `{project_root}/airflow/configs/` if present
- Existing DAGs in `{project_root}/airflow/dags/` for patterns

### Phase 2: Clarify
Use `AskUserQuestion` to confirm:
- Target Airflow version and executor (LocalExecutor / CeleryExecutor / KubernetesExecutor)
- Schedule interval
- Retry and SLA settings
- Connection IDs to use

### Phase 3: Generate DAG
- Follow the task dependency graph defined in the LLD `## Pipeline DAG` section
- Use `TaskGroup` to group bronze / silver / gold stages
- Parameterise connections and paths via Airflow Variables or a config YAML
- Include docstring referencing the LLD section and artifact version
- **CRITICAL — env-driven paths in every generated DAG file:**
  - `configs_dir = os.environ.get("AIRFLOW_CONFIGS_DIR", "/opt/airflow/configs")`
  - `application = os.environ.get("<TYPE>_RUNNER_APP", "/opt/airflow/jobs/run_<task_type>.py")` per task type from LLD §4.2
  - Never emit `application="run_local.py"` (relative — breaks under `/opt/airflow/`)
  - Never emit `configs_dir="airflow/configs"` (relative — same issue)
  - The validator (`DAG-PATHS-001`, `DAG-PATHS-002`) rejects either pattern.
  - Reference snippet: `inputs/code/v1/scripts/dag_factory.py.snippet`.
- **CRITICAL — env-tiered Spark sizing (LLD §6.1, NOT §4.2):** resolve
  `driver_memory`/`executor_memory`/`spark.sql.shuffle.partitions` for every
  `SparkSubmitOperator` from an env-keyed `SPARK_SIZING` map on
  `PATIENT360_ENV` (DEV `1g`/8 · STAGING `4g`/16 · PROD `8g`/32), per the
  `airflow-dag-pattern.md` "Resource sizing" section. Never hardcode a single
  memory literal; never read memory off §4.2 (its integers are
  retries/timeouts). DEV `2g` OS-OOM-kills spark-submit (`Error code is: -9`)
  on the 8 GB co-resident compose stack — DEV must be `1g`.

### Phase 3b: Generate per-task entry wrappers (MANDATORY)

`SparkSubmitOperator.application` is a path to a `.py` file, not a `-m
module` spec. Spokane learned this when its wrapper failed at runtime with
`PermissionError: '-m'`. To prevent recurrence, this skill auto-generates
per-task entry shims under `<project_root>/airflow/jobs/run_<task_type>.py`
from `inputs/code/v1/scripts/run_layer_entrypoint.py.j2`, one shim per
distinct task type listed in **LLD §4.2 task inventory**.

**Generation steps:**

1. **Parse LLD §4.2 task inventory.** Extract the distinct task-type set
   (e.g. for the patient_360 LLD: `bronze_ingestion`, `bronze_recon`,
   `silver_dim`, `silver_fact`, `gold_aggregate`). Group rows that share a
   `Type` column — emit one wrapper per type, not per-row.
2. **For each task type, resolve the runner contract.** Read LLD §5 task
   table to extract `Module Path` (the dotted runner module) and the argv
   signature (typical args: `--config-path`, `--ds`, sometimes `--layer`,
   `--table`, `--configs-dir`). The runner's entry function is `main` by
   convention; if the LLD §2.3 contract names it differently, use that.
3. **Render the Jinja template** with these variables and write to
   `<project_root>/airflow/jobs/run_<task_type>.py`:
   ```python
   from jinja2 import Environment, FileSystemLoader
   env = Environment(loader=FileSystemLoader(f"{workspace_root}/inputs/code/v1/scripts"))
   tmpl = env.get_template("run_layer_entrypoint.py.j2")
   for task_type, spec in task_types.items():
       (jobs_dir / f"run_{task_type}.py").write_text(tmpl.render(
           project=project_name,
           task_type=task_type,
           runner_module=spec["module"],
           entry_function=spec.get("entry", "main"),
           argv_spec=spec["argv"],
       ))
   ```
4. **Emit env-var bindings in the airflow service of `_infra/docker/docker-compose.yml`.**
   Each generated wrapper gets a `<TYPE>_RUNNER_APP=/opt/airflow/jobs/run_<task_type>.py`
   line in `environment:` so the DAG factory's
   `application=os.environ["<TYPE>_RUNNER_APP"]` lookup resolves at runtime.
   The current cookiecutter ships with `BRONZE_RUNNER_APP` and `BRONZE_RECON_APP`
   pre-wired; add others here when LLD §4.2 introduces new task types.
5. **DAG factory consumes the env vars.** Generated DAG files MUST resolve
   `application` from the `<TYPE>_RUNNER_APP` env var (not hardcode the path).
   See `inputs/code/v1/scripts/dag_factory.py.snippet:_spark_task` for the
   reference pattern.

**Worked example — Bronze, two task types:**

| LLD §4.2 row | task_type | Wrapper file | Runner module | Compose env var |
|---|---|---|---|---|
| `ingest_*` (13 rows) | `bronze_ingestion` | `airflow/jobs/run_bronze_ingestion.py` | `patient_360.bronze.ingestion_runner` | `BRONZE_RUNNER_APP` |
| `reconciliation_bronze` | `bronze_recon` | `airflow/jobs/run_bronze_recon.py` | `patient_360.bronze.reconciliation` | `BRONZE_RECON_APP` |

The DAG factory's `_spark_task("ingest_patients", "bronze", "synthea_patients")`
call resolves `application` to `os.environ["BRONZE_RUNNER_APP"]` →
`/opt/airflow/jobs/run_bronze_ingestion.py` → which imports
`patient_360.bronze.ingestion_runner.main(args)`.

### Phase 4: Write Output
Save to `{project_root}/airflow/dags/{dag_id}.py`

### Phase 5: Validate
Invoke `/developer-plugin:validate-dag` on the generated file.
Fix any CRITICAL issues before finishing.

### Phase 6: Verification Compliance Self-Check (MANDATORY before reporting OK)

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


## Learnings & Corrections

### Active Learnings

- **L-001** (2026-05-11): Always: In Airflow 3.x, resolve the active DAG via airflow.sdk.definitions._internal.contextmanager.DagContext.get_current() and pass explicitly to factories rather than relying on contextual binding.
- **L-002** (2026-05-12): Always: Dev DAG defaults: max_active_tasks=1 and catchup=False. Document that production raises these only after the SE stats table has been seeded by at least one successful run.
- **L-003** (2026-05-12): Always: Any task that touches Spark must use SparkSubmitOperator (own JVM). PythonOperator with build_spark_session inside the callable is forbidden under Airflow 3.x.
- **L-004** (2026-05-12): Always: Target tables with either 3-part `unity.<schema>.<table>` FQNs OR 2-part `<schema>.<table>` names that resolve through `spark.sql.defaultCatalog=unity`. The named side catalog `unity` (io.unitycatalog.spark.UCSingleCatalog) is the default catalog at runtime, so bare 2-part names resolve to it; `spark_catalog` is bound to DeltaCatalog for Delta ops. Never bind `spark_catalog` to UCSingleCatalog. Both forms are valid in writer and query code; pick one and apply it consistently.
