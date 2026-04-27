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
6. Open `http://localhost:3001` (Unity Catalog UI) and verify the `unity` catalog with `bronze` schema is browsable

### Expected outcome

- Containers running (`docker compose ps` — airflow, unity-catalog, unity-catalog-ui, marquez, marquez-db, otel-collector)
- UC API returns `["unity"]`
- Schemas list returns `["bronze","silver","gold"]`
- Step 4 prints `version 4.0.0` and exits 0
- Step 5 prints `SE OK` (spark-expectations 2.10+ imports cleanly — DQ enforcement path is live)
- Step 6 shows the `unity.bronze` schema in the browser without manual `docker network connect`

## Documentation Updates

- [ ] Update `<project>/README.md` § "Bootstrap" with the `make dev-up` one-liner and expected ports
- [ ] Update `<project>/README.md` § "Troubleshooting" with the JDK-17 / port-conflict / SE-import / UC-UI-proxy checklist
```

---

## Example 2 — `integration-test` story (with ≥1 automated verifier)

Closes a layer epic. Validator rules: `STORIES-CLOSURE-002`,
`STORIES-CLOSURE-003`, `STORIES-INTEGRATION-AUTOMATED-001`.

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
