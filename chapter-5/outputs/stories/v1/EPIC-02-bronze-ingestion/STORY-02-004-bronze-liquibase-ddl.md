# STORY-02-004: Author Liquibase DDL changelogs for 13 Bronze tables

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 3 |
| **Sprint** | 4 |
| **Dependencies** | STORY-01-004 |
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

As a data engineer, I want have one Liquibase changelog per Bronze table referenced from `contracts/{table}.yml` so that schema evolution is versioned and rollback-safe per LLD §9.1.

## Description

Author 13 `ddl/liquibase/changelogs/{table}.xml` files (one per Bronze table). Each declares the Bronze Delta table DDL per DMS §2 with metadata columns (`ds`, `_ingested_at`, `_source_batch_id`). Add a `master-changelog.xml` that includes all 13. Include rollback statements for each changeset.

## Acceptance Criteria


- [ ] 13 `ddl/liquibase/changelogs/{table}.xml` files exist for Bronze tables [LLD §9.1, DMS §2]

- [ ] `master-changelog.xml` includes all 13 Bronze changelogs [LLD §9.1]

- [ ] Each changeset has a `<rollback>` element [LLD §9.1]


## Technical Notes

- **Upstream references**: LLD §9.1, DMS §2
- **Implementation hints**: Generate from a Jinja template seeded by DMS §2 column lists.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §9.1 Scaffold Infrastructure |

| DMS | §2 Bronze layer schemas |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Contract | Liquibase XMLs parse and validate | pytest patient_360/tests/bronze/test_liquibase_changelogs.py |



## Verification

```yaml
AC1:
  - file_count: {glob: "patient_360/ddl/liquibase/changelogs/synthea_*.xml", equals: 13}
AC2:
  - file_exists: "patient_360/ddl/liquibase/master-changelog.xml"
  - grep_count: {file: "patient_360/ddl/liquibase/master-changelog.xml", pattern: '<include\s+file=', equals: 13}
AC3:
  - grep_count: {glob: "patient_360/ddl/liquibase/changelogs/synthea_*.xml", pattern: "<rollback>", equals: 13}
```


## How to Test (User)

### Prerequisites


- STORY-01-004 done


### Steps


1. `cd patient_360 && uv run pytest tests/bronze/test_liquibase_changelogs.py -v`


### Expected outcome


- All Liquibase XMLs parse and tests pass


## Documentation Updates


- [ ] N/A — internal DDL files

