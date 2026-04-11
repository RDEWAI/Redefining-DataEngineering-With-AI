# STORY-05-002: Build Clinical History Gold Table

| Field | Value |
|-------|-------|
| **Epic** | EPIC-05: Gold Layer + Reconciliation |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 5 |
| **Sprint** | Sprint 7 |
| **Dependencies** | STORY-04-012 |
| **Status** | To Do |

## User Story

As a data engineer, I want the patient_clinical_history Gold table built with full encounter history and readmission flags so that physicians and nurses can review complete clinical timelines.

## Description

Implement `src/pipelines/gold/build_patient_clinical_history.py` that joins clinical_patients, clinical_encounters, clinical_conditions, clinical_medications, clinical_observations, clinical_procedures, clinical_immunizations, and clinical_careplans to build a comprehensive clinical history table. Include is_30_day_readmission flag from derived_fields.py. Inline SE with action_if_failed: fail. Cache clinical_patients and clinical_encounters (shared with other Gold tasks).

## Acceptance Criteria

- [ ] Joins 8 Silver tables to produce clinical history [LLD §5.3]
- [ ] Readmission flag (is_30_day_readmission) computed per DRD SS5.2 [DRD §5.2]
- [ ] Broadcast join for clinical_patients (is_current=TRUE) [LLD §6.2]
- [ ] Output written to `warehouse/{env}/gold/patient_clinical_history/` with full overwrite [LLD §3.3]
- [ ] Inline SE validates Gold clinical history rules with action_if_failed: fail [DQS §2]
- [ ] Caching applied for clinical_patients and clinical_encounters [LLD §6.4]

## Technical Notes

- **Upstream references**: LLD SS5.3, SS6.2, SS6.4, DMS SS5 (patient_clinical_history schema)
- **Implementation hints**: This is the widest join in the pipeline. Use cached DataFrames from STORY-05-001 if running in same Spark session. The readmission flag requires window functions on encounter dates partitioned by patient_id.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS5.3, SS6.2, SS6.4 |
| DMS | SS5 (patient_clinical_history schema) |
| STM | Tab:Silver-to-Gold (patient_clinical_history) |
| DQS | SS2 (Gold clinical history rules) |
