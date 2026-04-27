# STORY-02-007: Integration test — trigger bronze DAG on Airflow local against UC OSS local

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion Layer |
| **Story Type** | integration-test |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 2 |
| **Dependencies** | STORY-02-006 |
| **Status** | To Do |

## User Story

As a QA / Data Engineer, I want an integration test that triggers the Bronze TaskGroup on the local Airflow stack against Unity Catalog OSS local, validates all 13 Bronze Delta tables landed in UC, and asserts SE produced runtime artifacts, so that Bronze can independently reach Done.

## Description

Add `patient_360/tests/integration/test_bronze_uc.py` that uses `airflow dags trigger patient360_hourly_v1` (or `airflow tasks test bronze_ingestion.<task> <ds>` for each Bronze task), waits for completion, then queries Unity Catalog OSS via `curl http://localhost:8080/api/2.1/unity-catalog/tables?catalog_name=unity&schema_name=bronze` to assert all 13 `synthea_*` tables exist. Then assert SE produced runtime artifacts: `bronze_se_stats` has ≥ 1 row for the run's `meta_dq_run_id`, and at least one `<table>_error` table exists (or is empty for a clean run) per LLD §8.6.1 + STORIES-INTEGRATION-SE-001.

## Acceptance Criteria

- [ ] `airflow dags trigger patient360_hourly_v1 --conf '{"ds": "<ds>"}'` succeeds against local Airflow stack [LLD §2.4, §4.2]
- [ ] All 13 Bronze tables listed in Unity Catalog at `unity.bronze.synthea_*` after run [LLD §5.1, Decision 15]
- [ ] `unity.bronze.bronze_se_stats` has ≥ 1 row whose `meta_dq_run_id` matches the run [LLD §8.6.1]
- [ ] `<table>_error` Delta tables exist for at least the 6 critical tables (created by SE) [LLD §8.2]
- [ ] `reconciliation_bronze` task completes successfully (does not raise SE_RUN_MISSING_FOR_DS) [LLD §8.6.1]
- [ ] Row counts in UC bronze tables match source DuckDB row counts within ±1% [DQS §4]

## Technical Notes

- **Upstream references**: LLD §2.4 (testing strategy — local docker-compose stack), §4.2 (DAG id `patient360_hourly_v1`), §5.1, §8.2, §8.6.1; story-standards.md §1 SE end-to-end mandate; scrum-master rule STORIES-INTEGRATION-SE-001
- **Implementation hints**: Use `pytest -m integration`. Poll `airflow dags list-runs -d patient360_hourly_v1` until state ∈ {success, failed}. Then `requests.get` the UC tables API. Test must NOT mock SE — must hit a real Spark session via spark-submit inside the Airflow container.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §2.4, §4.2, §5.1, §5.5, §8.2, §8.6.1 |
| DMS | §3 Bronze (13 tables) |
| STM | Source-to-Bronze |
| DQS | §2-4 (rules running inline) |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | UC API client + assertions | `pytest patient_360/tests/integration/test_uc_client_unit.py` |
| Integration | Bronze DAG triggers and 13 UC tables land | `pytest -m integration patient_360/tests/integration/test_bronze_uc.py` |
| Smoke | UC `/catalogs` returns 200 | `curl http://localhost:8080/api/2.1/unity-catalog/catalogs` |
| DQ | bronze_se_stats populated, _error tables created | `pytest -m integration patient_360/tests/integration/test_bronze_uc.py::test_se_artifacts` |

## Verification

```yaml
AC1:
  - pytest: {node: "patient_360/tests/integration/test_bronze_uc.py::test_dag_trigger", marker: "integration"}
  - manual: "Airflow UI shows patient360_hourly_v1 run succeeded for ds"
AC2:
  - pytest: {node: "patient_360/tests/integration/test_bronze_uc.py::test_uc_tables_exist", marker: "integration"}
  - manual: "curl http://localhost:8080/api/2.1/unity-catalog/tables?catalog_name=unity&schema_name=bronze lists 13 synthea_* tables"
AC3:
  - pytest: {node: "patient_360/tests/integration/test_bronze_uc.py::test_se_stats_populated", marker: "integration"}
AC4:
  - pytest: {node: "patient_360/tests/integration/test_bronze_uc.py::test_se_error_tables", marker: "integration"}
AC5:
  - pytest: {node: "patient_360/tests/integration/test_bronze_uc.py::test_reconciliation_passes", marker: "integration"}
AC6:
  - pytest: {node: "patient_360/tests/integration/test_bronze_uc.py::test_row_count_parity", marker: "integration"}
```

## How to Test (User)

### Prerequisites

- STORY-01-006 runtime-bootstrap completed
- All EPIC-02 build + perf stories complete and merged
- Local docker stack up: `docker compose -f patient_360/_infra/docker/docker-compose.yml up -d`

### Steps

1. `cd patient_360 && airflow dags trigger patient360_hourly_v1 --conf '{"ds": "2026-04-27"}'`
2. `cd patient_360 && airflow dags list-runs -d patient360_hourly_v1` (poll until success)
3. `curl -sS 'http://localhost:8080/api/2.1/unity-catalog/tables?catalog_name=unity&schema_name=bronze' | jq '.tables | length'`
4. `cd patient_360 && uv run pytest -m integration tests/integration/test_bronze_uc.py -v`

### Expected outcome

- Step 1 returns DAG run id
- Step 2 reports `state=success` within 10 minutes
- Step 3 returns 13 (one for each Bronze table) or more (with `_error` and `_se_stats`)
- Step 4 all integration tests pass; SE evidence asserted

## Documentation Updates

- [ ] Update `patient_360/README.md` § "Run Bronze locally" with `airflow dags trigger` command
- [ ] Update `patient_360/tests/integration/README.md` § "Running integration tests" with prerequisites and `pytest -m integration` invocation
- [ ] Update top-level `chapter-5/README.md` § "Verifying Bronze layer" linking to this runbook
