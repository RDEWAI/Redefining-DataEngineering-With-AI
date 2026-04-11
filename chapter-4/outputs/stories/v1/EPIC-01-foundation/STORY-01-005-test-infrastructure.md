# STORY-01-005: Set Up Test Infrastructure

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 3 |
| **Sprint** | Sprint 1 |
| **Dependencies** | STORY-01-001 |
| **Status** | To Do |

## User Story

As a data engineer, I want a pytest test infrastructure with fixtures and conftest.py so that all team members can write and run tests consistently from Sprint 1.

## Description

Set up the test infrastructure in the `tests/` directory. Create `conftest.py` with shared fixtures including a SparkSession fixture (local mode), DuckDB test connection fixture, and sample data fixtures for key tables (patients, encounters, allergies). Create `tests/unit/` and `tests/integration/` directories with their own `conftest.py` files. Configure pytest settings in `pyproject.toml` including test markers for `unit`, `integration`, and `slow`. Ensure `pytest` runs green with an empty test suite.

## Acceptance Criteria

- [ ] `tests/conftest.py` exists with SparkSession fixture (local master) [LLD §2.4]
- [ ] DuckDB test connection fixture provides read-only access to test data [LLD §2.4]
- [ ] Sample data fixtures exist for patients, encounters, and allergies tables [LLD §2.4]
- [ ] `pytest` runs green with empty test suite and all fixtures importable [LLD §2.4]
- [ ] Test markers configured: `unit`, `integration`, `slow` [development-standards.md SS5]
- [ ] Coverage target of >= 90% configured in pytest settings [LLD §2.4]

## Technical Notes

- **Upstream references**: LLD SS2.4 (Testing Strategy), development-standards.md SS5
- **Implementation hints**: Use `pyspark.sql.SparkSession.builder.master("local[*]")` for the Spark fixture. Use `pytest-cov` for coverage measurement. Integration tests should use Unity Catalog OSS.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS2.4 (Testing Strategy) |
| DMS | SS2 (table schemas for fixture data) |
| STM | -- |
| DQS | -- |
