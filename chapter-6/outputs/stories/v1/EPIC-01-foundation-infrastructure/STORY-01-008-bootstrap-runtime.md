# STORY-01-008: Bootstrap local dev runtime (JDK / Docker / UC / Spark / SE end-to-end)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation & Infrastructure |
| **Story Type** | runtime-bootstrap |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 2 |
| **Dependencies** | STORY-01-005, STORY-01-006, STORY-01-007 |
| **Status** | In Progress |

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

As a data engineer, I want have one command bring my laptop from clean to a verified runtime where Spark + UC OSS + SE are wired end-to-end so that every downstream `build` story lands on a known-good stack — no `BRONZE_SKIP_SE=1` or 'works on my machine' drift.

## Description

Wire `make dev-bootstrap` and `make smoke-se` to: bring up the docker-compose stack, bootstrap UC OSS catalog/schemas, seed Synthea source data, exercise spark-submit against `local[2]`, and run `with_expectations(...)` end-to-end against a real Spark session writing to `bronze_se_stats`. Provide a `tests/bootstrap/test_se_smoke.py::test_with_expectations_runs_end_to_end` integration test enforcing run-evidence per LLD §8.6.1. This story exists because Spokane shipped a Bronze pipeline where DQ silently did nothing — we close that gap end-to-end.

## Acceptance Criteria


- [x] `java -version` reports 17.x.x [LLD §6.1]

- [x] `docker compose -f _infra/docker/docker-compose.yml up -d` succeeds [LLD §1]

- [x] UC catalog `unity` and schemas `bronze`/`silver`/`gold` created via `scripts/uc_init.py` [LLD §1]

- [x] Synthea source data seeded into local source DB (13 Phase-1 source tables) [LLD §5.1]

- [x] `curl http://localhost:8080/api/2.1/unity-catalog/catalogs` returns 200 with `unity` listed [LLD §1]

- [x] `docker compose exec airflow spark-submit --master 'local[2]' --version` exits 0 and reports Spark 4.0.0 [LLD §6.1]

- [x] `docker compose exec airflow python -c 'from spark_expectations.core.expectations import SparkExpectations'` exits 0 (proves SE 2.10+ imports — DQ is mandatory) [LLD §6.1]

- [x] SE end-to-end smoke `pytest -m integration tests/bootstrap/test_se_smoke.py::test_with_expectations_runs_end_to_end` invokes `WrappedDataFrameWriter(...).with_expectations(...)` and asserts `bronze_se_stats` has ≥1 row whose `meta_dq_run_id` matches the run [LLD §8.6.1]

- [ ] `scripts/bootstrap_uc_tables.py` exists and is a one-shot **pure-Python REST client** against UC OSS (NOT a Spark application, NOT a Liquibase wrapper, NOT a JDBC client). Uses `httpx` (or stdlib `urllib.request`) to call UC OSS `/api/2.1/unity-catalog/{schemas,tables}` endpoints. Reads every populated `contracts/*.yml` directly. For each contract: (1) `GET /api/2.1/unity-catalog/schemas?catalog_name={catalog}` → if `contract.schema` not present, `POST /api/2.1/unity-catalog/schemas` with `{name, catalog_name}`; (2) `GET /api/2.1/unity-catalog/tables?catalog_name={catalog}&schema_name={schema}` → if `contract.table` not present, `POST /api/2.1/unity-catalog/tables` with `{name, catalog_name, schema_name, table_type="EXTERNAL", data_source_format="DELTA", columns=[...], storage_location}`. Idempotent (GET-before-POST). Logs each created/skipped table at INFO. Accumulates failures during iteration and fail-loud at end (exit non-zero) if any registration failed. **NO SparkSession, NO UCSingleCatalog, NO JDBC, NO `spark.sql`, NO `unitycatalog-spark` Maven coordinate.** Runtime tasks remain `DeltaCatalog` per LLD §13 Decision 12. [LLD v1.18 §13 Decision 17 (Revised 2026-05-23 second pivot); supersedes v1.17 Spark-DDL approach which was binary-incompat with Spark 4.x (`unitycatalog-spark_2.13:0.3.0` → `NoSuchMethodError: LogKey.$init$`)]

- [ ] `Makefile` target `bootstrap-uc` exists: runs `python scripts/bootstrap_uc_tables.py --env $(ENV)` directly — **no Spark, no spark-submit, no Liquibase invocation for UC**. Idempotent (REST GET-before-POST per object). Documented in `make help`. [LLD v1.18 §13 Decision 17 (Revised 2026-05-23 second pivot); supersedes v1.17 AC10]

