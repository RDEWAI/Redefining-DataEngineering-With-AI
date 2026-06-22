# Sample Stories — full-pattern examples

These three stories show what a fully-populated story looks like under the
mandatory section requirements. Use `<project>` as a placeholder for whatever
the cookiecutter project name is — these examples are intentionally generic.

---

## Example 1 — `runtime-bootstrap` story

Every backlog must contain ≥1 of these (typically EPIC-01). Validator rule:
`STORIES-BOOTSTRAP-001`.

```markdown
# STORY-01-006: Bootstrap local dev runtime

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation & Infrastructure |
| **Story Type** | runtime-bootstrap |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 1 |
| **Dependencies** | STORY-01-001 |
| **Status** | To Do |

## User Story

As a data engineer, I want a one-command local dev runtime so that I can
verify the full pipeline end-to-end on my laptop without tribal knowledge.

## Description

Bring up the local docker-compose stack (Airflow + Unity Catalog OSS +
Marquez), bootstrap the medallion catalog and schemas, seed source data,
and prove health with smoke checks. Removes the gap between "code complete"
and "data actually lands in UC".

## Acceptance Criteria

- [ ] `java -version` reports 17.x.x [LLD §6.1]
- [ ] `docker compose -f _infra/docker/docker-compose.yml up -d` succeeds [LLD §1]
- [ ] UC catalog `unity` and schemas `bronze`/`silver`/`gold` created via `scripts/uc_init.py` [LLD §1]
- [ ] Source data seeded into local source DB [LLD §5.1]
- [ ] `curl http://localhost:8080/api/2.1/unity-catalog/catalogs` returns 200 with `unity` listed [LLD §1]
- [ ] `docker compose exec airflow spark-submit --master 'local[2]' --version` exits 0 and reports the LLD-pinned Spark version (4.0.0) [LLD §6.1 — closes STORIES-BOOTSTRAP-COVERAGE-001]
- [ ] `docker compose exec airflow python -c "from spark_expectations.core.expectations import SparkExpectations"` exits 0 (proves SE 2.10+ imports cleanly — DQ is mandatory, no BRONZE_SKIP_SE bypass) [LLD §6.1]
- [ ] **SE end-to-end smoke**: `docker compose exec airflow pytest -m integration tests/bootstrap/test_se_smoke.py::test_with_expectations_runs_end_to_end` invokes `WrappedDataFrameWriter(...).with_expectations(...)` against a real Spark session and a 1-row test DataFrame; the test asserts `bronze_se_stats` has ≥1 row with `meta_dq_run_id` matching the run [LLD §8.6 — closes STORIES-SE-COVERAGE-001]

## Technical Notes

- Upstream references: LLD §1, §6.1, §9
- Implementation hints: `make dev-up` wraps the five-step bootstrap (compose up → wait-for-uc → uc-init → seed → spark-smoke).
- The Spark-submit smoke is the gate that proves the Airflow→Spark→UC bridge is wired before any `build` story runs. AC content varies by `local_executor_mode` per the standards table.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §1 Overview, §6.1 Compute, §9 Deployment |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Smoke | UC OSS catalog/schemas exist | pytest tests/bootstrap/test_uc_health.py |
| Smoke | spark-submit reachable from airflow worker | pytest tests/bootstrap/test_spark_smoke.py |
| Smoke | spark-expectations imports cleanly (DQ path live) | pytest tests/bootstrap/test_se_smoke.py |
| Smoke | SE runs end-to-end (with_expectations against real Spark) | pytest -m integration tests/bootstrap/test_se_smoke.py::test_with_expectations_runs_end_to_end |

## Verification

