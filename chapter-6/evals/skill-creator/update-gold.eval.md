---
skill: update-gold
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# update-gold — Skill-Creator Eval

## What this skill should do

Apply incremental edits to existing Gold when LLD §5.3, DMS §4, STM, DQS Gold rules, or Silver changes.

## Scenarios

### S1 — Story mode (single builder)

**Invoke**: `/developer-plugin:update-gold STORY-05-005`.

**Expected**: reads previous Gold state, applies diff implied by ACs, preserves unchanged builders, increments file-level version per the 3-scenario rule.

### S2 — Diff mode

**Invoke**: `/developer-plugin:update-gold diff` → prints `(builder, latest_LLD_sig, current_code_sig, action)` table BEFORE editing, asks AskUserQuestion to confirm.

### S3 — Full mode

**Invoke**: `/developer-plugin:update-gold full` → re-emits every Gold builder/contract/DQ file; existing tests on removed columns flagged INFO.

### S4 — Silver ripple-effect warning

**Setup**: `clinical_patients_silver` schema renamed a column.

**Expected**: skill warns that all 3 Gold tables read this column; lists impacted builders; user approves via AskUserQuestion before edits.

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "the DMS gold section changed, update the builders" | update-gold | create-gold |
| "patient_summary needs a new column" | update-gold | update-silver |
| "regenerate every gold builder" | update-gold (full) | create-gold |

## Hard rules

- Never deletes a builder file without an LLD §5.3 row being removed.
- Never edits Gold if Silver hasn't been re-`Approved` after upstream changes.
- Bumps minor version on the file-level comment for every edit.

## Known weaknesses

- Diff mode's heuristic is keyword-based; structural AST diff would catch subtler drift.
