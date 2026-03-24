# STORY-05-005: Implement Reconciliation Gold Task

| Field | Value |
|-------|-------|
| **Epic** | EPIC-05: Gold Layer + Reconciliation |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 3 |
| **Sprint** | Sprint 7 |
| **Dependencies** | STORY-02-007 |
| **Status** | To Do |

## User Story

As a data quality engineer, I want a Gold reconciliation task that validates patient completeness and allergy completeness so that consumer-facing tables meet 100% data requirements before access is granted.

## Description

Extend `src/quality/reconciliation.py` with Gold reconciliation logic and wire `reconciliation_gold` into the Airflow DAG. The task runs after all 3 Gold build tasks complete and executes: (1) row count reconciliation (Silver vs Gold per table), (2) patient completeness assertion (exactly 5,767 patients), (3) allergy completeness (all patients with allergies have them in patient_summary). On CRITICAL failure, block consumer access. Allergy failures trigger PagerDuty + Clinical Ops Director alert.

## Acceptance Criteria

- [ ] Row count reconciliation: Silver vs Gold per table [DQS §4]
- [ ] Patient completeness: exactly 5,767 patients in patient_summary [DQS §4, DRD SS4.4]
- [ ] Allergy completeness: all patient allergies present in patient_summary [DQS §4, DRD SS1.3]
- [ ] `reconciliation_gold` depends on all 3 Gold build tasks [LLD §4.2]
- [ ] CRITICAL failure blocks consumer access [LLD §5.5]
- [ ] Allergy failures route to PagerDuty + Clinical Ops Director [LLD §8.4, DQS SS1]

## Technical Notes

- **Upstream references**: LLD SS5.5, DQS SS4, LLD SS8.3, SS8.4, DRD SS1.3
- **Implementation hints**: Patient completeness is the hard gate: if != 5,767, something was lost in the pipeline. Allergy completeness cross-checks patient_summary allergy arrays against clinical_allergies distinct patient count.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS5.5, SS8.3, SS8.4 |
| DMS | SS5 (Gold schemas) |
| STM | -- |
| DQS | SS4 (Gold reconciliation), SS1 (allergy escalation) |
