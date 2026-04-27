# STORY-02-002: TaskGroup factory and SparkSubmit wrapper

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion Layer |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 1 |
| **Dependencies** | STORY-02-001 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want a TaskGroup factory and SparkSubmit wrapper so that the Bronze Airflow DAG is generated from per-table YAML configs without per-table Python code.

## Description

Implement `patient_360/src/patient_360/bronze/ingestion_factory.py` exposing `build_bronze_taskgroup(dag, config_dir)` that scans `airflow/configs/*.yml` and emits one task per file using `patient_360/src/patient_360/bronze/spark_submit_wrapper.py` (a thin SparkSubmitOperator wrapper that injects spark conf, jars, and the runner module). Per LLD Decision 8 + 9.

## Acceptance Criteria

- [ ] `patient_360/src/patient_360/bronze/ingestion_factory.py` exposes `build_bronze_taskgroup(dag, config_dir)` [LLD §2.3, Decision 8]
- [ ] `patient_360/src/patient_360/bronze/spark_submit_wrapper.py` exposes a SparkSubmitOperator wrapper [LLD §2.3, Decision 9]
- [ ] Factory produces one task per YAML config in `airflow/configs/*.yml` [LLD §4.2]
- [ ] `patient_360/tests/bronze/test_ingestion_factory_unit.py` asserts task count = config-file count [LLD §4.2]

## Technical Notes

- **Upstream references**: LLD §2.3, §4.2 task inventory, Decision 8 (TaskGroup factory), Decision 9 (SparkSubmitOperator wrapper)
- **Implementation hints**: Pin retries=3, retry_delay_seconds=60 with exponential backoff per §8.1.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §2.3, §4.2, §8.1, Decision 8, Decision 9 |
| DMS | — |
| STM | — |
| DQS | — |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | factory creates 13 tasks given 13 configs | `pytest patient_360/tests/bronze/test_ingestion_factory_unit.py` |
| Unit | SparkSubmit wrapper injects conf+jars | `pytest patient_360/tests/bronze/test_spark_submit_wrapper_unit.py` |

## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/bronze/ingestion_factory.py"
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_factory.py", pattern: 'build_bronze_taskgroup'}
AC2:
  - file_exists: "patient_360/src/patient_360/bronze/spark_submit_wrapper.py"
  - grep: {file: "patient_360/src/patient_360/bronze/spark_submit_wrapper.py", pattern: 'SparkSubmitOperator'}
AC3:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_factory.py", pattern: 'configs'}
AC4:
  - pytest: {node: "patient_360/tests/bronze/test_ingestion_factory_unit.py"}
```

## How to Test (User)

### Prerequisites

- STORY-02-001 complete

### Steps

1. `cd patient_360 && uv run pytest tests/bronze/test_ingestion_factory_unit.py tests/bronze/test_spark_submit_wrapper_unit.py -v`

### Expected outcome

- All factory + wrapper tests pass

## Documentation Updates

- [ ] N/A — internal framework module, not user-facing
