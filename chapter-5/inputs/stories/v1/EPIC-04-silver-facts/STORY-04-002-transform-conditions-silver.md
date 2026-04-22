# STORY-04-002: Transform Conditions to Silver

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts + Reconciliation |
| **Priority** | P2 -- Important |
| **Story Points** | 2 |
| **Sprint** | Sprint 6 |
| **Dependencies** | STORY-04-001 |
| **Status** | To Do |

## User Story

As a data engineer, I want the conditions fact table transformed to Silver with FK validation so that clinical condition records are linked to valid encounters and patients.

## Description

Implement `src/pipelines/silver/transform_conditions.py` that reads Bronze `synthea_conditions`, validates FKs against encounters, applies clinical status mapping, and writes to `warehouse/{env}/silver/clinical/clinical_conditions/`. Inline SE with action_if_failed: drop quarantines invalid rows. 209K rows.

## Acceptance Criteria

- [ ] Reads from Bronze and writes to Silver `clinical_conditions` [LLD §5.2]
- [ ] FK validated against clinical_encounters [DMS §5]
- [ ] Inline SE validates rules DQ-FLD-066 to DQ-FLD-070 with action_if_failed: drop [DQS §2]
- [ ] Empty input writes empty table (non-critical) [LLD §5.2]
- [ ] Delta write uses `replaceWhere ds = '{ds}'` [LLD §4.5]

## Technical Notes

- **Upstream references**: LLD SS5.2, DMS SS5, DQS SS2 (DQ-FLD-066 to DQ-FLD-070)
- **Implementation hints**: Depends on encounters_silver. FK orphan records quarantined to dead-letter. Clinical status mapped via code_systems.py.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS5.2 |
| DMS | SS5 (clinical_conditions schema) |
| STM | Tab:Bronze-to-Silver (conditions) |
| DQS | SS2 (DQ-FLD-066 to DQ-FLD-070) |