```yaml
AC1:
  - manual: "java -version — depends on host JDK install"
AC2:
  - manual: "docker compose up — requires Docker Desktop"
AC3:
  - pytest: {node: "tests/bootstrap/test_uc_health.py::test_schemas_exist"}
AC5:
  - pytest: {node: "tests/bootstrap/test_uc_health.py::test_catalog_api_200"}
AC6:
  - pytest: {node: "tests/bootstrap/test_spark_smoke.py::test_spark_submit_local_master"}
AC7:
  - pytest: {node: "tests/bootstrap/test_se_smoke.py::test_spark_expectations_imports"}
AC8:
  - pytest: {node: "tests/bootstrap/test_se_smoke.py::test_with_expectations_runs_end_to_end", marker: "integration"}
```

## How to Test (User)

### Prerequisites

- Docker Desktop running
- JDK 17 installed (`java -version` shows 17.x)
- `make dev-setup` completed

### Steps

1. `make dev-up`
2. `curl -s http://localhost:8080/api/2.1/unity-catalog/catalogs | jq '.catalogs[].name'`
3. Expect `unity` listed; query schemas: `curl -s 'http://localhost:8080/api/2.1/unity-catalog/schemas?catalog_name=unity' | jq '.schemas[].name'`
4. `docker compose exec airflow spark-submit --master 'local[2]' --version`
5. `docker compose exec airflow python -c "from spark_expectations.core.expectations import SparkExpectations; print('SE OK')"`
6. `docker compose exec airflow pytest -m integration tests/bootstrap/test_se_smoke.py::test_with_expectations_runs_end_to_end -q`
7. `docker compose exec airflow python -c "from pyspark.sql import SparkSession; s=SparkSession.builder.getOrCreate(); s.sql('SELECT count(*) FROM unity.bronze.bronze_se_stats').show()"` (must show >=1 row after Step 6)
8. Open `http://localhost:3001` (Unity Catalog UI) and verify the `unity` catalog with `bronze` schema is browsable

### Expected outcome

- Containers running (`docker compose ps` — airflow, unity-catalog, unity-catalog-ui, marquez, marquez-db, otel-collector)
- UC API returns `["unity"]`
- Schemas list returns `["bronze","silver","gold"]`
- Step 4 prints `version 4.0.0` and exits 0
- Step 5 prints `SE OK` (spark-expectations 2.10+ imports cleanly — DQ enforcement path is live)
- **Step 6 passes** — `with_expectations(...)` invoked against a real Spark session; this is the no-opt-out gate that proves DQ actually fired (spokane shipped a "DQ-wired" pipeline that never executed `with_expectations` end-to-end; this AC closes that gap)
- **Step 7 returns count ≥ 1** — `bronze_se_stats` table has a row with `meta_dq_run_id` matching Step 6's run; confirms SE persisted runtime evidence
- Step 8 shows the `unity.bronze` schema in the browser without manual `docker network connect`

## Documentation Updates

- [ ] Update `<project>/README.md` § "Bootstrap" with the `make dev-up` one-liner and expected ports
- [ ] Update `<project>/README.md` § "Troubleshooting" with the JDK-17 / port-conflict / SE-import / UC-UI-proxy checklist
```

---

## Example 2 — `integration-test` story (with ≥1 automated verifier)

Closes a layer epic. Validator rules: `STORIES-CLOSURE-002`,
`STORIES-CLOSURE-003`, `STORIES-INTEGRATION-AUTOMATED-001`,
`STORIES-INTEGRATION-SE-001`.

```markdown
# STORY-02-007: Bronze layer integration test on local UC OSS

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion |
| **Story Type** | integration-test |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 4 |
| **Dependencies** | STORY-02-006 |
| **Status** | To Do |

## User Story

As a data engineer, I want the Bronze ingestion DAG verified end-to-end
against Unity Catalog OSS local so that we have a green gate before any
Silver work begins.

## Description

Trigger the Bronze ingestion Airflow DAG on the local docker-compose
stack and assert the expected Bronze Delta tables land in Unity Catalog
OSS local with correct schema and metadata columns. Reconciliation must
pass per LLD §5.5.

## Acceptance Criteria

