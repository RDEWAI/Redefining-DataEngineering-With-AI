# STORY-03-002: Transform Patients to Silver (SCD2)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-03: Silver Dimensions -- SCD Type 2 |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 3 |
| **Sprint** | Sprint 5 |
| **Dependencies** | STORY-03-001 |
| **Status** | To Do |

## User Story

As a data engineer, I want the patients dimension table transformed to Silver with SCD Type 2 tracking and inline SE validation so that clinical applications always see the current patient record while maintaining full change history.

## Description

Implement `src/pipelines/silver/transform_patients.py` that reads from Bronze `synthea_patients`, drops PHI columns (SSN and other PII per DRD SS7), computes derived fields (calculated_age from birthdate/deathdate), applies SCD Type 2 merge using the generic scd2.py function, and writes to `warehouse/{env}/silver/clinical/clinical_patients/`. Inline SE validation with action_if_failed: fail executes DQ rules DQ-FLD-046 through DQ-FLD-059 and DQ-FLD-102 through DQ-FLD-104. This is the most critical dimension -- it has 5,767 patients and is required by all downstream Silver facts and Gold tables.

## Acceptance Criteria

- [ ] Reads from Bronze `synthea_patients` and writes to Silver `clinical_patients` [LLD §5.2]
- [ ] PHI columns dropped per DRD SS7 (SSN never present in Silver) [DRD §7, LLD SS5.2]
- [ ] `calculated_age` derived field computed from birthdate/deathdate [DRD §5.2]
- [ ] SCD Type 2 merge applied using generic scd2.py function [DMS §6]
- [ ] Inline SE validates rules DQ-FLD-046 to DQ-FLD-059, DQ-FLD-102 to DQ-FLD-104 with action_if_failed: fail [DQS §2]
- [ ] Empty input triggers task failure (empty_input_behavior: fail) [LLD §5.2]
- [ ] Output table has is_current, effective_from, effective_to, scd2_version columns [DMS §6]

## Technical Notes

- **Upstream references**: LLD SS5.2, DMS SS6, DRD SS5.2 (derived fields), DRD SS7 (PHI), DQS SS2 (Silver patient rules)
- **Implementation hints**: Hash columns for patients SCD2 defined in DMS SS6. Broadcast hint not needed here (processing, not joining). This task depends on reconciliation_bronze in the DAG.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS5.2 (patients Silver task) |
| DMS | SS5 (clinical_patients schema), SS6 (SCD2) |
| STM | Tab:Bronze-to-Silver (patients) |
| DQS | SS2 (DQ-FLD-046 to DQ-FLD-059, DQ-FLD-102 to DQ-FLD-104) |
