# STORY-07-002: Liquibase DDL Migrations for All Tables

| Field | Value |
|-------|-------|
| **Epic** | EPIC-07: Deployment + Rollback |
| **Priority** | P2 -- Important |
| **Story Points** | 3 |
| **Sprint** | Sprint 9 |
| **Dependencies** | STORY-07-001 |
| **Status** | To Do |

## User Story

As a data engineer, I want Liquibase XML changelogs for all Bronze, Silver, and Gold tables so that schema migrations are versioned, auditable, and reversible across all environments.

## Description

Create Liquibase XML changelog files under `ddl/liquibase/changelogs/{table}.xml` for all 13 Bronze tables, 13 Silver tables (clinical_*, reference_*, billing_*), and 3 Gold tables (29 total). Create the `ddl/liquibase/liquibase.properties` connection config and `ddl/liquibase/master-changelog.xml` that includes all individual changelogs. Each table changelog contains the `CREATE TABLE` changeset for the initial schema per DMS §2-4. Update `contracts/{table}.yml` `ddl_path` pointers to resolve to the correct changelog path. Add `make migrate` target (via `liquibase update`) to the project Makefile.

## Acceptance Criteria

- [ ] `ddl/liquibase/changelogs/{table}.xml` exists for all 13 Bronze + 13 Silver + 3 Gold tables (29 files) [LLD §2.3, §9.1]
- [ ] `ddl/liquibase/master-changelog.xml` includes all 29 table changelogs [LLD §9.1]
- [ ] `ddl/liquibase/liquibase.properties` configured for DEV environment [LLD §9.1]
- [ ] Each changelog's initial changeset matches the DMS schema for that table [DMS §2-4]
- [ ] All `contracts/{table}.yml` files have `ddl_path` pointing to a valid changelog file [LLD §2.3]
- [ ] Contract test (STORY-02-011) verifies `ddl_path` resolves for all tables [LLD §2.4]
- [ ] `make migrate` runs `liquibase update` against DEV warehouse without error [LLD §9.3]
- [ ] Changelogs include rollback sections for reversibility [LLD §9.4]

## Technical Notes

- **Upstream references**: LLD §2.3 (DDL module contract), LLD §9.1 (scaffold `ddl/liquibase/`), LLD §9.3 (Make targets), DMS §2-4 (table schemas for changelog content)
- **Implementation hints**: Use Liquibase Community (open source). Changelog format: XML with `<changeSet>` per table. Delta Lake tables do not use traditional DDL (they are schema-on-write); the Liquibase changelogs serve as the schema audit trail and reference for column definitions used by the contract tests and developer tooling.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §2.3 (DDL interface), §9.1 (scaffold `ddl/liquibase/`), §9.3 (Make targets) |
| DMS | §2 (Bronze schemas), §3 (Silver schemas), §4 (Gold schemas) |
| STM | -- |
| DQS | -- |
