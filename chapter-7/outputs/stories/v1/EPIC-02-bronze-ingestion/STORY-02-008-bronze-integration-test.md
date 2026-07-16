# STORY-02-008: Local integration test: trigger Bronze DAG against Unity Catalog OSS local

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion |
| **Story Type** | integration-test |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 5 |
| **Dependencies** | STORY-02-006, STORY-02-007 |
| **Status** | Done |

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

As a data engineer, I want trigger the `patient360_hourly_v1` Airflow DAG on the local docker-compose stack and validate Bronze data lands in the `unity.bronze.*` UC tables so that Bronze layer can reach Done independently — we have evidence the DAG runs and DQ produced run-evidence.

## Description

Pre-create the UC EXTERNAL Delta tables with `make ddl-apply` (beeline applying plain dated `ddl/migrations/*.sql` in lexical order against the Spark Thrift Server), then trigger the `patient360_hourly_v1` Airflow DAG on local Airflow with Spark wired to `spark_catalog=DeltaCatalog` + named `unity=UCSingleCatalog` side catalog (`defaultCatalog=unity`) per LLD §13 Decision 12 (re-adopted 2026-06-18). Assert all 13 Bronze tables are readable via `spark.read.table("unity.bronze.synthea_*")` and visible in UC with correct metadata columns; `reconciliation_bronze` (a `SparkSubmitOperator` per LLD §4.2) succeeds; SE produced runtime artifacts (per-table MANAGED UC stats tables `unity.bronze.synthea_<table>_stats` populated, `unity.bronze.synthea_<table>_error` tables exist) per LLD §8.6.1. The SE run-evidence query filters on `meta_dq_run_date` only — **not** on `meta_dq_run_id` (SE generates its own run id and rejects any Airflow `ts_nodash` override per LLD §8.6.1). Failure modes: empty stats table, missing UC tables (forgot `make ddl-apply`), schema drift.

## Acceptance Criteria


- [ ] Airflow DAG `patient360_hourly_v1` triggers and Bronze TaskGroup completes successfully on local Airflow [LLD §4.2]

- [ ] All 13 `unity.bronze.synthea_*` tables are readable via `spark.read.table(...)` and present in the Unity Catalog OSS local catalog after the DAG run; **no** assertion against path-based `warehouse/.../bronze/*` directories (Bronze is UC-managed `insertInto` per LLD §13 Decision 12/15 re-adopted 2026-06-18) [LLD §13 Decision 12/15, §9.1]

- [ ] Each Bronze table has `ds`, `_ingested_at`, `_source_batch_id` metadata columns populated [LLD §2.3]

- [ ] `bronze_se_stats` has ≥1 row for the current `meta_dq_run_date`; `reconciliation_bronze` succeeds (SE run-evidence). The evidence query filters on `meta_dq_run_date` **only** (no `meta_dq_run_id = ts_nodash` clause — SE generates its own run id) per LLD §8.6.1 (2026-05-12 pivot) [LLD §8.6.1]

- [ ] `dq_pass_rate` reported in Marquez run facets / Grafana dashboard for the run [LLD §8.6.1, §10.2]


## Technical Notes

- **Upstream references**: LLD §4.2, §8.6.1, §13 Decision 15
- **Implementation hints**: Test body: run `make ddl-apply` to pre-create UC tables, then `subprocess.run(['docker', 'compose', 'exec', 'airflow', 'airflow', 'dags', 'trigger', 'patient360_hourly_v1'])`, poll `airflow dags list-runs` until success, then `spark.read.table("unity.bronze.synthea_<t>").count()` for each of the 13 tables (or `curl` UC OSS `/api/2.1/unity-catalog/tables` and assert 13 entries).

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §4.2, §8.6.1, §13 Decision 15 |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Integration | DAG trigger + UC OSS table presence + SE stats populated | pytest -m integration patient_360/tests/integration/bronze/test_bronze_uc.py |

| Smoke | Airflow + UC OSS up | make dev-status |

| DQ | bronze_se_stats has run-evidence row | pytest -m integration patient_360/tests/integration/bronze/test_bronze_se_evidence.py |

| Unit | DAG parses without import errors | pytest patient_360/tests/bronze/test_dag_unit.py |



## Verification

```yaml
AC1:
  - pytest: {node: "patient_360/tests/integration/bronze/test_bronze_uc.py::test_dag_run_succeeds", marker: "integration"}
AC2:
  - pytest: {node: "patient_360/tests/integration/bronze/test_bronze_uc.py::test_13_bronze_uc_tables_exist", marker: "integration"}
  - grep: {file: "patient_360/tests/integration/bronze/test_bronze_uc.py", pattern: "unity\\.bronze\\.|unity-catalog/tables"}
  - forbidden_grep: {file: "patient_360/tests/integration/bronze/test_bronze_uc.py", pattern: "warehouse/.*/bronze/.*_delta_log|_delta_log", reason: "Bronze is UC-managed; integration test must validate UC catalog tables (spark.read.table / UC API), not path-based Delta directories per LLD §13 Decision 12/15 (re-adopted 2026-06-18)"}
AC3:
  - pytest: {node: "patient_360/tests/integration/bronze/test_bronze_uc.py::test_metadata_columns_populated", marker: "integration"}
AC4:
  - pytest: {node: "patient_360/tests/integration/bronze/test_bronze_se_evidence.py::test_se_stats_populated", marker: "integration"}
  - grep: {file: "patient_360/tests/integration/bronze/test_bronze_se_evidence.py", pattern: "meta_dq_run_date"}
  - forbidden_grep: {file: "patient_360/tests/integration/bronze/test_bronze_se_evidence.py", pattern: "meta_dq_run_id\\s*=\\s*['\"]?\\{?\\s*ts_nodash|meta_dq_run_id\\s*=\\s*['\"]?\\{run_id", reason: "SE rejects Airflow-supplied run_id overrides; evidence query must filter on meta_dq_run_date only per LLD §8.6.1 (2026-05-12 pivot)"}
AC5:
  - manual: "Marquez UI / Grafana DQ board — visual check"
```


## How to Test (User)

### Prerequisites


- STORY-01-008 done — local stack bootstrapped (renumbered from STORY-01-006)

- STORY-02-006 / -02-007 done


### Steps


1. `cd patient_360 && make dev-up && make dev-bootstrap && make ddl-apply`

2. `docker compose exec airflow airflow dags trigger patient360_hourly_v1`

3. `uv run pytest -m integration tests/integration/bronze/test_bronze_uc.py tests/integration/bronze/test_bronze_se_evidence.py -v`

4. Open `http://localhost:5001` (Marquez) and inspect the run lineage


### Expected outcome


- DAG run reaches `success` state

- All integration tests pass

- Marquez shows lineage edges from `synthea.*` to the `unity.bronze.synthea_*` UC tables


## Documentation Updates


- [ ] Update patient_360/README.md § "Local integration testing" with the Bronze DAG trigger + verification flow

- [ ] Add patient_360/docs/runbooks/bronze-integration-test.md

