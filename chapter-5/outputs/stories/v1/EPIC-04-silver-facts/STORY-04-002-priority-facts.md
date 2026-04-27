# STORY-04-002: Implement 4 high-priority fact transforms (allergies, conditions, medications, observations)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts Layer |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 8 |
| **Sprint** | 4 |
| **Dependencies** | STORY-04-001 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want the 4 high-priority Silver fact transforms (allergies, conditions, medications, observations) implemented so that the safety-critical and clinical fact tables are available for Gold builds.

## Description

Implement `transform_allergies.py`, `transform_conditions.py`, `transform_medications.py`, `transform_observations.py` under `patient_360/src/patient_360/silver/`. Each reads its Bronze source, joins encounters/patients via `is_current=true`, applies STM Bronze-to-Silver transforms, runs inline SE per its `dq_rules/clinical_<table>.yml`, and writes to `unity.silver.clinical_<table>`. `clinical_allergies` MUST use `action_if_failed: fail` per DRD §1.3 (safety-critical).

## Acceptance Criteria

- [ ] 4 transform modules exist: `transform_allergies.py`, `transform_conditions.py`, `transform_medications.py`, `transform_observations.py` [LLD §5.2]
- [ ] Each writes to `unity.silver.clinical_<table>` [LLD §5.2]
- [ ] Each invokes `se_runner.run_dq` with its `dq_rules/clinical_<table>.yml` [DQS §2]
- [ ] `transform_allergies.py` config sets `se_action_if_failed: fail` (safety-critical) [DRD §1.3, LLD §5.2]
- [ ] 4 DQ rule YAMLs exist under `patient_360/dq_rules/clinical_{allergies,conditions,medications,observations}.yml` [DQS §2]

## Technical Notes

- **Upstream references**: LLD §5.2 (Silver tasks for these 4), DRD §1.3 (allergy safety), DQS §2 (DQ-FLD-066..083)
- **Implementation hints**: Pattern shared with encounters; only the source table, contract, and DQ rule file change.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §5.2, §8.6.1 |
| DMS | §4 Silver clinical_{allergies,conditions,medications,observations} |
| STM | Bronze-to-Silver these 4 |
| DQS | §2 DQ-FLD-066..083 |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | each transform's SE+write wiring | `pytest patient_360/tests/silver/test_priority_facts_unit.py` |
| Contract | 4 dq_rules YAMLs present | `ls patient_360/dq_rules/clinical_{allergies,conditions,medications,observations}.yml \| wc -l` (expect 4) |

## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/silver/transform_allergies.py"
  - file_exists: "patient_360/src/patient_360/silver/transform_conditions.py"
  - file_exists: "patient_360/src/patient_360/silver/transform_medications.py"
  - file_exists: "patient_360/src/patient_360/silver/transform_observations.py"
AC2:
  - grep_count: {glob: "patient_360/src/patient_360/silver/transform_{allergies,conditions,medications,observations}.py", pattern: 'unity.silver.clinical_', equals: 4}
AC3:
  - grep_count: {glob: "patient_360/src/patient_360/silver/transform_{allergies,conditions,medications,observations}.py", pattern: 'se_runner|run_dq', equals: 4}
AC4:
  - grep: {file: "patient_360/dq_rules/clinical_allergies.yml", pattern: 'action_if_failed:\s*fail'}
AC5:
  - file_count: {glob: "patient_360/dq_rules/clinical_{allergies,conditions,medications,observations}.yml", equals: 4}
```

## How to Test (User)

### Prerequisites

- STORY-04-001 complete

### Steps

1. `cd patient_360 && for t in allergies conditions medications observations; do uv run python src/patient_360/silver/transform_${t}.py --env dev --ds 2026-04-27; done`
2. `cd patient_360 && uv run pytest tests/silver/test_priority_facts_unit.py -v`

### Expected outcome

- Step 1: each invocation logs `wrote N rows to unity.silver.clinical_<table>`
- Step 2: all unit tests pass

## Documentation Updates

- [ ] Update `patient_360/README.md` § "Silver Facts" listing the 4 priority facts and the safety-critical allergy fail-closed behavior
