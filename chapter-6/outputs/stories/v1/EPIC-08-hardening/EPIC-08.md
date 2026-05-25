# EPIC-08: Hardening

| Field | Value |
|-------|-------|
| **LLD Section** | §9.5, §10.3 |
| **Epic Scope** | crosscut |
| **Stories** | 3 |
| **Total Points** | 8 |
| **Sprints** | 11-12 |
| **Status** | Draft |

<!--
  Epic Scope vocabulary:
    - layer      → medallion layer epic (Bronze/Silver Dims/Silver Facts/Gold). MUST include closure sequence: performance-optimization → integration-test → (optional) deploy-validation.
    - foundation → scaffold/infra epic (no closure sequence required).
    - crosscut   → cross-layer concerns (observability, release, hardening).
-->

## Objective

Harden the pipeline: PHI/HIPAA security audit, documentation + coverage audit, and Delta VACUUM/OPTIMIZE maintenance schedule.



## Scope

### In Scope

- PHI / HIPAA audit

- Documentation + coverage audit

- Weekly Delta maintenance DAG


### Out of Scope

- Layer-specific perf or integration work


## Stories

| ID | Title | Type | Points | Sprint | Dependencies |
|----|-------|------|--------|--------|-------------|

| STORY-08-001 | Security & PHI audit (NFR-6 masking, NFR-7 audit trail) | hardening | 3 | 11 | STORY-07-004 |

| STORY-08-002 | Documentation & coverage audit | hardening | 3 | 11 | STORY-07-004 |

| STORY-08-003 | Schedule Delta VACUUM / OPTIMIZE maintenance | hardening | 2 | 12 | STORY-08-002 |




## Acceptance Criteria (Epic-Level)


- [ ] PHI audit signed off — no SSN/DRIVERS/PASSPORT in Silver tables [DMS §3, NFR-6]

- [ ] Coverage ≥ 90% across `src/patient_360/` [LLD §2.4]

- [ ] Weekly maintenance DAG green for 4 weeks [LLD §3.1, §10.3]


## Risks & Assumptions


- Coverage gaps in Silver fact transforms may push the audit beyond Sprint 11.

