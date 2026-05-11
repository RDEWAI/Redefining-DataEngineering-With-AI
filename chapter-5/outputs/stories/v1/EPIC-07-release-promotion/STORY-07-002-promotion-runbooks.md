# STORY-07-002: Build DEV→STAGING→PROD promotion runbooks

| Field | Value |
|-------|-------|
| **Epic** | EPIC-07: Release & Promotion |
| **Story Type** | release |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 10 |
| **Dependencies** | STORY-07-001 |
| **Status** | To Do |

<!--
  Story Type vocabulary (required):
    - build                    → primary construction work
    - performance-optimization → layer-scoped perf tuning (LLD §6); runs BEFORE integration-test
    - integration-test         → triggers layer DAG on local Airflow against Unity Catalog OSS local; validates landed data in UC local
    - deploy-validation        → layer-scoped DDL/DAG/config deploy smoke (optional; only when LLD prescribes it)
    - observability            → layer-scoped lineage/metrics/dashboard wiring
    - release                  → cross-layer promotion/rollback (trailing epic only)
    - hardening                → cross-layer security/docs/maintenance (trailing epic only)
    - runtime-bootstrap        → JDK/Docker/UC catalog/source-data prerequisites (≥1 per backlog, typically EPIC-01)
-->


## User Story

As a platform engineer, I want have `_infra/cd/{dev,staging,prod}/promote.sh` runbooks per LLD §9.3 so that promotion is repeatable and gated per LLD §9.3 (manual approval, two reviewers for PROD).

## Description

Author 3 promote scripts that wrap `make` targets per LLD §9.3 and enforce gates: DEV (post-merge, `make test`); STAGING (manual approval, integration tests); PROD (manual + 2 reviewers, STAGING green + DQ scores ≥ threshold).

## Acceptance Criteria


- [ ] 3 promote scripts at `_infra/cd/{dev,staging,prod}/promote.sh` [LLD §9.3]

- [ ] STAGING gate runs `make test` integration markers [LLD §9.3]

- [ ] PROD gate requires DQ score above threshold (parsed from `gold_se_stats`) [LLD §9.3, §10.1]


## Technical Notes

- **Upstream references**: LLD §9.3, §10.1
- **Implementation hints**: Use bash + jq to parse DQ scores.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §9.3 Promotion |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Smoke | promote scripts execute | bash _infra/cd/dev/promote.sh |



## Verification

```yaml
AC1:
  - file_count: {glob: "patient_360/_infra/cd/*/promote.sh", equals: 3}
AC2:
  - grep: {file: "patient_360/_infra/cd/staging/promote.sh", pattern: "make test|integration"}
AC3:
  - grep: {file: "patient_360/_infra/cd/prod/promote.sh", pattern: "dq.*threshold|gold_se_stats"}
```


## How to Test (User)

### Prerequisites


- STORY-07-001 done


### Steps


1. `bash _infra/cd/dev/promote.sh`


### Expected outcome


- DEV promote completes; integration tests pass


## Documentation Updates


- [ ] Update patient_360/_infra/cd/README.md with the 3-stage promotion flow

