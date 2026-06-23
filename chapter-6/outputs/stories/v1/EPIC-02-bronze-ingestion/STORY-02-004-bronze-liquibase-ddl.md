# STORY-02-004: Author plain .sql DDL migrations for 13 Bronze tables

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

As a data engineer, I want one plain dated `.sql` DDL migration per Bronze table under `ddl/migrations/` referenced from `contracts/{table}.yml` so that the UC EXTERNAL Delta tables are pre-created idempotently before any pipeline write, applied in lexical order via beeline against the Spark Thrift Server per LLD §9.1.

## Description

Author 13 plain dated `ddl/migrations/<YYYYMMDD>_<NNN>_synthea_{table}.sql` migration files (one per Bronze table). Each **pre-creates a UC EXTERNAL Delta table** via `CREATE TABLE IF NOT EXISTS unity.bronze.synthea_{table} (...) USING DELTA LOCATION '<warehouse path>'` per DMS §2 with the four metadata columns (`ds`, `_ingested_at`, `_source_batch_id`, `_source_file STRING`) — `_source_file STRING` is mandatory per LLD §2.3 so the runner's `insertInto` column arity matches (omitting it triggers `DELTA_INSERT_COLUMN_ARITY_MISMATCH`). All layers' migrations live in the single flat `ddl/migrations/` directory — there are **no** per-layer `ddl/bronze/` / `ddl/silver/` / `ddl/gold/` subdirectories; the dated + zero-padded sequence filename prefix (`<YYYYMMDD>_<NNN>_`) gives the bronze → silver → gold apply order under a plain **lexical sort**. The `.sql` files are applied in lexical order by the beeline one-shot `_infra/docker/ddl-apply.sh` against the Spark Thrift Server (`jdbc:hive2://spark-thrift-server:10000/unity`) via `make ddl-apply` per LLD §13 Decision 12 — Liquibase is retired (UPGRADE-NOTES UC 0.5.0 / Spark 4.1: plain beeline-applied `.sql` replaces the Liquibase changelog/master-changelog machinery). These tables exist before the runner ever writes (the runner only `insertInto`s). `CREATE TABLE IF NOT EXISTS` makes each migration idempotent and re-runnable, so no separate rollback element is required. `make ddl-apply` runs every `ddl/migrations/*.sql` in lexical order (downstream Silver/Gold layer stories add their own dated `ddl/migrations/*.sql` files, applied by the same target — 29 tables total once all layers complete).

## Acceptance Criteria


- [ ] 13 plain dated `ddl/migrations/<YYYYMMDD>_<NNN>_synthea_{table}.sql` migration files exist for Bronze tables, each issuing `CREATE TABLE IF NOT EXISTS unity.bronze.synthea_{table} ... USING DELTA LOCATION` (UC EXTERNAL Delta pre-create); all migrations are flat under `ddl/migrations/` (no per-layer subdirs) [LLD §9.1, §13 Decision 12, DMS §2]

- [ ] `make ddl-apply` runs every `ddl/migrations/*.sql` in lexical order via beeline against `jdbc:hive2://spark-thrift-server:10000/unity`; the 13 Bronze migrations are applied before the first Bronze pipeline run (Silver +13 / Gold +3 migrations authored by their own layer stories as dated `ddl/migrations/*.sql` files, applied by the same target — 29 total once all layers complete) [LLD §9.1, §13 Decision 12, DMS §2/§3/§4]

- [ ] Each migration uses `CREATE TABLE IF NOT EXISTS` so it is idempotent and re-runnable (no Liquibase changelog/rollback element needed) [LLD §9.1]


## Technical Notes

- **Upstream references**: LLD §9.1, §13 Decision 12, DMS §2; UPGRADE-NOTES UC 0.5.0 / Spark 4.1 (Liquibase → beeline-applied plain `.sql`)
- **Implementation hints**: Generate from a Jinja template seeded by DMS §2 column lists; name each file `ddl/migrations/<YYYYMMDD>_<NNN>_synthea_<t>.sql` (dated + zero-padded sequence so lexical order = bronze → silver → gold); emit `CREATE TABLE IF NOT EXISTS unity.bronze.synthea_<t> (...) USING DELTA LOCATION '${PATIENT360_WAREHOUSE_ROOT}/{env}/bronze/synthea_<t>'`. `make ddl-apply` (the `_infra/docker/ddl-apply.sh` one-shot) invokes `beeline -u jdbc:hive2://spark-thrift-server:10000/unity -f <each ddl/migrations/*.sql in lexical order>` (the Spark Thrift Server is the only endpoint that can run Delta DDL). No `master-changelog.xml`, no `<changeSet>`/`<rollback>` XML — plain `.sql` only.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §9.1 Scaffold Infrastructure |

| DMS | §2 Bronze layer schemas |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Contract | Bronze .sql migrations parse and create UC EXTERNAL Delta tables | pytest patient_360/tests/bronze/test_bronze_ddl_sql.py |



## Verification

```yaml
AC1:
  - file_count: {glob: "patient_360/ddl/migrations/*synthea_*.sql", equals: 13}
  - grep_count: {glob: "patient_360/ddl/migrations/*.sql", pattern: "unity\\.bronze\\.synthea_", min: 13}
  - grep_count: {glob: "patient_360/ddl/migrations/*synthea_*.sql", pattern: "USING DELTA|LOCATION", min: 13}
  - grep_count: {glob: "patient_360/ddl/migrations/*synthea_*.sql", pattern: "CREATE TABLE IF NOT EXISTS", min: 13}
AC2:
  - grep: {file: "patient_360/Makefile", pattern: "ddl-apply:"}
  - grep: {file: "patient_360/Makefile", pattern: "beeline|hive2://spark-thrift-server:10000"}
  - grep: {file: "patient_360/Makefile", pattern: "ddl/migrations/.*\\.sql|ddl/migrations"}
  # Liquibase machinery is retired (UPGRADE-NOTES UC 0.5.0 / Spark 4.1): no master-changelog.xml.
  - forbidden_grep: {glob: "patient_360/ddl/**", pattern: "master-changelog|<changeSet|<databaseChangeLog", reason: "Liquibase retired — plain beeline-applied .sql only"}
AC3:
  - grep_count: {glob: "patient_360/ddl/migrations/*synthea_*.sql", pattern: "CREATE TABLE IF NOT EXISTS", equals: 13}
  - forbidden_grep: {glob: "patient_360/ddl/migrations/*.sql", pattern: "<rollback>", reason: "idempotent CREATE TABLE IF NOT EXISTS replaces Liquibase rollback elements"}
```


## How to Test (User)

### Prerequisites


- STORY-01-004 done


### Steps


1. `cd patient_360 && uv run pytest tests/bronze/test_bronze_ddl_sql.py -v`


### Expected outcome


- All 13 Bronze `.sql` migrations parse; `make ddl-apply` creates the `unity.bronze.synthea_*` EXTERNAL Delta tables idempotently; tests pass


## Documentation Updates


- [ ] N/A — internal DDL files

