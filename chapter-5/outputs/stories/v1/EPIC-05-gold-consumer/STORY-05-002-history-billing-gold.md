# STORY-05-002: Implement build_clinical_history_gold + build_billing_summary_gold

| Field | Value |
|-------|-------|
| **Epic** | EPIC-05: Gold Consumer Layer |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 4 |
| **Dependencies** | STORY-05-001 |
| **Status** | To Do |

## User Story

As a Physician/Nurse, I want `patient_clinical_history` and `patient_billing_summary` Gold tables so that physicians have time-ordered clinical history and billing staff have financial summaries.

## Description

Implement `patient_360/src/patient_360/gold/build_patient_clinical_history.py` (denormalizes patient + encounters + conditions + medications + observations + procedures + immunizations + careplans, time-ordered) and `patient_360/src/patient_360/gold/build_patient_billing_summary.py` (joins patient + encounters + claims + payers). Both run inline SE per their `dq_rules/<table>.yml` and write full-overwrite to `unity.gold.<table>`.

## Acceptance Criteria

- [ ] `patient_360/src/patient_360/gold/build_patient_clinical_history.py` exists [LLD §5.3]
- [ ] `patient_360/src/patient_360/gold/build_patient_billing_summary.py` exists [LLD §5.3]
- [ ] Both write to `unity.gold.<table>` via overwrite [LLD §4.5, §5.3]
- [ ] Both invoke `se_runner.run_dq` with their `dq_rules/<table>.yml` [DQS §2 Gold]
- [ ] 2 DQ rule YAMLs exist (`patient_clinical_history.yml`, `patient_billing_summary.yml`) [DQS §2]

## Technical Notes

- **Upstream references**: LLD §5.3 (Gold tasks), STM Silver-to-Gold (these 2), DQS §2 Gold rules
- **Implementation hints**: clinical_history is time-ordered — sort by `event_date`. billing_summary uses `reference_payers` (broadcast).

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §4.5, §5.3, §8.6.1 |
| DMS | §5 Gold |
| STM | Silver-to-Gold |
| DQS | §2 Gold |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | both builder modules | `pytest patient_360/tests/gold/test_build_history_billing_unit.py` |

## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/gold/build_patient_clinical_history.py"
AC2:
  - file_exists: "patient_360/src/patient_360/gold/build_patient_billing_summary.py"
AC3:
  - grep_count: {glob: "patient_360/src/patient_360/gold/build_patient_{clinical_history,billing_summary}.py", pattern: 'unity.gold', equals: 2}
AC4:
  - grep_count: {glob: "patient_360/src/patient_360/gold/build_patient_{clinical_history,billing_summary}.py", pattern: 'se_runner|run_dq', equals: 2}
AC5:
  - file_exists: "patient_360/dq_rules/patient_clinical_history.yml"
  - file_exists: "patient_360/dq_rules/patient_billing_summary.yml"
```

## How to Test (User)

### Prerequisites

- STORY-05-001 complete

### Steps

1. `cd patient_360 && uv run python src/patient_360/gold/build_patient_clinical_history.py --env dev --ds 2026-04-27`
2. `cd patient_360 && uv run python src/patient_360/gold/build_patient_billing_summary.py --env dev --ds 2026-04-27`
3. `cd patient_360 && uv run pytest tests/gold/test_build_history_billing_unit.py -v`

### Expected outcome

- Steps 1-2: each logs `wrote N rows to unity.gold.<table>`
- Step 3: all unit tests pass

## Documentation Updates

- [ ] Update `patient_360/README.md` § "Gold layer" with the 2 additional builder invocations
