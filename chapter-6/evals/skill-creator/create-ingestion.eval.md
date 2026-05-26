---
skill: create-ingestion
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# create-ingestion — Skill-Creator Eval

## What this skill should do

Generate the Bronze config-driven ingestion layer from approved LLD/DMS/STM/DQS and a target story.

## Scenarios

### S1 — Story mode (single source)

**Invoke**: `/developer-plugin:create-ingestion STORY-02-003` (scope: `patients` CSV).

**Expected**:
- Emits `airflow/configs/bronze/patients.yml` (config-driven runner input) with schema + DQ pointer.
- Emits or reuses `src/patient_360/bronze/runner.py`, `factory.py`, `spark_submit_wrapper.py`.
- DAG TaskGroup `bronze_ingestion` wired with one SparkSubmit task per source.
- Idempotent: re-running on an existing config either edits in place or no-ops if unchanged.

### S2 — Full mode

**Invoke**: `/developer-plugin:create-ingestion full` → emits configs for every Bronze source declared in LLD §5.1.

### S3 — Hard rules

- Anchors all relative paths against `PATIENT360_PROJECT_ROOT` (IL-005).
- Uses `SparkSubmitOperator`, never `PythonOperator` (IL-011).
- DQ runs inline BEFORE the Bronze write.
- Never inlines table names — every name comes from STM rows.

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "scaffold the bronze ingestion for the patients CSV" | create-ingestion | create-scaffold |
| "wire bronze_ingestion task group into the DAG" | create-ingestion | create-dag |
| "generate config-driven ingestion" | create-ingestion | create-scaffold |

## Description quality checks

- [x] States it reads LLD/DMS/STM/DQS.
- [x] Story / Full modes explicit.
- [x] Inherited-learnings references present.

## Known weaknesses

- No CDC-type negotiation eval; the LLD currently only mandates Full Snapshot.
