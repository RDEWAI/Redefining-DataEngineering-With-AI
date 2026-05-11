---
name: validate-dag
description: >
  Validates an Airflow DAG file for correctness, import errors, and
  compliance with project conventions. Runs static checks and reports
  CRITICAL / WARNING / INFO findings.
  Use when the user asks to:
  - Validate, check, or lint a DAG
  - Verify a DAG has no import errors
  - Confirm DAG follows project standards
argument-hint: "[dag-file-path]"
allowed-tools: Read, Bash, Grep, Glob
context: fork
---

# Validate Airflow DAG

You are a senior Data Engineer. Validate the target DAG file and report findings.

## Workspace Discovery

Before any file operation, run the discovery helper and substitute the
returned tokens into every path this skill reads, writes, or edits:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py --mode discover
```

The JSON output supplies `{workspace_root}`, `{project_root}`,
`{project_name}`, `{stories_dir}`, and `{learnings_queue}`. The plugin is
project-agnostic — never hardcode project or chapter names in edits.

## Coding Patterns Handbook

Load the pattern docs this skill checks against (read-only; no freshness prompt):

```bash
PATTERNS_DIR=$(ls -d "{workspace_root}/inputs/code/v"* 2>/dev/null | sort -V | tail -1)
if [ -z "$PATTERNS_DIR" ] || [ ! -d "$PATTERNS_DIR" ]; then
  echo "WARNING: inputs/code/v*/ not found — pattern-conformance checks will be INDETERMINATE."
fi
```

**Pattern docs consulted:**

- `$PATTERNS_DIR/airflow-dag-pattern.md` — factory/TaskGroup/SparkSubmitOperator defaults
- `$PATTERNS_DIR/test-pattern.md` — DAG-integrity test expectations

### References trailer (in output)

Cite each pattern doc consulted, e.g. `Checked against inputs/code/v1/airflow-dag-pattern.md §2`.

## Phase 0.a — Argument Resolution (mandatory, runs first)

The Skill-tool argument frequently fails to reach forked subagents. Resolve
the target via the shared resolver, which checks four sources in order:
`$SKILL_ARG` → `{workspace_root}/.skill-arg` → conversational arg → auto-mode.

```bash
read -r RESOLVED_ARG RESOLVED_SOURCE < <(
  WORKSPACE_ROOT="{workspace_root}" \
    bash "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_skill_arg.sh" "$USER_ARG" | \
    paste -sd' ' -
)
```

Print this banner as the **first line** of skill output:

```
RESOLVED TARGET: <value> (source: <SKILL_ARG | .skill-arg | conversational | __AUTO__>)
```

If `$RESOLVED_SOURCE == EMPTY`, fall through to the skill's existing
clarification step (typically `AskUserQuestion`). DO NOT ask the user before
running this resolver.

## Checks

### Automated regression rules (run via `scripts/validate_dag.py`)

```bash
uv run python ${CLAUDE_PLUGIN_ROOT}/skills/validate-dag/scripts/validate_dag.py {file}
# or, recursive over a project root:
uv run python ${CLAUDE_PLUGIN_ROOT}/skills/validate-dag/scripts/validate_dag.py --all {project_root}
```

CRITICAL rules — fail-the-build:

- **DAG-PATHS-001** — literal `application="run_local.py"` (relative path)
  is rejected. Path doesn't resolve when Airflow runs from `/opt/airflow/`.
  Use `os.environ.get("<TYPE>_RUNNER_APP", "/opt/airflow/jobs/run_<task_type>.py")`.
- **DAG-PATHS-002** — literal `configs_dir="airflow/configs"` (relative)
  is rejected. Use `os.environ.get("AIRFLOW_CONFIGS_DIR", "/opt/airflow/configs")`.
- **UC-WIRING-001** — Bronze runners under `src/**/bronze/**.py` may not
  use `df.write.format("delta").save(...)` (path-based Delta). Use
  `saveAsTable("unity.bronze.<table>")` per LLD Decision 15 — otherwise
  Unity Catalog never sees the table.

The script skips pure-comment lines and lines containing negative-keyword
markers (`NEVER`, `don't`, `pitfall`, …) so anti-pattern documentation is
allowed.

### CRITICAL (must fix before merge)
- Python syntax errors (`python -m py_compile {file}`)
- Missing required imports
- Hardcoded credentials or connection strings
- DAG without a schedule interval or `schedule=None` intentional marker
- Tasks with no upstream/downstream dependencies (orphaned tasks)

### WARNING (should fix)
- DAG ID does not match filename
- Missing `doc_md` or docstring
- Retry count is 0 for production tasks
- No SLA defined on critical tasks

### INFO (good to know)
- Task count above 50 (consider splitting)
- No `on_failure_callback` set

## Output Format

```
CRITICAL: [count] issue(s)
  - [description]

WARNING: [count] issue(s)
  - [description]

INFO: [count] item(s)
  - [description]

Result: PASS / FAIL
```
