# STORY-07-001: Build CI pipeline (GitHub Actions: lint + unit + integration)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-07: Release & Promotion |
| **Story Type** | release |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 10 |
| **Dependencies** | STORY-05-005, STORY-06-004 |
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

As a platform engineer, I want have GitHub Actions workflows for lint, unit tests, and integration tests on every PR so that every change is gated by the LLD §9.3 CI stages before reaching `main`.

## Description

Author `_infra/ci/.github/workflows/{lint,unit-test,integration-test}.yml` per LLD §9.3. Lint runs `ruff check`; unit-test runs `pytest -m 'not integration' --cov` ≥ 90%; integration-test brings up docker-compose, runs `pytest -m integration` against UC OSS local.

## Acceptance Criteria


- [ ] 3 GitHub Actions workflow files exist (lint, unit-test, integration-test) [LLD §9.3]

- [ ] Unit-test gate enforces ≥ 90% line coverage per LLD §2.4 [LLD §2.4, §9.3]

- [ ] Integration-test workflow brings up docker-compose and runs `pytest -m integration` [LLD §9.3]


## Technical Notes

- **Upstream references**: LLD §2.4, §9.3
- **Implementation hints**: Use `actions/checkout@v4`, `astral-sh/setup-uv@v3`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §2.4 Testing, §9.3 Promotion |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Manual | PR triggers all 3 workflows | open a draft PR and inspect Actions |



## Verification

```yaml
AC1:
  - file_count: {glob: "patient_360/_infra/ci/.github/workflows/*.yml", equals: 3}
AC2:
  - grep: {file: "patient_360/_infra/ci/.github/workflows/unit-test.yml", pattern: "cov.*90|--cov-fail-under=90"}
AC3:
  - grep: {file: "patient_360/_infra/ci/.github/workflows/integration-test.yml", pattern: "docker.*compose|services:"}
```


## How to Test (User)

### Prerequisites


- STORY-05-005 + STORY-06-004 done


### Steps


1. Push a draft PR and observe Actions runs


### Expected outcome


- All three workflows run; unit-test enforces 90% coverage


## Documentation Updates


- [ ] Update patient_360/README.md § "CI/CD" with the workflow descriptions

- [ ] Update patient_360/_infra/ci/README.md

