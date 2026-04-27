# STORY-07-003: DEV→STAGING→PROD promotion runbook + full-pipeline E2E load test

| Field | Value |
|-------|-------|
| **Epic** | EPIC-07: Release & CI/CD |
| **Story Type** | release |
| **Priority** | P1 |
| **Story Points** | 3 |
| **Sprint** | 5 |
| **Dependencies** | STORY-07-001, STORY-07-002 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want a single promotion runbook + a full-pipeline E2E load test so that deploying to STAGING/PROD is repeatable and meets SLA.

## Description

Author `patient_360/_infra/cd/promote.md` runbook describing the merge → DEV run → STAGING test → PROD deploy flow per LLD §9.3. Implement `patient_360/tests/integration/test_e2e_load.py` triggering `patient360_hourly_v1` end-to-end and asserting: critical-path runtime ≤ 30 min per LLD §4.4, all 3 reconciliations pass, all 3 Gold tables populated, DQ pass rate ≥ threshold.

## Acceptance Criteria

- [ ] `patient_360/_infra/cd/promote.md` runbook exists with DEV/STAGING/PROD steps [LLD §9.3]
- [ ] `patient_360/tests/integration/test_e2e_load.py` exercises full DAG end-to-end [LLD §4.4, §9.3]
- [ ] E2E test asserts critical-path runtime ≤ 30 min on STAGING [LLD §4.4]
- [ ] E2E test asserts patient_summary row count = 5,767 and all 3 reconciliations pass [DQS §4]

## Technical Notes

- **Upstream references**: LLD §4.4 (critical path), §9.3 (promotion process)
- **Implementation hints**: Use `pytest -m integration` with a longer timeout. Capture wall-clock per task.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §4.4, §9.3 |
| DMS | — |
| STM | — |
| DQS | §4 |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Integration | E2E DAG runs and meets SLA | `pytest -m integration patient_360/tests/integration/test_e2e_load.py` |
| Smoke | Promotion runbook present | `test -f patient_360/_infra/cd/promote.md` |

## Verification

```yaml
AC1:
  - file_exists: "patient_360/_infra/cd/promote.md"
  - grep: {file: "patient_360/_infra/cd/promote.md", pattern: 'STAGING|PROD'}
AC2:
  - file_exists: "patient_360/tests/integration/test_e2e_load.py"
  - pytest: {node: "patient_360/tests/integration/test_e2e_load.py", marker: "integration"}
AC3:
  - grep: {file: "patient_360/tests/integration/test_e2e_load.py", pattern: 'critical_path|runtime|1800|30'}
AC4:
  - grep: {file: "patient_360/tests/integration/test_e2e_load.py", pattern: '5767|patient_summary'}
```

## How to Test (User)

### Prerequisites

- STORY-07-001, STORY-07-002 complete
- STAGING config reachable

### Steps

1. `cat patient_360/_infra/cd/promote.md`
2. `cd patient_360 && uv run pytest -m integration tests/integration/test_e2e_load.py -v`

### Expected outcome

- Step 1: full STAGING/PROD runbook readable
- Step 2: E2E test passes within 30 min; row count + reconciliation assertions green

## Documentation Updates

- [ ] Update `patient_360/_infra/cd/promote.md` § "STAGING test", § "PROD deploy"
- [ ] Update `patient_360/README.md` § "Releasing to STAGING/PROD" linking to the runbook
- [ ] Update top-level `chapter-5/README.md` § "Release process"
