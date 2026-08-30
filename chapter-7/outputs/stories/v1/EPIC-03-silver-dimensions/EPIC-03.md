# EPIC-03: Silver Dimensions (SCD Type 2)

| Field | Value |
|-------|-------|
| **LLD Section** | §5.2 |
| **Epic Scope** | layer |
| **Stories** | 7 |
| **Total Points** | 30 |
| **Sprints** | 5-6 |
| **Status** | Draft |

<!--
  Epic Scope vocabulary:
    - layer      → medallion layer epic (Bronze/Silver Dims/Silver Facts/Gold). MUST include closure sequence: performance-optimization → integration-test → (optional) deploy-validation.
    - foundation → scaffold/infra epic (no closure sequence required).
    - crosscut   → cross-layer concerns (observability, release, hardening).
-->

## Objective

Implement the 4 Silver dimension transforms (patients, organizations, providers, payers) with SCD Type 2 and PHI drop. Gold tables join the current version via `is_current=TRUE`.


**Deploy Scope**: N/A — layer completes at integration-test; system-wide deploy handled in trailing release epic
<!--
  Deploy Scope must be ONE of:
    - "Layer-scoped — see deploy-validation story below"  (when LLD prescribes layer-scoped deploy work)
    - "N/A — layer completes at integration-test; system-wide deploy handled in trailing release epic"
-->


## Scope

### In Scope

- 4 SCD2 dimension transforms

- Layer perf tuning (broadcast + is_current pre-filter)

- Local integration test against UC OSS local


### Out of Scope

- Silver fact transforms (EPIC-04)

- Per-layer deploy beyond integration-test (system-wide deploy in EPIC-07)


## Stories

| ID | Title | Type | Points | Sprint | Dependencies |
|----|-------|------|--------|--------|-------------|

| STORY-03-001 | Implement transform_patients_silver (SCD2 dimension) | build | 5 | 5 | STORY-01-003, STORY-02-008 |

| STORY-03-002 | Implement transform_organizations_silver (SCD2 dimension) | build | 5 | 5 | STORY-01-003, STORY-02-008 |

| STORY-03-003 | Implement transform_providers_silver (SCD2 dimension) | build | 5 | 5 | STORY-01-003, STORY-02-008 |

| STORY-03-004 | Implement transform_payers_silver (SCD2 dimension) | build | 5 | 5 | STORY-01-003, STORY-02-008 |

| STORY-03-005 | Performance: broadcast small dims + SCD2-aware filter pushdown | performance-optimization | 2 | 6 | STORY-03-001, STORY-03-002, STORY-03-003, STORY-03-004 |

| STORY-03-007 | Wire the silver_dimensions TaskGroup into patient360_hourly_v1 | build | 3 | 6 | STORY-02-006, STORY-03-001, STORY-03-002, STORY-03-003, STORY-03-004 |

| STORY-03-006 | Local integration test: trigger Silver dim tasks against UC OSS | integration-test | 5 | 6 | STORY-03-005, STORY-03-007 |



## Layer Closure Sequence

Stories below must execute in this order (enforced by dependencies):

1. **Build** → all `build` stories complete before perf starts.
2. **Performance Optimization** (LLD §6 derived):

   - STORY-03-005: Performance: broadcast small dims + SCD2-aware filter pushdown

3. **Local Integration Testing** (trigger layer DAG on local Airflow, validate data in UC OSS local):

   - STORY-03-006: Local integration test: trigger Silver dim tasks against UC OSS

4. **Deployment Validation** (optional — only if LLD prescribes layer-scoped deploy work):

   - _N/A — layer moves to Done after integration testing; system-wide deploy in trailing release epic._



## Acceptance Criteria (Epic-Level)


- [ ] 4 Silver dim tables populated and SCD2 idempotency verified on rerun [LLD §4.5, §5.2]

- [ ] PHI columns dropped per DMS §3 / NFR-6 [DMS §3]

- [ ] `silver_se_stats` populated for each dim [LLD §8.6.1]


## Risks & Assumptions


- Hash-column selection drift: a missed column in DMS §6 will cause spurious SCD2 versions.

