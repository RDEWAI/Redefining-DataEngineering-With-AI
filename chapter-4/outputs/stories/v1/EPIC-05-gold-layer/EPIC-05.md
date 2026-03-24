# EPIC-05: Gold Layer + Reconciliation

| Field | Value |
|-------|-------|
| **LLD Section** | Phase 5 (LLD impl-sequence) |
| **Stories** | 6 |
| **Total Points** | 23 |
| **Sprints** | Sprint 7 |
| **Status** | To Do |

## Objective

Build 3 consumer-ready denormalized Gold tables (patient_summary, patient_clinical_history, patient_billing_summary) with inline SE validation, implement Gold DQ rules, add reconciliation_gold with patient and allergy completeness checks, and validate with integration and end-to-end tests.

## Scope

### In Scope
- 3 Gold table builds with broadcast joins and caching
- Gold DQ rules YAML (DQ-FLD-105 to DQ-FLD-140+)
- Reconciliation_gold with 100% patient completeness check
- Gold integration test and full end-to-end test

### Out of Scope
- Observability dashboards (EPIC-06)
- CI/CD pipeline (EPIC-07)
- Performance tuning (EPIC-08)

## Stories

| ID | Title | Points | Sprint | Dependencies |
|----|-------|--------|--------|-------------|
| STORY-05-001 | Build Patient Summary Gold Table | 5 | Sprint 7 | STORY-04-012 |
| STORY-05-002 | Build Clinical History Gold Table | 5 | Sprint 7 | STORY-04-012 |
| STORY-05-003 | Build Billing Summary Gold Table | 3 | Sprint 7 | STORY-04-012 |
| STORY-05-004 | Implement Gold DQ Rules YAML | 2 | Sprint 7 | STORY-02-006 |
| STORY-05-005 | Implement Reconciliation Gold Task | 3 | Sprint 7 | STORY-02-007 |
| STORY-05-006 | Integration Test for Gold Pipeline and End-to-End | 5 | Sprint 7 | STORY-05-005 |

## Acceptance Criteria (Epic-Level)

- [ ] patient_summary contains exactly 5,767 patients (100% completeness) [DRD §4.4]
- [ ] ARRAY columns populated for allergies, conditions, medications [DMS §5]
- [ ] Readmission flags computed correctly in clinical_history [DRD §5.2]
- [ ] Billing summary includes total_visit_cost [DRD §5.2]
- [ ] Reconciliation_gold passes: patient completeness, allergy completeness [DQS §4]
- [ ] End-to-end test: DuckDB -> Bronze -> Silver -> Gold complete [LLD §2.4]

## Risks & Assumptions

- ARRAY Gold builds may timeout -- mitigated by pre-aggregating arrays in subquery
- 100% patient completeness (5,767) is a hard gate -- any data loss blocks this epic
- Assumption: All Silver tables available from EPIC-03 and EPIC-04 completion
