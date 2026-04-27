# STORY-07-004: Rollback runbook — Delta RESTORE + re-run procedure

| Field | Value |
|-------|-------|
| **Epic** | EPIC-07: Release & CI/CD |
| **Story Type** | release |
| **Priority** | P2 |
| **Story Points** | 3 |
| **Sprint** | 5 |
| **Dependencies** | STORY-07-003 |
| **Status** | To Do |

## User Story

As a Data Engineer on-call, I want a tested rollback runbook so that a bad pipeline run can be reverted via Delta RESTORE in minutes rather than hours.

## Description

Author `patient_360/_infra/cd/rollback.md` per LLD §9.4 — detection (Grafana + PagerDuty), immediate recovery (Delta RESTORE on Gold tables to last good version), root cause review, correctness re-run with `airflow dags trigger ... --conf '{"ds": "<ds>"}'`. Add `patient_360/tests/integration/test_rollback_smoke.py` exercising the RESTORE step against a controlled Gold version.

## Acceptance Criteria

- [ ] `patient_360/_infra/cd/rollback.md` runbook exists per LLD §9.4 [LLD §9.4]
- [ ] Runbook covers: detection, Delta RESTORE, RCA, re-run, notification [LLD §9.4]
- [ ] `patient_360/tests/integration/test_rollback_smoke.py` exercises Delta RESTORE [LLD §9.4]
- [ ] Time-to-recovery measured ≤ 15 min per LLD §9.4 [LLD §9.4]

## Technical Notes

- **Upstream references**: LLD §9.4 (rollback procedure), §9.2 (env definitions), §10.3 (alerting)
- **Implementation hints**: Use `RESTORE TABLE ... TO VERSION AS OF N`. Time-travel window is 168h.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §9.2, §9.4, §10.3 |
| DMS | — |
| STM | — |
| DQS | — |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Integration | Delta RESTORE rolls back a Gold table to prior version | `pytest -m integration patient_360/tests/integration/test_rollback_smoke.py` |
| Manual | Runbook readable + complete | Review `patient_360/_infra/cd/rollback.md` |

## Verification

```yaml
AC1:
  - file_exists: "patient_360/_infra/cd/rollback.md"
AC2:
  - grep: {file: "patient_360/_infra/cd/rollback.md", pattern: 'RESTORE TABLE'}
  - grep: {file: "patient_360/_infra/cd/rollback.md", pattern: 'detection|RCA|re-run|notification'}
AC3:
  - file_exists: "patient_360/tests/integration/test_rollback_smoke.py"
  - pytest: {node: "patient_360/tests/integration/test_rollback_smoke.py", marker: "integration"}
AC4:
  - manual: "measure time from Grafana alert to Gold rollback completion ≤ 15 min in a controlled drill"
```

## How to Test (User)

### Prerequisites

- STORY-07-003 complete

### Steps

1. `cat patient_360/_infra/cd/rollback.md`
2. `cd patient_360 && uv run pytest -m integration tests/integration/test_rollback_smoke.py -v`
3. Run a controlled rollback drill: trigger a bad Gold write, then follow runbook steps 1-5

### Expected outcome

- Step 1: full rollback procedure readable
- Step 2: smoke test passes
- Step 3: drill completes within 15 min wall-clock

## Documentation Updates

- [ ] Update `patient_360/_infra/cd/rollback.md` § "Drill log" with the most recent drill date and timing
- [ ] Update `patient_360/README.md` § "Incident response" linking to rollback.md
