# STORY-03-005: Transform Payers to Silver (SCD2)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-03: Silver Dimensions -- SCD Type 2 |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 2 |
| **Sprint** | Sprint 5 |
| **Dependencies** | STORY-03-001 |
| **Status** | To Do |

## User Story

As a data engineer, I want the payers dimension table transformed to Silver with SCD Type 2 tracking so that billing FK references resolve correctly and payer changes are tracked.

## Description

Implement `src/pipelines/silver/transform_payers.py` that reads from Bronze `synthea_payers`, applies SCD Type 2 merge, and writes to `warehouse/{env}/silver/reference/reference_payers/`. Inline SE validation with action_if_failed: fail executes rules DQ-FLD-100 to DQ-FLD-101.

## Acceptance Criteria

- [ ] Reads from Bronze `synthea_payers` and writes to Silver `reference_payers` [LLD §5.2]
- [ ] SCD Type 2 merge applied using generic scd2.py function [DMS §6]
- [ ] Inline SE validates rules DQ-FLD-100 to DQ-FLD-101 with action_if_failed: fail [DQS §2]
- [ ] Empty input triggers task failure [LLD §5.2]
- [ ] Output table includes SCD2 columns [DMS §6]

## Technical Notes

- **Upstream references**: LLD SS5.2, DMS SS6, DQS SS2 (DQ-FLD-100 to DQ-FLD-101)
- **Implementation hints**: Payers is very small (~10 rows). FK dimension for billing_claims. Used by billing_summary Gold table with broadcast join.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS5.2 (payers Silver task) |
| DMS | SS5 (reference_payers schema), SS6 (SCD2) |
| STM | Tab:Bronze-to-Silver (payers) |
| DQS | SS2 (DQ-FLD-100 to DQ-FLD-101) |
