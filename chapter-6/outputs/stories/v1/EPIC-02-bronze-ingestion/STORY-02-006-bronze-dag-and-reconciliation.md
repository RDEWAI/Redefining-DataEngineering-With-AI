# STORY-02-006: Wire Bronze TaskGroup + reconciliation_bronze into the Airflow DAG

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 4 |
| **Dependencies** | STORY-02-002, STORY-02-003, STORY-02-005 |
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

As a data engineer, I want have `airflow/dags/patient360_hourly_v1.py` import the factory and render the Bronze TaskGroup + reconciliation so that Bronze runs end-to-end on the local Airflow with reconciliation checking the SE-RUN-EVIDENCE invariant.

## Description

Author `patient_360/airflow/dags/patient360_hourly_v1.py` per LLD §4. The DAG begins with a one-shot **`bootstrap_se`** `SparkSubmitOperator` root task (LLD §4.2) that idempotently creates the shared `bronze.bronze_se_stats` / `bronze.bronze_se_errors` Delta tables via `scripts/bootstrap_se_tables.py` (path resolved through the `SE_BOOTSTRAP_APP` env var, defaulting to `/opt/patient_360/scripts/bootstrap_se_tables.py`). The DAG then calls `build_bronze_taskgroup(dag, 'airflow/configs')` with `bootstrap_se` set as the upstream dependency for the whole `bronze_ingestion` TaskGroup, followed by a `reconciliation_bronze` **`SparkSubmitOperator`** task that runs the SE run-evidence query (LLD §8.6.1) — fail-closed when `bronze_se_stats` has 0 rows for the current `meta_dq_run_date`. Per LLD §4.2 (2026-05-12 pivot), any task that touches Spark MUST use `SparkSubmitOperator` (Airflow 3.x embedded PySpark hangs on classloader collisions). Schedule = `0 * * * *`; DEV defaults (LLD v1.15 §4.1 — re-capped 2026-05-21 per §13 Decision 12 Constraints) `max_active_tasks=1`, `catchup=False`, `max_active_runs=1`. The Derby Hive metastore is single-process; the 2026-05-20 v1.14 raise to 16 was reverted on 2026-05-21 after `ERROR XSDB6: Another instance of Derby may have already booted the database null` reproduced on the first DAG run. STAGING/PROD scale per LLD §4.1. **Rationale for the `bootstrap_se` task**: addresses LLD-DEVIATIONS row 6 — closes the SE shared-stats-table CREATE-race on cold-start metastores and the warm-restart `DELTA_CREATE_TABLE_WITH_NON_EMPTY_LOCATION` failure on persistent on-disk Delta data after a container/metastore reset (LLD v1.14 §4.2).

## Acceptance Criteria


- [ ] DAG file `patient360_hourly_v1.py` exists with `dag_id='patient360_hourly_v1'`, schedule `0 * * * *` [LLD §4.1]

- [ ] DAG calls `build_bronze_taskgroup(dag, 'airflow/configs')` to render the 13-task Bronze TaskGroup [LLD §4.2]

- [ ] `reconciliation_bronze` task is a **`SparkSubmitOperator`** (NOT `PythonOperator`) and runs after the Bronze TaskGroup, executing the SE run-evidence query against `bronze_se_stats` per LLD §8.6.1 [LLD §4.2, §5.5, §8.6.1]

- [ ] DEV DAG defaults: `max_active_runs=1`, `max_active_tasks=1` (re-capped in LLD v1.15 §4.1 per the §13 Decision 12 Constraints paragraph added 2026-05-21 — embedded Derby Hive metastore is single-process; reproduced as `ERROR XSDB6: Another instance of Derby may have already booted the database null` when `max_active_tasks=16`), `catchup=False`, `default_timeout=60` per LLD §4.1. Rationale: `bootstrap_se` (AC5) closes the SE-table CREATE race, and `max_active_tasks=1` closes Derby's concurrent-metastore-access race — both gates are required together; neither alone is sufficient. [LLD §4.1, §13 Decision 12 Constraints]

- [ ] A `bootstrap_se` **`SparkSubmitOperator`** task exists upstream of the `bronze_ingestion` TaskGroup, whose `application` points at `scripts/bootstrap_se_tables.py` (resolved via the `SE_BOOTSTRAP_APP` env var; default `/opt/patient_360/scripts/bootstrap_se_tables.py`) and is wired as `bootstrap_se >> bronze_tg` (or equivalent dependency wiring). This addresses LLD-DEVIATIONS row 6 (SE table CREATE-race on cold-start + warm-restart `DELTA_CREATE_TABLE_WITH_NON_EMPTY_LOCATION`) per LLD v1.14 §4.2. Still required under LLD v1.15: closes the SE-table CREATE race independently of the Derby concurrency cap in AC4. [LLD §4.2]

