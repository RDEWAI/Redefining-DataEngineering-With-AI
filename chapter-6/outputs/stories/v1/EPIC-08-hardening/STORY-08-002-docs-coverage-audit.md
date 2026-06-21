# STORY-08-002: Documentation & coverage audit

| Field | Value |
|-------|-------|
| **Epic** | EPIC-08: Hardening |
| **Story Type** | hardening |
| **Priority** | P2 |
| **Story Points** | 3 |
| **Sprint** | 11 |
| **Dependencies** | STORY-07-004 |
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

As a data engineer, I want ensure all README sections, runbooks, and architecture docs are consistent + coverage ≥ 90% so that onboarding a new engineer requires only the README + runbooks — no tribal knowledge.

## Description

Audit `patient_360/README.md`, `patient_360/docs/runbooks/*.md`, and per-module docstrings. Run `pytest --cov` and confirm ≥ 90% line coverage per LLD §2.4. Fix any coverage gaps.

## Acceptance Criteria


- [ ] `pytest --cov` reports ≥ 90% line coverage per LLD §2.4 [LLD §2.4]

- [ ] README has sections for Bootstrap, Run pipeline, Local integration testing, CI/CD, Rollback [LLD §9.3, §9.4]

- [ ] Each layer has a runbook in `docs/runbooks/` [LLD §9]


## Technical Notes

- **Upstream references**: LLD §2.4, §9
- **Implementation hints**: Use `pytest --cov --cov-fail-under=90`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §2.4 Testing, §9 Deployment |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Smoke | coverage threshold met | pytest --cov --cov-fail-under=90 |



## Verification

```yaml
AC1:
  - manual: "pytest --cov --cov-fail-under=90 — runs full suite"
AC2:
  - grep_count: {file: "patient_360/README.md", pattern: "## Bootstrap|## Run|## Local integration|## CI/CD|## Rollback", equals: 5}
AC3:
  - file_count: {glob: "patient_360/docs/runbooks/*.md", equals: 5}
```


## How to Test (User)

### Prerequisites


- STORY-07-004 done


### Steps


1. `cd patient_360 && uv run pytest --cov=src/patient_360 --cov-fail-under=90`


### Expected outcome


- Coverage report ≥ 90%


## Documentation Updates


- [ ] Update patient_360/README.md sections enumerated in AC2

- [ ] Add patient_360/docs/runbooks/*.md (one per layer + bootstrap + rollback)

