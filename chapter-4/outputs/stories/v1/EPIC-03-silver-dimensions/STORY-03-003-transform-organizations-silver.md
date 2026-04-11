# STORY-03-003: Transform Organizations to Silver (SCD2)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-03: Silver Dimensions -- SCD Type 2 |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 2 |
| **Sprint** | Sprint 5 |
| **Dependencies** | STORY-03-001 |
| **Status** | To Do |

## User Story

As a data engineer, I want the organizations dimension table transformed to Silver with SCD Type 2 tracking so that encounter FK references resolve correctly and organization changes are tracked.

## Description

Implement `src/pipelines/silver/transform_organizations.py` that reads from Bronze `synthea_organizations`, applies SCD Type 2 merge, and writes to `warehouse/{env}/silver/reference/reference_organizations/`. Inline SE validation with action_if_failed: fail executes rules DQ-FLD-095 to DQ-FLD-096. Organizations is a small FK dimension table required by encounters_silver.

## Acceptance Criteria

- [ ] Reads from Bronze `synthea_organizations` and writes to Silver `reference_organizations` [LLD §5.2]
- [ ] SCD Type 2 merge applied using generic scd2.py function [DMS §6]
- [ ] Inline SE validates rules DQ-FLD-095 to DQ-FLD-096 with action_if_failed: fail [DQS §2]
- [ ] Empty input triggers task failure [LLD §5.2]
- [ ] Output table includes SCD2 columns (is_current, effective_from, effective_to) [DMS §6]

## Technical Notes

- **Upstream references**: LLD SS5.2, DMS SS6, DQS SS2 (DQ-FLD-095 to DQ-FLD-096)
- **Implementation hints**: Organizations is a small table (~1K rows). SCD2 hash columns per DMS SS6. This is an FK dimension required by encounters_silver (which depends on patients, organizations, and providers completing first).

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS5.2 (organizations Silver task) |
| DMS | SS5 (reference_organizations schema), SS6 (SCD2) |
| STM | Tab:Bronze-to-Silver (organizations) |
| DQS | SS2 (DQ-FLD-095 to DQ-FLD-096) |