- [ ] Canonical local bring-up is `make dev-up && make bootstrap-uc` — `make dev-up` brings compose services to healthy; `make bootstrap-uc` runs AFTER. Documented in `patient_360/README.md` and in the Makefile `help` output. (Decision: keep `bootstrap-uc` as a separate target rather than chaining inside `dev-up` so contributors can re-run UC table registration after editing `contracts/*.yml` without bouncing the stack.) [LLD v1.18 §13 Decision 17]

- [ ] Pipeline config keys `uc.bootstrap_catalog_name` (env var `UC_BOOTSTRAP_CATALOG_NAME`, default `unity`), `uc.bootstrap_uri` (env var `UC_BOOTSTRAP_URI`, default `http://localhost:8080` for DEV host invocation — STAGING/PROD may use `http://unity-catalog:8080` for in-container invocation), and `uc.bootstrap_timeout_seconds` (env var `UC_BOOTSTRAP_TIMEOUT_SECONDS`, default `30`) are present in `_infra/cd/config/DEV.yaml` (and the `STAGING.yaml` + `PROD.yaml` templates) under the `monitoring:` block as flattened keys `catalog_uc_bootstrap_catalog_name`, `catalog_uc_bootstrap_uri`, and `catalog_uc_bootstrap_timeout_seconds` (matching the existing `catalog_*` flatten convention). Consumed exclusively by `scripts/bootstrap_uc_tables.py`. **DEV default `http://localhost:8080`** is required because host-side `make bootstrap-uc` invocations cannot resolve the compose-internal hostname `unity-catalog` (would fail with `UnresolvedAddressException`). [LLD v1.18 §7.1 — Decision 17 Revised 2026-05-23 second pivot]


## Technical Notes

- **Upstream references**: LLD §1, §6.1, §7.1, §8.6, §8.6.1, §9.1, §13 Decision 17 (Revised v1.18, 2026-05-23 second pivot)
- **Implementation hints**: `make dev-bootstrap` = `dev-up && wait-for-uc && uc-init && seed && smoke-spark && smoke-se`. The SE smoke test must write to a temp Delta table and assert the SE stats table populated.
- **Decision 17 (Revised v1.18, second pivot) — Deploy-time UC table registration via pure-Python REST client**: The v1.17 Spark-DDL approach is **abandoned** because `io.unitycatalog:unitycatalog-spark_2.13:0.3.0` (the latest on Maven Central as of 2026-05-23) is built against Spark 3.5.x and binary-incompat with Spark 4.x. UCSingleCatalog raises `java.lang.NoSuchMethodError: 'void org.apache.spark.internal.LogKey.$init$(org.apache.spark.internal.LogKey)'` on first `CREATE TABLE` call. No newer `unitycatalog-spark_2.13` version exists. The REST API is the only UC integration path that works with the project's Spark 4.x stack today — verified working 2026-05-23 via curl smoke test against `/api/2.1/unity-catalog/{schemas,tables}`. `contracts/*.yml` remains the human-edited source of truth. `scripts/bootstrap_uc_tables.py` is now a **pure-Python httpx client** (one-shot — invokes REST, exits). For each populated contract: `GET /schemas` then conditional `POST /schemas`; `GET /tables` then conditional `POST /tables` with `{name, catalog_name, schema_name, table_type=EXTERNAL, data_source_format=DELTA, columns, storage_location}`. Idempotent (GET-before-POST). Fail-loud at end. **NO Spark, NO JDBC, NO Maven coordinates** — only `httpx` + `pyyaml` (both already in project deps). Runtime Spark writers stay path-based via `DeltaCatalog` and are FORBIDDEN from calling `CREATE TABLE` (see STORY-03-001 AC8-AC10 — unaffected by this pivot). DEV `uc.bootstrap_uri` default flips to `http://localhost:8080` because host-side `make bootstrap-uc` cannot resolve the compose-internal hostname `unity-catalog`; STAGING/PROD may stay `http://unity-catalog:8080` if those run in-container. Decoupling UC registration from the Spark stack also lets UC OSS and the project's Spark/Delta versions evolve independently.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §1 Overview, §6.1 Compute, §8.6.1 SE Run-Evidence, §9.1 Scaffold |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Smoke | UC OSS catalog/schemas exist | pytest patient_360/tests/bootstrap/test_uc_health.py |

