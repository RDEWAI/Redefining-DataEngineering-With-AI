# STORY-08-003: Schedule Delta VACUUM / OPTIMIZE maintenance

| Field | Value |
|-------|-------|
| **Epic** | EPIC-08: Hardening |
| **Story Type** | hardening |
| **Priority** | P2 |
| **Story Points** | 2 |
| **Sprint** | 12 |
| **Dependencies** | STORY-08-002 |
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

As a data engineer, I want have weekly VACUUM + OPTIMIZE Airflow DAGs that maintain Delta tables at the LLD-stated thresholds so that small-file proliferation (LLD §10.3) is prevented and time-travel retention windows hold.

## Description

Author `airflow/dags/maintenance_weekly.py` running `OPTIMIZE` + `VACUUM RETAIN 168 HOURS` across all Bronze + Silver tables on a weekly schedule. Per LLD §3.1 (vacuum 168h) + §10.3 (small file proliferation alert).

## Acceptance Criteria


- [ ] `maintenance_weekly` DAG exists and schedules `0 2 * * SUN` [LLD §3.1, §10.3]

- [ ] DAG runs `OPTIMIZE` + `VACUUM RETAIN 168 HOURS` on every Bronze + Silver table [LLD §3.1]

- [ ] File-count metric `storage.delta_file_count` < 1000 per table after run [LLD §10.3]


## Technical Notes

- **Upstream references**: LLD §3.1, §10.3
- **Implementation hints**: Use a generated task per table via a small factory.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §3.1 Storage, §10.3 Alerts |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Smoke | maintenance DAG parses | pytest patient_360/tests/maintenance/test_dag_unit.py |



## Verification

```yaml
AC1:
  - file_exists: "patient_360/airflow/dags/maintenance_weekly.py"
  - grep: {file: "patient_360/airflow/dags/maintenance_weekly.py", pattern: '0 2 \* \* SUN|@weekly'}
AC2:
  - grep: {file: "patient_360/airflow/dags/maintenance_weekly.py", pattern: "OPTIMIZE|VACUUM RETAIN 168"}
AC3:
  - manual: "Run DAG and inspect Grafana storage.delta_file_count"
```


## How to Test (User)

### Prerequisites


- STORY-08-002 done


### Steps


1. `docker compose exec airflow airflow dags trigger maintenance_weekly`


### Expected outcome


- DAG runs to success; file counts drop


## Documentation Updates


- [ ] Update patient_360/docs/runbooks/maintenance.md with VACUUM/OPTIMIZE cadence

