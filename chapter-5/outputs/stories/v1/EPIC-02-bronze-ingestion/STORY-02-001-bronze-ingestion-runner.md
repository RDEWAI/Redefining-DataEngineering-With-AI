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

Implement `src/patient_360/bronze/ingestion_runner.py` per LLD §2.3. The runner accepts a `--config-path` arg, loads the per-table YAML, builds a SparkSession with `UCSingleCatalog`, reads the source via the source-system reader (DuckDB), enforces the StructType from the contract (no inference), adds metadata columns `ds`/`_ingested_at`/`_source_batch_id`, calls `se_runner.run_dq(...)` inline, and writes via `df.write.mode('append').format('delta').partitionBy('ds').option('replaceWhere', "ds = '<ds>'").saveAsTable(f'unity.bronze.{table}')` per LLD §13 Decision 15. **No path-based writes** — UC OSS is the source of truth at write time.

## Acceptance Criteria


- [ ] `ingestion_runner.py` exposes `--config-path` and `--ds` args [LLD §2.3]

- [ ] Schema enforcement uses `StructType` from `contracts/{table}.yml` (no inference) [LLD §2.3]

- [ ] Runner adds `ds` (DateType→string), `_ingested_at` (TimestampType), `_source_batch_id` (StringType) before write [LLD §2.3]

- [ ] Bronze write uses `saveAsTable('unity.bronze.{table}')` with `replaceWhere ds = '{ds}'`; no path-based writes [LLD §13 Decision 15]

- [ ] Runner calls `se_runner.run_dq(...)` inline per LLD §5.1 with `action_if_failed` resolved from per-table YAML [LLD §5.1, §5.4]

- [ ] Unit tests at `tests/bronze/test_ingestion_runner_unit.py` cover argparse, schema enforcement, and metadata-column additions [LLD §2.4]

- [ ] UC catalog name, schema name, and UC service URI are sourced from the `catalog_bronze_catalog_name` / `catalog_bronze_schema` config keys and the `UC_URI` env var (LLD §7.1) — no hardcoded `unity.bronze` literals; the `{catalog}.{schema}.{table}` triple is composed from config [LLD §7.1, §13 Decision 15]


## Technical Notes

- **Upstream references**: LLD §2.3, §5.1, §7.1, §13 Decision 15
- **Implementation hints**: Read source via DuckDB JDBC or `duckdb` Python connector + `spark.createDataFrame(...)`. Use `spark.read.format('delta')` only for downstream layers.

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
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "StructType"}
AC3:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "_source_batch_id"}
AC4:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "saveAsTable"}
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "replaceWhere"}
AC5:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "se_runner|run_dq"}
AC6:
  - pytest: {node: "patient_360/tests/bronze/test_ingestion_runner_unit.py"}
AC7:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "UC_URI|catalog_bronze_catalog_name|catalog_bronze_schema"}
  - grep_absent: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "['\"]unity\\.bronze\\."}
```


## How to Test (User)

### Prerequisites


- STORY-01-002 done; STORY-01-009 done; STORY-01-010 done (se_runner.py shipped so `run_dq` is callable inline)


### Steps


1. `cd patient_360 && uv run pytest tests/bronze/test_ingestion_runner_unit.py -v`


### Expected outcome


- All unit tests pass


## Documentation Updates


- [ ] Update patient_360/README.md § "Run Bronze ingestion" with the runner CLI invocation