- [ ] `src/patient_360/bronze/reconciliation.py` exists and honors LLD §13 Decision 12 — does NOT reference `uc_uri`, `UCSingleCatalog`, or `UC_URI` (UC is not in the runtime path per Decision 12 revised 2026-05-12); `build_spark()` is called without a `uc_uri` kwarg. See LLD-DEVIATIONS row 8. [LLD §13 Decision 12, LLD-DEVIATIONS row 8]

- [ ] `developer-plugin:validate-dag` passes against the rendered DAG [LLD §2.4]


## Technical Notes

- **Upstream references**: LLD v1.15 §4.1 (DEV `max_active_tasks=1` re-cap), §4.2 (bootstrap_se root task), §5.5, §8.6.1, §13 Decision 12 Constraints (2026-05-21 Derby single-process); LLD-DEVIATIONS row 6
- **Implementation hints**: Use Airflow 3.2.1 syntax (`@dag` decorator). The `bootstrap_se` task resolves its `application` from `os.environ.get('SE_BOOTSTRAP_APP', '/opt/patient_360/scripts/bootstrap_se_tables.py')` and runs under `conn_id=spark_default` with `driver_memory=1g`, `executor_memory=1g`, `executor_cores=1`, `num_executors=1`, `retries=1`, `retry_delay=timedelta(seconds=60)`, `execution_timeout=timedelta(minutes=5)`. Wire every task in the Bronze TaskGroup with `bootstrap_se >> bronze_tg`. The reconciliation task should accept the run's `{{ ts_nodash }}` to derive `meta_dq_run_id`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §4.1 DAG Config (v1.15 — DEV `max_active_tasks=1` re-capped per §13 Decision 12 Constraints), §4.2 Tasks (`bootstrap_se` root SparkSubmitOperator retained — closes SE-table CREATE race), §5.5 Reconciliation, §8.6.1 SE-RUN-EVIDENCE, §13 Decision 12 Constraints (Derby single-process metastore, 2026-05-21) |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Unit | DAG parses and exposes 14 Bronze tasks | pytest patient_360/tests/bronze/test_dag_unit.py |



## Verification

```yaml
AC1:
  - file_exists: "patient_360/airflow/dags/patient360_hourly_v1.py"
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "patient360_hourly_v1"}
AC2:
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "build_bronze_taskgroup"}
AC3:
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "reconciliation_bronze"}
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "bronze_se_stats"}
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "SparkSubmitOperator"}
  - forbidden_grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "PythonOperator\\([^)]*reconciliation_bronze|reconciliation_bronze[^)]*PythonOperator", reason: "reconciliation_bronze must be SparkSubmitOperator per LLD §4.2 (2026-05-12 pivot)"}
AC4:
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "max_active_runs.*1"}
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "max_active_tasks\\s*[:=]\\s*1\\b"}
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "catchup.*False"}
AC5:
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "task_id=[\"']bootstrap_se[\"']"}
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "bootstrap_se_tables\\.py"}
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "SE_BOOTSTRAP_APP"}
  - grep: {file: "patient_360/airflow/dags/patient360_hourly_v1.py", pattern: "bootstrap_se\\s*>>\\s*bronze_tg|bootstrap_se\\.set_downstream\\(bronze_tg\\)|bronze_tg\\.set_upstream\\(bootstrap_se\\)|bronze_tg\\s*<<\\s*bootstrap_se"}
AC6:
  - file_exists: "patient_360/src/patient_360/bronze/reconciliation.py"
  - grep: {file: "patient_360/src/patient_360/bronze/reconciliation.py", pattern: "def run_reconciliation_bronze"}
  - forbidden_grep: {file: "patient_360/src/patient_360/bronze/reconciliation.py", pattern: "uc_uri", reason: "LLD §13 Decision 12 (revised 2026-05-12) removes UC from runtime path; build_spark no longer accepts uc_uri. See LLD-DEVIATIONS row 8."}
  - forbidden_grep: {file: "patient_360/src/patient_360/bronze/reconciliation.py", pattern: "UCSingleCatalog", reason: "UC catalog wiring not in runtime path per LLD §13 Decision 12."}
  - forbidden_grep: {file: "patient_360/src/patient_360/bronze/reconciliation.py", pattern: "UC_URI", reason: "UC env var not in runtime path per LLD §13 Decision 12."}
AC7:
  - pytest: {node: "patient_360/tests/bronze/test_dag_unit.py"}
```


