# STORY-03-004: Integration test — Silver-dims DAG subtree on Airflow local against UC OSS local

| Field | Value |
|-------|-------|
| **Epic** | EPIC-03: Silver Dimensions Layer (SCD Type 2) |
| **Story Type** | integration-test |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 3 |
| **Dependencies** | STORY-03-003 |
| **Status** | To Do |

## User Story

As a QA / Data Engineer, I want an integration test that triggers the Silver-dims subtree of `patient360_hourly_v1` on local Airflow against Unity Catalog OSS local, validates SCD2 versioning behavior, and asserts SE produced runtime artifacts so that Silver-dims can independently reach Done.

## Description

Add `patient_360/tests/integration/test_silver_dims_uc.py` that triggers the Silver-dim subtree (`transform_patients_silver`, `transform_organizations_silver`, `transform_providers_silver`, `transform_payers_silver`) via `airflow tasks test` on the local Airflow stack against UC OSS local. Validates: (1) the 4 `unity.silver.{clinical_patients,reference_*}` tables exist in UC OSS local; (2) SCD2 columns populated; (3) re-running with unchanged source produces 0 new versions (idempotency per §4.5); (4) `unity.silver.silver_se_stats` has rows for the run (SE end-to-end evidence per §8.6.1 / STORIES-INTEGRATION-SE-001); (5) `<dim>_error` tables exist.

## Acceptance Criteria

- [ ] Airflow DAG `patient360_hourly_v1` Silver-dim subtree triggered via `airflow tasks test transform_patients_silver <ds>` succeeds on local Airflow stack [LLD §2.4, §4.2]
- [ ] All 4 Silver dim tables present in Unity Catalog OSS local at `unity.silver.{clinical_patients,reference_*}` [LLD §5.2, Decision 15]
- [ ] SCD2 columns (`effective_from`, `effective_to`, `is_current`, `record_hash`) populated on all 4 [LLD §5.2, DMS §6]
- [ ] Re-running with unchanged source yields 0 new SCD2 versions (idempotency) [LLD §4.5]
- [ ] `unity.silver.silver_se_stats` has ≥ 4 rows for the run's `meta_dq_run_id` (one per dim) [LLD §8.6.1]
- [ ] `<dim>_error` Delta tables exist for all 4 dims (created by SE) [LLD §8.2]

## Technical Notes

- **Upstream references**: LLD §2.4, §4.2 (DAG `patient360_hourly_v1`), §4.5 (idempotency), §5.2, §8.2, §8.6.1; story-standards.md §1; STORIES-INTEGRATION-SE-001
- **Implementation hints**: For idempotency test — capture row count of `clinical_patients` after first run, re-run, assert post-count == pre-count (same `is_current` row count, no new effective_from rows).

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §2.4, §4.2, §4.5, §5.2, §8.2, §8.6.1 |
| DMS | §4 Silver, §6 SCD2 |
| STM | Bronze-to-Silver dims |
| DQS | §2 row_dq |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | UC client + SCD2 column assertions | `pytest patient_360/tests/integration/test_uc_client_unit.py` |
| Integration | Silver-dim DAG subtree triggers and 4 UC tables land | `pytest -m integration patient_360/tests/integration/test_silver_dims_uc.py` |
| Smoke | UC silver schema reachable | `curl http://localhost:8080/api/2.1/unity-catalog/schemas?catalog_name=unity` |
| DQ | silver_se_stats populated, _error tables created | `pytest -m integration patient_360/tests/integration/test_silver_dims_uc.py::test_se_artifacts` |

## Verification

```yaml
AC1:
  - pytest: {node: "patient_360/tests/integration/test_silver_dims_uc.py::test_dag_subtree_runs", marker: "integration"}
AC2:
  - pytest: {node: "patient_360/tests/integration/test_silver_dims_uc.py::test_uc_silver_dims_exist", marker: "integration"}
  - manual: "curl UC tables API for schema=silver lists all 4 dims"
AC3:
  - pytest: {node: "patient_360/tests/integration/test_silver_dims_uc.py::test_scd2_columns_populated", marker: "integration"}
AC4:
  - pytest: {node: "patient_360/tests/integration/test_silver_dims_uc.py::test_idempotency_no_new_versions", marker: "integration"}
AC5:
  - pytest: {node: "patient_360/tests/integration/test_silver_dims_uc.py::test_silver_se_stats_populated", marker: "integration"}
AC6:
  - pytest: {node: "patient_360/tests/integration/test_silver_dims_uc.py::test_se_error_tables", marker: "integration"}
```

## How to Test (User)

### Prerequisites

- STORY-02-007 (Bronze integration test) green
- All EPIC-03 build + perf stories complete

### Steps

1. `cd patient_360 && for t in patients organizations providers payers; do airflow tasks test patient360_hourly_v1 transform_${t}_silver 2026-04-27; done`
2. `curl -sS 'http://localhost:8080/api/2.1/unity-catalog/tables?catalog_name=unity&schema_name=silver' | jq '.tables[].name'`
3. `cd patient_360 && uv run pytest -m integration tests/integration/test_silver_dims_uc.py -v`

### Expected outcome

- Step 1: each task exits 0
- Step 2: lists `clinical_patients`, `reference_organizations`, `reference_providers`, `reference_payers` (plus their `_error` and `silver_se_stats`)
- Step 3: all integration tests pass

## Documentation Updates

- [ ] Update `patient_360/README.md` § "Silver Dimensions" with the test invocation
- [ ] Update `patient_360/tests/integration/README.md` § "Silver-dims integration test" with prerequisites