| Smoke | spark-submit reachable from Airflow worker | pytest patient_360/tests/bootstrap/test_spark_smoke.py |

| Smoke | SE imports cleanly (DQ path live) | pytest patient_360/tests/bootstrap/test_se_smoke.py::test_se_imports |

| Smoke | SE runs end-to-end against real Spark | pytest -m integration patient_360/tests/bootstrap/test_se_smoke.py::test_with_expectations_runs_end_to_end |



## Verification

```yaml
AC1:
  - manual: "java -version — depends on host JDK install"
AC2:
  - manual: "docker compose up — requires Docker Desktop"
AC3:
  - pytest: {node: "patient_360/tests/bootstrap/test_uc_health.py"}
AC4:
  - manual: "source seed — runs against live source DB"
AC5:
  - manual: "curl against running UC OSS"
AC6:
  - pytest: {node: "patient_360/tests/bootstrap/test_spark_smoke.py"}
AC7:
  - pytest: {node: "patient_360/tests/bootstrap/test_se_smoke.py::test_se_imports"}
AC8:
  - pytest: {node: "patient_360/tests/bootstrap/test_se_smoke.py::test_with_expectations_runs_end_to_end", marker: "integration"}
AC9:
  - file_exists: "patient_360/scripts/bootstrap_uc_tables.py"
  - required_grep: {file: "patient_360/scripts/bootstrap_uc_tables.py", pattern: "httpx|urllib\\.request"}
  - required_grep: {file: "patient_360/scripts/bootstrap_uc_tables.py", pattern: "/api/2\\.1/unity-catalog/schemas"}
  - required_grep: {file: "patient_360/scripts/bootstrap_uc_tables.py", pattern: "/api/2\\.1/unity-catalog/tables"}
  - required_grep: {file: "patient_360/scripts/bootstrap_uc_tables.py", pattern: "POST"}
  - required_grep: {file: "patient_360/scripts/bootstrap_uc_tables.py", pattern: "GET"}
  - required_grep: {file: "patient_360/scripts/bootstrap_uc_tables.py", pattern: "EXTERNAL"}
  - required_grep: {file: "patient_360/scripts/bootstrap_uc_tables.py", pattern: "DELTA"}
  - required_grep: {file: "patient_360/scripts/bootstrap_uc_tables.py", pattern: "storage_location"}
  - required_grep: {file: "patient_360/scripts/bootstrap_uc_tables.py", pattern: "contracts/"}
  - forbidden_grep: {file: "patient_360/scripts/bootstrap_uc_tables.py", pattern: "SparkSession"}
  - forbidden_grep: {file: "patient_360/scripts/bootstrap_uc_tables.py", pattern: "UCSingleCatalog"}
  - forbidden_grep: {file: "patient_360/scripts/bootstrap_uc_tables.py", pattern: "spark\\.sql"}
  - forbidden_grep: {file: "patient_360/scripts/bootstrap_uc_tables.py", pattern: "JDBC"}
  - forbidden_grep: {file: "patient_360/scripts/bootstrap_uc_tables.py", pattern: "liquibase"}
  - forbidden_grep: {file: "patient_360/scripts/bootstrap_uc_tables.py", pattern: "unitycatalog-spark"}
AC10:
  - required_grep: {file: "patient_360/Makefile", pattern: "^bootstrap-uc:"}
  - required_grep: {file: "patient_360/Makefile", pattern: "bootstrap_uc_tables\\.py"}
  - forbidden_grep: {file: "patient_360/Makefile", pattern: "bootstrap-uc:.*liquibase-apply|bootstrap-uc:.*gen_liquibase"}
  - forbidden_grep: {file: "patient_360/Makefile", pattern: "bootstrap-uc:.*spark-submit|bootstrap-uc:.*pyspark"}
AC11:
  - required_grep: {file: "patient_360/Makefile", pattern: "bootstrap-uc"}
  - required_grep: {file: "patient_360/README.md", pattern: "make dev-up.*make bootstrap-uc|bootstrap-uc"}
AC12:
  - required_grep: {file: "patient_360/_infra/cd/config/DEV.yaml", pattern: "uc_bootstrap_catalog_name|UC_BOOTSTRAP_CATALOG_NAME"}
  - required_grep: {file: "patient_360/_infra/cd/config/DEV.yaml", pattern: "uc_bootstrap_uri|UC_BOOTSTRAP_URI|localhost:8080"}
  - required_grep: {file: "patient_360/_infra/cd/config/DEV.yaml", pattern: "uc_bootstrap_timeout_seconds|UC_BOOTSTRAP_TIMEOUT_SECONDS"}
  - required_grep: {file: "patient_360/_infra/cd/config/STAGING.yaml", pattern: "uc_bootstrap_catalog_name|UC_BOOTSTRAP_CATALOG_NAME"}
  - required_grep: {file: "patient_360/_infra/cd/config/STAGING.yaml", pattern: "uc_bootstrap_uri|UC_BOOTSTRAP_URI"}
  - required_grep: {file: "patient_360/_infra/cd/config/STAGING.yaml", pattern: "uc_bootstrap_timeout_seconds|UC_BOOTSTRAP_TIMEOUT_SECONDS"}
  - required_grep: {file: "patient_360/_infra/cd/config/PROD.yaml", pattern: "uc_bootstrap_catalog_name|UC_BOOTSTRAP_CATALOG_NAME"}
  - required_grep: {file: "patient_360/_infra/cd/config/PROD.yaml", pattern: "uc_bootstrap_uri|UC_BOOTSTRAP_URI"}
  - required_grep: {file: "patient_360/_infra/cd/config/PROD.yaml", pattern: "uc_bootstrap_timeout_seconds|UC_BOOTSTRAP_TIMEOUT_SECONDS"}
```


