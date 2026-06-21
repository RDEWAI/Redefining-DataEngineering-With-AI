# STORY-02-001: Implement generic Bronze ingestion runner

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 8 |
| **Sprint** | 3 |
| **Dependencies** | STORY-01-002, STORY-01-009, STORY-01-010 |
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

As a data engineer, I want have a single `ingestion_runner.py` that drives all 13 Bronze tasks from per-table YAML so that we eliminate 13 duplicate ingestion modules; new tables ship by adding one YAML.

## Description

Implement `src/patient_360/bronze/ingestion_runner.py` per LLD §2.3. The runner accepts a `--config-path` arg, loads the per-table YAML, builds a SparkSession wired with `spark_catalog=DeltaCatalog` **plus** a named side catalog `spark.sql.catalog.unity=io.unitycatalog.spark.UCSingleCatalog` (`uri`/`token`/`warehouse`) and `spark.sql.defaultCatalog=unity` per LLD §13 Decision 12 (re-adopted 2026-06-18); reads the source via the source-system reader (CSV by default; DuckDB only for tables whose raw CSV is < 100 MB per LLD §5.1 source-selection rule), enforces the source-derived column contract (DuckDB `DESCRIBE` / CSV header — Bronze is a permissive landing zone per LLD §2.3), adds metadata columns `ds`/`_ingested_at`/`_source_batch_id`, calls `se_runner.run_dq(...)` inline, and writes into the **Liquibase-pre-created** `unity.bronze.<table>` EXTERNAL Delta table via `df.write.mode("overwrite").insertInto("unity.bronze.<table>")` — idempotent per-`ds` via **dynamic partition overwrite** (`spark.sql.sources.partitionOverwriteMode=dynamic`), **NOT** `replaceWhere` (`insertInto` silently ignores `replaceWhere`, which causes re-runs to append/double the data — empirically confirmed) per LLD §13 Decision 15 (re-adopted 2026-06-18). The runner **NEVER** creates a table (`saveAsTable`/CTAS/RTAS rejected by `UCSingleCatalog`); `make ddl-apply` pre-creates every `unity.bronze.<table>`. `spark_catalog` is **never** bound to `UCSingleCatalog`.

## Acceptance Criteria


- [ ] `ingestion_runner.py` exposes `--config-path` and `--ds` args [LLD §2.3]

- [ ] Column contract is derived from the source itself (DuckDB `DESCRIBE` for DuckDB sources; CSV header for CSV sources) — no `StructType` enforcement from `contracts/{table}.yml` (Bronze is a permissive landing zone; DMS owns Silver/Gold contracts only) [LLD §2.3]

- [ ] Runner adds `ds` (DateType→string), `_ingested_at` (TimestampType), `_source_batch_id` (StringType) before write [LLD §2.3]

- [ ] Bronze write targets the pre-created UC table: `df.write.mode("overwrite").insertInto("unity.bronze.{table}")` with **no** `.option("replaceWhere", ...)` — idempotency comes from dynamic partition overwrite (`spark.sql.sources.partitionOverwriteMode=dynamic`), since `insertInto` silently ignores `replaceWhere` and would otherwise append/double on re-run; **no** `saveAsTable` / CTAS / RTAS (runner never creates the table — Liquibase pre-creates it) and **no** path-based `.save("warehouse/...")` [LLD §13 Decision 12/15 (re-adopted 2026-06-18)]

- [ ] Runner calls `se_runner.run_dq(...)` inline per LLD §5.1 with `action_if_failed` resolved from per-table YAML [LLD §5.1, §5.4]

- [ ] Unit tests at `tests/bronze/test_ingestion_runner_unit.py` cover argparse, source-derived contract resolution, and metadata-column additions [LLD §2.4]

- [ ] SparkSession is built with `spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog` **plus** a named side catalog `spark.sql.catalog.unity=io.unitycatalog.spark.UCSingleCatalog` (`spark.sql.catalog.unity.uri`/`.token`/`.warehouse`), `spark.sql.defaultCatalog=unity`, and `spark.sql.sources.partitionOverwriteMode=dynamic` (idempotency mechanism for the `insertInto` write — LLD §13 Decision 15); `spark_catalog` is **never** bound to `UCSingleCatalog`; warehouse root resolved via `PATIENT360_PROJECT_ROOT` env var [LLD §13 Decision 12, §13 Decision 15, §9.1]

- [ ] Source reader honors LLD §5.1 source-selection rule: `source.type=csv` is the default; `source.type=duckdb` is allowed only for tables whose raw CSV is < 100 MB (organizations, providers, payers, careplans, allergies, immunizations) [LLD §5.1]

