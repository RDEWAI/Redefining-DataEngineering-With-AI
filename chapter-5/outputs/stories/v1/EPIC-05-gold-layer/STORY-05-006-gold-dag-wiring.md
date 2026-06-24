# STORY-05-006: Wire the gold_build TaskGroup + reconciliation_gold into patient360_hourly_v1

| Field | Value |
|-------|-------|
| **Epic** | EPIC-05: Gold Consumer Tables |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 3 |
| **Sprint** | 8 |
| **Dependencies** | STORY-04-010, STORY-05-001, STORY-05-002, STORY-05-003 |
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

As a data engineer, I want add the three `build_*_gold` consumer-table tasks plus `reconciliation_gold` to the shared `patient360_hourly_v1` Airflow DAG as a `gold_build` TaskGroup downstream of `reconciliation_silver` so that the Gold layer runs in the pipeline DAG and the layer integration test has tasks to trigger.

## Description

Extend `patient_360/airflow/dags/patient360_hourly_v1.py` per LLD §4.2 / §4.3 to add a `gold_build` TaskGroup containing the three consumer-table tasks `build_patient_summary_gold`, `build_clinical_history_gold`, `build_billing_summary_gold`, each a **`SparkSubmitOperator`** that submits the matching `src/patient_360/gold/build_*.py` module (LLD §4.2 mandates `SparkSubmitOperator` for all Spark tasks — 2026-05-12 pivot). All three gold tasks depend on `reconciliation_silver` (the Silver→Gold gate). Then wire `reconciliation_gold` downstream of all three gold tasks, reusing `utils/reconciliation.py` with `layer='gold'` (same pattern as `reconciliation_silver`, STORY-04-010) — it runs the DQS §4 query_dq checks (silver→gold row-count reconciliation, patient completeness = 5,767 per NFR-4, allergy completeness DQ-FLD-138) and fails-closed when `gold_se_stats` is empty for the run (LLD §8.6.1). The downstream `emit_lineage` / `emit_metrics` observability tasks (EPIC-06) attach to `reconciliation_gold` and are out of scope here.

## Acceptance Criteria


- [ ] `patient360_hourly_v1.py` defines a `gold_build` TaskGroup with the three tasks `build_patient_summary_gold`, `build_clinical_history_gold`, `build_billing_summary_gold` [LLD §4.2, §4.3]

- [ ] Each gold build task is a **`SparkSubmitOperator`** (NOT `PythonOperator`) submitting the matching `src/patient_360/gold/build_*.py` module, and all three run downstream of `reconciliation_silver` [LLD §4.2, §4.3]

- [ ] `reconciliation_gold` runs after all three gold tasks, executing the DQS §4 query_dq checks (silver→gold row-count reconciliation, patient completeness, allergy completeness) and fails-closed when `gold_se_stats` is empty for the run [LLD §4.2, §5.5, §8.6.1; DQS §4]

- [ ] `developer-plugin:validate-dag` passes against the full DAG (Bronze → Silver → Gold) with no import/parse errors [LLD §2.4]

- [ ] Unit test asserts the DAG exposes the three gold task IDs under `gold_build` with `reconciliation_silver` upstream, and `reconciliation_gold` downstream of all three [LLD §2.4]


## Technical Notes

- **Upstream references**: LLD §4.2, §4.3, §5.5, §8.6.1; DQS §4
- **Implementation hints**: Hand-wire each gold task (no factory — Decision 8 scopes the factory to Bronze). `reconciliation_gold` reuses `utils/reconciliation.py` (STORY-01-010) — pass `layer='gold'`. Set the three `build_*_gold` tasks' upstream to `reconciliation_silver` and `reconciliation_gold`'s upstream to all three gold tasks, matching the §4.3 dependency diagram.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §4.2 Task Inventory (gold_build + reconciliation_gold), §4.3 DAG Dependency Diagram, §5.5 Reconciliation |

| DQS | §4 query_dq rules (gold reconciliation) |

| STM | Tab:Silver-to-Gold (3 consumer tables) |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Unit | DAG parses and exposes the 3 gold tasks + reconciliation_gold with correct edges | pytest patient_360/tests/gold/test_dag_unit.py |



## Verification

```yaml
AC1:
  - file_exists: "patient_360/airflow/dags/patient360_hourly_v1.py"
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "gold_build"}
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "build_patient_summary_gold"}
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "build_billing_summary_gold"}
AC2:
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "SparkSubmitOperator"}
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "reconciliation_silver"}
  - forbidden_grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: 'PythonOperator\([^)]*build_\w+_gold', reason: "gold build tasks must be SparkSubmitOperator per LLD §4.2 (2026-05-12 pivot)"}
AC3:
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "reconciliation_gold"}
  - grep: {file: "patient_360/src/patient_360/utils/reconciliation.py", pattern: "gold"}
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "gold_se_stats"}
AC4:
  - pytest: {node: "patient_360/tests/gold/test_dag_unit.py"}
AC5:
  - pytest: {node: "patient_360/tests/gold/test_dag_unit.py::test_gold_tasks_between_reconciliations"}
```


## How to Test (User)

### Prerequisites


- STORY-04-010 done (reconciliation_silver wired); STORY-05-001 / -05-002 / -05-003 done

- Local Airflow up via `make dev-up`


### Steps


1. `cd patient_360 && uv run pytest tests/gold/test_dag_unit.py -v`

2. `docker compose exec airflow airflow tasks list patient360_hourly_v1 | grep -E '(build_\w+_gold|reconciliation_gold)'`


### Expected outcome


- Tests pass; DAG imports without error

- Airflow CLI lists the 3 `build_*_gold` tasks under `gold_build` plus `reconciliation_gold`


## Documentation Updates


- [ ] N/A — DAG wiring covered by the layer integration test (STORY-05-005) run instructions
