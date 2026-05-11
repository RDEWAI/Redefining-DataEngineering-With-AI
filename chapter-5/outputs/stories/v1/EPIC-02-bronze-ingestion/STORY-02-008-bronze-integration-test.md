# STORY-02-008: Local integration test: trigger Bronze DAG against Unity Catalog OSS local

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion |
| **Story Type** | integration-test |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 5 |
| **Dependencies** | STORY-02-006, STORY-02-007 |
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

As a data engineer, I want trigger the `patient360_hourly_v1` Airflow DAG on the local docker-compose stack and validate Bronze data lands in Unity Catalog OSS so that Bronze layer can reach Done independently — we have evidence the DAG runs and DQ produced run-evidence.

## Description

Trigger the `patient360_hourly_v1` Airflow DAG on local Airflow against Unity Catalog OSS local. Assert all 13 Bronze Delta tables register in `unity.bronze.*` with correct schema + metadata columns; `reconciliation_bronze` succeeds; SE produced runtime artifacts (`bronze_se_stats` populated, `<table>_error` tables exist) per LLD §8.6.1. Failure modes: empty stats table, missing UC tables, schema drift.

## Acceptance Criteria


- [ ] Airflow DAG `patient360_hourly_v1` triggers and Bronze TaskGroup completes successfully on local Airflow [LLD §4.2]

- [ ] 13 Bronze Delta tables visible in Unity Catalog OSS local at `unity.bronze.synthea_*` after the DAG run [LLD §13 Decision 15]

- [ ] Each Bronze table has `ds`, `_ingested_at`, `_source_batch_id` metadata columns populated [LLD §2.3]

- [ ] `bronze_se_stats` has ≥1 row whose `meta_dq_run_id` matches the run; `reconciliation_bronze` succeeds (SE run-evidence) [LLD §8.6.1]

- [ ] `dq_pass_rate` reported in Marquez run facets / Grafana dashboard for the run [LLD §8.6.1, §10.2]


## Technical Notes

- **Upstream references**: LLD §4.2, §8.6.1, §13 Decision 15
- **Implementation hints**: Test body: `subprocess.run(['docker', 'compose', 'exec', 'airflow', 'airflow', 'dags', 'trigger', 'patient360_hourly_v1'])`, poll `airflow dags list-runs` until success, then `curl` UC OSS `/api/2.1/unity-catalog/tables` and assert 13 entries.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §4.2, §8.6.1, §13 Decision 15 |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Integration | DAG trigger + UC OSS table presence + SE stats populated | pytest -m integration patient_360/tests/integration/test_bronze_uc.py |

| Smoke | Airflow + UC OSS up | make dev-status |

| DQ | bronze_se_stats has run-evidence row | pytest -m integration patient_360/tests/integration/test_bronze_se_evidence.py |

| Unit | DAG parses without import errors | pytest patient_360/tests/bronze/test_dag_unit.py |



## Verification

```yaml
AC1:
  - pytest: {node: "patient_360/tests/integration/test_bronze_uc.py::test_dag_run_succeeds", marker: "integration"}
AC2:
  - pytest: {node: "patient_360/tests/integration/test_bronze_uc.py::test_13_bronze_tables_in_uc", marker: "integration"}
AC3:
  - pytest: {node: "patient_360/tests/integration/test_bronze_uc.py::test_metadata_columns_populated", marker: "integration"}
AC4:
  - pytest: {node: "patient_360/tests/integration/test_bronze_se_evidence.py::test_se_stats_populated", marker: "integration"}
AC5:
  - manual: "Marquez UI / Grafana DQ board — visual check"
```


## How to Test (User)

### Prerequisites


- STORY-01-008 done — local stack bootstrapped (renumbered from STORY-01-006)

- STORY-02-006 / -02-007 done


### Steps


1. `cd patient_360 && make dev-up && make dev-bootstrap`

2. `docker compose exec airflow airflow dags trigger patient360_hourly_v1`

3. `uv run pytest -m integration tests/integration/test_bronze_uc.py tests/integration/test_bronze_se_evidence.py -v`

4. Open `http://localhost:5001` (Marquez) and inspect the run lineage


### Expected outcome


- DAG run reaches `success` state

- All integration tests pass

- Marquez shows lineage edges from `synthea.*` to `unity.bronze.synthea_*`


## Documentation Updates


- [ ] Update patient_360/README.md § "Local integration testing" with the Bronze DAG trigger + verification flow

- [ ] Add patient_360/docs/runbooks/bronze-integration-test.md

