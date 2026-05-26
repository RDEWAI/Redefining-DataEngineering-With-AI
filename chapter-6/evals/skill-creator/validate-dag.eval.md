---
skill: validate-dag
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# validate-dag — Skill-Creator Eval

## What this skill should do

Validate an Airflow DAG file for correctness, import errors, and convention compliance.

## Scenarios

### S1 — Clean DAG

**Expected**: PASS, "no import errors, 5 TaskGroups, 23 tasks, all SparkSubmit, max_active_tasks=1".

### S2 — Import error

**Setup**: typo in `from airflow.providers.apache.spark...`.

**Expected**: CRITICAL — "DAG fails to import: ModuleNotFoundError".

### S3 — Non-SparkSubmit task

**Expected**: CRITICAL — "transform_patient_silver uses PythonOperator (IL-011 violation)".

### S4 — Missing catchup=False

**Expected**: WARNING — "DAG missing catchup=False; backfill avalanche risk (IL-014)".

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "lint the dag" | validate-dag | validate-pipeline |
| "check the dag for import errors" | validate-dag | validate-stories |
| "is the DAG using SparkSubmitOperator everywhere" | validate-dag | validate-ingestion |

## Description quality checks

- [x] Argument-hint clear.
- [x] CRITICAL/WARNING/INFO documented.

## Known weaknesses

- Static check only — doesn't actually call `airflow dags list` against a live scheduler.
