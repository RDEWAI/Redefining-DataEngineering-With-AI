# STORY-05-001: Build Patient Summary Gold Table

| Field | Value |
|-------|-------|
| **Epic** | EPIC-05: Gold Layer + Reconciliation |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 5 |
| **Sprint** | Sprint 7 |
| **Dependencies** | STORY-04-012 |
| **Status** | To Do |

## User Story

As a data engineer, I want the patient_summary Gold table built with denormalized arrays for allergies, conditions, and medications so that clinical users can search and view complete patient profiles in under 2 seconds.

## Description

Implement `src/pipelines/gold/build_patient_summary.py` that joins Silver dimension and fact tables to produce a denormalized patient_summary Gold table. The table includes patient demographics (from clinical_patients WHERE is_current=TRUE), ARRAY-aggregated allergies, conditions, and medications, encounter counts, and latest encounter date. Use broadcast joins for small dimension tables. Inline SE with action_if_failed: fail validates DQ-FLD-105 to DQ-FLD-140 including ARRAY validations. Output must contain exactly 5,767 patients (100% completeness).

## Acceptance Criteria

- [ ] Reads from clinical_patients (is_current=TRUE), clinical_encounters, clinical_conditions, clinical_medications, clinical_allergies [LLD §5.3]
- [ ] Broadcast join used for clinical_patients (5,767 rows) [LLD §6.2]
- [ ] ARRAY columns for allergies, conditions, medications per Gold schema [DMS §5]
- [ ] Output written to `warehouse/{env}/gold/patient_summary/` with full overwrite [LLD §3.3]
- [ ] Inline SE validates rules DQ-FLD-105 to DQ-FLD-140 with action_if_failed: fail [DQS §2]
- [ ] Output contains exactly 5,767 patients (100% completeness) [DRD §4.4]
- [ ] Empty input triggers task failure [LLD §5.3]

## Technical Notes

- **Upstream references**: LLD SS5.3, SS6.2, SS6.4, DMS SS5 (patient_summary schema), DQS SS2, DRD SS4.4
- **Implementation hints**: Pre-aggregate arrays in subquery before join to avoid OOM. Cache clinical_patients and clinical_encounters (used by all 3 Gold tasks per LLD SS6.4). Filter dimensions with `is_current=TRUE` before broadcast per LLD SS6.2.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS5.3, SS6.2, SS6.4 |
| DMS | SS5 (patient_summary schema) |
| STM | Tab:Silver-to-Gold (patient_summary) |
| DQS | SS2 (DQ-FLD-105 to DQ-FLD-140) |
