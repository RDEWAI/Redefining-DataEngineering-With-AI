# STORY-02-005: reconciliation_bronze query_dq task with SE-evidence gate

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion Layer |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 3 |
| **Sprint** | 2 |
| **Dependencies** | STORY-02-004, STORY-02-003 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want a `reconciliation_bronze` task that runs cross-table query_dq AND fails closed when SE didn't actually run, so that silent-DQ failures (Spokane 2026-04-26 regression) are impossible.

## Description

Implement `patient_360/src/patient_360/bronze/reconciliation.py` running cross-table query_dq from DQS §4 (row-count reconciliation, freshness, completeness) AND a mandatory SE-evidence gate per LLD §8.6.1 — `SELECT count(*) FROM unity.bronze.bronze_se_stats WHERE meta_dq_run_id = '${run_id}' AND meta_dq_run_date = '${ds}'` must return ≥ 1 or the task fails-closed with `SE_RUN_MISSING_FOR_DS=<ds>`.

## Acceptance Criteria

- [ ] `patient_360/src/patient_360/bronze/reconciliation.py` runs query_dq from DQS §4 [LLD §5.5, DQS §4]
- [ ] Reconciliation queries `unity.bronze.bronze_se_stats` for current `meta_dq_run_id` [LLD §8.6.1]
- [ ] Task fails-closed with `SE_RUN_MISSING_FOR_DS` when `bronze_se_stats` count = 0 [LLD §8.6.1]
- [ ] `patient_360/tests/bronze/test_reconciliation_unit.py` exercises pass + fail-closed paths [LLD §8.6.1]

## Technical Notes

- **Upstream references**: LLD §5.5 (reconciliation tasks), §8.6.1 (SE run-evidence contract), DQS §4 (cross-table query_dq)
- **Implementation hints**: This task runs **after** all 13 Bronze tasks complete, before Silver. The SE-evidence query is non-negotiable per Decision 16.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §5.5, §8.6.1, Decision 16 |
| DMS | — |
| STM | — |
| DQS | §4 query_dq |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | recon happy + fail-closed paths | `pytest patient_360/tests/bronze/test_reconciliation_unit.py` |
| Integration | recon raises when bronze_se_stats empty | `pytest -m integration patient_360/tests/integration/test_reconciliation_se_gate.py` |

## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/bronze/reconciliation.py"
  - grep: {file: "patient_360/src/patient_360/bronze/reconciliation.py", pattern: 'query_dq|count|reconciliation'}
AC2:
  - grep: {file: "patient_360/src/patient_360/bronze/reconciliation.py", pattern: 'bronze_se_stats'}
  - grep: {file: "patient_360/src/patient_360/bronze/reconciliation.py", pattern: 'meta_dq_run_id'}
AC3:
  - grep: {file: "patient_360/src/patient_360/bronze/reconciliation.py", pattern: 'SE_RUN_MISSING_FOR_DS'}
AC4:
  - pytest: {node: "patient_360/tests/bronze/test_reconciliation_unit.py"}
```

## How to Test (User)

### Prerequisites

- STORY-02-003, STORY-02-004 complete

### Steps

1. `cd patient_360 && uv run pytest tests/bronze/test_reconciliation_unit.py -v`
2. `cd patient_360 && uv run pytest -m integration tests/integration/test_reconciliation_se_gate.py -v`

### Expected outcome

- Step 1: unit tests pass; both pass and fail paths exercised
- Step 2: integration test confirms the task raises when bronze_se_stats is empty for the ds

## Documentation Updates

- [ ] N/A — internal task module; reconciliation behavior surfaces in integration-test runbook (STORY-02-007)
