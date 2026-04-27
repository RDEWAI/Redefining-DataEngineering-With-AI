# EPIC-04: Silver Facts Layer

| Field | Value |
|-------|-------|
| **LLD Section** | §5.2 |
| **Epic Scope** | layer |
| **Stories** | 6 |
| **Total Points** | 26 |
| **Sprints** | 4 |
| **Status** | To Do |

## Objective

Build the 9 Silver fact transforms (encounters, conditions, medications, observations, allergies, immunizations, procedures, claims, careplans) per LLD §5.2. Encounters is the FK hub; the other 8 fan out from it. Each runs inline SE row_dq + agg_dq and writes Delta to `unity.silver.<table>`. Includes `reconciliation_silver` (cross-table query_dq + SE-evidence gate). Closes itself with perf tuning + integration test.

**Deploy Scope**: N/A — layer completes at integration-test; system-wide deploy handled in trailing release epic.

## Scope

### In Scope
- 9 Silver fact transform modules under `src/patient_360/silver/`
- 9 DQ rule YAMLs in `dq_rules/`
- `reconciliation_silver` query_dq + SE-evidence gate
- Silver-facts perf tuning (sort-merge, partitioning observations to 8)
- Local DAG integration test

### Out of Scope
- SCD2 dimensions (EPIC-03)
- Gold tables (EPIC-05)

## Stories

| ID | Title | Type | Points | Sprint | Dependencies |
|----|-------|------|--------|--------|-------------|
| STORY-04-001 | Implement transform_encounters_silver (FK hub) | build | 5 | 3 | STORY-03-004 |
| STORY-04-002 | Implement 4 high-priority fact transforms (allergies, conditions, medications, observations) | build | 8 | 4 | STORY-04-001 |
| STORY-04-003 | Implement 4 remaining fact transforms (immunizations, procedures, claims, careplans) | build | 5 | 4 | STORY-04-001 |
| STORY-04-004 | reconciliation_silver query_dq + SE-evidence gate | build | 3 | 4 | STORY-04-002, STORY-04-003 |
| STORY-04-005 | Silver-facts perf — observations partitioning + sort-merge tuning | performance-optimization | 2 | 4 | STORY-04-004 |
| STORY-04-006 | Integration test — Silver-facts subtree on Airflow local against UC OSS local | integration-test | 3 | 4 | STORY-04-005 |

## Layer Closure Sequence

1. **Build** → STORY-04-001..004.
2. **Performance Optimization**:
   - STORY-04-005: Silver-facts perf — observations partitioning + sort-merge tuning
3. **Local Integration Testing**:
   - STORY-04-006: Integration test — Silver-facts subtree on Airflow local against UC OSS local
4. **Deployment Validation**:
   - _N/A — layer moves to Done after integration testing; system-wide deploy in trailing release epic._

## Acceptance Criteria (Epic-Level)

- [ ] All 9 Silver fact tables present in `unity.silver.*` [LLD §5.2]
- [ ] FK orphan rate < 0.1% per allergy/encounter checks [DQS §4]
- [ ] `reconciliation_silver` fails-closed when `silver_se_stats` empty for run [LLD §8.6.1]
- [ ] `clinical_allergies` writes use `action_if_failed: fail` (safety-critical) [DRD §1.3]

## Risks & Assumptions

- Fact volumes vary 30K–4.4M rows; observations needs 8-partition repartition [LLD §6.5]
- Encounters must complete before its 8 dependents
