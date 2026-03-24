# STORY-04-007: Transform Procedures to Silver

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts + Reconciliation |
| **Priority** | P2 -- Important |
| **Story Points** | 2 |
| **Sprint** | Sprint 6 |
| **Dependencies** | STORY-04-001 |
| **Status** | To Do |

## User Story

As a data engineer, I want the procedures fact table transformed to Silver with FK validation so that procedure records are linked to valid encounters.

## Description

Implement `src/pipelines/silver/transform_procedures.py` that reads Bronze `synthea_procedures`, validates FKs against encounters, and writes to Silver `clinical_procedures`. Inline SE with action_if_failed: drop. Rules DQ-FLD-084 to DQ-FLD-087. 946K rows -- second largest fact table.

## Acceptance Criteria

- [ ] Reads from Bronze and writes to Silver `clinical_procedures` [LLD §5.2]
- [ ] FK validated against clinical_encounters [DMS §5]
- [ ] Inline SE validates rules DQ-FLD-084 to DQ-FLD-087 with action_if_failed: drop [DQS §2]
- [ ] Empty input writes empty table [LLD §5.2]

## Technical Notes

- **Upstream references**: LLD SS5.2, DQS SS2 (DQ-FLD-084 to DQ-FLD-087)
- **Implementation hints**: 946K rows is moderately large. May need 2 output partitions per LLD SS6.5.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS5.2, SS6.5 |
| DMS | SS5 (clinical_procedures schema) |
| STM | Tab:Bronze-to-Silver (procedures) |
| DQS | SS2 (DQ-FLD-084 to DQ-FLD-087) |
