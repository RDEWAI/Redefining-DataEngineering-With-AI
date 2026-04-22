# STORY-05-003: Build Billing Summary Gold Table

| Field | Value |
|-------|-------|
| **Epic** | EPIC-05: Gold Layer + Reconciliation |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 3 |
| **Sprint** | Sprint 7 |
| **Dependencies** | STORY-04-012 |
| **Status** | To Do |

## User Story

As a data engineer, I want the patient_billing_summary Gold table built with cost aggregations so that billing staff can review patient financial data with role-based access.

## Description

Implement `src/pipelines/gold/build_patient_billing_summary.py` that joins clinical_patients, clinical_encounters, billing_claims, and reference_payers to produce a billing summary. Include total_visit_cost from derived_fields.py. Inline SE with action_if_failed: fail. Broadcast reference_payers (10 rows). This table serves 50 billing staff users with restricted access.

## Acceptance Criteria

- [ ] Joins clinical_patients, clinical_encounters, billing_claims, reference_payers [LLD §5.3]
- [ ] total_visit_cost computed per DRD SS5.2 [DRD §5.2]
- [ ] Broadcast join for reference_payers (is_current=TRUE, 10 rows) [LLD §6.2]
- [ ] Output written to `warehouse/{env}/gold/patient_billing_summary/` with full overwrite [LLD §3.3]
- [ ] Inline SE validates Gold billing rules with action_if_failed: fail [DQS §2]
- [ ] Empty input triggers task failure [LLD §5.3]

## Technical Notes

- **Upstream references**: LLD SS5.3, SS6.2, DMS SS5 (patient_billing_summary schema), DRD SS5.2
- **Implementation hints**: reference_payers is tiny (10 rows) -- broadcast and cache. Billing-only access pattern means this table may have separate access controls in production.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS5.3, SS6.2 |
| DMS | SS5 (patient_billing_summary schema) |
| STM | Tab:Silver-to-Gold (patient_billing_summary) |
| DQS | SS2 (Gold billing rules) |