## How to Test (User)

### Prerequisites


- Host JDK 17 installed

- Docker Desktop running

- STORY-01-005, STORY-01-006, STORY-01-007 done (full docker-compose stack health-checked)


### Steps


1. `java -version`

2. `cd patient_360 && make dev-bootstrap`

3. `make smoke-se`

4. `curl http://localhost:8080/api/2.1/unity-catalog/catalogs`


### Expected outcome


- JDK 17 reported

- All five bootstrap steps complete green

- `bronze_se_stats` has ≥1 row after `make smoke-se`

- UC OSS API returns `unity` catalog


## Documentation Updates


- [x] Update patient_360/README.md § "Bootstrap" with the `make dev-bootstrap` + `make smoke-se` runbook

- [x] Add patient_360/docs/runbooks/bootstrap.md with the eight-step verification checklist


User-Verified-By: Phani Vemuri 2026-05-11

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-05-23 | Scrum Master Agent | Added 6 new acceptance criteria (AC9-AC14) for LLD v1.16 §13 Decision 17 — deploy-time UC table registration via Liquibase over the open-source UC JDBC driver. AC9: `scripts/gen_liquibase_from_contracts.py` reads `contracts/*.yml` and overwrites `ddl/liquibase/changelogs/*.xml` with `CREATE TABLE IF NOT EXISTS ... USING DELTA LOCATION '...'` change-sets (idempotent, stable column order). AC10: `scripts/bootstrap_uc_tables.py` health-checks UC and shells out to `liquibase-apply.sh`. AC11: `_infra/cd/liquibase-apply.sh` re-pointed at UC JDBC defaults (`JDBC_URL=jdbc:unitycatalog://unity-catalog:8080`, `JDBC_DRIVER=io.unitycatalog.client.jdbc.UCDriver`); UC JDBC driver JAR mounted; Postgres fallback via `JDBC_FLAVOR=postgres`. AC12: Makefile `bootstrap-uc` target. AC13: canonical bring-up documented as `make dev-up && make bootstrap-uc` (kept as separate target so contributors can re-run table registration after editing contracts without bouncing the stack). AC14: `io.unitycatalog:unitycatalog-jdbc` driver coordinates pinned in script header. Folded contract-generator scope here per user direction (keeps EPIC-01 size manageable; no new STORY-01-011 created). Cross-references LLD v1.16 §13 Decision 17 and `chapter-6/developer-plugin/LLD-DEVIATIONS.md` row 10 (forward reference). Verification block extended with file_exists + required_grep checks for each new AC. Scope, dependencies, sprint, status, and prior ACs unchanged. |
| 2026-05-23 | Scrum Master Agent | **PIVOTED ACs (SECOND PIVOT) for LLD v1.18 §13 Decision 17 Revised (2026-05-23 second pivot) — pure-Python REST client replaces Spark-DDL.** The v1.17 Spark-DDL approach was unbuildable because `io.unitycatalog:unitycatalog-spark_2.13:0.3.0` is binary-incompat with Spark 4.x (`NoSuchMethodError` on `LogKey.$init$`). REST API verified working via curl. **REWROTE AC9 verifications**: `scripts/bootstrap_uc_tables.py` is now a pure-Python httpx client (NO Spark, NO JDBC). New required_grep: `httpx` (or `urllib.request`), `/api/2.1/unity-catalog/schemas`, `/api/2.1/unity-catalog/tables`, `POST`, `GET`, `EXTERNAL`, `DELTA`, `storage_location`, `contracts/`. New forbidden_grep: `SparkSession`, `UCSingleCatalog`, `spark.sql`, `JDBC`, `liquibase`, `unitycatalog-spark`. **UPDATED AC10**: Makefile `bootstrap-uc` now calls plain `python scripts/bootstrap_uc_tables.py` (no spark-submit, no pyspark); extended `forbidden_grep` with `bootstrap-uc:.*spark-submit|bootstrap-uc:.*pyspark`. **KEPT AC11** unchanged. **UPDATED AC12**: added `uc.bootstrap_timeout_seconds` config key (env var `UC_BOOTSTRAP_TIMEOUT_SECONDS`, default `30`) per LLD v1.18 §7.1; flipped DEV `uc_bootstrap_uri` default from `http://unity-catalog:8080` to `http://localhost:8080` (host-side `make bootstrap-uc` invocations cannot resolve the compose-internal hostname — fails with `UnresolvedAddressException`). STAGING/PROD may keep `http://unity-catalog:8080` if running in-container. Verification block extended with required_grep for `localhost:8080` and timeout key across all three env configs. Cross-references LLD v1.18 §13 Decision 17 (Revised 2026-05-23 second pivot) and supersedes v1.17 Spark-DDL ACs. STORY-03-001 unaffected (runtime `CREATE TABLE` prohibition AC8-AC10 still hold verbatim). Scope, dependencies, sprint, and AC1-AC8 unchanged. |
| 2026-05-23 | Scrum Master Agent | **PIVOTED ACs for LLD v1.17 §13 Decision 17 Revised (2026-05-23) — Spark-DDL replaces Liquibase-over-UC-JDBC.** v1.16 plan was unbuildable because `io.unitycatalog:unitycatalog-jdbc` is not published on Maven Central. **REMOVED** old AC9 (`scripts/gen_liquibase_from_contracts.py` existence/greps — script will be deleted by next `update-scaffold`). **REMOVED** old AC11 (`_infra/cd/liquibase-apply.sh` UC JDBC mode — Liquibase reverts to pre-v1.16 Postgres-only audit role). **REMOVED** old AC14 (`unitycatalog-jdbc` driver pinning — artifact does not exist). **REWROTE** old AC10 → new AC9: `scripts/bootstrap_uc_tables.py` is now a one-shot **Spark application** (NOT a Liquibase wrapper) — boots a SparkSession with `UCSingleCatalog` (DDL-only binding, used only by this script — runtime tasks remain `DeltaCatalog` per LLD §13 Decision 12), reads `contracts/*.yml` directly, issues idempotent `CREATE SCHEMA IF NOT EXISTS` + `CREATE TABLE IF NOT EXISTS … USING DELTA LOCATION …` per contract. New required_grep list: `SparkSession`, `UCSingleCatalog`, `CREATE SCHEMA IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`, `USING DELTA`, `LOCATION`, `contracts/`. New forbidden_grep list: `liquibase`, `JDBC`. **KEPT** old AC12 → new AC10 (Makefile `bootstrap-uc` target) with description updated to call `python scripts/bootstrap_uc_tables.py` directly — no Liquibase invocation; verification extended with `forbidden_grep` for `bootstrap-uc:.*liquibase-apply|bootstrap-uc:.*gen_liquibase` to prevent regression. **KEPT** old AC13 → new AC11 (canonical bring-up `make dev-up && make bootstrap-uc`) unchanged. **ADDED** new AC12 — pipeline config keys `uc.bootstrap_catalog_name` (env var `UC_BOOTSTRAP_CATALOG_NAME`, default `unity`) and `uc.bootstrap_uri` (env var `UC_BOOTSTRAP_URI`, default `http://unity-catalog:8080`) per LLD v1.17 §7.1; verifies they appear in `_infra/cd/config/{DEV,STAGING,PROD}.yaml` (existing pipeline config templates). Cross-references LLD v1.17 §13 Decision 17 (Revised 2026-05-23) and supersedes the v1.16 JDBC ACs. Scope, dependencies, sprint, and AC1-AC8 unchanged. |
