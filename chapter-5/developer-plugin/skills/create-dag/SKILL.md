---
name: create-dag
description: >
  Generates an Airflow DAG from the LLD artifact and pipeline configs.
  Reads the approved LLD from inputs/, applies DAG templates, and writes
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

## Workflow

### Phase 0: Upstream Gate
Read the latest LLD from `inputs/` and verify `Status: Approved`.
If not approved, stop and inform the user.

### Phase 1: Read Inputs
- Latest LLD markdown from `{workspace_root}/inputs/`
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

### Phase 4: Write Output
Save to `{project_root}/airflow/dags/{dag_id}.py`

### Phase 5: Validate
Invoke `/developer-plugin:validate-dag` on the generated file.
Fix any CRITICAL issues before finishing.
