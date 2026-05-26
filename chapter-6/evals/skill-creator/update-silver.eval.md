---
skill: update-silver
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# update-silver — Skill-Creator Eval

## What this skill should do

Apply incremental edits to Silver when LLD §5.2 / DMS §3 / STM / DQS §2 changes; surface Gold ripple effects.

## Scenarios

### S1 — Story mode (single transform)

**Invoke**: `/developer-plugin:update-silver STORY-03-007`.

**Expected**: edits `src/patient_360/silver/transform_<table>.py` only, preserves unchanged transforms, bumps version comment, re-emits contract if schema changed.

### S2 — Diff mode

**Invoke**: `/developer-plugin:update-silver diff` → table of `(table, latest_sig, current_sig, action)`, AskUserQuestion before editing.

### S3 — Full mode

**Invoke**: `/developer-plugin:update-silver full` → re-emits every transform; preserves user-added test data; never deletes SCD2 helper.

### S4 — Gold ripple-effect

**Setup**: SCD2 hash-column list for `clinical_patients` changes.

**Expected**: warns that `patient_summary` + `patient_clinical_history` read this dim; suggests `/developer-plugin:update-gold diff` after.

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "the STM bronze-to-silver mapping changed" | update-silver | create-silver |
| "fix the SCD2 hash columns for clinical_patients" | update-silver | update-gold |
| "regenerate every silver transform" | update-silver (full) | create-silver |

## Hard rules

- Honours inherited learnings IL-001…IL-017.
- Never deletes the shared SCD2 helper without an explicit deprecation story.
- Always re-runs validate-silver after an edit.

## Known weaknesses

- Ripple-effect detection is name-based; renames upstream that don't change the Silver name go undetected.
