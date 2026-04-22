# STORY-02-011: Implement Contract and Schema Migration Tests

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Layer -- Config-Driven Ingestion |
| **Priority** | P2 -- Important |
| **Story Points** | 2 |
| **Sprint** | Sprint 4 |
| **Dependencies** | STORY-02-001, STORY-02-006 |
| **Status** | To Do |

## User Story

As a data engineer, I want `tests/test_contracts.py` to assert that every table has a matching contract file, DQ rules file, and Liquibase DDL changelog so that convention-based discovery failures are caught at test time rather than silently at runtime.

## Description

Implement `tests/test_contracts.py` that parametrically validates the contract completeness for all tables defined in `airflow/configs/`. For each table config, assert: (1) `contracts/{table}.yml` exists and is valid YAML with required fields (`layer`, `schema`, `ddl_path`, `dq_path`). (2) `contracts/dq/{table}.yml` exists with threshold fields (`completeness_min`, `validity_min`, `freshness_max_hours`). (3) The `dq_path` pointer in `contracts/{table}.yml` resolves to an existing `dq_rules/{table}.yml` with at least one rule. (4) The `ddl_path` pointer in `contracts/{table}.yml` resolves to an existing `ddl/liquibase/changelogs/{table}.xml`. This test suite is the primary mitigation for convention-based DQ discovery silently missing rules for a table (LLD §2.4, Decision 10).

## Acceptance Criteria

- [ ] `tests/test_contracts.py` tests parametrize over all 13 tables in `airflow/configs/` [LLD §2.4]
- [ ] Test asserts `contracts/{table}.yml` exists and parses without error [LLD §2.3]
- [ ] Test asserts `contracts/{table}.yml` contains `ddl_path` and `dq_path` pointer fields [LLD §2.3]
- [ ] Test asserts `contracts/dq/{table}.yml` exists with `completeness_min`, `validity_min`, `freshness_max_hours` [LLD §2.3]
- [ ] Test asserts `dq_rules/{table}.yml` exists and contains >= 1 SE rule [LLD §2.3, Decision 10]
- [ ] Test asserts `ddl/liquibase/changelogs/{table}.xml` exists (Liquibase changelog file) [LLD §2.3]
- [ ] `make test` runs contract tests without requiring Spark or live UC OSS [LLD §2.4]
- [ ] All 13 contract tests pass green [LLD §2.4]

## Technical Notes

- **Upstream references**: LLD §2.3 (module interface contracts for `contracts/` and `dq_rules/`), LLD §2.4 (contract-test category in testing strategy), LLD §13 Decision 10 (convention-based DQ discovery + mitigation)
- **Implementation hints**: Use `pytest.mark.parametrize` with a list of table names collected from `airflow/configs/*.yml` filenames. Tests should use `pathlib.Path` to resolve paths relative to project root. No Spark or live database needed -- pure file system checks.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §2.3 (contracts + dq_rules interface), §2.4 (contract-test category), §13 Decision 10 |
| DMS | -- |
| STM | -- |
| DQS | §2 (Bronze rules -- must have at least one per table) |
