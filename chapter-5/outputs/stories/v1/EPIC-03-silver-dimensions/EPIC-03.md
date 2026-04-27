# EPIC-03: Silver Dimensions Layer (SCD Type 2)

| Field | Value |
|-------|-------|
| **LLD Section** | §5.2 |
| **Epic Scope** | layer |
| **Stories** | 4 |
| **Total Points** | 21 |
| **Sprints** | 3 |
| **Status** | To Do |

## Objective

Build the four Silver dimension transforms with SCD Type 2 (patients, organizations, providers, payers) per LLD §5.2. Each runs SHA-256 hash + Delta MERGE INTO, applies inline SE row_dq + agg_dq, and lands in `unity.silver.<dim>`. Closes itself with perf tuning + local-DAG + UC integration test.

**Deploy Scope**: N/A — layer completes at integration-test; system-wide deploy handled in trailing release epic.

## Scope

### In Scope
- 4 Silver dimension modules under `src/patient_360/silver/transform_{dim}.py`
- SCD2 hash + MERGE INTO via `utils/scd2.py`
- Inline SE row_dq + agg_dq per DQS §2 / §4
- 4 Silver dim DQ rule YAMLs in `dq_rules/`
- Silver-dims perf tuning (broadcast small dims, shuffle.partitions)
- Integration test triggering Silver-dims subtree on local Airflow against UC OSS local

### Out of Scope
- Silver fact tables (EPIC-04)
- Gold tables (EPIC-05)
- Reconciliation_silver (EPIC-04 closure — recon spans dims+facts)

## Stories

| ID | Title | Type | Points | Sprint | Dependencies |
|----|-------|------|--------|--------|-------------|
| STORY-03-001 | Implement transform_patients_silver (SCD2) | build | 5 | 2 | STORY-01-004, STORY-02-007 |
| STORY-03-002 | Implement transform_organizations / providers / payers silver (SCD2) | build | 8 | 3 | STORY-03-001 |
| STORY-03-003 | Silver-dims perf — broadcast small dims + shuffle tuning | performance-optimization | 3 | 3 | STORY-03-002 |
| STORY-03-004 | Integration test — Silver-dims DAG subtree on Airflow local against UC OSS local | integration-test | 5 | 3 | STORY-03-003 |

## Layer Closure Sequence

1. **Build** → STORY-03-001, STORY-03-002.
2. **Performance Optimization**:
   - STORY-03-003: Silver-dims perf — broadcast small dims + shuffle tuning
3. **Local Integration Testing**:
   - STORY-03-004: Integration test — Silver-dims DAG subtree on Airflow local against UC OSS local
4. **Deployment Validation**:
   - _N/A — layer moves to Done after integration testing; system-wide deploy in trailing release epic._

## Acceptance Criteria (Epic-Level)

- [ ] All 4 Silver dim Delta tables (`unity.silver.clinical_patients`, `unity.silver.reference_{organizations,providers,payers}`) populated [LLD §5.2]
- [ ] SCD2 versioning columns (`effective_from`, `effective_to`, `is_current`, `record_hash`) present on each [LLD §5.2, DMS §6]
- [ ] `silver_se_stats` populated with run rows [LLD §8.6.1]
- [ ] Re-run with unchanged source produces 0 new SCD2 versions [LLD §4.5]

## Risks & Assumptions

- Alex must own SCD2 work (Spark expertise constraint)
- Bronze must complete before Silver-dims runs (DAG sequencing per §4.3)
