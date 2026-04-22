# STORY-03-004: Transform Providers to Silver (SCD2)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-03: Silver Dimensions -- SCD Type 2 |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 2 |
| **Sprint** | Sprint 5 |
| **Dependencies** | STORY-03-001 |
| **Status** | To Do |

## User Story

As a data engineer, I want the providers dimension table transformed to Silver with SCD Type 2 tracking so that encounter FK references resolve correctly and provider changes are tracked.

## Description

Implement `src/pipelines/silver/transform_providers.py` that reads from Bronze `synthea_providers`, applies SCD Type 2 merge, and writes to `warehouse/{env}/silver/reference/reference_providers/`. Inline SE validation with action_if_failed: fail executes rules DQ-FLD-097 to DQ-FLD-099.

## Acceptance Criteria

- [ ] Reads from Bronze `synthea_providers` and writes to Silver `reference_providers` [LLD §5.2]
- [ ] SCD Type 2 merge applied using generic scd2.py function [DMS §6]
- [ ] Inline SE validates rules DQ-FLD-097 to DQ-FLD-099 with action_if_failed: fail [DQS §2]
- [ ] Empty input triggers task failure [LLD §5.2]
- [ ] Output table includes SCD2 columns [DMS §6]

## Technical Notes

- **Upstream references**: LLD SS5.2, DMS SS6, DQS SS2 (DQ-FLD-097 to DQ-FLD-099)
- **Implementation hints**: Providers is a small table (~1K rows). FK dimension for encounters. Runs in parallel with patients, organizations, and payers transforms.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS5.2 (providers Silver task) |
| DMS | SS5 (reference_providers schema), SS6 (SCD2) |
| STM | Tab:Bronze-to-Silver (providers) |
| DQS | SS2 (DQ-FLD-097 to DQ-FLD-099) |
