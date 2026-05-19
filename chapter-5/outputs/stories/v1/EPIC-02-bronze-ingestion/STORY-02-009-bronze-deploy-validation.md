# STORY-02-009: Deploy validation: apply Liquibase Bronze changelogs locally + DAG deploy smoke

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion |
| **Story Type** | deploy-validation |
| **Priority** | P2 |
| **Story Points** | 3 |
| **Sprint** | 5 |
| **Dependencies** | STORY-02-008 |
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

As a data engineer, I want apply 13 Bronze Liquibase changelogs locally and verify the DAG redeploys cleanly so that we have a repeatable per-layer deploy gate that exercises LLD §9.1 / §9.3 before integration with system-wide CI.

## Description

Run `liquibase update` against local Postgres (Marquez backing DB used as a local target) to apply the 13 Bronze changelogs, then redeploy the DAG via `_infra/cd/airflow-sync.sh` and re-trigger `patient360_hourly_v1`. Verify Liquibase changelog table records all 13 changesets and the DAG run completes producing path-based Delta outputs under `${PATIENT360_PROJECT_ROOT}/warehouse/{env}/bronze/`. **No UC-managed write expectations** — Bronze writes are path-based Delta per LLD §13 Decision 15 (revoked 2026-05-12); the deploy smoke must not assert against `unity.bronze.*` catalog entries.

## Acceptance Criteria


- [ ] `liquibase update --changelog-file=master-changelog.xml` succeeds locally and registers 13 Bronze changesets [LLD §9.1]

- [ ] `_infra/cd/airflow-sync.sh` re-syncs the DAG and Airflow `dags list-import-errors` reports none [LLD §9.1, §9.3]

- [ ] Re-triggered DAG run completes successfully end-to-end and produces path-based Delta outputs under `${PATIENT360_PROJECT_ROOT}/warehouse/{env}/bronze/synthea_*/_delta_log/`; deploy smoke does **NOT** assert UC-managed write targets [LLD §9.3, §13 Decision 12/15]


## Technical Notes

- **Upstream references**: LLD §9.1, §9.3
- **Implementation hints**: Use the Liquibase Docker image; point at the local Postgres in docker-compose. The airflow-sync script can be a `make` target that copies dags into the airflow container.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §9.1 Scaffold Infra, §9.3 Promotion |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Deploy smoke | Liquibase apply + Airflow re-sync + DAG re-trigger | pytest -m integration patient_360/tests/integration/test_bronze_deploy.py |



## Verification

```yaml
AC1:
  - pytest: {node: "patient_360/tests/integration/test_bronze_deploy.py::test_liquibase_apply", marker: "integration"}
AC2:
  - file_exists: "patient_360/_infra/cd/airflow-sync.sh"
  - pytest: {node: "patient_360/tests/integration/test_bronze_deploy.py::test_airflow_sync_no_errors", marker: "integration"}
AC3:
  - pytest: {node: "patient_360/tests/integration/test_bronze_deploy.py::test_dag_retrigger", marker: "integration"}
  - forbidden_grep: {file: "patient_360/tests/integration/test_bronze_deploy.py", pattern: "unity\\.bronze\\.|/api/2\\.1/unity-catalog/tables", reason: "Bronze writes are path-based Delta per LLD §13 Decision 15 (revoked 2026-05-12); deploy smoke must not assert UC-managed write targets"}
```


## How to Test (User)

### Prerequisites


- STORY-02-008 done


### Steps


1. `cd patient_360 && make liquibase-apply`

2. `bash _infra/cd/airflow-sync.sh`

3. `docker compose exec airflow airflow dags trigger patient360_hourly_v1`


### Expected outcome


- Liquibase reports 13 changesets applied

- Airflow reports no import errors

- DAG run reaches success


## Documentation Updates


- [ ] Update patient_360/_infra/cd/README.md with the Bronze deploy runbook

