# STORY-04-003: Implement 4 remaining fact transforms (immunizations, procedures, claims, careplans)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts Layer |
| **Story Type** | build |
| **Priority** | P2 |
| **Story Points** | 5 |
| **Sprint** | 4 |
| **Dependencies** | STORY-04-001 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want the 4 remaining Silver fact transforms (immunizations, procedures, claims, careplans) implemented so that all 9 Silver fact tables are complete.

## Description

Implement `transform_immunizations.py`, `transform_procedures.py`, `transform_claims.py`, `transform_careplans.py` under `patient_360/src/patient_360/silver/`. Same pattern as STORY-04-002 — read Bronze, join encounters, transform, inline SE, write to `unity.silver.{clinical,billing}_<table>`. All 4 use `empty_input_behavior: write_empty` (default — non-required tables).

## Acceptance Criteria

- [ ] 4 transform modules exist: `transform_immunizations.py`, `transform_procedures.py`, `transform_claims.py`, `transform_careplans.py` [LLD §5.2]
- [ ] `transform_claims.py` writes to `unity.silver.billing_claims` (billing schema, not clinical) [LLD §5.2]
- [ ] Other 3 write to `unity.silver.clinical_<table>` [LLD §5.2]
- [ ] All 4 invoke `se_runner.run_dq` with their `dq_rules/<table>.yml` [DQS §2]
- [ ] 4 DQ rule YAMLs exist [DQS §2]

## Technical Notes

- **Upstream references**: LLD §5.2 (these 4 tasks), DQS §2 (DQ-FLD-084..094)
- **Implementation hints**: claims uses `billing_*` namespace per DMS §4 semantic grouping.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §5.2, §8.6.1 |
| DMS | §4 Silver |
| STM | Bronze-to-Silver these 4 |
| DQS | §2 DQ-FLD-084..094 |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | each transform | `pytest patient_360/tests/silver/test_remaining_facts_unit.py` |

## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/silver/transform_immunizations.py"
  - file_exists: "patient_360/src/patient_360/silver/transform_procedures.py"
  - file_exists: "patient_360/src/patient_360/silver/transform_claims.py"
  - file_exists: "patient_360/src/patient_360/silver/transform_careplans.py"
AC2:
  - grep: {file: "patient_360/src/patient_360/silver/transform_claims.py", pattern: 'unity.silver.billing_claims'}
AC3:
  - grep_count: {glob: "patient_360/src/patient_360/silver/transform_{immunizations,procedures,careplans}.py", pattern: 'unity.silver.clinical_', equals: 3}
AC4:
  - grep_count: {glob: "patient_360/src/patient_360/silver/transform_{immunizations,procedures,claims,careplans}.py", pattern: 'se_runner|run_dq', equals: 4}
AC5:
  - file_exists: "patient_360/dq_rules/clinical_immunizations.yml"
  - file_exists: "patient_360/dq_rules/clinical_procedures.yml"
  - file_exists: "patient_360/dq_rules/billing_claims.yml"
  - file_exists: "patient_360/dq_rules/clinical_careplans.yml"
```

## How to Test (User)

### Prerequisites

- STORY-04-001 complete

### Steps

1. `cd patient_360 && for t in immunizations procedures claims careplans; do uv run python src/patient_360/silver/transform_${t}.py --env dev --ds 2026-04-27; done`
2. `cd patient_360 && uv run pytest tests/silver/test_remaining_facts_unit.py -v`

### Expected outcome

- Step 1: each invocation logs `wrote N rows to unity.silver.{clinical,billing}_<table>`
- Step 2: all unit tests pass

## Documentation Updates

- [ ] N/A — internal Silver modules; user docs surface in EPIC-04 integration test
