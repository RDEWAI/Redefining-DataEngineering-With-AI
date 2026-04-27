# STORY-03-001: Implement transform_patients_silver (SCD2)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-03: Silver Dimensions Layer (SCD Type 2) |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 2 |
| **Dependencies** | STORY-01-004, STORY-02-007 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want `transform_patients_silver` implemented with SCD Type 2 + inline SE so that the patient dimension carries full version history with safety-critical DQ enforcement.

## Description

Implement `patient_360/src/patient_360/silver/transform_patients.py` reading `unity.bronze.synthea_patients`, applying STM Bronze-to-Silver transformations (derived `age`, `full_name`, etc.), running SCD2 via `utils/scd2.apply_scd2(...)` (SHA-256 hash + Delta MERGE INTO), invoking `se_runner.run_dq` for row_dq + agg_dq from `dq_rules/clinical_patients.yml`, and writing to `unity.silver.clinical_patients` with SCD2 columns (`effective_from`, `effective_to`, `is_current`, `record_hash`).

## Acceptance Criteria

- [ ] `patient_360/src/patient_360/silver/transform_patients.py` exists with `main(--env, --ds)` CLI [LLD §2.3, §5.2]
- [ ] Module applies SCD2 via `utils/scd2.apply_scd2` (SHA-256 hash + MERGE INTO) [LLD §5.2, DMS §6]
- [ ] Module writes to `unity.silver.clinical_patients` with SCD2 columns [LLD §5.2, DMS §6]
- [ ] Inline SE invoked with `dq_rules/clinical_patients.yml` (DQ-FLD-046 to DQ-FLD-059) [LLD §5.2, DQS §2]
- [ ] `empty_input_behavior: fail` — raises when Bronze is empty [LLD §5.2]
- [ ] `patient_360/dq_rules/clinical_patients.yml` SE rule file present [DQS §2]

## Technical Notes

- **Upstream references**: LLD §2.3, §5.2 (Silver tasks + SCD2 notes), DMS §6 (SCD2 hash columns), STM Bronze-to-Silver (patients), DQS §2 (DQ-FLD-046..059, 102..104)
- **Implementation hints**: `apply_scd2` should encapsulate the MERGE; the transform module supplies `key_cols=[patient_id]` and `hash_cols` from DMS §6.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §2.3, §5.2, §8.6.1 |
| DMS | §4 Silver patients, §6 SCD2 |
| STM | Bronze-to-Silver patients |
| DQS | §2 row_dq DQ-FLD-046..059, 102..104 |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | transform + SCD2 hash logic | `pytest patient_360/tests/silver/test_transform_patients_unit.py` |
| Contract | dq_rules/clinical_patients.yml present | `test -f patient_360/dq_rules/clinical_patients.yml` |

## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/silver/transform_patients.py"
  - grep: {file: "patient_360/src/patient_360/silver/transform_patients.py", pattern: '--ds'}
AC2:
  - grep: {file: "patient_360/src/patient_360/silver/transform_patients.py", pattern: 'apply_scd2|scd2'}
AC3:
  - grep: {file: "patient_360/src/patient_360/silver/transform_patients.py", pattern: 'unity.silver.clinical_patients'}
AC4:
  - grep: {file: "patient_360/src/patient_360/silver/transform_patients.py", pattern: 'se_runner|run_dq'}
AC5:
  - pytest: {node: "patient_360/tests/silver/test_transform_patients_unit.py"}
AC6:
  - file_exists: "patient_360/dq_rules/clinical_patients.yml"
```

## How to Test (User)

### Prerequisites

- EPIC-02 complete (Bronze patient table populated in UC)

### Steps

1. `cd patient_360 && uv run python src/patient_360/silver/transform_patients.py --env dev --ds 2026-04-27`
2. `cd patient_360 && uv run pytest tests/silver/test_transform_patients_unit.py -v`

### Expected outcome

- Step 1 logs `wrote N rows to unity.silver.clinical_patients` with SCD2 columns populated
- Step 2 unit tests pass

## Documentation Updates

- [ ] Update `patient_360/README.md` § "Silver layer" with the transform_patients invocation
