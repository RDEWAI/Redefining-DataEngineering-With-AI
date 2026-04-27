# STORY-08-003: Delta VACUUM / OPTIMIZE maintenance DAG

| Field | Value |
|-------|-------|
| **Epic** | EPIC-08: Hardening — Security, Documentation, Maintenance |
| **Story Type** | hardening |
| **Priority** | P2 |
| **Story Points** | 3 |
| **Sprint** | 6 |
| **Dependencies** | STORY-07-003 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want a nightly Delta VACUUM/OPTIMIZE DAG so that storage costs and query performance stay tuned over time, with extended retention preserved for the safety-critical allergy `_error` table.

## Description

Author `patient_360/airflow/dags/patient360_maintenance_v1.py` running nightly: `OPTIMIZE` + `VACUUM RETAIN 168 HOURS` on all Bronze/Silver/Gold tables per LLD §3.4. The `clinical_allergies_error` table uses `VACUUM RETAIN 2160 HOURS` (90 days) per DRD §1.3 / LLD §8.2. Test exercises the DAG against a controlled Delta table.

## Acceptance Criteria

- [ ] `patient_360/airflow/dags/patient360_maintenance_v1.py` schedules nightly maintenance [LLD §3.4]
- [ ] DAG runs `OPTIMIZE` and `VACUUM RETAIN 168 HOURS` on Bronze/Silver/Gold [LLD §3.4]
- [ ] `clinical_allergies_error` uses `VACUUM RETAIN 2160 HOURS` (90 days) [DRD §1.3, LLD §8.2]
- [ ] `patient_360/tests/integration/test_maintenance_dag.py` exercises maintenance against a controlled table [LLD §3.4]

## Technical Notes

- **Upstream references**: LLD §3.4 (retention policy), §8.2 (allergy `_error` extended retention), DRD §1.3
- **Implementation hints**: Loop tables from `contracts/`. Override per-table retention via a small registry.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §3.4, §8.2 |
| DMS | — |
| STM | — |
| DQS | — |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Integration | Maintenance DAG runs and vacuum/optimize succeed on test tables | `pytest -m integration patient_360/tests/integration/test_maintenance_dag.py` |
| Manual | Allergy retention override applied | Inspect DAG logic |

## Verification

```yaml
AC1:
  - file_exists: "patient_360/airflow/dags/patient360_maintenance_v1.py"
  - grep: {file: "patient_360/airflow/dags/patient360_maintenance_v1.py", pattern: 'schedule|@daily|cron'}
AC2:
  - grep: {file: "patient_360/airflow/dags/patient360_maintenance_v1.py", pattern: 'OPTIMIZE'}
  - grep: {file: "patient_360/airflow/dags/patient360_maintenance_v1.py", pattern: 'VACUUM.*168'}
AC3:
  - grep: {file: "patient_360/airflow/dags/patient360_maintenance_v1.py", pattern: '2160|clinical_allergies_error'}
AC4:
  - pytest: {node: "patient_360/tests/integration/test_maintenance_dag.py", marker: "integration"}
```

## How to Test (User)

### Prerequisites

- STORY-07-003 complete

### Steps

1. `cd patient_360 && airflow dags trigger patient360_maintenance_v1`
2. `cd patient_360 && uv run pytest -m integration tests/integration/test_maintenance_dag.py -v`

### Expected outcome

- Step 1: DAG run completes successfully
- Step 2: integration test passes; allergy retention override verified

## Documentation Updates

- [ ] Update `patient_360/airflow/dags/README.md` § "Maintenance DAG" with the schedule and per-table retention overrides
