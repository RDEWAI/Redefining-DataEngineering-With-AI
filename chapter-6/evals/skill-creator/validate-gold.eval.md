---
skill: validate-gold
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# validate-gold — Skill-Creator Eval

## What this skill should do

Read-only validation of Gold against LLD §5.3, DMS §4, STM Silver-to-Gold, DQS §2-3 Gold rules. Reports CRITICAL / WARNING / INFO.

## Scenarios

### S1 — Clean Gold layer

**Expected**: PASS, "3 builders present, 3 contracts aligned, 3 DQ files aligned".

### S2 — Builder missing

**Setup**: `build_patient_billing_summary.py` deleted.

**Expected**: CRITICAL — "DMS §4 declares patient_billing_summary but builder is missing".

### S3 — Schema drift

**Setup**: builder writes a column not in DMS §4.

**Expected**: CRITICAL — "patient_summary.cost_total written but not declared in DMS §4".

### S4 — DQ-after-write violation

**Setup**: builder calls `df.write.format('delta')…` before `run_dq()`.

**Expected**: CRITICAL — "LLD §8.2 mandates DQ-before-write order".

### S5 — Bronze import (boundary violation)

**Setup**: builder imports `from patient_360.bronze import …`.

**Expected**: CRITICAL — "Gold must read from Silver only (LLD §5.3)".

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "lint the gold builders" | validate-gold | validate-silver |
| "is patient_summary still aligned with the DMS" | validate-gold | validate-silver |
| "check gold layer for DQ-before-write order" | validate-gold | validate-ingestion |

## Description quality checks

- [x] Severity tiers explicit.
- [x] Names which LLD/DMS sections it cross-checks.
- [x] Read-only claim explicit.

## Known weaknesses

- No standalone `scripts/validate_gold.py` yet; runs as prose. Phase 2 should add a mechanical validator.
