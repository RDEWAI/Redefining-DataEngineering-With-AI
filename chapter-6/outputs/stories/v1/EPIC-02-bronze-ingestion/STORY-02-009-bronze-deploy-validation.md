# STORY-02-009: Deploy validation: apply Bronze .sql DDL migrations locally + DAG deploy smoke

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

As a data engineer, I want apply the 13 Bronze `.sql` DDL migrations locally and verify the DAG redeploys cleanly so that we have a repeatable per-layer deploy gate that exercises LLD §9.1 / §9.3 before integration with system-wide CI.

## Description

Run `make ddl-apply` (beeline applying `ddl/migrations/*.sql` against the `spark-thrift-server` container at `jdbc:hive2://spark-thrift-server:10000/unity`) to **pre-create** the 13 Bronze `unity.bronze.*` EXTERNAL Delta tables per LLD §13 Decision 12, then redeploy the DAG via `_infra/cd/airflow-sync.sh` and re-trigger `patient360_hourly_v1`. Verify the 13 `unity.bronze.synthea_*` tables exist in UC (the migrations are idempotent `CREATE TABLE IF NOT EXISTS`, so a re-apply is a no-op), and the DAG run completes by `insertInto`-ing into those pre-created tables. Bronze writes are `insertInto` per LLD §13 Decision 15 (re-adopted 2026-06-18); the deploy smoke asserts the UC tables exist and are populated, **not** path-based warehouse directories. (Liquibase retired — UPGRADE-NOTES UC 0.5.0 / Spark 4.1.)

## Acceptance Criteria


- [ ] `make ddl-apply` (beeline applying `ddl/migrations/*.sql` against `jdbc:hive2://spark-thrift-server:10000/unity`) succeeds locally — applying all 13 Bronze migrations idempotently and pre-creating the 13 `unity.bronze.synthea_*` EXTERNAL Delta tables [LLD §9.1, §13 Decision 12]

- [ ] `_infra/cd/airflow-sync.sh` re-syncs the DAG and Airflow `dags list-import-errors` reports none [LLD §9.1, §9.3]

- [ ] Re-triggered DAG run completes successfully end-to-end and `insertInto`s the pre-created `unity.bronze.synthea_*` UC tables (each readable via `spark.read.table` and non-empty); deploy smoke asserts UC tables exist, **NOT** path-based warehouse directories [LLD §9.3, §13 Decision 12/15]


## Technical Notes

- **Upstream references**: LLD §9.1, §9.3
- **Implementation hints**: `make ddl-apply` runs `beeline -u jdbc:hive2://spark-thrift-server:10000/unity -f <each ddl/migrations/*.sql>` — the Spark Thrift Server is the SQL endpoint needed to run Delta `CREATE TABLE IF NOT EXISTS ... USING DELTA LOCATION` DDL — after `spark-thrift-server` is healthy. No Liquibase image, no master-changelog. The airflow-sync script can be a `make` target that copies dags into the airflow container.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §9.1 Scaffold Infra, §9.3 Promotion |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Deploy smoke | beeline DDL apply + Airflow re-sync + DAG re-trigger | pytest -m integration patient_360/tests/integration/test_bronze_deploy.py |



## Verification

```yaml
AC1:
  - pytest: {node: "patient_360/tests/integration/test_bronze_deploy.py::test_ddl_apply", marker: "integration"}
AC2:
  - file_exists: "patient_360/_infra/cd/airflow-sync.sh"
  - pytest: {node: "patient_360/tests/integration/test_bronze_deploy.py::test_airflow_sync_no_errors", marker: "integration"}
AC3:
  - pytest: {node: "patient_360/tests/integration/test_bronze_deploy.py::test_dag_retrigger", marker: "integration"}
  - grep: {file: "patient_360/tests/integration/test_bronze_deploy.py", pattern: "unity\\.bronze\\.|ddl-apply|spark-thrift-server"}
  - forbidden_grep: {file: "patient_360/tests/integration/test_bronze_deploy.py", pattern: "warehouse/.*/bronze/.*_delta_log", reason: "Bronze writes are insertInto into beeline-pre-created tables per LLD §13 Decision 12/15 (re-adopted 2026-06-18); deploy smoke asserts UC tables, not path-based warehouse dirs"}
```


## How to Test (User)

### Prerequisites


- STORY-02-008 done


### Steps


1. `cd patient_360 && make ddl-apply`

2. `bash _infra/cd/airflow-sync.sh`

3. `docker compose exec airflow airflow dags trigger patient360_hourly_v1`


### Expected outcome


- `make ddl-apply` applies all 13 Bronze `.sql` migrations and the 13 `unity.bronze.synthea_*` UC tables exist

- Airflow reports no import errors

- DAG run reaches success and the UC tables are populated


## Documentation Updates


- [ ] Update patient_360/_infra/cd/README.md with the Bronze deploy runbook

