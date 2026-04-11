# STORY-04-012: Integration Test for Silver Pipeline

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts + Reconciliation |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 3 |
| **Sprint** | Sprint 6 |
| **Dependencies** | STORY-04-011 |
| **Status** | To Do |

## User Story

As a data engineer, I want an integration test that validates the full Silver pipeline path so that we confirm Bronze to Silver transforms work correctly with inline SE and reconciliation.

## Description

Create `tests/integration/test_silver_pipeline.py` that exercises: Bronze tables as input -> all 13 Silver transforms (4 SCD2 dimensions + 9 fact tables) -> inline SE validation -> reconciliation_silver. Verify SCD2 tables have correct versioning, fact tables have valid FK references, derived fields are correct, and reconciliation passes.

## Acceptance Criteria

- [ ] Integration test runs Bronze -> Silver for all 13 tables [LLD §2.4]
- [ ] SCD2 dimension tables verified: is_current, effective_from, effective_to correct [DMS §6]
- [ ] Fact tables verified: FK references resolve, no orphans [DMS §5]
- [ ] Inline SE validation executes during transforms [LLD §5.4]
- [ ] Reconciliation_silver passes for test data [LLD §5.5]
- [ ] Test uses `@pytest.mark.integration` marker [development-standards.md SS5]

## Technical Notes

- **Upstream references**: LLD SS2.4, SS5.2, SS5.4, SS5.5
- **Implementation hints**: Build on Bronze integration test fixtures. Test SCD2 by running transform twice with changed data to verify version management.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS2.4, SS5.2, SS5.4, SS5.5 |
| DMS | SS5, SS6 |
| STM | Tab:Bronze-to-Silver |
| DQS | SS2 (Silver rules), SS4 (reconciliation) |
