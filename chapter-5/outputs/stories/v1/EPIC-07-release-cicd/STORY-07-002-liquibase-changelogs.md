# STORY-07-002: Liquibase DDL changelogs for all 29 tables

| Field | Value |
|-------|-------|
| **Epic** | EPIC-07: Release & CI/CD |
| **Story Type** | release |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 5 |
| **Dependencies** | STORY-01-003 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want a Liquibase changelog per table so that schema migrations are versioned and reproducible across DEV/STAGING/PROD.

## Description

Author `patient_360/ddl/liquibase/master-changelog.xml` and per-table changelog XML files under `patient_360/ddl/liquibase/changelogs/{table}.xml` for all 13 Bronze + 13 Silver + 3 Gold = 29 tables. Each changelog declares the table create + ALTER history. `patient_360/ddl/liquibase/liquibase.properties` configures the JDBC URL (UC OSS local).

## Acceptance Criteria

- [ ] 29 changelog files exist under `patient_360/ddl/liquibase/changelogs/*.xml` [LLD §9.1]
- [ ] `patient_360/ddl/liquibase/master-changelog.xml` includes all 29 [LLD §9.1]
- [ ] `patient_360/ddl/liquibase/liquibase.properties` configures JDBC for UC OSS [LLD §9.1]
- [ ] `liquibase update` succeeds against the local UC OSS catalog [LLD §9.1]

## Technical Notes

- **Upstream references**: LLD §9.1 (scaffold infrastructure layout — Liquibase paths)
- **Implementation hints**: Each `contracts/{table}.yml` carries a `ddl_path:` — use it to wire master-changelog includes.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §9.1 |
| DMS | §3, §4, §5 (table schemas) |
| STM | — |
| DQS | — |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Manual | `liquibase update` against local UC OSS succeeds | `cd patient_360 && liquibase --defaults-file=ddl/liquibase/liquibase.properties update` |
| Unit | XML well-formed | `pytest patient_360/tests/_infra/test_liquibase_xml_unit.py` |

## Verification

```yaml
AC1:
  - file_count: {glob: "patient_360/ddl/liquibase/changelogs/*.xml", equals: 29}
AC2:
  - file_exists: "patient_360/ddl/liquibase/master-changelog.xml"
  - grep_count: {file: "patient_360/ddl/liquibase/master-changelog.xml", pattern: 'changelogs/', equals: 29}
AC3:
  - file_exists: "patient_360/ddl/liquibase/liquibase.properties"
AC4:
  - manual: "run `liquibase --defaults-file=ddl/liquibase/liquibase.properties update` against local UC OSS"
```

## How to Test (User)

### Prerequisites

- STORY-01-003 complete (29 contracts present)
- Liquibase CLI installed
- Docker stack up (UC OSS reachable)

### Steps

1. `ls patient_360/ddl/liquibase/changelogs/*.xml | wc -l`
2. `cd patient_360 && liquibase --defaults-file=ddl/liquibase/liquibase.properties update`

### Expected outcome

- Step 1: 29
- Step 2: Liquibase reports `ChangeSets executed: 29` (or more on subsequent runs)

## Documentation Updates

- [ ] Update `patient_360/ddl/liquibase/README.md` § "Running migrations" with the `liquibase update` command and properties file
