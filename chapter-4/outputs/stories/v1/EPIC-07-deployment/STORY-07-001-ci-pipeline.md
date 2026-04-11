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

Create `.github/workflows/ci.yaml` with two workflows: (1) On PR: run ruff lint, run unit tests with >= 90% coverage gate, fail PR if coverage drops. (2) On merge to main: run integration tests including Bronze, Silver, Gold, and e2e. Use Python 3.11, install dependencies via uv. Report coverage results as PR comments.

## Acceptance Criteria

- [ ] CI runs ruff lint + unit tests on every PR [LLD §9.2]
- [ ] Unit test coverage gate >= 90% [LLD §2.4]
- [ ] Integration tests run on merge to main [LLD §9.2]
- [ ] Python 3.11 base with uv for dependency management [LLD §9.2]
- [ ] CI failure blocks PR merge [LLD §9.2]

## Technical Notes

- **Upstream references**: LLD SS9.2 (Promotion Process), LLD SS2.4 (Testing Strategy)
- **Implementation hints**: Use `actions/setup-python@v5` with uv. Run `uv run pytest tests/unit/ --cov --cov-fail-under=90`. Integration tests need Docker services (Spark, DuckDB, Unity Catalog OSS).

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS9.2, SS2.4 |
| DMS | -- |
| STM | -- |
| DQS | -- |
