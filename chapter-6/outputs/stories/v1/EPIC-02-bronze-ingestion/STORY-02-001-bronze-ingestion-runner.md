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

Implement `src/patient_360/bronze/ingestion_runner.py` per LLD §2.3. The runner accepts a `--config-path` arg, loads the per-table YAML, builds a SparkSession with the default `spark_catalog` backed by `DeltaCatalog` + an embedded Hive metastore (Derby) per LLD §13 Decision 12 (revoked & replaced 2026-05-12), reads the source via the source-system reader (CSV by default; DuckDB only for tables whose raw CSV is < 100 MB per LLD §5.1 source-selection rule), enforces the source-derived column contract (DuckDB `DESCRIBE` / CSV header — Bronze is a permissive landing zone per LLD §2.3), adds metadata columns `ds`/`_ingested_at`/`_source_batch_id`, calls `se_runner.run_dq(...)` inline, and writes via `df.write.mode('append').format('delta').partitionBy('ds').option('replaceWhere', "ds = '<ds>'").save(f"${{PATIENT360_PROJECT_ROOT}}/warehouse/{env}/bronze/{table}/")` per LLD §13 Decision 15 (revoked 2026-05-12). **Path-based Delta writes** — UC OSS is no longer in the read/write path (UI-demo only).

## Acceptance Criteria


- [ ] `ingestion_runner.py` exposes `--config-path` and `--ds` args [LLD §2.3]

- [ ] Column contract is derived from the source itself (DuckDB `DESCRIBE` for DuckDB sources; CSV header for CSV sources) — no `StructType` enforcement from `contracts/{table}.yml` (Bronze is a permissive landing zone; DMS owns Silver/Gold contracts only) [LLD §2.3]

- [ ] Runner adds `ds` (DateType→string), `_ingested_at` (TimestampType), `_source_batch_id` (StringType) before write [LLD §2.3]

- [ ] Bronze write uses path-based Delta: `df.write.mode('append').format('delta').partitionBy('ds').option('replaceWhere', "ds = '{ds}'").save(f"${PATIENT360_PROJECT_ROOT}/warehouse/{env}/bronze/{table}/")`; **no** `saveAsTable('unity.bronze.<table>')` and no 3-part FQN [LLD §13 Decision 12/15 (revoked & replaced 2026-05-12)]

- [ ] Runner calls `se_runner.run_dq(...)` inline per LLD §5.1 with `action_if_failed` resolved from per-table YAML [LLD §5.1, §5.4]

- [ ] Unit tests at `tests/bronze/test_ingestion_runner_unit.py` cover argparse, source-derived contract resolution, and metadata-column additions [LLD §2.4]

- [ ] SparkSession is built with `spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog` and `javax.jdo.option.ConnectionURL=jdbc:derby:${PATIENT360_PROJECT_ROOT}/warehouse/{env}/metastore_db;create=true` (Hive metastore on Derby). **No** `UCSingleCatalog` wiring and no hardcoded `unity.bronze` literals; warehouse root resolved via `PATIENT360_PROJECT_ROOT` env var [LLD §13 Decision 12, §9.1]

- [ ] Source reader honors LLD §5.1 source-selection rule: `source.type=csv` is the default; `source.type=duckdb` is allowed only for tables whose raw CSV is < 100 MB (organizations, providers, payers, careplans, allergies, immunizations) [LLD §5.1]


## Technical Notes

- **Upstream references**: LLD §2.3, §5.1, §6.1, §9.1, §13 Decision 12 (revoked & replaced 2026-05-12), §13 Decision 15 (revoked 2026-05-12)
- **Implementation hints**: Default reader is `spark.read.csv("${PATIENT360_PROJECT_ROOT}/data/raw/<table>.csv", header=True)`. For the six small reference tables, use the `duckdb` Python connector + `spark.createDataFrame(...)`. Wire SparkSession with Delta + Hive (Derby) per LLD §13 Decision 12; resolve every path through `PATIENT360_PROJECT_ROOT`.

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
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "\\.save\\("}
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "replaceWhere"}
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "warehouse/.*/bronze/"}
  - forbidden_grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "saveAsTable", reason: "Bronze writes are path-based Delta per LLD §13 Decision 15 (revoked 2026-05-12)"}
  - forbidden_grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "['\"]unity\\.bronze\\.", reason: "3-part unity.bronze.<table> FQN retired per LLD §13 Decision 12 (revoked 2026-05-12)"}
AC5:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "se_runner|run_dq"}
AC6:
  - pytest: {node: "patient_360/tests/bronze/test_ingestion_runner_unit.py"}
AC7:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "DeltaCatalog|spark\\.sql\\.catalog\\.spark_catalog"}
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "PATIENT360_PROJECT_ROOT"}
  - forbidden_grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "UCSingleCatalog", reason: "UCSingleCatalog incompatible with Airflow 3.x embedded Spark; reverted to DeltaCatalog + Hive (Derby) per LLD §13 Decision 12 (2026-05-12)"}
AC8:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "source\\.type|source_type"}
  - grep: {glob: "patient_360/airflow/configs/*.yml", pattern: "type:\\s*csv"}
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

