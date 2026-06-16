# STORY-04-010: Implement reconciliation_silver task (cross-table query_dq)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 3 |
| **Sprint** | 7 |
| **Dependencies** | STORY-04-001, STORY-04-002, STORY-04-003, STORY-04-004, STORY-04-005, STORY-04-006, STORY-04-007, STORY-04-008, STORY-04-009, STORY-04-013 |
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

As a data engineer, I want run cross-table reconciliation after all Silver tasks complete so that we have a fail-closed gate proving Silver row counts match Bronze + FK orphans = 0 + SCD2 sane.

## Description

Wire `reconciliation_silver` task per LLD §5.5 — runs query_dq rules from DQS §4: row count reconciliation Bronze→Silver, FK orphan checks, SCD2 version-count sanity. Fails-closed when `silver_se_stats` is empty for the current `ds` (LLD §8.6.1).

## Acceptance Criteria


- [ ] `reconciliation_silver` task runs after all Silver fact + dim tasks per LLD §4.2 / §4.3 [LLD §4.2]

- [ ] Executes query_dq rules from DQS §4 (row count, FK orphans, SCD2 version sanity) [DQS §4, LLD §5.5]

- [ ] Fails-closed when `silver_se_stats` has 0 rows for the run's `meta_dq_run_id` (LLD §8.6.1) [LLD §8.6.1]


## Technical Notes

- **Upstream references**: LLD §4.2, §5.5, §8.6.1; DQS §4
- **Implementation hints**: Reuse `utils/reconciliation.py` (STORY-01-010) — pass layer='silver'.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §5.5 Reconciliation, §8.6.1 SE run-evidence |

| DQS | §4 query_dq rules |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Unit | reconciliation_silver query construction | pytest patient_360/tests/silver/test_reconciliation_unit.py |



## Verification

```yaml
AC1:
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "reconciliation_silver"}
AC2:
  - grep: {file: "patient_360/src/patient_360/utils/reconciliation.py", pattern: "silver|FK orphan|version"}
AC3:
  - grep: {file: "patient_360/src/patient_360/utils/reconciliation.py", pattern: "silver_se_stats"}
```


## How to Test (User)

### Prerequisites


- All silver fact stories done


### Steps


1. `cd patient_360 && uv run pytest tests/silver/test_reconciliation_unit.py -v`


### Expected outcome


- Tests pass


## Documentation Updates


- [ ] N/A — internal task

