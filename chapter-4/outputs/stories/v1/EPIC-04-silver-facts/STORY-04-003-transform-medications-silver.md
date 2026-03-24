# STORY-04-003: Transform Medications to Silver

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts + Reconciliation |
| **Priority** | P2 -- Important |
| **Story Points** | 2 |
| **Sprint** | Sprint 6 |
| **Dependencies** | STORY-04-001 |
| **Status** | To Do |

## User Story

As a data engineer, I want the medications fact table transformed to Silver with medication_status derived field so that clinical applications see accurate active/completed/stopped status.

## Description

Implement `src/pipelines/silver/transform_medications.py` that reads Bronze `synthea_medications`, validates FKs against encounters, computes `medication_status` derived field, and writes to `warehouse/{env}/silver/clinical/clinical_medications/`. Inline SE with action_if_failed: drop. 290K rows.

## Acceptance Criteria

- [ ] Reads from Bronze and writes to Silver `clinical_medications` [LLD §5.2]
- [ ] FK validated against clinical_encounters [DMS §5]
- [ ] `medication_status` derived from start/stop dates via derived_fields.py [DRD §5.2]
- [ ] Inline SE validates rules DQ-FLD-071 to DQ-FLD-076 with action_if_failed: drop [DQS §2]
- [ ] Empty input writes empty table [LLD §5.2]

## Technical Notes

- **Upstream references**: LLD SS5.2, DMS SS5, DQS SS2 (DQ-FLD-071 to DQ-FLD-076), DRD SS5.2
- **Implementation hints**: medication_status: active if stop_date is NULL and start_date <= current_date, completed if stop_date is not NULL, stopped otherwise.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS5.2 |
| DMS | SS5 (clinical_medications schema) |
| STM | Tab:Bronze-to-Silver (medications) |
| DQS | SS2 (DQ-FLD-071 to DQ-FLD-076) |
