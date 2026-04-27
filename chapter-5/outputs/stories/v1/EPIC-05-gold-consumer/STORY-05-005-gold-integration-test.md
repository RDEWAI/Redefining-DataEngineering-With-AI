# STORY-05-005: Integration test — Gold subtree on Airflow local against UC OSS local

| Field | Value |
|-------|-------|
| **Epic** | EPIC-05: Gold Consumer Layer |
| **Story Type** | integration-test |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 4 |
| **Dependencies** | STORY-05-004 |
| **Status** | To Do |

## User Story

As a QA / Data Engineer, I want an integration test that triggers the Gold subtree of `patient360_hourly_v1` on local Airflow against UC OSS local, validates the 3 Gold tables landed in UC, asserts patient completeness = 5,767, and confirms SE produced runtime artifacts so that Gold can independently reach Done.

## Description

Add `patient_360/tests/integration/test_gold_uc.py` triggering `build_patient_summary_gold`, `build_clinical_history_gold`, `build_billing_summary_gold`, then `reconciliation_gold` via `airflow tasks test`. Validates: (1) all 3 Gold tables exist in `unity.gold.*`; (2) `patient_summary` row count = 5,767; (3) `gold_se_stats` populated with ≥ 3 rows for run; (4) `<table>_error` Delta tables exist; (5) reconciliation_gold succeeds.

## Acceptance Criteria

- [ ] Airflow DAG `patient360_hourly_v1` Gold subtree triggered via `airflow tasks test patient360_hourly_v1 build_patient_summary_gold <ds>` succeeds on local Airflow stack [LLD §2.4, §4.2]
- [ ] All 3 Gold tables present in Unity Catalog OSS local at `unity.gold.*` [LLD §5.3, Decision 15]
- [ ] `unity.gold.patient_summary` row count = 5,767 (patient completeness) [DQS §4]
- [ ] `unity.gold.gold_se_stats` has ≥ 3 rows for run's `meta_dq_run_id` [LLD §8.6.1]
- [ ] `<gold-table>_error` Delta tables exist for all 3 Gold tables (created by SE) [LLD §8.2]
- [ ] `reconciliation_gold` succeeds (does not raise SE_RUN_MISSING_FOR_DS) [LLD §8.6.1]

## Technical Notes

- **Upstream references**: LLD §2.4, §4.2, §5.3, §5.5, §8.2, §8.6.1; STORIES-INTEGRATION-SE-001
- **Implementation hints**: Use `airflow tasks test` for each Gold task. Then poll UC tables API.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §2.4, §4.2, §5.3, §5.5, §8.2, §8.6.1 |
| DMS | §5 Gold |
| STM | Silver-to-Gold |
| DQS | §1, §2, §4 |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | UC client + 5767 assertion | `pytest patient_360/tests/integration/test_uc_client_unit.py` |
| Integration | Gold subtree triggers and 3 UC tables land | `pytest -m integration patient_360/tests/integration/test_gold_uc.py` |
| Smoke | UC gold schema reachable | `curl http://localhost:8080/api/2.1/unity-catalog/schemas?catalog_name=unity` |
| DQ | gold_se_stats populated, _error tables, 5767 row check | `pytest -m integration patient_360/tests/integration/test_gold_uc.py::test_se_artifacts` |

## Verification

```yaml
AC1:
  - pytest: {node: "patient_360/tests/integration/test_gold_uc.py::test_subtree_runs", marker: "integration"}
AC2:
  - pytest: {node: "patient_360/tests/integration/test_gold_uc.py::test_uc_gold_tables_exist", marker: "integration"}
AC3:
  - pytest: {node: "patient_360/tests/integration/test_gold_uc.py::test_patient_summary_row_count", marker: "integration"}
AC4:
  - pytest: {node: "patient_360/tests/integration/test_gold_uc.py::test_gold_se_stats_populated", marker: "integration"}
AC5:
  - pytest: {node: "patient_360/tests/integration/test_gold_uc.py::test_se_error_tables", marker: "integration"}
AC6:
  - pytest: {node: "patient_360/tests/integration/test_gold_uc.py::test_reconciliation_gold_passes", marker: "integration"}
```

## How to Test (User)

### Prerequisites

- STORY-04-006 (Silver-facts integration) green
- All EPIC-05 build + perf stories complete

### Steps

1. `cd patient_360 && for t in patient_summary clinical_history billing_summary; do airflow tasks test patient360_hourly_v1 build_${t}_gold 2026-04-27; done`
2. `cd patient_360 && airflow tasks test patient360_hourly_v1 reconciliation_gold 2026-04-27`
3. `curl -sS 'http://localhost:8080/api/2.1/unity-catalog/tables?catalog_name=unity&schema_name=gold' | jq '.tables[].name'`
4. `cd patient_360 && uv run pytest -m integration tests/integration/test_gold_uc.py -v`

### Expected outcome

- Step 1: each task exits 0
- Step 2: reconciliation_gold passes
- Step 3: lists `patient_summary`, `patient_clinical_history`, `patient_billing_summary` (plus their `_error` and `gold_se_stats`)
- Step 4: all integration tests pass; patient_summary row count = 5,767

## Documentation Updates

- [ ] Update `patient_360/README.md` § "Gold layer" with the test invocation
- [ ] Update `patient_360/tests/integration/README.md` § "Gold integration test"
- [ ] Update top-level `chapter-5/README.md` § "End-to-end pipeline verification"
