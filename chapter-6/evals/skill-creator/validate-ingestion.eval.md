---
skill: validate-ingestion
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# validate-ingestion — Skill-Creator Eval

## What this skill should do

Validate the Bronze ingestion framework against LLD §2.3 and §5.1 — runner, factory, SparkSubmit wrapper, per-table YAML configs.

## Scenarios

### S1 — Clean ingestion layer

**Expected**: PASS, "N source configs present, all schemas aligned with LLD §5.1".

### S2 — Missing schema in config

**Expected**: CRITICAL — "patients.yml missing schema block".

### S3 — Hardcoded path

**Expected**: CRITICAL — "absolute path `/opt/...` detected; use PATIENT360_PROJECT_ROOT-anchored relative path (IL-005)".

### S4 — PythonOperator instead of SparkSubmitOperator

**Expected**: CRITICAL — "IL-011: bronze tasks must use SparkSubmitOperator".

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "lint the bronze configs" | validate-ingestion | validate-dag |
| "check the ingestion runner" | validate-ingestion | validate-scaffold |
| "did we use SparkSubmitOperator everywhere in bronze" | validate-ingestion | validate-dag |

## Description quality checks

- [x] Severity tiers documented.
- [x] Names the LLD sections it checks.

## Known weaknesses

- Has a `scripts/validate_ingestion.py` (Phase 2 work — the only validator with a real Python script today); it does YAML lint but not full LLD-cross-reference.