- [ ] Airflow DAG `<bronze_dag_id>` triggered on local Airflow against Unity Catalog OSS local [LLD §4.2, §5.1]
- [ ] All N expected Bronze Delta tables registered in `unity.bronze` [LLD §5.1]
- [ ] Metadata columns (`ds`, `_ingested_at`, `_run_id`) populated on every row [LLD §3.2]
- [ ] Reconciliation task passes (row counts match source within tolerance) [LLD §5.5]
- [ ] **SE actually ran**: `bronze_se_stats` (or the LLD-named stats table) has ≥1 row whose `meta_dq_run_id` matches the DAG run's `--ds` [LLD §8.3, §8.6 — closes STORIES-INTEGRATION-SE-001]
- [ ] **DQ pass-rate reported**: `dq_pass_rate` exposed in Marquez run facets or Grafana dashboard for the run; ingestion fails-closed if SE never executed [LLD §8.6]

## Technical Notes

- Upstream references: LLD §2.4, §4.2, §5.1, §5.5
- Implementation hints: pytest with `@pytest.mark.integration`; use `airflow dags trigger` + poll until run state is `success`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §4.2 DAG Spec, §5.1 Bronze Tasks, §5.5 Reconciliation |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | DAG-trigger helper | pytest tests/integration/test_dag_trigger_helper.py |
| Integration | Bronze DAG end-to-end on local UC | pytest -m integration tests/integration/test_bronze_uc.py |
| Smoke | UC OSS API liveness | curl localhost:8080 /catalogs → 200 |
| DQ | Reconciliation thresholds | Spark Expectations row_dq pass |

## Verification

```yaml
AC1:
  - pytest: {node: "tests/integration/test_bronze_uc.py::test_dag_triggers", marker: "integration"}
AC2:
  - pytest: {node: "tests/integration/test_bronze_uc.py::test_tables_registered_in_uc", marker: "integration"}
AC3:
  - pytest: {node: "tests/integration/test_bronze_uc.py::test_metadata_columns_populated", marker: "integration"}
AC4:
  - pytest: {node: "tests/integration/test_bronze_uc.py::test_reconciliation_passes", marker: "integration"}
  - manual: "Marquez UI — visually confirm bronze_* lineage edges"
AC5:
  - pytest: {node: "tests/integration/test_bronze_uc.py::test_se_stats_populated", marker: "integration"}
AC6:
  - pytest: {node: "tests/integration/test_bronze_uc.py::test_dq_pass_rate_recorded", marker: "integration"}
  - manual: "Grafana DQ board — confirm dq_pass_rate gauge for the run"
```

## How to Test (User)

### Prerequisites

- runtime-bootstrap story (STORY-01-006) Done — stack up, schemas exist, source data seeded

### Steps

1. `airflow dags trigger <bronze_dag_id>`
2. `airflow dags list-runs -d <bronze_dag_id> --state success` (poll until non-empty)
3. `curl -s 'http://localhost:8080/api/2.1/unity-catalog/tables?catalog_name=unity&schema_name=bronze' | jq '.tables | length'`
4. Open Marquez at `http://localhost:5001` and inspect the `bronze_*` lineage graph

### Expected outcome

- DAG run state = `success` within 10 minutes
- Tables count ≥ N (the LLD §5.1 expected count)
- Marquez shows lineage edges from source → bronze tasks

## Documentation Updates

- [ ] Update `<project>/README.md` § "Run Bronze ingestion" with the DAG id and trigger command
- [ ] Update `<project>/README.md` § "Verify" with the UC tables curl one-liner
```

---

## Example 3 — `build` story with filled-in new sections

Layer-build story. Validator rules: `STORIES-TESTING-001`, `STORIES-USER-TEST-001`,
`STORIES-DOCS-001` (WARNING only — internal module).

```markdown
# STORY-02-001: Config-driven Bronze ingestion runner

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 2 |
| **Dependencies** | STORY-01-006 |
| **Status** | To Do |

## User Story

As a data engineer, I want a single config-driven Bronze ingestion runner
so that adding a new source table requires only a YAML config, not new code.

## Description

Implement `<project>/src/<project>/bronze/ingestion_runner.py` with `--config-path`
argparse, load the YAML, dispatch to the per-source extractor, and write
Delta to `unity.bronze.<table>` with metadata columns.

