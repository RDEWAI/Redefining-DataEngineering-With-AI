---
skill: create-silver
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# create-silver — Skill-Creator Eval

## What this skill should do

Generate the Silver layer from approved LLD/DMS/STM/DQS — SCD2 dims + cleansed facts + DAG wiring.

## Scenarios

### S1 — Story mode, single Silver table

**Invoke**: `/developer-plugin:create-silver STORY-03-005` (a story scoped to silver patient transform).

**Expected**:
- Phase 0 confirms all upstream artifacts are `Approved`.
- Emits `src/patient_360/silver/transform_<table>.py` (SCD2 path).
- Emits `contracts/<silver_table>.yml` + `dq_rules/<silver_table>.yml`.
- Emits `tests/silver/test_transform_<table>_unit.py`.
- Wires `silver_dimensions` TaskGroup into `airflow/dags/patient360_hourly_v1.py`.
- Phase 7 validate-silver returns PASS.

### S2 — Hard rules

- Never invents columns: only DMS §3 columns appear in the contract and module.
- Never reorders STM rows.
- For SCD2 dims, never calls `write_silver_delta`; calls `apply_scd2` exclusively.
- For cleansed facts, never calls `apply_scd2`.

### S3 — Inherited learnings still applied

- IL-001 (no `pyspark==4.0.0`), IL-006 (no `monotonically_increasing_id`),
  IL-011 (SparkSubmitOperator only) must appear in emitted code review.

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "build the silver layer for this story" | create-silver | create-gold |
| "update the silver dimensions because the STM changed" | update-silver | create-silver |
| "validate the silver MERGE pattern" | validate-silver | create-silver |

## Description quality checks

- [x] First sentence states the skill's job.
- [x] Project-agnostic claim explicit.
- [x] Modes block (Story / Full).
- [x] Argument-hint format clear.

## Known weaknesses

- Silver fact-table generation has no end-to-end golden in this round (Phase 2 backfill).
