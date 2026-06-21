# STORY-04-013: Wire the silver_facts TaskGroup into patient360_hourly_v1

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 3 |
| **Sprint** | 7 |
| **Dependencies** | STORY-03-007, STORY-04-001, STORY-04-002, STORY-04-003, STORY-04-004, STORY-04-005, STORY-04-006, STORY-04-007, STORY-04-008, STORY-04-009 |
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

As a data engineer, I want add the nine `transform_*_silver` fact tasks to the shared `patient360_hourly_v1` Airflow DAG as a `silver_facts` TaskGroup with the correct intra-layer dependencies so that the Silver fact transforms run in the pipeline DAG after the dimensions and before `reconciliation_silver`.

## Description

Extend `patient_360/airflow/dags/patient360_hourly_v1.py` per LLD §4.2 / §4.3 to add a `silver_facts` TaskGroup containing the nine fact tasks `transform_{encounters,conditions,medications,observations,allergies,immunizations,procedures,claims,careplans}_silver`, each a **`SparkSubmitOperator`** submitting the matching `src/patient_360/silver/transform_*.py` module (LLD §4.2 mandates `SparkSubmitOperator` for all Spark tasks — 2026-05-12 pivot). Wire the intra-layer dependencies exactly as LLD §4.2/§4.3 specify: `transform_encounters_silver` depends on `transform_{patients,organizations,providers}_silver`; the seven encounter-dependent facts (`conditions`, `medications`, `observations`, `immunizations`, `procedures`, `claims`, `careplans`) depend on `transform_encounters_silver`; `transform_allergies_silver` depends on `transform_patients_silver`. The Silver dimension tasks are added by STORY-03-007; this story consumes those task IDs as upstreams. `reconciliation_silver` (STORY-04-010) is wired downstream of every task in this group.

## Acceptance Criteria


- [ ] `patient360_hourly_v1.py` defines a `silver_facts` TaskGroup with the nine tasks `transform_{encounters,conditions,medications,observations,allergies,immunizations,procedures,claims,careplans}_silver` [LLD §4.2, §4.3]

- [ ] Intra-layer dependencies wired per LLD §4.2: `transform_encounters_silver` ← `transform_{patients,organizations,providers}_silver`; the seven encounter-dependent facts (`conditions`, `medications`, `observations`, `immunizations`, `procedures`, `claims`, `careplans`) ← `transform_encounters_silver`; `transform_allergies_silver` ← `transform_patients_silver` [LLD §4.2, §4.3]

- [ ] Each silver-fact task is a **`SparkSubmitOperator`** (NOT `PythonOperator`) submitting the matching `src/patient_360/silver/transform_*.py` module [LLD §4.2]

- [ ] `developer-plugin:validate-dag` passes against the rendered DAG with Bronze + Silver-dim + Silver-fact tasks (no import/parse errors) [LLD §2.4]

- [ ] Unit test asserts the nine silver-fact task IDs exist under the `silver_facts` group and the `transform_encounters_silver` upstream/downstream edges match LLD §4.2 [LLD §2.4]


## Technical Notes

- **Upstream references**: LLD §4.2, §4.3
- **Implementation hints**: `transform_encounters_silver` is the fan-in/fan-out hub — set its upstream to the three dimension tasks from `silver_dimensions` (STORY-03-007) and its downstream to the seven encounter-dependent facts. `transform_allergies_silver` attaches to `transform_patients_silver`, not encounters. Hand-wire each task (no factory — Decision 8 scopes the factory to Bronze).

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §4.2 Task Inventory (silver_facts), §4.3 DAG Dependency Diagram |

| STM | Tab:Bronze-to-Silver (9 fact tables) |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Unit | DAG parses and exposes the 9 silver-fact tasks with correct encounters edges | pytest patient_360/tests/silver/test_dag_unit.py |



## Verification

```yaml
AC1:
  - file_exists: "patient_360/airflow/dags/patient360_hourly_v1.py"
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "silver_facts"}
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "transform_encounters_silver"}
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "transform_careplans_silver"}
AC2:
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "transform_allergies_silver"}
AC3:
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "SparkSubmitOperator"}
  - forbidden_grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: 'PythonOperator\([^)]*transform_\w+_silver', reason: "silver transform tasks must be SparkSubmitOperator per LLD §4.2 (2026-05-12 pivot)"}
AC4:
  - pytest: {node: "patient_360/tests/silver/test_dag_unit.py"}
AC5:
  - pytest: {node: "patient_360/tests/silver/test_dag_unit.py::test_silver_fact_task_edges"}
```


## How to Test (User)

### Prerequisites


- STORY-03-007 done (silver_dimensions group exists); STORY-04-001 … STORY-04-009 done

- Local Airflow up via `make dev-up`


### Steps


1. `cd patient_360 && uv run pytest tests/silver/test_dag_unit.py -v`

2. `docker compose exec airflow airflow tasks list patient360_hourly_v1 | grep -E 'transform_(conditions|encounters|careplans)_silver'`


### Expected outcome


- Tests pass; DAG imports without error

- Airflow CLI lists the 9 `transform_*_silver` fact tasks under the `silver_facts` group with encounters as the join hub


## Documentation Updates


- [ ] N/A — DAG wiring covered by the layer integration test (STORY-04-012) run instructions
