# STORY-03-007: Wire the silver_dimensions TaskGroup into patient360_hourly_v1

| Field | Value |
|-------|-------|
| **Epic** | EPIC-03: Silver Dimensions (SCD Type 2) |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 3 |
| **Sprint** | 6 |
| **Dependencies** | STORY-02-006, STORY-03-001, STORY-03-002, STORY-03-003, STORY-03-004 |
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

As a data engineer, I want add the four `transform_*_silver` dimension tasks to the shared `patient360_hourly_v1` Airflow DAG (created in Bronze STORY-02-006) as a `silver_dimensions` TaskGroup downstream of `reconciliation_bronze` so that the Silver dimension transforms actually run inside the pipeline DAG and the layer integration test has tasks to trigger.

## Description

Extend `patient_360/airflow/dags/patient360_hourly_v1.py` per LLD §4.2 / §4.3. The DAG already renders the Bronze TaskGroup + `reconciliation_bronze` (STORY-02-006); this story adds a `silver_dimensions` TaskGroup containing the four SCD2 dimension tasks `transform_{patients,organizations,providers,payers}_silver`, each a **`SparkSubmitOperator`** that submits the matching `src/patient_360/silver/transform_*.py` module. Per LLD §4.2 (2026-05-12 pivot) every Spark-touching task MUST be a `SparkSubmitOperator` (Airflow 3.x embedded PySpark hangs on classloader collisions) — wrap via the project's `spark_submit_wrapper.py`. All four dimension tasks depend on `reconciliation_bronze` and fan out in parallel within the TaskGroup (governed by `max_active_tasks` from LLD §4.1). The Silver dimensions feed the Silver fact wiring (STORY-04-013) and `reconciliation_silver` (STORY-04-010).

## Acceptance Criteria


- [ ] `patient360_hourly_v1.py` defines a `silver_dimensions` TaskGroup with the four tasks `transform_patients_silver`, `transform_organizations_silver`, `transform_providers_silver`, `transform_payers_silver` [LLD §4.2, §4.3]

- [ ] Each silver-dim task is a **`SparkSubmitOperator`** (NOT `PythonOperator`) submitting the matching `src/patient_360/silver/transform_*.py` module [LLD §4.2]

- [ ] All four silver-dim tasks run downstream of `reconciliation_bronze` (set as upstream) per the §4.3 dependency diagram [LLD §4.2, §4.3]

- [ ] `developer-plugin:validate-dag` passes against the rendered DAG with Bronze + Silver-dim tasks (no import/parse errors) [LLD §2.4]

- [ ] Unit test asserts the DAG exposes the four silver-dim task IDs under the `silver_dimensions` group with `reconciliation_bronze` as their upstream [LLD §2.4]


## Technical Notes

- **Upstream references**: LLD §4.1, §4.2, §4.3
- **Implementation hints**: Use Airflow 3.2.1 syntax (`@dag` / `TaskGroup`). Unlike Bronze (factory-generated), the Silver dimension tasks are hand-wired `SparkSubmitOperator`s — one per `transform_*.py` module (Decision 8 scopes the factory to Bronze only). Keep `silver_dimensions` upstream of the (later) `silver_facts` group and `reconciliation_silver`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §4.1 DAG Config, §4.2 Task Inventory (silver_dimensions), §4.3 DAG Dependency Diagram |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Unit | DAG parses and exposes the 4 silver-dim tasks downstream of reconciliation_bronze | pytest patient_360/tests/silver/test_dag_unit.py |



## Verification

```yaml
AC1:
  - file_exists: "patient_360/airflow/dags/patient360_hourly_v1.py"
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "silver_dimensions"}
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "transform_patients_silver"}
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "transform_payers_silver"}
AC2:
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "SparkSubmitOperator"}
  - forbidden_grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: 'PythonOperator\([^)]*transform_\w+_silver', reason: "silver transform tasks must be SparkSubmitOperator per LLD §4.2 (2026-05-12 pivot)"}
AC3:
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "reconciliation_bronze"}
AC4:
  - pytest: {node: "patient_360/tests/silver/test_dag_unit.py"}
AC5:
  - pytest: {node: "patient_360/tests/silver/test_dag_unit.py::test_silver_dim_tasks_downstream_of_reconciliation_bronze"}
```


## How to Test (User)

### Prerequisites


- STORY-02-006 done (DAG + Bronze TaskGroup exists); STORY-03-001 / -03-002 / -03-003 / -03-004 done

- Local Airflow up via `make dev-up`


### Steps


1. `cd patient_360 && uv run pytest tests/silver/test_dag_unit.py -v`

2. `docker compose exec airflow airflow tasks list patient360_hourly_v1 | grep transform_.*_silver`


### Expected outcome


- Tests pass; DAG imports without error

- Airflow CLI lists the 4 `transform_*_silver` dimension tasks under the `silver_dimensions` group


## Documentation Updates


- [ ] N/A — DAG wiring covered by the layer integration test (STORY-03-006) run instructions
