# STORY-07-001: GitHub Actions CI — lint + unit + integration workflows

| Field | Value |
|-------|-------|
| **Epic** | EPIC-07: Release & CI/CD |
| **Story Type** | release |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 5 |
| **Dependencies** | STORY-05-005 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want GitHub Actions workflows for lint, unit tests, and integration tests so that every PR and `main` push is automatically validated.

## Description

Author 3 GitHub Actions workflow files under `patient_360/_infra/ci/.github/workflows/` per LLD §9.3: `lint.yml` (`make lint`), `unit-test.yml` (`pytest -m "not integration"` ≥ 90% coverage), `integration-test.yml` (`pytest -m integration` against the docker-compose UC OSS stack — runs only on PRs to `main`). Use `actions/setup-java@v4` (JDK 17), `astral-sh/setup-uv@v5`, and a `services:` block for Docker.

## Acceptance Criteria

- [ ] `patient_360/_infra/ci/.github/workflows/lint.yml` runs `make lint` on PR [LLD §9.3]
- [ ] `patient_360/_infra/ci/.github/workflows/unit-test.yml` enforces ≥ 90% line coverage [LLD §9.3]
- [ ] `patient_360/_infra/ci/.github/workflows/integration-test.yml` runs `pytest -m integration` against UC OSS local in CI services [LLD §9.3]
- [ ] CI runs JDK 17 + Python 3.12 [LLD §6.1, §2.1]

## Technical Notes

- **Upstream references**: LLD §6.1 (JDK 17), §9.3 (CI stages and gates)
- **Implementation hints**: Use `services:` to start UC OSS in CI, or `docker compose up -d` as a step.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §2.1, §6.1, §9.3 |
| DMS | — |
| STM | — |
| DQS | — |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Manual | CI green on PR | GitHub Actions UI |
| Unit | Workflow YAML parses | `pytest patient_360/tests/_infra/test_workflow_yaml_unit.py` |

## Verification

```yaml
AC1:
  - file_exists: "patient_360/_infra/ci/.github/workflows/lint.yml"
  - grep: {file: "patient_360/_infra/ci/.github/workflows/lint.yml", pattern: 'make lint|ruff'}
AC2:
  - file_exists: "patient_360/_infra/ci/.github/workflows/unit-test.yml"
  - grep: {file: "patient_360/_infra/ci/.github/workflows/unit-test.yml", pattern: 'cov-fail-under|--cov'}
AC3:
  - file_exists: "patient_360/_infra/ci/.github/workflows/integration-test.yml"
  - grep: {file: "patient_360/_infra/ci/.github/workflows/integration-test.yml", pattern: '-m integration|integration'}
AC4:
  - grep_count: {glob: "patient_360/_infra/ci/.github/workflows/*.yml", pattern: 'java-version.*17|setup-java', equals: 3}
```

## How to Test (User)

### Prerequisites

- Repo connected to GitHub Actions

### Steps

1. Open a PR with a small change
2. Watch GitHub Actions run

### Expected outcome

- All 3 jobs (lint, unit-test, integration-test) green within 15 min

## Documentation Updates

- [ ] Update `patient_360/README.md` § "CI/CD" with badge URLs and gate descriptions
- [ ] Update top-level `chapter-5/README.md` § "CI status" linking to the workflows
