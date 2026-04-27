# STORY-04-001: Implement transform_encounters_silver (FK hub)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts Layer |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 3 |
| **Dependencies** | STORY-03-004 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want `transform_encounters_silver` implemented so that the FK hub for 8 dependent fact transforms is available with inline SE validation and FK joins to all 4 SCD2 dims.

## Description

Implement `patient_360/src/patient_360/silver/transform_encounters.py` reading `unity.bronze.synthea_encounters`, joining to current dim versions (broadcast small dims, filter `is_current=true` per LLD §6.2), applying STM Bronze-to-Silver derived fields, running inline SE row_dq+agg_dq via `dq_rules/clinical_encounters.yml`, and writing to `unity.silver.clinical_encounters`. `empty_input_behavior: fail` — encounters required.

## Acceptance Criteria

- [ ] `patient_360/src/patient_360/silver/transform_encounters.py` exists [LLD §5.2]
- [ ] Joins to 3 dims (`clinical_patients`, `reference_organizations`, `reference_providers`) with `is_current=true` filter [LLD §5.2, §6.2]
- [ ] Inline SE invoked with `dq_rules/clinical_encounters.yml` (DQ-FLD-060..065) [DQS §2]
- [ ] Writes to `unity.silver.clinical_encounters` [LLD §5.2]
- [ ] Fails on empty Bronze [LLD §5.2]
- [ ] `patient_360/dq_rules/clinical_encounters.yml` present [DQS §2]

## Technical Notes

- **Upstream references**: LLD §5.2 (Silver fact dependencies), §6.2 (broadcast joins), STM Bronze-to-Silver encounters, DQS §2 DQ-FLD-060..065
- **Implementation hints**: Use `broadcast()` on each dim; filter dim by `is_current=true` before broadcast.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §5.2, §6.2, §8.6.1 |
| DMS | §4 Silver clinical_encounters |
| STM | Bronze-to-Silver encounters |
| DQS | §2 DQ-FLD-060..065 |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | join + transform + SE wiring | `pytest patient_360/tests/silver/test_transform_encounters_unit.py` |

## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/silver/transform_encounters.py"
AC2:
  - grep_count: {file: "patient_360/src/patient_360/silver/transform_encounters.py", pattern: 'broadcast\(', equals: 3}
  - grep: {file: "patient_360/src/patient_360/silver/transform_encounters.py", pattern: 'is_current'}
AC3:
  - grep: {file: "patient_360/src/patient_360/silver/transform_encounters.py", pattern: 'se_runner|run_dq'}
AC4:
  - grep: {file: "patient_360/src/patient_360/silver/transform_encounters.py", pattern: 'unity.silver.clinical_encounters'}
AC5:
  - pytest: {node: "patient_360/tests/silver/test_transform_encounters_unit.py"}
AC6:
  - file_exists: "patient_360/dq_rules/clinical_encounters.yml"
```

## How to Test (User)

### Prerequisites

- EPIC-03 complete (4 Silver dims populated)

### Steps

1. `cd patient_360 && uv run python src/patient_360/silver/transform_encounters.py --env dev --ds 2026-04-27`
2. `cd patient_360 && uv run pytest tests/silver/test_transform_encounters_unit.py -v`

### Expected outcome

- Step 1: logs `wrote N rows to unity.silver.clinical_encounters`
- Step 2: unit tests pass

## Documentation Updates

- [ ] Update `patient_360/README.md` § "Silver layer" with `transform_encounters` invocation and dim dependencies
