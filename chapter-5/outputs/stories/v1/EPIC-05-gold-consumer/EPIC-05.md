# EPIC-05: Gold Consumer Layer

| Field | Value |
|-------|-------|
| **LLD Section** | §5.3 |
| **Epic Scope** | layer |
| **Stories** | 5 |
| **Total Points** | 21 |
| **Sprints** | 4 |
| **Status** | To Do |

## Objective

Build the 3 Gold consumer tables (`patient_summary`, `patient_clinical_history`, `patient_billing_summary`) per LLD §5.3, plus `reconciliation_gold` and Gold layer integration test. Each Gold builder denormalizes Silver into a consumer-friendly wide table, applies inline SE, and writes to `unity.gold.<table>`. Closes itself with perf tuning + integration test.

**Deploy Scope**: N/A — layer completes at integration-test; system-wide deploy handled in trailing release epic.

## Scope

### In Scope
- 3 Gold builder modules under `src/patient_360/gold/`
- 3 Gold DQ rule YAMLs in `dq_rules/`
- `reconciliation_gold` query_dq + SE-evidence gate
- Gold perf tuning (cache patient + encounters dim, full-table overwrite)
- Local DAG integration test

### Out of Scope
- Bronze (EPIC-02), Silver (EPIC-03/04)
- CI/CD (EPIC-07)

## Stories

| ID | Title | Type | Points | Sprint | Dependencies |
|----|-------|------|--------|--------|-------------|
| STORY-05-001 | Implement build_patient_summary_gold | build | 5 | 4 | STORY-04-006 |
| STORY-05-002 | Implement build_clinical_history_gold + build_billing_summary_gold | build | 5 | 4 | STORY-05-001 |
| STORY-05-003 | reconciliation_gold query_dq + SE-evidence gate | build | 3 | 4 | STORY-05-002 |
| STORY-05-004 | Gold perf — cache patients/encounters, partition tuning | performance-optimization | 3 | 4 | STORY-05-003 |
| STORY-05-005 | Integration test — Gold subtree on Airflow local against UC OSS local | integration-test | 5 | 4 | STORY-05-004 |

## Layer Closure Sequence

1. **Build** → STORY-05-001..003.
2. **Performance Optimization**:
   - STORY-05-004: Gold perf — cache patients/encounters, partition tuning
3. **Local Integration Testing**:
   - STORY-05-005: Integration test — Gold subtree on Airflow local against UC OSS local
4. **Deployment Validation**:
   - _N/A — layer moves to Done after integration testing; system-wide deploy in trailing release epic._

## Acceptance Criteria (Epic-Level)

- [ ] All 3 Gold tables present in `unity.gold.*` [LLD §5.3]
- [ ] `unity.gold.patient_summary` row count = 5,767 (patient completeness assertion) [DQS §4]
- [ ] `gold_se_stats` populated for run [LLD §8.6.1]
- [ ] `reconciliation_gold` succeeds (Silver→Gold row counts within DQS thresholds) [DQS §4]

## Risks & Assumptions

- Gold tables use full-table overwrite (idempotent) [LLD §4.5]
- Allergy completeness check elevated path to Clinical Ops Director per DQS §1
