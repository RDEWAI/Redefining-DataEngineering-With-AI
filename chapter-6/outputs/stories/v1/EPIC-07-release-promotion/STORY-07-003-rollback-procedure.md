# STORY-07-003: Implement rollback procedure (Delta RESTORE + re-run)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-07: Release & Promotion |
| **Story Type** | release |
| **Priority** | P1 |
| **Story Points** | 3 |
| **Sprint** | 11 |
| **Dependencies** | STORY-07-002 |
| **Status** | To Do |

<!--
  Story Type vocabulary (required):
    - build                    → primary construction work
    - performance-optimization → layer-scoped perf tuning (LLD §6); runs BEFORE integration-test
    - integration-test         → triggers layer DAG on local Airflow against Unity Catalog OSS local; validates landed data in UC local
    - deploy-validation        → layer-scoped DDL/DAG/config deploy smoke (optional; only when LLD prescribes it)
    - observability            → layer-scoped lineage/metrics/dashboard wiring
    - release                  → cross-layer promotion/rollback (trailing epic only)
    - hardening                → cross-layer security/docs/maintenance (trailing epic only)
    - runtime-bootstrap        → JDK/Docker/UC catalog/source-data prerequisites (≥1 per backlog, typically EPIC-01)
-->


## User Story

As a data engineer, I want have a documented + scripted rollback that uses Delta RESTORE for instant recovery + pipeline re-run for correctness so that we meet NFR-10 (RTO ≤ 4 hours) and recover from a bad release with a single command.

## Description

Author `_infra/cd/rollback.sh` that performs the LLD §9.4 four-step procedure: detect (parse PagerDuty incident); RESTORE Gold tables to last_good_version; trigger DAG re-run for affected `ds`; verify via reconciliation. Add a runbook `docs/runbooks/rollback.md`.

## Acceptance Criteria


- [ ] `_infra/cd/rollback.sh` performs Delta RESTORE on 3 Gold tables [LLD §9.4]

- [ ] Rollback triggers `airflow dags trigger patient360_hourly_v1 --conf '{"ds": "<ds>"}'` [LLD §9.4]

- [ ] Runbook `docs/runbooks/rollback.md` exists with the 5 LLD §9.4 steps [LLD §9.4]


## Technical Notes

- **Upstream references**: LLD §9.4
- **Implementation hints**: `spark-sql` for RESTORE; `airflow dags trigger` for re-run.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §9.4 Rollback |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Smoke | rollback script executes against synthetic regression | bash _infra/cd/rollback.sh |



## Verification

```yaml
AC1:
  - file_exists: "patient_360/_infra/cd/rollback.sh"
  - grep: {file: "patient_360/_infra/cd/rollback.sh", pattern: "RESTORE TABLE"}
AC2:
  - grep: {file: "patient_360/_infra/cd/rollback.sh", pattern: "airflow dags trigger"}
AC3:
  - file_exists: "patient_360/docs/runbooks/rollback.md"
```


## How to Test (User)

### Prerequisites


- STORY-07-002 done


### Steps


1. `bash _infra/cd/rollback.sh --ds 2026-05-09 --dry-run`


### Expected outcome


- Dry-run prints intended RESTORE statements


## Documentation Updates


- [ ] Add patient_360/docs/runbooks/rollback.md with the 5-step procedure

- [ ] Update patient_360/README.md § "Rollback" with the runbook link

