---
skill: validate-silver
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# validate-silver — Skill-Creator Eval

## What this skill should do

Read-only validation of Silver against LLD §5.2, DMS §3, STM Bronze-to-Silver, DQS §2.

## Scenarios

### S1 — Clean Silver layer

**Expected**: PASS, "13 transforms present, 4 SCD2 dims, 9 cleansed facts, all contracts aligned".

### S2 — SCD2 dim missing apply_scd2 import

**Expected**: CRITICAL — "SCD2 dim must use shared apply_scd2 helper".

### S3 — Surrogate key uses monotonically_increasing_id

**Expected**: CRITICAL — "IL-006 violated: never monotonically_increasing_id for SCD2 surrogate keys".

### S4 — DQ-after-write order

**Setup**: transform calls `write_silver_delta()` before `run_dq()`.

**Expected**: CRITICAL — "LLD §8.2 mandates DQ-before-write".

### S5 — Fact uses apply_scd2

**Expected**: CRITICAL — "cleansed facts must use write_silver_delta, never apply_scd2".

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "lint the silver transforms" | validate-silver | validate-gold |
| "check the SCD2 wiring" | validate-silver | validate-stories |
| "is silver still aligned with the LLD" | validate-silver | validate-gold |

## Description quality checks

- [x] Names upstream sections.
- [x] Read-only claim explicit.
- [x] Severity tiers documented.

## Known weaknesses

- No `scripts/validate_silver.py` yet — runs as prose. Phase 2 backfill.
- Hash-column drift is name-based; type mismatches go undetected.
