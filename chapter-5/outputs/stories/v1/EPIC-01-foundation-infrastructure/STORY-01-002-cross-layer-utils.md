# STORY-01-002: Implement cross-layer utilities (config loader, logging, metrics, delta_helpers)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation & Infrastructure |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 1 |
| **Dependencies** | STORY-01-001 |
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

As a data engineer, I want have a tested config loader and reusable utility modules so that every Bronze/Silver/Gold task can resolve env-specific config and emit structured logs/metrics consistently.

## Description

Implement `src/patient_360/utils/pipeline_config.py` (loads `_infra/cd/config/{env}.yaml` and applies env overrides per LLD §7.2), `logging_config.py` (structured JSON logging), `metrics.py` (OpenTelemetry counter/gauge wrappers), and `delta_helpers.py` (Delta MERGE / replaceWhere helpers and SparkSession factory using UCSingleCatalog per LLD §13 Decision 12). Provide unit tests for each module.

## Acceptance Criteria


- [ ] `pipeline_config.py` resolves DEV/STAGING/PROD profiles from `_infra/cd/config/{env}.yaml` per LLD §7.2 [LLD §7.2]

- [ ] `logging_config.py` emits JSON logs with `pipeline_run_id`, `task_id`, `ds` fields [LLD §10.1]

- [ ] `metrics.py` exposes `record_counter`, `record_gauge`, `record_histogram` wrapping OpenTelemetry [LLD §10.1]

- [ ] `delta_helpers.py` provides `build_spark_session()` returning a SparkSession with UCSingleCatalog wired (LLD §13 Decision 12) [LLD §13]

- [ ] Unit test suite at `tests/utils/` exits 0 with ≥90% coverage [LLD §2.4]


## Technical Notes

- **Upstream references**: LLD §2.1, §7.2, §10.1, §13
- **Implementation hints**: Use `pyyaml` for config parsing and `opentelemetry-api`/`opentelemetry-sdk` for metrics. Set spark conf `spark.sql.catalog.spark_catalog=io.unitycatalog.spark.UCSingleCatalog`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §2.1, §7, §10.1, §13 Decision 12 |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Unit | config loader, logging, metrics, delta_helpers | pytest patient_360/tests/utils/ |



## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/utils/pipeline_config.py"
  - grep: {file: "patient_360/src/patient_360/utils/pipeline_config.py", pattern: "load_config"}
AC2:
  - file_exists: "patient_360/src/patient_360/utils/logging_config.py"
AC3:
  - file_exists: "patient_360/src/patient_360/utils/metrics.py"
  - grep: {file: "patient_360/src/patient_360/utils/metrics.py", pattern: "record_counter"}
AC4:
  - file_exists: "patient_360/src/patient_360/utils/delta_helpers.py"
  - grep: {file: "patient_360/src/patient_360/utils/delta_helpers.py", pattern: "UCSingleCatalog"}
AC5:
  - pytest: {node: "patient_360/tests/utils/"}
```


## How to Test (User)

### Prerequisites


- STORY-01-001 done — scaffold present

- `make dev-setup` completed


### Steps


1. `cd patient_360 && uv run pytest tests/utils/ -v`

2. `uv run python -c 'from patient_360.utils.pipeline_config import load_config; print(load_config("DEV"))'`


### Expected outcome


- All tests pass

- DEV config dict prints with `compute.spark_driver_memory: 2g`


## Documentation Updates


- [ ] Update patient_360/README.md § "Configuration" with the env-override resolution flow

