# STORY-04-001: Transform Encounters to Silver

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts + Reconciliation |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 3 |
| **Sprint** | Sprint 6 |
| **Dependencies** | STORY-03-002, STORY-03-003, STORY-03-004 |
| **Status** | To Do |

## User Story

As a data engineer, I want the encounters fact table transformed to Silver with FK validation against dimension tables so that referential integrity is enforced and downstream fact tables have a reliable encounters foundation.

## Description

Implement `src/pipelines/silver/transform_encounters.py` that reads Bronze `synthea_encounters`, validates foreign keys against Silver dimension tables (patients, organizations, providers), applies code system mappings for encounter class, and writes to `warehouse/{env}/silver/clinical/clinical_encounters/`. Inline SE with action_if_failed: fail executes rules DQ-FLD-060 to DQ-FLD-065. This is the critical junction table -- 7 of 9 fact tables depend on it.

## Acceptance Criteria

- [ ] Reads from Bronze `synthea_encounters` and writes to Silver `clinical_encounters` [LLD §5.2]
- [ ] FK validation against clinical_patients (patient_id), reference_organizations (organization_id), reference_providers (provider_id) [DMS §5]
- [ ] Encounter class code mapped via code_systems.py [STM Tab:Code Systems]
- [ ] Inline SE validates rules DQ-FLD-060 to DQ-FLD-065 with action_if_failed: fail [DQS §2]
- [ ] Empty input triggers task failure [LLD §5.2]
- [ ] Delta write uses `replaceWhere ds = '{ds}'` for idempotency [LLD §4.5]

## Technical Notes

- **Upstream references**: LLD SS5.2, DMS SS5 (clinical_encounters schema), DQS SS2
- **Implementation hints**: Depends on patients, organizations, and providers Silver dimensions completing first. Use left anti join to detect FK orphans. 340K rows -- moderate size.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS5.2 (encounters Silver task) |
| DMS | SS5 (clinical_encounters schema) |
| STM | Tab:Bronze-to-Silver (encounters) |
| DQS | SS2 (DQ-FLD-060 to DQ-FLD-065) |
