---
skill: update-ingestion
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# update-ingestion — Skill-Creator Eval

## What this skill should do

Apply minimal incremental edits to the Bronze ingestion framework when LLD or STM changes.

## Scenarios

### S1 — Add a new column to existing config

**Invoke**: `/developer-plugin:update-ingestion patients.yml`.

**Expected**: appends the column to the YAML schema block, preserves other entries, bumps the file's `version:` field.

### S2 — Runner change requires factory update

**Setup**: LLD §5.1 changes the partition strategy.

**Expected**: edits `bronze/runner.py` minimally, edits `bronze/factory.py` to match, updates the YAML configs that depend on the changed partition.

### S3 — Hard rules

- Never rewrites unchanged files.
- Never inlines new patient_360-style names — all names from STM at runtime.
- Always re-validates with `/developer-plugin:validate-ingestion`.

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "add a column to the patients bronze config" | update-ingestion | create-ingestion |
| "fix the spark submit wrapper" | update-ingestion | create-ingestion |
| "patch the bronze runner" | update-ingestion | create-ingestion |

## Description quality checks

- [x] "Minimal incremental edits" claim explicit.
- [x] Argument-hint accepts table-name OR config-file-path.

## Known weaknesses

- Edits don't detect orphaned configs (config exists, no LLD source row anymore).