## How to Test (User)

### Prerequisites


- STORY-02-002 / -02-003 / -02-005 done

- Local Airflow up via `make dev-up`


### Steps


1. `cd patient_360 && uv run pytest tests/bronze/test_dag_unit.py -v`

2. `docker compose exec airflow airflow dags list | grep patient360_hourly_v1`


### Expected outcome


- Tests pass; DAG imports without error

- Airflow CLI lists `patient360_hourly_v1`


## Documentation Updates


- [ ] Update patient_360/README.md § "Run the pipeline" with the DAG trigger command


## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-05-20 | Scrum Master Agent | Re-baselined against LLD v1.14 §4.2 — added a new acceptance criterion requiring an upstream `bootstrap_se` `SparkSubmitOperator` whose `application` resolves to `scripts/bootstrap_se_tables.py` via the `SE_BOOTSTRAP_APP` env var (default `/opt/patient_360/scripts/bootstrap_se_tables.py`) and whose downstream wires to the `bronze_ingestion` TaskGroup. Updated AC4: dropped the `max_active_tasks=1` mandate (a v1.12 workaround) — LLD v1.14 §4.1 restored DEV concurrency to `max_active_tasks=16` once `bootstrap_se` is in place. Verification block extended with grep checks for `task_id="bootstrap_se"`, `bootstrap_se_tables.py`, `SE_BOOTSTRAP_APP`, and the `bootstrap_se >> bronze_tg` dependency wiring; AC4 gained a `forbidden_grep` for `max_active_tasks=1`. Description, Technical Notes, and Estimation Support updated to cite LLD v1.14 and LLD-DEVIATIONS row 6 (SE shared stats-table CREATE-race on cold-start + warm-restart `DELTA_CREATE_TABLE_WITH_NON_EMPTY_LOCATION`). Scope, dependencies, sprint, status, and remaining ACs unchanged. |
| 2026-05-21 | Scrum Master Agent | Reverted AC4 to mandate DEV `max_active_tasks=1` per LLD v1.15 §4.1 (Derby single-process constraint added to §13 Decision 12 Constraints on 2026-05-21; reproduced as `ERROR XSDB6: Another instance of Derby may have already booted the database null` with `max_active_tasks=16`). AC4 verification: required_grep `max_active_tasks\s*[:=]\s*1\b` (matches `max_active_tasks=1` and `max_active_tasks: 1`); REMOVED the prior v1.8 `forbidden_grep` for `max_active_tasks\s*=\s*1\b` (now required, not forbidden) and the required_grep for `max_active_tasks.*16`. AC5 (`bootstrap_se` task) unchanged — bootstrap closes the SE-table CREATE race; the Derby cap closes the metastore-concurrency race; both gates are required together. AC4 rationale text updated to call this out. Description, Technical Notes, and Estimation Support re-cite LLD v1.15 §4.1 and §13 Decision 12 Constraints. Scope, dependencies, sprint, status, and other ACs unchanged. |
| 2026-05-22 | Scrum Master Agent | Added new AC6 explicitly listing `src/patient_360/bronze/reconciliation.py` as a deliverable of this story so future LLD pivots flow through to that file — retrofit for LLD-DEVIATIONS row 8 (the 2026-05-12 §13 Decision 12 revision removed UC from the runtime path; `build_spark()` lost the `uc_uri` kwarg, but the previously-generated `reconciliation.py` still passed `uc_uri=` and failed at runtime with `TypeError: build_spark() got an unexpected keyword argument 'uc_uri'`; direct-edit fix landed 2026-05-22). AC6 requires the file exist and forbids any reference to `uc_uri`, `UCSingleCatalog`, or `UC_URI`. Verification block adds: required_grep `def run_reconciliation_bronze` in `src/patient_360/bronze/reconciliation.py`; forbidden_grep `uc_uri` (+ `UCSingleCatalog`, `UC_URI`) in the same file. Renumbered the prior validate-dag AC from AC6 to AC7 (Verification block AC6 pytest entry moved to AC7). Without this AC, the file fell through the chain — `update-dag` doesn't touch Python modules, and `update-ingestion` only touches files declared in story ACs. Scope, dependencies, sprint, status, and all other ACs unchanged. Cites LLD-DEVIATIONS row 8 + the 2026-05-22 direct-edit retrofit. |
