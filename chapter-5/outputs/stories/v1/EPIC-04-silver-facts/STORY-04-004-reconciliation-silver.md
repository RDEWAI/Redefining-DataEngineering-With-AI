# STORY-04-004: reconciliation_silver query_dq + SE-evidence gate

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts Layer |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 3 |
| **Sprint** | 4 |
| **Dependencies** | STORY-04-002, STORY-04-003 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want a `reconciliation_silver` task running cross-table query_dq AND a Silver SE-evidence gate so that Bronze→Silver row-count reconciliation, FK orphan checks, and SCD2 sanity are enforced before Gold runs.

## Description

Implement `patient_360/src/patient_360/silver/reconciliation.py` running DQS §4 query_dq (Bronze vs Silver row counts, FK orphans, SCD2 version count sanity). Adds the SE-evidence gate per LLD §8.6.1 — `SELECT count(*) FROM unity.silver.silver_se_stats WHERE meta_dq_run_id = '${run_id}' AND meta_dq_run_date = '${ds}'` must return ≥ 13 (one per Silver table — 4 dims + 9 facts) or fail-closed with `SE_RUN_MISSING_FOR_DS`.

## Acceptance Criteria

- [ ] `patient_360/src/patient_360/silver/reconciliation.py` runs query_dq from DQS §4 [LLD §5.5, DQS §4]
- [ ] Reconciliation queries `unity.silver.silver_se_stats` for run's `meta_dq_run_id` [LLD §8.6.1]
- [ ] Task fails-closed with `SE_RUN_MISSING_FOR_DS` when expected SE row count not met [LLD §8.6.1]
- [ ] FK orphan rate < 0.1% asserted per DQS §4 [DQS §4]
- [ ] `patient_360/tests/silver/test_reconciliation_silver_unit.py` exercises pass + fail-closed paths [LLD §8.6.1]

## Technical Notes

- **Upstream references**: LLD §5.5, §8.6.1, DQS §4 query_dq cross-table checks
- **Implementation hints**: Mirror Bronze reconciliation pattern; expand the SE-evidence query to Silver.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §5.5, §8.6.1 |
| DMS | §4 Silver |
| STM | — |
| DQS | §4 query_dq |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | recon happy + fail-closed paths | `pytest patient_360/tests/silver/test_reconciliation_silver_unit.py` |

## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/silver/reconciliation.py"
  - grep: {file: "patient_360/src/patient_360/silver/reconciliation.py", pattern: 'query_dq|reconciliation'}
AC2:
  - grep: {file: "patient_360/src/patient_360/silver/reconciliation.py", pattern: 'silver_se_stats'}
  - grep: {file: "patient_360/src/patient_360/silver/reconciliation.py", pattern: 'meta_dq_run_id'}
AC3:
  - grep: {file: "patient_360/src/patient_360/silver/reconciliation.py", pattern: 'SE_RUN_MISSING_FOR_DS'}
AC4:
  - grep: {file: "patient_360/src/patient_360/silver/reconciliation.py", pattern: 'orphan|fk'}
AC5:
  - pytest: {node: "patient_360/tests/silver/test_reconciliation_silver_unit.py"}
```

## How to Test (User)

### Prerequisites

- STORY-04-002, STORY-04-003 complete

### Steps

1. `cd patient_360 && uv run pytest tests/silver/test_reconciliation_silver_unit.py -v`

### Expected outcome

- All unit tests pass; both pass and fail-closed paths exercised

## Documentation Updates

- [ ] N/A — internal task module
