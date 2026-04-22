# EPIC-03: Silver Dimensions -- SCD Type 2

| Field | Value |
|-------|-------|
| **LLD Section** | Phase 3 (LLD impl-sequence) |
| **Stories** | 8 |
| **Total Points** | 23 |
| **Sprints** | Sprint 5 |
| **Status** | To Do |

## Objective

Implement SCD Type 2 processing for 4 dimension tables (patients, organizations, providers, payers) with inline SE validation, plus shared transformation modules for code system mappings and derived fields. This is the most complex transformation logic in the pipeline.

## Scope

### In Scope
- Generic SCD2 merge function using SHA-256 and Delta MERGE INTO
- 4 dimension Silver transforms with SCD2
- Code system mappings (HL7, SNOMED)
- Derived fields module (calculated_age, medication_status, readmission, cost)
- Unit tests for SCD2 and derived fields

### Out of Scope
- Silver fact tables (EPIC-04)
- Silver DQ rules YAML (EPIC-04)
- Silver reconciliation (EPIC-04)

## Stories

| ID | Title | Points | Sprint | Dependencies |
|----|-------|--------|--------|-------------|
| STORY-03-001 | Implement SCD2 Generic Merge Function | 5 | Sprint 5 | STORY-02-010 |
| STORY-03-002 | Transform Patients to Silver (SCD2) | 3 | Sprint 5 | STORY-03-001 |
| STORY-03-003 | Transform Organizations to Silver (SCD2) | 2 | Sprint 5 | STORY-03-001 |
| STORY-03-004 | Transform Providers to Silver (SCD2) | 2 | Sprint 5 | STORY-03-001 |
| STORY-03-005 | Transform Payers to Silver (SCD2) | 2 | Sprint 5 | STORY-03-001 |
| STORY-03-006 | Implement Code System Mappings | 3 | Sprint 5 | STORY-01-001 |
| STORY-03-007 | Implement Derived Fields Module | 3 | Sprint 5 | STORY-01-001 |
| STORY-03-008 | Unit Tests for SCD2 and Derived Fields | 3 | Sprint 5 | STORY-03-001, STORY-03-007 |

## Acceptance Criteria (Epic-Level)

- [ ] SCD2 merge function handles new, changed, and unchanged records correctly [DMS §6]
- [ ] All 4 dimension tables have is_current, effective_from, effective_to, scd2_version columns [DMS §6]
- [ ] PHI (SSN) dropped from patients at Silver boundary [DRD §7]
- [ ] Code system mappings produce standardized values [STM Tab:Code Systems]
- [ ] Derived fields computed correctly with edge case handling [DRD §5.2]
- [ ] Unit tests >= 90% coverage on SCD2 and derived fields [LLD §2.4]

## Risks & Assumptions

- SCD2 hash mismatch causing false changes -- mitigated by unit test with known input/output pairs
- Hash columns must match DMS SS6 exactly -- verify against DMS during development
- Assumption: Bronze data is available from EPIC-02 completion
