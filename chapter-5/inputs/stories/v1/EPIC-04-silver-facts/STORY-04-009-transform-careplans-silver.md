# STORY-04-009: Transform Careplans to Silver

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts + Reconciliation |
| **Priority** | P2 -- Important |
| **Story Points** | 2 |
| **Sprint** | Sprint 6 |
| **Dependencies** | STORY-04-001 |
| **Status** | To Do |

## User Story

As a data engineer, I want the careplans fact table transformed to Silver with FK validation so that care plan records are linked to valid encounters.

## Description

Implement `src/pipelines/silver/transform_careplans.py` that reads Bronze `synthea_careplans`, validates FKs against encounters, and writes to Silver `clinical_careplans`. Inline SE with action_if_failed: drop. Rules DQ-FLD-091 to DQ-FLD-092.

## Acceptance Criteria

- [ ] Reads from Bronze and writes to Silver `clinical_careplans` [LLD §5.2]
- [ ] FK validated against clinical_encounters [DMS §5]
- [ ] Inline SE validates rules DQ-FLD-091 to DQ-FLD-092 with action_if_failed: drop [DQS §2]
- [ ] Empty input writes empty table [LLD §5.2]

## Technical Notes

- **Upstream references**: LLD SS5.2, DQS SS2 (DQ-FLD-091 to DQ-FLD-092)
- **Implementation hints**: Careplans feed the clinical_history Gold table.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS5.2 |
| DMS | SS5 (clinical_careplans schema) |
| STM | Tab:Bronze-to-Silver (careplans) |
| DQS | SS2 (DQ-FLD-091 to DQ-FLD-092) |
