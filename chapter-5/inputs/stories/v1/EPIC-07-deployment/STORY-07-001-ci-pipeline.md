# STORY-07-001: GitHub Actions CI Pipeline

| Field | Value |
|-------|-------|
| **Epic** | EPIC-07: Deployment + Rollback |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 5 |
| **Sprint** | Sprint 9 |
| **Dependencies** | STORY-05-006 |
| **Status** | To Do |

## User Story

As a data engineer, I want a GitHub Actions CI pipeline that runs lint and unit tests on PR and integration tests on merge so that code quality is enforced automatically.

## Description

Create GitHub Actions workflow files under `_infra/ci/.github/workflows/`: (1) `lint.yml` -- runs `make lint` (`uv run ruff check src/ tests/`) on every PR. (2) `unit-test.yml` -- runs `uv run pytest tests/ -m "not integration"` with >= 90% coverage gate on every PR. (3) `integration-test.yml` -- runs `uv run pytest tests/` (all markers, including integration) on merge to main. Use Python 3.12, install dependencies via `uv sync --all-extras`. All three stages per LLD §9.3 GitHub Actions CI table.

## Acceptance Criteria

- [ ] `_infra/ci/.github/workflows/lint.yml` runs `make lint` on every PR [LLD §9.3]
- [ ] `_infra/ci/.github/workflows/unit-test.yml` runs unit tests with >= 90% coverage gate [LLD §2.4, §9.3]
- [ ] `_infra/ci/.github/workflows/integration-test.yml` runs integration tests (including UC OSS) on merge to main [LLD §9.3]
- [ ] Python 3.12 used in all workflows (aligned with cookiecutter `python_version=3.12`) [LLD §2.1]
- [ ] `uv sync --all-extras` used for dependency installation [LLD §9.3]
- [ ] CI failure blocks PR merge [LLD §9.3]

## Technical Notes

- **Upstream references**: LLD §9.3 (GitHub Actions CI Stages table + Make Targets table), LLD §2.4 (Testing Strategy), LLD §9.1 (scaffold `_infra/ci/` path)
- **Implementation hints**: Use `actions/setup-python@v5` with Python 3.12 and `uv`. Integration tests require UC OSS -- use `_infra/docker/docker-compose.yml` services in the CI job. Test paths are layer-mirrored (`tests/bronze/`, `tests/silver/`, `tests/gold/`) -- no `tests/unit/` or `tests/integration/` subdirs.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §9.1 (scaffold infra), §9.3 (CI stages + Make targets), §2.4 (testing strategy) |
| DMS | -- |
| STM | -- |
| DQS | -- |
