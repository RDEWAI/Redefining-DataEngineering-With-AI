# EPIC-07: Release & Promotion

| Field | Value |
|-------|-------|
| **LLD Section** | §9.3, §9.4 |
| **Epic Scope** | crosscut |
| **Stories** | 4 |
| **Total Points** | 18 |
| **Sprints** | 10-11 |
| **Status** | Draft |

<!--
  Epic Scope vocabulary:
    - layer      → medallion layer epic (Bronze/Silver Dims/Silver Facts/Gold). MUST include closure sequence: performance-optimization → integration-test → (optional) deploy-validation.
    - foundation → scaffold/infra epic (no closure sequence required).
    - crosscut   → cross-layer concerns (observability, release, hardening).
-->

## Objective

Build the system-wide CI pipeline, DEV→STAGING→PROD promotion runbooks, rollback procedure (NFR-10 RTO ≤ 4h), and a full-pipeline E2E load test on staging-equivalent data.



## Scope

### In Scope

- GitHub Actions CI (lint, unit, integration)

- 3 promote.sh scripts

- Rollback.sh + runbook

- Full-pipeline E2E load test


### Out of Scope

- Layer-specific deploy (lives in layer epic — only Bronze in this backlog has a layer-scoped DDL deploy-validation story)


## Stories

| ID | Title | Type | Points | Sprint | Dependencies |
|----|-------|------|--------|--------|-------------|

| STORY-07-001 | Build CI pipeline (GitHub Actions: lint + unit + integration) | release | 5 | 10 | STORY-05-005, STORY-06-004 |

| STORY-07-002 | Build DEV→STAGING→PROD promotion runbooks | release | 5 | 10 | STORY-07-001 |

| STORY-07-003 | Implement rollback procedure (Delta RESTORE + re-run) | release | 3 | 11 | STORY-07-002 |

| STORY-07-004 | Full-pipeline E2E load test (Bronze → Gold) on staging-equivalent data | release | 5 | 11 | STORY-07-003 |




## Acceptance Criteria (Epic-Level)


- [ ] CI workflows pass on a fresh PR with ≥ 90% coverage gate [LLD §2.4, §9.3]

- [ ] DEV→STAGING→PROD promotion runbooks executable end-to-end [LLD §9.3]

- [ ] Full-pipeline E2E load test < 33 min critical path on staging-equivalent data [LLD §4.4]


## Risks & Assumptions


- Two-reviewer PROD gate requires human availability; not blocking but slows promotion.

