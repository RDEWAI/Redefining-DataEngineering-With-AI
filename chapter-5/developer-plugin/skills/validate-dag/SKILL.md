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

## Checks

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
