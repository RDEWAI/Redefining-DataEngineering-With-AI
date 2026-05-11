# EPIC-02: Bronze Ingestion

| Field | Value |
|-------|-------|
| **LLD Section** | §5.1, §6.5, §9.1 |
| **Epic Scope** | layer |
| **Stories** | 9 |
| **Total Points** | 42 |
| **Sprints** | 3-5 |
| **Status** | Draft |

<!--
  Epic Scope vocabulary:
    - layer      → medallion layer epic (Bronze/Silver Dims/Silver Facts/Gold). MUST include closure sequence: performance-optimization → integration-test → (optional) deploy-validation.
    - foundation → scaffold/infra epic (no closure sequence required).
    - crosscut   → cross-layer concerns (observability, release, hardening).
-->

## Objective

Land all 13 Phase-1 Synthea source tables in `unity.bronze.*` via the config-driven ingestion framework. Every Bronze write is UC-managed (LLD Decision 15), schema-enforced, idempotent via `replaceWhere`, and gated by inline SE row_dq + agg_dq + cross-table reconciliation.


**Deploy Scope**: Layer-scoped — see deploy-validation story below
<!--
  Deploy Scope must be ONE of:
    - "Layer-scoped — see deploy-validation story below"  (when LLD prescribes layer-scoped deploy work)
    - "N/A — layer completes at integration-test; system-wide deploy handled in trailing release epic"
-->


## Scope

### In Scope

- Generic ingestion runner + TaskGroup factory + SparkSubmit wrapper

- 13 per-table YAML configs + 13 Liquibase changelogs + 13 SE rule YAMLs

- DAG wiring (Bronze TaskGroup + reconciliation_bronze with SE-RUN-EVIDENCE query)

- Layer-scoped perf tuning (LLD §6.3 / §6.5)

- Local integration test against UC OSS local

- Liquibase deploy validation (LLD §9.1 prescribes per-layer DDL)


### Out of Scope

- Silver / Gold transforms (their own epics)

- System-wide CI / promotion (EPIC-07)


## Stories

| ID | Title | Type | Points | Sprint | Dependencies |
|----|-------|------|--------|--------|-------------|

| STORY-02-001 | Implement generic Bronze ingestion runner | build | 8 | 3 | STORY-01-002, STORY-01-009 |

| STORY-02-002 | Implement Bronze TaskGroup factory + SparkSubmit wrapper | build | 5 | 3 | STORY-02-001 |

| STORY-02-003 | Author 13 per-table Bronze ingestion YAML configs | build | 5 | 3 | STORY-02-001 |

| STORY-02-004 | Author Liquibase DDL changelogs for 13 Bronze tables | build | 3 | 4 | STORY-01-004 |

| STORY-02-005 | Author 13 per-table Bronze SE rule YAMLs | build | 5 | 4 | STORY-01-010 |

| STORY-02-006 | Wire Bronze TaskGroup + reconciliation_bronze into the Airflow DAG | build | 5 | 4 | STORY-02-002, STORY-02-003, STORY-02-005 |

| STORY-02-007 | Performance: replaceWhere partition pruning + shuffle.partitions + observations 8-partition tuning | performance-optimization | 3 | 5 | STORY-02-001, STORY-02-003 |

| STORY-02-008 | Local integration test: trigger Bronze DAG against Unity Catalog OSS local | integration-test | 5 | 5 | STORY-02-006, STORY-02-007 |

| STORY-02-009 | Deploy validation: apply Liquibase Bronze changelogs locally + DAG deploy smoke | deploy-validation | 3 | 5 | STORY-02-008 |



## Layer Closure Sequence

Stories below must execute in this order (enforced by dependencies):

1. **Build** → all `build` stories complete before perf starts.
2. **Performance Optimization** (LLD §6 derived):

   - STORY-02-007: Performance: replaceWhere partition pruning + shuffle.partitions + observations 8-partition tuning

3. **Local Integration Testing** (trigger layer DAG on local Airflow, validate data in UC OSS local):

   - STORY-02-008: Local integration test: trigger Bronze DAG against Unity Catalog OSS local

4. **Deployment Validation** (optional — only if LLD prescribes layer-scoped deploy work):

   - STORY-02-009: Deploy validation: apply Liquibase Bronze changelogs locally + DAG deploy smoke



## Acceptance Criteria (Epic-Level)


- [ ] All 13 Bronze tables registered in `unity.bronze.*` after triggering the DAG on local Airflow [LLD §5.1, §13 Decision 15]

- [ ] `bronze_se_stats` populated; reconciliation_bronze succeeds (SE run-evidence) [LLD §8.6.1]

- [ ] Liquibase Bronze changelogs apply locally and DAG re-deploys cleanly [LLD §9.1]


## Risks & Assumptions


- DuckDB read concurrency: 13 Bronze tasks running in parallel may saturate the source system.

- SE 2.10 stats-table writer must succeed at first run or `reconciliation_bronze` will fail-closed.

