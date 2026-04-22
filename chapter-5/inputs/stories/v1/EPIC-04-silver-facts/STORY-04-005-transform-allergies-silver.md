# STORY-04-005: Transform Allergies to Silver (Safety Critical)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts + Reconciliation |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 3 |
| **Sprint** | Sprint 6 |
| **Dependencies** | STORY-03-002 |
| **Status** | To Do |

## User Story

As a data engineer, I want the allergies fact table transformed to Silver with safety-critical DQ enforcement so that no allergy record is ever suppressed or lost, protecting patient safety.

## Description

Implement `src/pipelines/silver/transform_allergies.py` that reads Bronze `synthea_allergies`, validates FK against patients (not encounters -- allergies depend directly on patients), applies NULL severity defaulting to "Unknown", and writes to `warehouse/{env}/silver/clinical/clinical_allergies/`. This is safety-critical per DRD SS1.3: inline SE with action_if_failed: fail ensures any DQ failure halts the pipeline rather than dropping allergy records. DQ rules DQ-FLD-080 to DQ-FLD-083.

## Acceptance Criteria

- [ ] Reads from Bronze and writes to Silver `clinical_allergies` [LLD §5.2]
- [ ] FK validated against clinical_patients (NOT encounters) [LLD §4.2]
- [ ] NULL severity values defaulted to "Unknown" per DRD SS1.3 [DRD §1.3]
- [ ] Inline SE validates rules DQ-FLD-080 to DQ-FLD-083 with action_if_failed: fail [DQS §2, DRD SS1.3]
- [ ] Empty input triggers task failure (safety-critical) [LLD §5.2]
- [ ] No allergy records are ever dropped or suppressed [DRD §1.3]

## Technical Notes

- **Upstream references**: LLD SS5.2, DRD SS1.3 (allergy safety requirement), DQS SS2, LLD SS8.4 (Escalation Path)
- **Implementation hints**: This table should be implemented FIRST within this phase due to safety criticality. Unlike other Silver facts, allergies depend on patients_silver (not encounters_silver). Any DQ failure triggers PagerDuty + Clinical Ops Director alert per LLD SS8.4.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS5.2, SS8.3, SS8.4 |
| DMS | SS5 (clinical_allergies schema) |
| STM | Tab:Bronze-to-Silver (allergies) |
| DQS | SS2 (DQ-FLD-080 to DQ-FLD-083) |
