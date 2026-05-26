---
skill: update-dag
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# update-dag — Skill-Creator Eval

## What this skill should do

Apply incremental edits to an existing Airflow DAG to reflect LLD or config changes.

## Scenarios

### S1 — Add a new task to existing TaskGroup

**Invoke**: `/developer-plugin:update-dag airflow/dags/patient360_hourly_v1.py` with instruction "add transform_<new_table> to silver_facts".

**Expected**: inserts the task within the TaskGroup, preserves dependency edges, bumps the version-comment.

### S2 — Hard rules

- Never converts a `SparkSubmitOperator` to a `PythonOperator` (IL-011).
- Never deletes a TaskGroup wholesale; surface deletes via `update-silver` / `update-ingestion`.
- Always re-validates with `/developer-plugin:validate-dag` after an edit.

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "add a task to silver_dimensions" | update-dag | update-silver |
| "fix the dependency edges in the dag" | update-dag | create-dag |
| "bump the dag's schedule_interval" | update-dag | create-dag |

## Description quality checks

- [x] Argument-hint accepts dag-file-path.
- [x] "Incremental edits" claim explicit.

## Known weaknesses

- Cross-DAG awareness: doesn't check whether another DAG already owns the same task.
