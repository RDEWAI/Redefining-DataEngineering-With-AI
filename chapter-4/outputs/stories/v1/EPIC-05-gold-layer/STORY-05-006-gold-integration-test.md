# STORY-05-006: Integration Test for Gold Pipeline and End-to-End

| Field | Value |
|-------|-------|
| **Epic** | EPIC-05: Gold Layer + Reconciliation |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 5 |
| **Sprint** | Sprint 7 |
| **Dependencies** | STORY-05-005 |
| **Status** | To Do |

## User Story

As a data engineer, I want integration tests for the Gold layer and a full end-to-end test so that we confirm the complete DuckDB-to-Gold pipeline works correctly before observability and deployment work begins.

## Description

Create two test files: (1) `tests/integration/test_gold_pipeline.py` -- tests Silver -> Gold for all 3 tables with inline SE and reconciliation_gold passing. (2) `tests/integration/test_e2e_pipeline.py` -- full end-to-end test from DuckDB source through Bronze -> Silver -> Gold with all inline SE checks and all reconciliation tasks passing. Verify 5,767 patients in patient_summary, ARRAY columns populated, readmission flags correct, billing totals non-negative.

## Acceptance Criteria

- [ ] Gold integration test: Silver -> Gold for all 3 tables [LLD §2.4]
- [ ] End-to-end test: DuckDB -> Bronze -> Silver -> Gold complete path [LLD §2.4]
- [ ] All inline SE checks pass during e2e test [LLD §5.4]
- [ ] All 3 reconciliation tasks pass (bronze, silver, gold) [LLD §5.5]
- [ ] Patient_summary contains exactly 5,767 patients [DRD §4.4]
- [ ] Tests use `@pytest.mark.integration` marker [development-standards.md SS5]

## Technical Notes

- **Upstream references**: LLD SS2.4, SS5.3, SS5.4, SS5.5
- **Implementation hints**: The e2e test is the definitive validation of the full pipeline. Use a subset of source data for speed, but ensure all 3 Gold tables are produced. This test should run in CI on merge to main per LLD SS9.2.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS2.4, SS5.3, SS5.4, SS5.5 |
| DMS | SS5 (all layer schemas) |
| STM | All tabs |
| DQS | SS2-4 (all rules) |
