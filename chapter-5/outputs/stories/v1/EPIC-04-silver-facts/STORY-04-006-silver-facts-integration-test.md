# STORY-04-006: Integration test — Silver-facts subtree on Airflow local against UC OSS local

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts Layer |
| **Story Type** | integration-test |
| **Priority** | P1 |
| **Story Points** | 3 |
| **Sprint** | 4 |
| **Dependencies** | STORY-04-005 |
| **Status** | To Do |

## User Story

As a QA / Data Engineer, I want an integration test that triggers the Silver-facts subtree of `patient360_hourly_v1` on local Airflow against UC OSS local, validates the 9 fact tables landed in UC, and asserts SE produced runtime artifacts so that Silver-facts can independently reach Done.

## Description

Add `patient_360/tests/integration/test_silver_facts_uc.py`. Triggers `transform_encounters_silver` then the 8 dependent fact tasks via `airflow tasks test patient360_hourly_v1 <task> <ds>`. Validates: (1) all 9 fact tables exist in `unity.silver.{clinical,billing}_*`; (2) FK orphan rate < 0.1% per DQS §4; (3) `unity.silver.silver_se_stats` has ≥ 13 rows for the run (4 dims + 9 facts) per LLD §8.6.1; (4) `<table>_error` Delta tables exist; (5) `reconciliation_silver` task succeeds without raising `SE_RUN_MISSING_FOR_DS`.

## Acceptance Criteria

- [ ] Airflow DAG `patient360_hourly_v1` Silver-facts subtree triggered via `airflow tasks test patient360_hourly_v1 transform_encounters_silver <ds>` succeeds on local Airflow stack [LLD §2.4, §4.2]
- [ ] All 9 Silver fact tables present in Unity Catalog OSS local [LLD §5.2, Decision 15]
- [ ] FK orphan rate < 0.1% across all fact tables [DQS §4]
- [ ] `unity.silver.silver_se_stats` has ≥ 13 rows for run's `meta_dq_run_id` [LLD §8.6.1]
- [ ] `<table>_error` Delta tables exist for all fact tables (created by SE) [LLD §8.2]
- [ ] `reconciliation_silver` succeeds (does not raise SE_RUN_MISSING_FOR_DS) [LLD §8.6.1]

## Technical Notes

- **Upstream references**: LLD §2.4, §4.2, §5.2, §5.5, §8.2, §8.6.1; STORIES-INTEGRATION-SE-001
- **Implementation hints**: Topo-order: encounters → 8 dependents → reconciliation_silver. Use `airflow tasks test` to bypass scheduler.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §2.4, §4.2, §5.2, §5.5, §8.2, §8.6.1 |
| DMS | §4 Silver |
| STM | Bronze-to-Silver |
| DQS | §2-4 |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | UC client + FK orphan checker | `pytest patient_360/tests/integration/test_uc_client_unit.py` |
| Integration | Silver-facts subtree triggers and 9 UC tables land | `pytest -m integration patient_360/tests/integration/test_silver_facts_uc.py` |
| Smoke | UC silver schema reachable | `curl http://localhost:8080/api/2.1/unity-catalog/schemas?catalog_name=unity` |
| DQ | silver_se_stats populated, _error tables created | `pytest -m integration patient_360/tests/integration/test_silver_facts_uc.py::test_se_artifacts` |

## Verification

```yaml
AC1:
  - pytest: {node: "patient_360/tests/integration/test_silver_facts_uc.py::test_subtree_runs", marker: "integration"}
AC2:
  - pytest: {node: "patient_360/tests/integration/test_silver_facts_uc.py::test_uc_silver_facts_exist", marker: "integration"}
AC3:
  - pytest: {node: "patient_360/tests/integration/test_silver_facts_uc.py::test_fk_orphan_rate", marker: "integration"}
AC4:
  - pytest: {node: "patient_360/tests/integration/test_silver_facts_uc.py::test_silver_se_stats_populated", marker: "integration"}
AC5:
  - pytest: {node: "patient_360/tests/integration/test_silver_facts_uc.py::test_se_error_tables", marker: "integration"}
AC6:
  - pytest: {node: "patient_360/tests/integration/test_silver_facts_uc.py::test_reconciliation_silver_passes", marker: "integration"}
```

## How to Test (User)

### Prerequisites

- STORY-03-004 (Silver-dims integration) green
- All EPIC-04 build + perf stories complete

### Steps

1. `cd patient_360 && for t in encounters allergies conditions medications observations immunizations procedures claims careplans; do airflow tasks test patient360_hourly_v1 transform_${t}_silver 2026-04-27; done`
2. `cd patient_360 && airflow tasks test patient360_hourly_v1 reconciliation_silver 2026-04-27`
3. `cd patient_360 && uv run pytest -m integration tests/integration/test_silver_facts_uc.py -v`

### Expected outcome

- Step 1: each task exits 0
- Step 2: reconciliation passes
- Step 3: all integration tests pass

## Documentation Updates

- [ ] Update `patient_360/README.md` § "Silver Facts" with the test invocation
- [ ] Update `patient_360/tests/integration/README.md` § "Silver-facts integration test"
