# STORY-03-002: Implement transform_organizations / providers / payers silver (SCD2)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-03: Silver Dimensions Layer (SCD Type 2) |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 8 |
| **Sprint** | 3 |
| **Dependencies** | STORY-03-001 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want the remaining 3 SCD2 dimensions (organizations, providers, payers) implemented so that all FK dimensions for facts and Gold are versioned and DQ-validated.

## Description

Implement `transform_organizations.py`, `transform_providers.py`, `transform_payers.py` under `patient_360/src/patient_360/silver/` — each follows the STORY-03-001 pattern (read Bronze → STM transforms → SCD2 MERGE → SE row_dq+agg_dq → write `unity.silver.reference_<dim>`). Generate corresponding `dq_rules/reference_{organizations,providers,payers}.yml`. All three are critical FK dimensions per LLD §5.2 — `empty_input_behavior: fail`.

## Acceptance Criteria

- [ ] 3 transform modules exist: `transform_organizations.py`, `transform_providers.py`, `transform_payers.py` [LLD §5.2]
- [ ] Each writes to `unity.silver.reference_<dim>` via SCD2 MERGE [LLD §5.2, DMS §6]
- [ ] Each invokes `se_runner.run_dq` with `dq_rules/reference_<dim>.yml` [DQS §2]
- [ ] Each fails on empty Bronze input (FK dim — required) [LLD §5.2]
- [ ] 3 DQ rule YAMLs exist under `patient_360/dq_rules/reference_*.yml` [DQS §2]

## Technical Notes

- **Upstream references**: LLD §5.2 (Silver tasks: providers, payers, organizations), DMS §4 (Silver reference schemas), §6 (SCD2), DQS §2 (DQ-FLD-095..101)
- **Implementation hints**: All three use the same SCD2 pattern as STORY-03-001 — broadcast-eligible (small dims). Factor any duplicated boilerplate into `silver/_dim_base.py` if it appears.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §5.2, §8.6.1 |
| DMS | §4 Silver reference, §6 SCD2 |
| STM | Bronze-to-Silver organizations/providers/payers |
| DQS | §2 DQ-FLD-095..101 |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | each transform's SCD2 + SE wiring | `pytest patient_360/tests/silver/test_transform_dims_unit.py` |
| Contract | 3 dq_rules YAMLs present | `ls patient_360/dq_rules/reference_*.yml \| wc -l` (expect 3) |

## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/silver/transform_organizations.py"
  - file_exists: "patient_360/src/patient_360/silver/transform_providers.py"
  - file_exists: "patient_360/src/patient_360/silver/transform_payers.py"
AC2:
  - grep_count: {glob: "patient_360/src/patient_360/silver/transform_{organizations,providers,payers}.py", pattern: 'unity.silver.reference_', equals: 3}
AC3:
  - grep_count: {glob: "patient_360/src/patient_360/silver/transform_{organizations,providers,payers}.py", pattern: 'se_runner|run_dq', equals: 3}
AC4:
  - manual: "verify each transform raises when input DataFrame is empty"
AC5:
  - file_count: {glob: "patient_360/dq_rules/reference_*.yml", equals: 3}
```

## How to Test (User)

### Prerequisites

- STORY-03-001 complete

### Steps

1. `cd patient_360 && for dim in organizations providers payers; do uv run python src/patient_360/silver/transform_${dim}.py --env dev --ds 2026-04-27; done`
2. `cd patient_360 && uv run pytest tests/silver/test_transform_dims_unit.py -v`

### Expected outcome

- Step 1: each invocation logs `wrote N rows to unity.silver.reference_<dim>`
- Step 2: all unit tests pass

## Documentation Updates

- [ ] N/A — internal layer modules; user-facing docs come from EPIC-03 integration test
