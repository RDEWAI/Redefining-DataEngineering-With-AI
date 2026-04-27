# STORY-05-003: reconciliation_gold query_dq + SE-evidence gate

| Field | Value |
|-------|-------|
| **Epic** | EPIC-05: Gold Consumer Layer |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 3 |
| **Sprint** | 4 |
| **Dependencies** | STORY-05-002 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want a `reconciliation_gold` task that runs Silver→Gold cross-table query_dq, asserts patient completeness (5,767), and a Gold SE-evidence gate so that consumer-table integrity is enforced before clinical access.

## Description

Implement `patient_360/src/patient_360/gold/reconciliation.py` running DQS §4 query_dq (Silver→Gold row counts, patient completeness assertion = 5,767, allergy completeness). Adds the SE-evidence gate per LLD §8.6.1 — `gold_se_stats` must have ≥ 3 rows for the run's `meta_dq_run_id` (one per Gold table) or fail-closed. Allergy completeness failure escalates per DQS §1 to Clinical Ops Director.

## Acceptance Criteria

- [ ] `patient_360/src/patient_360/gold/reconciliation.py` exists [LLD §5.5]
- [ ] Asserts `unity.gold.patient_summary` row count = 5,767 [DQS §4]
- [ ] Queries `unity.gold.gold_se_stats` for current run; fails-closed if < 3 rows [LLD §8.6.1]
- [ ] Allergy completeness failure routes via elevated alert path (PagerDuty + Clinical Ops) [DQS §1, LLD §8.5]
- [ ] `patient_360/tests/gold/test_reconciliation_gold_unit.py` exercises pass + fail-closed paths [LLD §8.6.1]

## Technical Notes

- **Upstream references**: LLD §5.5, §8.5 (alerting elevated for allergies), §8.6.1, DQS §1 (allergy elevated escalation), DQS §4 (Silver→Gold reconciliation)
- **Implementation hints**: Patient completeness assertion is a hard equality (= 5,767) per Synthea fixed seed.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §5.5, §8.5, §8.6.1 |
| DMS | §5 Gold |
| STM | — |
| DQS | §1, §4 |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | recon happy + fail-closed paths | `pytest patient_360/tests/gold/test_reconciliation_gold_unit.py` |

## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/gold/reconciliation.py"
AC2:
  - grep: {file: "patient_360/src/patient_360/gold/reconciliation.py", pattern: '5767|patient_completeness'}
AC3:
  - grep: {file: "patient_360/src/patient_360/gold/reconciliation.py", pattern: 'gold_se_stats'}
  - grep: {file: "patient_360/src/patient_360/gold/reconciliation.py", pattern: 'SE_RUN_MISSING_FOR_DS'}
AC4:
  - grep: {file: "patient_360/src/patient_360/gold/reconciliation.py", pattern: 'allergy|Clinical Ops'}
AC5:
  - pytest: {node: "patient_360/tests/gold/test_reconciliation_gold_unit.py"}
```

## How to Test (User)

### Prerequisites

- STORY-05-002 complete

### Steps

1. `cd patient_360 && uv run pytest tests/gold/test_reconciliation_gold_unit.py -v`

### Expected outcome

- All unit tests pass; both pass and fail-closed paths exercised; allergy escalation path covered

## Documentation Updates

- [ ] N/A — internal task module; user-facing surfaces in EPIC-05 integration test