## Acceptance Criteria

- [ ] `ingestion_runner.py` accepts `--config-path` and loads YAML [LLD §2.3]
- [ ] Runner writes Delta to `unity.bronze.<table>` per config [LLD §5.1]
- [ ] Metadata columns (`ds`, `_ingested_at`, `_run_id`) appended [LLD §3.2]
- [ ] `empty_input_behavior: fail` honored for critical configs [LLD §5.1]

## Technical Notes

- Upstream references: LLD §2.3, §3.2, §5.1
- Implementation hints: reuse existing PySpark + Delta writer from /mvp.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §2.3 Module Contracts, §3.2 Metadata Cols, §5.1 Bronze Tasks |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | argparse + config load | pytest tests/bronze/test_ingestion_runner_unit.py |
| Unit | metadata-column appender | pytest tests/bronze/test_metadata_cols.py |

## Verification

```yaml
AC1:
  - file_exists: "<project>/src/<project>/bronze/ingestion_runner.py"
  - grep: {file: "<project>/src/<project>/bronze/ingestion_runner.py", pattern: "--config-path"}
AC4:
  - grep: {file: "<project>/src/<project>/bronze/ingestion_runner.py", pattern: "empty_input_behavior"}
```

## How to Test (User)

### Prerequisites

- runtime-bootstrap (STORY-01-006) Done
- One source table seeded

### Steps

1. `uv run python <project>/src/<project>/bronze/ingestion_runner.py --config-path airflow/configs/<table>.yml`
2. `duckdb /tmp/uc_query.db -c "SELECT count(*) FROM unity.bronze.<table>"`

### Expected outcome

- Process exits 0
- Bronze row count > 0; sample row contains `ds`, `_ingested_at`, `_run_id`

## Documentation Updates

- N/A — internal Bronze runner, not user-facing. Operator-facing usage is documented under STORY-02-007's runbook updates.
```

---

## Example 4 — phased contract (bootstrap → fail-closed) with Depends-On

When the LLD describes a temporal lifecycle (e.g. "in bootstrap mode
soft-import `se_runner`; once it ships, remove the soft-import and
fail-closed"), the scrum-master files **two stories** with a
`Dependencies` edge from the fail-closed-side story to the bootstrap-side
story. Both stories pass at their respective phases — the bootstrap
story's `grep` AC is superseded by the fail-closed story's `grep_absent`
once shipped. Validator rule: `STORIES-AC-CONTRADICTION-001` rejects
the same pair of ACs **without** the dependency edge.

**Bootstrap-side story (STORY-02-001):**

```markdown
# STORY-02-001: Bronze ingestion runner — bootstrap mode

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion |
| **Story Type** | build |
| **Dependencies** | STORY-01-006 |   ← runtime-bootstrap

## Acceptance Criteria

- [ ] Runner soft-imports `se_runner` and logs `WARNING: se_runner not available` if missing (bootstrap mode) [LLD §2.3, §8.6]

## Verification

```yaml
AC1:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "WARNING: se_runner not available"}
```
```

**Fail-closed-side story (STORY-02-004) — note the auto-added Dependency:**

```markdown
# STORY-02-004: Bronze SE runner — fail-closed (post-bootstrap)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion |
| **Story Type** | build |
| **Dependencies** | STORY-02-001 |   ← AUTO-ADDED by phased-contract guard

## Acceptance Criteria

- [ ] No soft-import, fail-closed if `se_runner` missing (post-bootstrap) [LLD §8.6]

## Verification

```yaml
AC1:
  - grep_absent: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "WARNING: se_runner not available"}
```
```

The validator sees the `grep` (STORY-02-001) and `grep_absent`
(STORY-02-004) on the same file + pattern, both citing §8.6 — but the
Dependencies edge from 02-004 → 02-001 tells it the contradiction is
ordered (bootstrap ships first, then fail-closed supersedes it). No
CRITICAL fires.
