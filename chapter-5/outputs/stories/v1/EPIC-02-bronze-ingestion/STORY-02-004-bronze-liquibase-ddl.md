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

Author 13 `ddl/liquibase/changelogs/{table}.xml` files (one per Bronze table). Each declares the Bronze Delta table DDL per DMS §2 with metadata columns (`ds`, `_ingested_at`, `_source_batch_id`). Include rollback statements for each changeset. Per LLD §9.1 the `master-changelog.xml` is **project-wide** (Bronze + Silver + Gold = 29 tables across DMS §2/§3/§4) — this story authors the 13 Bronze per-table changelogs and ensures the project-wide `master-changelog.xml` includes them; downstream Silver/Gold stories add their own includes. The aggregate include count in `master-changelog.xml` after this story is at least 13 (Bronze rows present) and grows to 29 once Silver + Gold complete.

## Acceptance Criteria


- [ ] 13 `ddl/liquibase/changelogs/{table}.xml` files exist for Bronze tables [LLD §9.1, DMS §2]

- [ ] Project-wide `master-changelog.xml` includes all 29 project changelogs (Bronze + Silver + Gold) per LLD §9.1; this story owns the 13 Bronze include entries (DMS §2), with Silver (+13, DMS §3) and Gold (+3, DMS §4) include entries authored by their own layer stories [LLD §9.1, DMS §2/§3/§4]

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
  # master-changelog.xml is project-wide per LLD §9.1 (Bronze + Silver + Gold = 29 includes total).
  # This story is the Bronze layer's contribution: 13 Bronze include entries MUST be present.
  # The full 29-include count is verified once Silver + Gold layer stories complete.
  - grep_count: {file: "patient_360/ddl/liquibase/master-changelog.xml", pattern: 'changelogs/synthea_', greater_or_equal: 13}
  - grep_count: {file: "patient_360/ddl/liquibase/master-changelog.xml", pattern: '<include\s+file=', greater_or_equal: 13}
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

