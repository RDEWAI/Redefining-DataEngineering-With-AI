# STORY-01-006: Runtime bootstrap — JDK17, UC schemas, source seed, SE smoke

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation & Runtime Bootstrap |
| **Story Type** | runtime-bootstrap |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 1 |
| **Dependencies** | STORY-01-005, STORY-01-002 |
| **Status** | To Do |

## User Story

As a Data Engineer joining the project, I want a single bootstrap path that verifies JDK 17, the docker stack, UC catalog/schemas, source seed, Spark, and Spark Expectations end-to-end so that I know the dev laptop is genuinely ready before any `build` story runs.

## Description

This is the mandatory runtime-bootstrap story per LLD §6.1 and §8.6.1. It is the only story that proves the developer environment can actually run the pipeline — not just lint and import. It must verify: (1) JDK 17 installed; (2) docker stack up; (3) UC `unity` catalog and `bronze`/`silver`/`gold` schemas created via `uc_init.py`; (4) Synthea source seed loaded; (5) `spark-submit --version` reports Spark 4.0.0 inside Airflow container; (6) Spark Expectations imports cleanly; (7) **end-to-end SE run via `make smoke-se`** lands ≥1 row in `bronze_se_stats` with `with_expectations(...)` actually invoked against a real Spark session.

## Acceptance Criteria

- [ ] `java -version` reports 17.x.x [LLD §6.1]
- [ ] `docker compose -f patient_360/_infra/docker/docker-compose.yml up -d` succeeds [LLD §1]
- [ ] UC catalog `unity` and schemas `bronze`/`silver`/`gold` created via `scripts/uc_init.py` [LLD §1]
- [ ] Synthea source seed loaded into DuckDB at chapter-2 path with all 13 source tables [LLD §5.1]
- [ ] `curl http://localhost:8080/api/2.1/unity-catalog/catalogs` returns 200 with `unity` listed [LLD §9.5]
- [ ] `docker compose exec airflow spark-submit --master 'local[2]' --version` reports Spark 4.0.0 [LLD §6.1, story-standards §1]
- [ ] `docker compose exec airflow python -c "from spark_expectations.core.expectations import SparkExpectations"` exits 0 [LLD §8.6, story-standards §1]
- [ ] `make smoke-se` invokes `with_expectations(...)` against a real Spark session and `bronze_se_stats` has ≥1 row whose `meta_dq_run_id` matches the smoke run [LLD §8.6.1, story-standards §1]
- [ ] `patient_360/tests/integration/test_se_smoke.py::test_se_stats_populated` passes (pytest -m integration) [LLD §8.6.1]

## Technical Notes

- **Upstream references**: LLD §1, §6.1 (local_executor_mode = `in-airflow-local[*]`), §8.6 (bootstrap mode), §8.6.1 (SE-RUN-EVIDENCE), §9.5 (health checks); story-standards.md §1 Runtime-Bootstrap Coverage Rules
- **Implementation hints**: `make smoke-se` should `airflow tasks test bronze_ingestion.ingest_patients <ds>` — actual Spark task with SE wired. Then `SELECT count(*) FROM unity.bronze.bronze_se_stats WHERE meta_dq_run_date = '<ds>'` must return ≥ 1. `BRONZE_SKIP_SE=1` is forbidden.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §1, §6.1, §8.6, §8.6.1, §9.5, Decision 16 |
| DMS | §3 Bronze (synthea_patients) |
| STM | Source-to-Bronze |
| DQS | §2 patients row_dq |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Smoke | UC API + JDK + docker stack health | `make dev-up && curl localhost:8080/api/2.1/unity-catalog/catalogs` |
| Smoke | Spark-submit reports 4.0.0 | `docker compose exec airflow spark-submit --version` |
| Smoke | SE imports | `docker compose exec airflow python -c 'from spark_expectations.core.expectations import SparkExpectations'` |
| Integration | SE end-to-end run produces bronze_se_stats row | `pytest -m integration patient_360/tests/integration/test_se_smoke.py` |
| DQ | bronze_se_stats populated for run | `pytest -m integration patient_360/tests/integration/test_se_smoke.py::test_se_stats_populated` |

## Verification

```yaml
AC1:
  - manual: "run `java -version` and verify 17.x"
AC2:
  - manual: "run docker compose up -d and verify all services healthy"
AC3:
  - file_exists: "patient_360/scripts/uc_init.py"
  - manual: "run scripts/uc_init.py and verify unity catalog has bronze/silver/gold schemas"
AC4:
  - manual: "duckdb chapter-2/data/duckdb/raw.db -c '.tables' shows synthea.patients..."
AC5:
  - manual: "curl http://localhost:8080/api/2.1/unity-catalog/catalogs | jq '.catalogs[].name' | grep unity"
AC6:
  - manual: "docker compose exec airflow spark-submit --master 'local[2]' --version reports 4.0.0"
AC7:
  - manual: "docker compose exec airflow python -c 'from spark_expectations.core.expectations import SparkExpectations' exits 0"
AC8:
  - pytest: {node: "patient_360/tests/integration/test_se_smoke.py::test_se_stats_populated", marker: "integration"}
  - manual: "make smoke-se completes; bronze_se_stats meta_dq_run_id matches smoke run"
AC9:
  - pytest: {node: "patient_360/tests/integration/test_se_smoke.py", marker: "integration"}
```

## How to Test (User)

### Prerequisites

- Docker Desktop running
- JDK 17 installed (`brew install openjdk@17` on macOS)
- UV installed
- chapter-2 Synthea source data present in DuckDB

### Steps

1. `java -version`  (expect 17.x.x)
2. `cd patient_360 && docker compose -f _infra/docker/docker-compose.yml up -d`
3. `cd patient_360 && uv run python scripts/uc_init.py --catalog unity --schemas bronze,silver,gold`
4. `curl -sS http://localhost:8080/api/2.1/unity-catalog/catalogs | jq '.catalogs[].name'`
5. `cd patient_360 && docker compose exec airflow spark-submit --master 'local[2]' --version`
6. `cd patient_360 && docker compose exec airflow python -c "from spark_expectations.core.expectations import SparkExpectations"`
7. `cd patient_360 && make smoke-se`
8. `cd patient_360 && uv run pytest -m integration tests/integration/test_se_smoke.py -v`

### Expected outcome

- Step 1 reports `openjdk version "17.x.x"`
- Step 2 all services healthy within 60s
- Step 3 logs `created schema unity.bronze`, `unity.silver`, `unity.gold`
- Step 4 includes `"unity"`
- Step 5 prints `Spark version 4.0.0`
- Step 6 exits 0 (no traceback)
- Step 7 `make smoke-se` ends with `bronze_se_stats: 1 row written for meta_dq_run_id=<id>`
- Step 8 `test_se_stats_populated` passes

## Documentation Updates

- [ ] Update `patient_360/README.md` § "Runtime Bootstrap" with steps 1-8 verbatim as the onboarding checklist
- [ ] Update `patient_360/_infra/docker/README.md` § "Bootstrap Sequence" with `uc_init.py` and `make smoke-se` references
- [ ] Update top-level `chapter-5/README.md` § "Quick Start" linking to the bootstrap runbook
