# STORY-02-006: Wire Bronze TaskGroup + reconciliation_bronze into the Airflow DAG

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 4 |
| **Dependencies** | STORY-02-002, STORY-02-003, STORY-02-005 |
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

As a data engineer, I want have `airflow/dags/patient360_hourly_v1.py` import the factory and render the Bronze TaskGroup + reconciliation so that Bronze runs end-to-end on the local Airflow with reconciliation checking the SE-RUN-EVIDENCE invariant.

## Description

Author `patient_360/airflow/dags/patient360_hourly_v1.py` per LLD §4. The DAG calls `build_bronze_taskgroup(dag, 'airflow/configs')` then a `reconciliation_bronze` PythonOperator that runs the SE run-evidence query (LLD §8.6.1) — fail-closed when `bronze_se_stats` has 0 rows for the current `meta_dq_run_id`. Schedule = `0 * * * *`, `max_active_runs=1`, `concurrency=16`.

## Acceptance Criteria


- [ ] DAG file `patient360_hourly_v1.py` exists with `dag_id='patient360_hourly_v1'`, schedule `0 * * * *` [LLD §4.1]

- [ ] DAG calls `build_bronze_taskgroup(dag, 'airflow/configs')` to render the 13-task Bronze TaskGroup [LLD §4.2]

- [ ] `reconciliation_bronze` task runs after Bronze TaskGroup and queries `bronze_se_stats` per LLD §8.6.1 [LLD §5.5, §8.6.1]

- [ ] `max_active_runs=1`, `concurrency=16`, `catchup=True`, `default_timeout=60` per LLD §4.1 [LLD §4.1]

- [ ] `developer-plugin:validate-dag` passes against the rendered DAG [LLD §2.4]


## Technical Notes

- **Upstream references**: LLD §4.1, §4.2, §5.5, §8.6.1
- **Implementation hints**: Use Airflow 3.2.1 syntax (`@dag` decorator). The reconciliation task should accept the run's `{{ ts_nodash }}` to derive `meta_dq_run_id`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §4.1 DAG Config, §4.2 Tasks, §5.5 Reconciliation, §8.6.1 SE-RUN-EVIDENCE |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Unit | DAG parses and exposes 14 Bronze tasks | pytest patient_360/tests/bronze/test_dag_unit.py |



## Verification

```yaml
AC1:
  - file_exists: "patient_360/airflow/dags/patient360_hourly_v1.py"
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "patient360_hourly_v1"}
AC2:
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "build_bronze_taskgroup"}
AC3:
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "reconciliation_bronze"}
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "bronze_se_stats"}
AC4:
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "max_active_runs.*1"}
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "concurrency.*16"}
AC5:
  - pytest: {node: "patient_360/tests/bronze/test_dag_unit.py"}
```


## How to Test (User)

### Prerequisites


- STORY-02-002 / -02-003 / -02-005 done

- Local Airflow up via `make dev-up`


### Steps


1. `cd patient_360 && uv run pytest tests/bronze/test_dag_unit.py -v`

2. `docker compose exec airflow airflow dags list | grep patient360_hourly_v1`


### Expected outcome


- Tests pass; DAG imports without error

- Airflow CLI lists `patient360_hourly_v1`


## Documentation Updates


- [ ] Update patient_360/README.md § "Run the pipeline" with the DAG trigger command

