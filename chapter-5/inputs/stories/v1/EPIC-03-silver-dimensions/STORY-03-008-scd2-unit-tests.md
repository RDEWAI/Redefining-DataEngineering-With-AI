# STORY-03-008: Unit Tests for SCD2 and Derived Fields

| Field | Value |
|-------|-------|
| **Epic** | EPIC-03: Silver Dimensions -- SCD Type 2 |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 3 |
| **Sprint** | Sprint 5 |
| **Dependencies** | STORY-03-001, STORY-03-007 |
| **Status** | To Do |

## User Story

As a data engineer, I want comprehensive unit tests for SCD2 merge logic and derived fields so that change-detection correctness and edge cases are verified before Silver tables are built.

## Description

Write unit tests in `tests/unit/test_scd2.py` covering: new record insert, unchanged record no-op, changed record close+insert, multiple changes in same batch, hash column mismatch detection. Write unit tests in `tests/unit/test_derived_fields.py` covering: calculated_age (living, deceased, NULL birthdate), medication_status (active, completed, stopped), is_30_day_readmission (within window, outside window, boundary), total_visit_cost (single claim, multiple claims, zero cost).

## Acceptance Criteria

- [ ] `test_scd2.py` covers new record, unchanged record, changed record, multiple changes [LLD §2.4]
- [ ] SCD2 tests verify effective_from, effective_to, is_current, scd2_version correctness [DMS §6]
- [ ] `test_derived_fields.py` covers calculated_age edge cases: NULL dates, deceased patients [LLD §2.4]
- [ ] Readmission test verifies 30-day boundary conditions [DRD §5.2]
- [ ] All tests pass with >= 90% coverage on scd2.py and derived_fields.py [LLD §2.4]

## Technical Notes

- **Upstream references**: LLD SS2.4 (Testing Strategy), DMS SS6 (SCD2), DRD SS5.2 (derived fields)
- **Implementation hints**: Use known input/output pairs for SCD2 tests. Create test DataFrames with specific hash values. For derived fields, test boundary conditions explicitly (e.g., exactly 30 days for readmission).

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS2.4 |
| DMS | SS6 (SCD2 hash columns for test assertions) |
| STM | -- |
| DQS | -- |
