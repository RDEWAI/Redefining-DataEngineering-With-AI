# EPIC-04: Silver Facts + Reconciliation

| Field | Value |
|-------|-------|
| **LLD Section** | Phase 4 (LLD impl-sequence) |
| **Stories** | 12 |
| **Total Points** | 30 |
| **Sprints** | Sprint 6 |
| **Status** | To Do |

## Objective

Transform all 9 Silver fact tables with inline SE validation, implement Silver DQ rules YAML, add reconciliation_silver for cross-table checks, and validate with integration tests. The allergies table is safety-critical and should be implemented first.

## Scope

### In Scope
- 9 Silver fact table transforms (encounters, conditions, medications, observations, allergies, immunizations, procedures, claims, careplans)
- Silver DQ rules YAML (DQ-FLD-046 to DQ-FLD-104)
- Reconciliation_silver task
- Silver integration test

### Out of Scope
- Gold layer builds (EPIC-05)
- Observability/monitoring (EPIC-06)

## Stories

| ID | Title | Points | Sprint | Dependencies |
|----|-------|--------|--------|-------------|
| STORY-04-001 | Transform Encounters to Silver | 3 | Sprint 6 | STORY-03-002, STORY-03-003, STORY-03-004 |
| STORY-04-002 | Transform Conditions to Silver | 2 | Sprint 6 | STORY-04-001 |
| STORY-04-003 | Transform Medications to Silver | 2 | Sprint 6 | STORY-04-001 |
| STORY-04-004 | Transform Observations to Silver | 3 | Sprint 6 | STORY-04-001 |
| STORY-04-005 | Transform Allergies to Silver (Safety Critical) | 3 | Sprint 6 | STORY-03-002 |
| STORY-04-006 | Transform Immunizations to Silver | 2 | Sprint 6 | STORY-04-001 |
| STORY-04-007 | Transform Procedures to Silver | 2 | Sprint 6 | STORY-04-001 |
| STORY-04-008 | Transform Claims to Silver | 2 | Sprint 6 | STORY-04-001 |
| STORY-04-009 | Transform Careplans to Silver | 2 | Sprint 6 | STORY-04-001 |
| STORY-04-010 | Implement Silver DQ Rules YAML | 3 | Sprint 6 | STORY-02-006 |
| STORY-04-011 | Implement Reconciliation Silver Task | 3 | Sprint 6 | STORY-02-007 |
| STORY-04-012 | Integration Test for Silver Pipeline | 3 | Sprint 6 | STORY-04-011 |

## Acceptance Criteria (Epic-Level)

- [ ] All 9 Silver fact tables produced with valid FK references [LLD §5.2]
- [ ] Allergies transform uses action_if_failed: fail (safety critical) [DRD §1.3]
- [ ] Observations table processes 4.4M rows within performance budget [LLD §6.5]
- [ ] Silver DQ rules DQ-FLD-046 to DQ-FLD-104 implemented [DQS §2]
- [ ] Reconciliation_silver passes: row counts, FK orphans, SCD2 version sanity [DQS §4]
- [ ] Integration test verifies full Bronze -> Silver path [LLD §2.4]

## Risks & Assumptions

- Observations table (4.4M rows) may cause OOM -- mitigated by shuffle partition tuning to 8
- Priority: allergies (4.5) should be implemented first due to safety criticality
- Assumption: Silver dimensions (EPIC-03) complete before fact processing begins
