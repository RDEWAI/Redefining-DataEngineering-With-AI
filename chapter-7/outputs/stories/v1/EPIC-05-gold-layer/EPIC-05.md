# EPIC-05: Gold Consumer Tables

| Field | Value |
|-------|-------|
| **LLD Section** | §5.3 |
| **Epic Scope** | layer |
| **Stories** | 6 |
| **Total Points** | 25 |
| **Sprints** | 8 |
| **Status** | Draft |

<!--
  Epic Scope vocabulary:
    - layer      → medallion layer epic (Bronze/Silver Dims/Silver Facts/Gold). MUST include closure sequence: performance-optimization → integration-test → (optional) deploy-validation.
    - foundation → scaffold/infra epic (no closure sequence required).
    - crosscut   → cross-layer concerns (observability, release, hardening).
-->

## Objective

Build the 3 denormalized Gold consumer tables (`patient_summary`, `patient_clinical_history`, `patient_billing_summary`) meeting the < 2s p90 query SLA (NFR-1) and 100% patient completeness (NFR-4).


**Deploy Scope**: N/A — layer completes at integration-test; system-wide deploy handled in trailing release epic
<!--
  Deploy Scope must be ONE of:
    - "Layer-scoped — see deploy-validation story below"  (when LLD prescribes layer-scoped deploy work)
    - "N/A — layer completes at integration-test; system-wide deploy handled in trailing release epic"
-->


## Scope

### In Scope

- 3 Gold builders

- `reconciliation_gold` gate (silver-vs-gold row counts + patient/allergy completeness)

- Layer perf (caching + broadcast)

- Local integration test against UC OSS local


### Out of Scope

- Per-layer deploy (system-wide promotion in EPIC-07)


## Stories

| ID | Title | Type | Points | Sprint | Dependencies |
|----|-------|------|--------|--------|-------------|

| STORY-05-001 | Implement build_patient_summary_gold | build | 5 | 8 | STORY-04-012 |

| STORY-05-002 | Implement build_patient_clinical_history_gold | build | 5 | 8 | STORY-05-001 |

| STORY-05-003 | Implement build_patient_billing_summary_gold | build | 5 | 8 | STORY-05-001 |

| STORY-05-004 | Performance: cache shared Silver inputs + broadcast small dims for Gold builds | performance-optimization | 2 | 8 | STORY-05-001, STORY-05-002, STORY-05-003 |

| STORY-05-006 | Implement reconciliation_gold task (silver-vs-gold row counts + patient/allergy completeness) | build | 3 | 8 | STORY-05-001, STORY-05-002, STORY-05-003 |

| STORY-05-005 | Local integration test: trigger Gold tasks against Unity Catalog OSS local | integration-test | 5 | 8 | STORY-05-004, STORY-05-006 |



## Layer Closure Sequence

Stories below must execute in this order (enforced by dependencies):

1. **Build** → the 3 Gold builder `build` stories (STORY-05-001/002/003) complete before perf starts. The `reconciliation_gold` gate (STORY-05-006, `build`) is a fan-in gate that runs after the 3 builders and before integration-test.
2. **Performance Optimization** (LLD §6 derived):

   - STORY-05-004: Performance: cache shared Silver inputs + broadcast small dims for Gold builds

   - STORY-05-006: Implement reconciliation_gold task (fan-in gate downstream of the 3 Gold builders; blocks integration-test)

3. **Local Integration Testing** (trigger layer DAG on local Airflow, validate data in UC OSS local):

   - STORY-05-005: Local integration test: trigger Gold tasks against Unity Catalog OSS local

4. **Deployment Validation** (optional — only if LLD prescribes layer-scoped deploy work):

   - _N/A — layer moves to Done after integration testing; system-wide deploy in trailing release epic._



## Acceptance Criteria (Epic-Level)


- [ ] 3 Gold tables in `unity.gold.*`; patient_summary count = 5,767 [LLD §10.4, NFR-4]

- [ ] `gold_se_stats` populated; allergy completeness DQ-FLD-138 passes [DQS §2 Gold, LLD §8.6.1]

- [ ] p90 query latency < 2s per DRD §4.3 / NFR-1 (benchmarked in EPIC-07) [LLD §10.4]


## Risks & Assumptions


- ARRAY<STRUCT> denormalization payload size may degrade query latency if patient encounters scale beyond 1K.

