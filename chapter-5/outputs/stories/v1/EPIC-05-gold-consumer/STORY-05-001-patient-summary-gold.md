# STORY-05-001: Implement build_patient_summary_gold

| Field | Value |
|-------|-------|
| **Epic** | EPIC-05: Gold Consumer Layer |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 4 |
| **Dependencies** | STORY-04-006 |
| **Status** | To Do |

## User Story

As a Clinical user, I want a `patient_summary` Gold table denormalizing patient + recent encounters + chronic conditions + active medications + allergies, so that 350 clinical users have a single-row-per-patient view.

## Description

Implement `patient_360/src/patient_360/gold/build_patient_summary.py` reading current-version `clinical_patients` (broadcast cache) joined to `clinical_encounters`, `clinical_conditions`, `clinical_medications`, `clinical_allergies`. Applies STM Silver-to-Gold denormalization, runs inline SE per `dq_rules/patient_summary.yml`, writes full-overwrite to `unity.gold.patient_summary`. Per LLD §4.5 idempotency, write mode is `overwrite` (full rebuild from current Silver state).

## Acceptance Criteria

- [ ] `patient_360/src/patient_360/gold/build_patient_summary.py` exists [LLD §5.3]
- [ ] Joins to `clinical_patients` filtered `is_current=true` (broadcast) [LLD §6.2]
- [ ] Inline SE invoked with `dq_rules/patient_summary.yml` (DQ-FLD-105+) [DQS §2 Gold]
- [ ] Writes to `unity.gold.patient_summary` via full-table overwrite [LLD §4.5, §5.3]
- [ ] Fails on empty input [LLD §5.3]
- [ ] `patient_360/dq_rules/patient_summary.yml` SE rule file present [DQS §2]

## Technical Notes

- **Upstream references**: LLD §5.3 (Gold tasks), §4.5 (idempotency — full overwrite), §6.2 (broadcast), STM Silver-to-Gold patient_summary, DQS §2 Gold rules
- **Implementation hints**: Cache `clinical_patients` (current) once; reuse in 3 Gold builders.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §4.5, §5.3, §6.2, §8.6.1 |
| DMS | §5 Gold patient_summary |
| STM | Silver-to-Gold patient_summary |
| DQS | §2 Gold rules (patient_summary) |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | denormalization + SE wiring | `pytest patient_360/tests/gold/test_build_patient_summary_unit.py` |
| Contract | dq_rules/patient_summary.yml present | `test -f patient_360/dq_rules/patient_summary.yml` |

## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/gold/build_patient_summary.py"
AC2:
  - grep: {file: "patient_360/src/patient_360/gold/build_patient_summary.py", pattern: 'is_current'}
  - grep: {file: "patient_360/src/patient_360/gold/build_patient_summary.py", pattern: 'broadcast'}
AC3:
  - grep: {file: "patient_360/src/patient_360/gold/build_patient_summary.py", pattern: 'se_runner|run_dq'}
AC4:
  - grep: {file: "patient_360/src/patient_360/gold/build_patient_summary.py", pattern: 'unity.gold.patient_summary'}
  - grep: {file: "patient_360/src/patient_360/gold/build_patient_summary.py", pattern: 'overwrite'}
AC5:
  - pytest: {node: "patient_360/tests/gold/test_build_patient_summary_unit.py"}
AC6:
  - file_exists: "patient_360/dq_rules/patient_summary.yml"
```

## How to Test (User)

### Prerequisites

- EPIC-04 complete (Silver layer populated in UC)

### Steps

1. `cd patient_360 && uv run python src/patient_360/gold/build_patient_summary.py --env dev --ds 2026-04-27`
2. `cd patient_360 && uv run pytest tests/gold/test_build_patient_summary_unit.py -v`

### Expected outcome

- Step 1: logs `wrote 5767 rows to unity.gold.patient_summary`
- Step 2: unit tests pass

## Documentation Updates

- [ ] Update `patient_360/README.md` § "Gold layer" with `build_patient_summary` invocation
