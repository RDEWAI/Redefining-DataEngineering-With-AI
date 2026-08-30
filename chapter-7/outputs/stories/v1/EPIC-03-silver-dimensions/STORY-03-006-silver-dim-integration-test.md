# STORY-03-006: Local integration test: trigger Silver dim tasks against UC OSS

| Field | Value |
|-------|-------|
| **Epic** | EPIC-03: Silver Dimensions (SCD Type 2) |
| **Story Type** | integration-test |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 6 |
| **Dependencies** | STORY-03-005, STORY-03-007 |
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

As a data engineer, I want trigger the `patient360_hourly_v1` Airflow DAG Silver-dim tasks against Unity Catalog OSS local and validate SCD2 outputs so that Silver dimension layer reaches Done with auditable evidence of SCD2 + DQ run-evidence.

## Description

Trigger the Airflow DAG `patient360_hourly_v1`, run the four Silver-dim tasks (`transform_{patients,organizations,providers,payers}_silver`) on local Airflow against UC OSS local. Assert: 4 Silver dim tables registered in `unity.silver.*`; SCD2 hash unchanged → no new rows; row count matches Bronze patient natural-key cardinality (5,767); `silver_se_stats` populated.

## Acceptance Criteria


- [ ] Airflow DAG `patient360_hourly_v1` runs Silver-dim tasks to success against local Airflow [LLD §4.2]

- [ ] 4 Silver dim tables visible in Unity Catalog OSS local (`unity.silver.clinical_patients`, `unity.silver.reference_*`) [LLD §3.2]

- [ ] `silver_se_stats` has ≥1 row per table whose `meta_dq_run_id` matches the run (SE run-evidence) [LLD §8.6.1]

- [ ] SCD2 idempotency: a re-run with unchanged source produces 0 new versions [LLD §4.5]


## Technical Notes

- **Upstream references**: LLD §3.2, §4.2, §4.5, §8.6.1
- **Implementation hints**: Trigger DAG, then assert via UC OSS REST API + Spark SQL queries.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §4.2 Silver tasks, §4.5 Idempotency, §8.6.1 SE run-evidence |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Integration | DAG Silver-dim run + UC tables + SCD2 idempotency | pytest -m integration patient_360/tests/integration/test_silver_dims_uc.py |

| Smoke | Silver dim DAG tasks parse | pytest patient_360/tests/silver/test_dag_unit.py |

| DQ | silver_se_stats populated | pytest -m integration patient_360/tests/integration/test_silver_se_evidence.py |

| Unit | SCD2 idempotency unit | pytest patient_360/tests/utils/test_scd2_unit.py |



## Verification

```yaml
AC1:
  - pytest: {node: "patient_360/tests/integration/test_silver_dims_uc.py::test_dag_runs", marker: "integration"}
AC2:
  - pytest: {node: "patient_360/tests/integration/test_silver_dims_uc.py::test_4_dim_tables_in_uc", marker: "integration"}
AC3:
  - pytest: {node: "patient_360/tests/integration/test_silver_se_evidence.py::test_silver_se_stats_populated", marker: "integration"}
AC4:
  - pytest: {node: "patient_360/tests/integration/test_silver_dims_uc.py::test_scd2_idempotent_rerun", marker: "integration"}
```


## How to Test (User)

### Prerequisites


- STORY-03-005 done

- Local stack up


### Steps


1. `cd patient_360 && make ddl-apply` (pre-create UC tables) then `docker compose exec airflow airflow dags trigger patient360_hourly_v1`

2. `uv run pytest -m integration tests/integration/test_silver_dims_uc.py tests/integration/test_silver_se_evidence.py -v`


### Expected outcome


- DAG run succeeds; integration tests pass; SCD2 idempotent re-run produces 0 new versions


## Documentation Updates


- [ ] Update patient_360/README.md § "Local integration testing" with the Silver dim trigger commands

- [ ] Add patient_360/docs/runbooks/silver-integration-test.md

