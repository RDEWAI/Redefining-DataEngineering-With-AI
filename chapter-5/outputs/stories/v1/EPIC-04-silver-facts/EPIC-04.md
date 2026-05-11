# EPIC-04: Silver Facts

| Field | Value |
|-------|-------|
| **LLD Section** | §5.2 |
| **Epic Scope** | layer |
| **Stories** | 12 |
| **Total Points** | 42 |
| **Sprints** | 6-7 |
| **Status** | Draft |

<!--
  Epic Scope vocabulary:
    - layer      → medallion layer epic (Bronze/Silver Dims/Silver Facts/Gold). MUST include closure sequence: performance-optimization → integration-test → (optional) deploy-validation.
    - foundation → scaffold/infra epic (no closure sequence required).
    - crosscut   → cross-layer concerns (observability, release, hardening).
-->

## Objective

Implement the 9 Silver fact transforms — encounters first, then conditions / medications / observations / immunizations / procedures / claims / careplans (depend on encounters), and allergies (depends on patients). Reconciliation_silver gates downstream Gold.


**Deploy Scope**: N/A — layer completes at integration-test; system-wide deploy handled in trailing release epic
<!--
  Deploy Scope must be ONE of:
    - "Layer-scoped — see deploy-validation story below"  (when LLD prescribes layer-scoped deploy work)
    - "N/A — layer completes at integration-test; system-wide deploy handled in trailing release epic"
-->


## Scope

### In Scope

- 9 Silver fact transforms

- Reconciliation_silver task (LLD §5.5)

- Layer perf tuning (LLD §6.3 / §6.5)

- Local integration test against UC OSS local


### Out of Scope

- Gold consumer tables (EPIC-05)

- Per-layer deploy beyond integration-test


## Stories

| ID | Title | Type | Points | Sprint | Dependencies |
|----|-------|------|--------|--------|-------------|

| STORY-04-001 | Implement transform_encounters_silver (fact) | build | 5 | 6 | STORY-03-001, STORY-02-008 |

| STORY-04-002 | Implement transform_conditions_silver (fact) | build | 3 | 7 | STORY-04-001 |

| STORY-04-003 | Implement transform_medications_silver (fact) | build | 3 | 7 | STORY-04-001 |

| STORY-04-004 | Implement transform_observations_silver (fact) | build | 5 | 7 | STORY-04-001 |

| STORY-04-005 | Implement transform_allergies_silver (fact) | build | 3 | 7 | STORY-03-001, STORY-02-008 |

| STORY-04-006 | Implement transform_immunizations_silver (fact) | build | 3 | 7 | STORY-04-001 |

| STORY-04-007 | Implement transform_procedures_silver (fact) | build | 3 | 7 | STORY-04-001 |

| STORY-04-008 | Implement transform_claims_silver (fact) | build | 3 | 7 | STORY-04-001 |

| STORY-04-009 | Implement transform_careplans_silver (fact) | build | 3 | 7 | STORY-04-001 |

| STORY-04-010 | Implement reconciliation_silver task (cross-table query_dq) | build | 3 | 7 | STORY-04-001, STORY-04-002, STORY-04-003, STORY-04-004, STORY-04-005, STORY-04-006, STORY-04-007, STORY-04-008, STORY-04-009 |

| STORY-04-011 | Performance: shuffle.partitions tuning + observations 8-partition repartition | performance-optimization | 3 | 7 | STORY-04-010 |

| STORY-04-012 | Local integration test: trigger Silver fact tasks against Unity Catalog OSS | integration-test | 5 | 7 | STORY-04-011 |



## Layer Closure Sequence

Stories below must execute in this order (enforced by dependencies):

1. **Build** → all `build` stories complete before perf starts.
2. **Performance Optimization** (LLD §6 derived):

   - STORY-04-011: Performance: shuffle.partitions tuning + observations 8-partition repartition

3. **Local Integration Testing** (trigger layer DAG on local Airflow, validate data in UC OSS local):

   - STORY-04-012: Local integration test: trigger Silver fact tasks against Unity Catalog OSS

4. **Deployment Validation** (optional — only if LLD prescribes layer-scoped deploy work):

   - _N/A — layer moves to Done after integration testing; system-wide deploy in trailing release epic._



## Acceptance Criteria (Epic-Level)


- [ ] 9 Silver fact tables in `unity.silver.*`; reconciliation_silver passes [LLD §4.2, §5.5]

- [ ] `silver_se_stats` populated; FK orphans = 0 per DQS §4 [DQS §4, LLD §8.6.1]

- [ ] `transform_observations_silver` finishes < 8 min on DEV per LLD §4.4 [LLD §4.4]


## Risks & Assumptions


- Encounters is the join hub for 7 dependent facts; a regression there blocks the layer.