- [ ] The inline `se_runner.run_dq(...)` call relies on `se_runner` writing SE STATS/ERROR tables as **per-table MANAGED Unity Catalog tables** by 3-part FQN (`unity.<schema>.<table>_stats` / `_error`, SE-created via `saveAsTable` on UC 0.5.0) — the runner does **not** register or pre-create SE tables and continues to write business data via `insertInto("unity.bronze.<table>")` (no write-method change; the runner itself still never calls `saveAsTable` — only `se_runner` does, for its SE-owned audit tables). Cross-reference: STORY-01-010 AC7 owns the SE MANAGED-FQN audit-table contract [LLD §2.3 (v1.20), §8.2, §8.3, §13 Decision 12 (corrected 2026-06-20)]


## Technical Notes

- **Upstream references**: LLD §2.3, §5.1, §6.1, §9.1, §13 Decision 12 (re-adopted 2026-06-18), §13 Decision 15 (re-adopted 2026-06-18)
- **Implementation hints**: Default reader is `spark.read.csv("${PATIENT360_PROJECT_ROOT}/data/raw/<table>.csv", header=True)`. For the six small reference tables, use the `duckdb` Python connector + `spark.createDataFrame(...)`. Wire SparkSession with `spark_catalog=DeltaCatalog` + named `unity=UCSingleCatalog` side catalog (`defaultCatalog=unity`) per LLD §13 Decision 12; resolve every path through `PATIENT360_PROJECT_ROOT`. The `unity.bronze.<table>` tables must already exist (run `make ddl-apply` first); the runner only `insertInto`s.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §2.3, §5.1, §13 |

| DMS | §2 Bronze schemas |

| STM | Tab:Source-to-Bronze |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Unit | argparse, schema enforcement, metadata cols | pytest patient_360/tests/bronze/test_ingestion_runner_unit.py |



## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/bronze/ingestion_runner.py"
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "--config-path"}
AC2:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "DESCRIBE|csv\\.header|csv_header|describe_columns"}
  - forbidden_grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "StructType", reason: "Bronze contract is now source-derived per LLD §2.3 (2026-05-12 pivot)"}
AC3:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "_source_batch_id"}
AC4:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "mode\\(['\"]overwrite['\"]\\)\\.insertInto|\\.insertInto"}
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "unity\\.bronze"}
  - forbidden_grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "replaceWhere", reason: "insertInto silently ignores replaceWhere — re-runs would append/double. Idempotency is via dynamic partition overwrite, not replaceWhere, per LLD §13 Decision 15 (re-adopted 2026-06-18)"}
  - forbidden_grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "saveAsTable", reason: "Runner never creates tables; Liquibase pre-creates unity.bronze.<table>; UCSingleCatalog rejects CTAS/RTAS per LLD §13 Decision 12/15 (re-adopted 2026-06-18)"}
  - forbidden_grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "\\.save\\(\\s*f?['\"].*warehouse", reason: "Bronze writes are insertInto unity.bronze.<table>, not path-based .save(warehouse/...) per LLD §13 Decision 15 (re-adopted 2026-06-18)"}
AC5:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "se_runner|run_dq"}
AC6:
  - pytest: {node: "patient_360/tests/bronze/test_ingestion_runner_unit.py"}
AC7:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "spark\\.sql\\.catalog\\.spark_catalog.*DeltaCatalog|DeltaCatalog"}
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "spark\\.sql\\.catalog\\.unity|UCSingleCatalog"}
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "defaultCatalog"}
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "partitionOverwriteMode.*dynamic|sources\\.partitionOverwriteMode"}
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "PATIENT360_PROJECT_ROOT"}
  - forbidden_grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "spark_catalog.*UCSingleCatalog|catalog\\.spark_catalog['\"]?\\s*[,:].*UCSingleCatalog", reason: "spark_catalog must be DeltaCatalog; UC is a NAMED side catalog (spark.sql.catalog.unity) per LLD §13 Decision 12 (re-adopted 2026-06-18)"}
AC8:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "source\\.type|source_type"}
  - grep: {glob: "patient_360/airflow/configs/*.yml", pattern: "type:\\s*csv"}
AC9:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "se_runner|run_dq"}
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "insertInto"}
  - forbidden_grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "saveAsTable", reason: "Runner writes business data via insertInto unity.bronze.<table> and never creates tables; the SE stats/error MANAGED UC tables are SE-owned and created by se_runner (not the runner) per STORY-01-010 AC7 / LLD §2.3 v1.20 / §13 Decision 12 corrected 2026-06-20"}
```


## How to Test (User)

### Prerequisites


- STORY-01-002 done; STORY-01-009 done; STORY-01-010 done (se_runner.py shipped so `run_dq` is callable inline)


### Steps


1. `cd patient_360 && uv run pytest tests/bronze/test_ingestion_runner_unit.py -v`


### Expected outcome


- All unit tests pass


## Documentation Updates


- [x] Update patient_360/README.md § "Run Bronze ingestion" with the runner CLI invocation

