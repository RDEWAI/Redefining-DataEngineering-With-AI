# STORY-02-002: Implement Bronze TaskGroup factory + SparkSubmit wrapper

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 3 |
| **Dependencies** | STORY-02-001 |
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

As a data engineer, I want have a TaskGroup factory that scans `airflow/configs/*.yml` and emits one SparkSubmitOperator per file so that Bronze TaskGroup is generated, not hand-coded — adding a 14th source table is one YAML drop.

## Description

Implement `src/patient_360/bronze/ingestion_factory.py` (scans `airflow/configs/*.yml` at DAG parse time, returns an Airflow TaskGroup with one task per file) and `src/patient_360/bronze/spark_submit_wrapper.py` (thin wrapper around SparkSubmitOperator that injects compute params from pipeline config and passes `--config-path`).

## Acceptance Criteria


- [ ] `ingestion_factory.build_bronze_taskgroup(dag, config_dir)` returns a TaskGroup with N tasks (one per YAML) [LLD §2.3, §4.2]

- [ ] `spark_submit_wrapper.py` configures memory/cores/executors from pipeline config and passes `--config-path` [LLD §6.1, §2.3]

- [ ] Unit tests cover empty config dir, single-file dir, and 13-file dir [LLD §2.4]


## Technical Notes

- **Upstream references**: LLD §2.3, §4.2, §6.1
- **Implementation hints**: Use Airflow `TaskGroup` context manager. Glob config_dir for `*.yml`; sort to make task ordering deterministic.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §2.3, §4.2 Bronze TaskGroup, §6.1 |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Unit | factory generates one task per YAML | pytest patient_360/tests/bronze/test_ingestion_factory_unit.py |



## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/bronze/ingestion_factory.py"
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_factory.py", pattern: "TaskGroup"}
AC2:
  - file_exists: "patient_360/src/patient_360/bronze/spark_submit_wrapper.py"
  - grep: {file: "patient_360/src/patient_360/bronze/spark_submit_wrapper.py", pattern: "--config-path"}
AC3:
  - pytest: {node: "patient_360/tests/bronze/test_ingestion_factory_unit.py"}
```


## How to Test (User)

### Prerequisites


- STORY-02-001 done


### Steps


1. `cd patient_360 && uv run pytest tests/bronze/test_ingestion_factory_unit.py -v`


### Expected outcome


- Tests pass for empty / single / 13-file scenarios


## Documentation Updates


- [ ] N/A — internal factory module

