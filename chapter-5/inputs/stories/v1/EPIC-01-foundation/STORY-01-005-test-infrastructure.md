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

Set up the test infrastructure in the `tests/` directory using the cookiecutter-provided layer-mirrored layout. Create `tests/conftest.py` with a session-scoped `project_name` fixture, SparkSession fixture (local mode), DuckDB test connection fixture, and sample data fixtures for key tables (patients, encounters, allergies). Tests live in `tests/{bronze,silver,gold}/` directories mirroring `src/patient_360/`; there is no separate `tests/unit/` or `tests/integration/` tree — unit and integration tests are distinguished by file name (`test_*_unit.py` vs `test_*_integration.py`) within each layer directory. Configure pytest settings in `pyproject.toml` including test markers for `unit`, `integration`, and `slow`. Ensure `pytest` runs green with an empty test suite.

## Acceptance Criteria

- [ ] `tests/conftest.py` exists with session-scoped `project_name` fixture and SparkSession fixture (local master) [LLD §2.4]
- [ ] DuckDB test connection fixture provides read-only access to test data [LLD §2.4]
- [ ] Sample data fixtures exist for patients, encounters, and allergies tables [LLD §2.4]
- [ ] `tests/{bronze,silver,gold}/` directories exist with `__init__.py` (layer-mirrored layout, no `tests/unit/` or `tests/integration/` tree) [LLD §2.4]
- [ ] `pytest` runs green with empty test suite and all fixtures importable [LLD §2.4]
- [ ] Test markers configured: `unit`, `integration`, `slow` [development-standards.md §5]
- [ ] Coverage target of >= 90% line coverage configured in pytest settings (`pyproject.toml`) [LLD §2.4]

## Technical Notes

- **Upstream references**: LLD §2.4 (Testing Strategy), development-standards.md §5
- **Implementation hints**: Use `pyspark.sql.SparkSession.builder.master("local[*]")` for the Spark fixture. Use `pytest-cov` for coverage measurement. Integration tests use Unity Catalog OSS. Test file naming: `test_{layer}_{operation}_{scenario}.py` — unit files are `test_*_unit.py`, integration files are `test_*_integration.py`, both within the same layer directory.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS2.4 (Testing Strategy) |
| DMS | SS2 (table schemas for fixture data) |
| STM | -- |
| DQS | -- |
