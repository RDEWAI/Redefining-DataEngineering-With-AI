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
