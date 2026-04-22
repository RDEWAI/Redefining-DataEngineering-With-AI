# STORY-04-006: Transform Immunizations to Silver

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts + Reconciliation |
| **Priority** | P2 -- Important |
| **Story Points** | 2 |
| **Sprint** | Sprint 6 |
| **Dependencies** | STORY-04-001 |
| **Status** | To Do |

## User Story

As a data engineer, I want the immunizations fact table transformed to Silver with FK validation so that vaccination records are linked to valid encounters.

## Description

Implement `src/pipelines/silver/transform_immunizations.py` that reads Bronze `synthea_immunizations`, validates FKs against encounters, and writes to Silver `clinical_immunizations`. Inline SE with action_if_failed: drop. Rules DQ-FLD-088 to DQ-FLD-090.

## Acceptance Criteria

- [ ] Reads from Bronze and writes to Silver `clinical_immunizations` [LLD §5.2]
- [ ] FK validated against clinical_encounters [DMS §5]
- [ ] Inline SE validates rules DQ-FLD-088 to DQ-FLD-090 with action_if_failed: drop [DQS §2]
- [ ] Empty input writes empty table [LLD §5.2]

## Technical Notes

- **Upstream references**: LLD SS5.2, DQS SS2 (DQ-FLD-088 to DQ-FLD-090)
- **Implementation hints**: Straightforward FK validation and write. Runs in parallel with other Silver fact tables after encounters completes.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS5.2 |
| DMS | SS5 (clinical_immunizations schema) |
| STM | Tab:Bronze-to-Silver (immunizations) |
| DQS | SS2 (DQ-FLD-088 to DQ-FLD-090) |
