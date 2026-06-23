# STORY-01-007: Build docker-compose service block — Airflow (Dockerfile.airflow) + otel-collector + Makefile dev-up/dev-down

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation & Infrastructure |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 3 |
| **Sprint** | 2 |
| **Dependencies** | STORY-01-001, STORY-01-005, STORY-01-006 |
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

As a platform engineer, I want the locally-built Airflow image and the otel-collector service in the shared `docker-compose.yml`, plus `make dev-up` / `make dev-down` targets, so that every developer can bring the full local stack up and down with one command.

## Description

Author the `airflow`, `otel-collector`, and `spark-thrift-server` service entries in `_infra/docker/docker-compose.yml` (the shared file is now complete after this story). Author `_infra/docker/Dockerfile.airflow` that bundles Airflow 3.2.1, Spark **4.1.1** (`local[2]` executor), JDK 17, and `spark-expectations>=2.10` per LLD §6.1. Author `_infra/docker/Dockerfile.thrift` (Spark **4.1.1** + delta-spark **4.3.0** + `unitycatalog-spark_4.1_2.13:0.5.0` + openlineage-spark **1.50.0** jars) for the `spark-thrift-server` service (HiveServer2 on :10000) — the Spark SQL endpoint that runs Delta DDL and that **beeline** targets via `make ddl-apply`, so UC tables are pre-created before pipeline writes per LLD §13 Decision 12. Pin `otel/opentelemetry-collector-contrib:0.107.0` per LLD §9.1.1. (Liquibase is retired — UPGRADE-NOTES UC 0.5.0 / Spark 4.1: DDL is now plain beeline-applied `.sql`; there is **no** `liquibase` container.) Mount a shared `_delta_log` volume between `spark-thrift-server`, `airflow`, and `unity-catalog` for coordinated commits on SE's MANAGED audit tables (UPGRADE-NOTES §4.5, §7). Wire `airflow` `depends_on:` UC OSS and Marquez with `condition: service_healthy`, and otel-collector with `condition: service_started`. **Do NOT add a `healthcheck:` block to `otel-collector`** — the `otel/opentelemetry-collector-contrib` image is distroless (no `/bin/sh`, no `wget`, no `curl`), so any in-container probe will fail with `exec: "/bin/sh": stat /bin/sh: no such file or directory`. The collector's own `health_check` extension on `:13133` is reachable from the host for verification. Add the `dev-up` / `dev-down` / `ddl-apply` targets to the project `Makefile` — `dev-up` brings the full stack up, waits for all healthcheck-bearing services healthy (including `spark-thrift-server`), runs `scripts/uc_init.py` once, then runs `make ddl-apply` (the `_infra/docker/ddl-apply.sh` one-shot, beeline applying every plain dated `ddl/migrations/*.sql` in lexical order against `jdbc:hive2://spark-thrift-server:10000/unity`) to pre-create the UC EXTERNAL Delta tables before any DAG trigger.

## Acceptance Criteria


- [ ] `_infra/docker/Dockerfile.airflow` installs JDK 17, Spark 4.1.1, Airflow 3.2.1, and `spark-expectations>=2.10` per LLD §6.1 [LLD §6.1; UPGRADE-NOTES §2]

- [x] `_infra/docker/docker-compose.yml` declares `airflow` (built from `Dockerfile.airflow`) and `otel-collector` (`otel/opentelemetry-collector-contrib:0.107.0`) per LLD §9.1.1 [LLD §9.1.1]

- [ ] `_infra/docker/docker-compose.yml` declares `spark-thrift-server` (built from `Dockerfile.thrift`, Spark 4.1.1 + delta-spark 4.3.0 + `unitycatalog-spark_4.1_2.13:0.5.0` jars, HiveServer2 :10000) and mounts the shared `_delta_log` volume; there is **no** `liquibase` container (DDL is beeline-applied `.sql` — UPGRADE-NOTES) per LLD §9.1.1, §13 Decision 12 [LLD §9.1.1, §13 Decision 12; UPGRADE-NOTES §2, §4.5]

- [ ] `_infra/docker/Dockerfile.thrift` exists and bundles Spark 4.1.1 + delta-spark 4.3.0 + `unitycatalog-spark_4.1_2.13:0.5.0` jars, launching the Spark Thrift Server (HiveServer2) on :10000 [LLD §9.1.1, §13 Decision 12; UPGRADE-NOTES §2]

- [x] `airflow` declares `depends_on:` `unity-catalog` and `marquez` with `condition: service_healthy`, and `otel-collector` with `condition: service_started` (otel image is distroless — see Description) [LLD §9.1.1]

- [x] `airflow` declares a `healthcheck:` block such that `docker compose ps` reports it `healthy` within 120s of start. `otel-collector` MUST NOT declare a `healthcheck:`; verify it via `curl localhost:13133/` from the host [LLD §9.1.1]

- [ ] `make dev-up` brings the full seven-service stack up, waits for healthy (incl. `spark-thrift-server`), runs `scripts/uc_init.py`, then runs `make ddl-apply`, and exits 0; `make dev-down` tears it down cleanly [LLD §9.3]

- [ ] `Makefile` declares a `ddl-apply` target that runs `beeline -u jdbc:hive2://spark-thrift-server:10000/unity -f` over every plain dated `ddl/migrations/*.sql` in lexical order (all layers' migrations live flat under `ddl/migrations/` — no per-layer subdirs) to pre-create the UC EXTERNAL Delta tables; `dev-up` invokes it after `spark-thrift-server` is healthy and before any DAG trigger. **No** Liquibase (retired — UPGRADE-NOTES) [LLD §9.1, §13 Decision 12]

- [ ] **Definition of Done** evidence captured in the Verification block: (a) `docker compose ps` output showing the six healthcheck-bearing services (`unity-catalog`, `unity-catalog-ui`, `marquez-db`, `marquez`, `airflow`, `spark-thrift-server`) `healthy` and `otel-collector` `running`, AND (b) HTTP probe `curl -fsS http://localhost:8081/health` (Airflow webserver) returning 200 AND `curl -fsS http://localhost:13133/` (otel-collector health_check extension, probed from host) returning 200 AND `make ddl-apply` (beeline) reporting the UC tables created [LLD §6.1, §9.1.1, §13 Decision 12]

- [ ] The `airflow` service block exports `PATIENT360_PROJECT_ROOT` (and the derived `AIRFLOW_CONFIGS_DIR`, `DQ_RULES_DIR`, `PATIENT360_WAREHOUSE_ROOT`) so every Airflow task resolves paths against the project root rather than CWD (LLD §9.1 — 2026-05-12 pivot) [LLD §9.1]

- [ ] `_infra/docker/Dockerfile.thrift` resolves the Delta + Unity Catalog jars at **BUILD time** INTO Spark's classpath directory `/opt/spark/jars/` (copied as root before switching to `USER spark`), so the Thrift Server starts with NO network access and NO ivy resolution at runtime. The generated `/opt/spark/conf/spark-defaults.conf` MUST NOT contain a `spark.jars.packages` line (runtime package resolution fails because the `spark` user's `HOME=/nonexistent` cannot write the ivy cache → `java.io.FileNotFoundException /nonexistent/.ivy2...`). `spark-defaults.conf` keeps only `spark.sql.extensions` + the catalog wiring (`spark_catalog=DeltaCatalog`, `unity=UCSingleCatalog`, `.uri`, `.token`, `defaultCatalog=unity`) [LLD §9.1.1, §13 Decision 12]


## Technical Notes

- **Upstream references**: LLD §1, §6.1, §9.1, §9.1.1, §9.3
- **Implementation hints**: Airflow healthcheck = `curl -fsS http://localhost:8081/health`. otel-collector exposes the `health_check` extension on `:13133` BUT the image is distroless (no `/bin/sh`, no `wget`, no `curl`) — do **NOT** add a `healthcheck:` block to that service. Wire airflow's `depends_on.otel-collector` as `condition: service_started`. `make dev-up` should `docker compose up -d --wait` (compose v2 native wait-for-healthy); the collector reports `running` (not `healthy`) and `--wait` accepts that. Verify the collector from the host via `curl localhost:13133/`. Keep all six services in the single `docker-compose.yml` co-authored across STORY-01-005/006/007.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §1, §6.1, §9.1, §9.1.1, §9.3 |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Smoke | Full compose stack health | make dev-up && docker compose ps |

| Smoke | Airflow webserver reachable | curl http://localhost:8081/health |



## Verification

```yaml
AC1:
  - file_exists: "patient_360/_infra/docker/Dockerfile.airflow"
  - grep: {file: "patient_360/_infra/docker/Dockerfile.airflow", pattern: "openjdk-17"}
  - grep: {file: "patient_360/_infra/docker/Dockerfile.airflow", pattern: "spark-expectations"}
  - grep: {file: "patient_360/_infra/docker/Dockerfile.airflow", pattern: "apache-airflow.*3\\.2\\.1|airflow==3\\.2\\.1"}
AC2:
  - grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "Dockerfile.airflow"}
  - grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "otel/opentelemetry-collector-contrib:0.107.0"}
AC3:
  - grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "spark-thrift-server:"}
  - grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "10000"}
  - grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "_delta_log"}
  - forbidden_grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "liquibase", reason: "Liquibase retired — DDL is beeline-applied .sql per UPGRADE-NOTES UC 0.5.0 / Spark 4.1"}
AC4:
  - file_exists: "patient_360/_infra/docker/Dockerfile.thrift"
  - grep: {file: "patient_360/_infra/docker/Dockerfile.thrift", pattern: "spark|Spark"}
  - grep: {file: "patient_360/_infra/docker/Dockerfile.thrift", pattern: "0\\.5\\.0|unitycatalog-spark_4\\.1"}
AC5:
  - grep_count: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "condition: service_healthy", at_least: 2}
  - grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "condition: service_started"}
AC6:
  - grep_count: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "healthcheck:", greater_or_equal: 6}
  - forbidden_grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "otel-collector:[\\s\\S]{0,400}healthcheck:", reason: "otel-collector image is distroless; in-container healthcheck cannot succeed"}
  - manual: "docker compose ps shows airflow 'healthy' and otel-collector 'running'; curl localhost:13133/ from host returns 200"
AC7:
  - grep: {file: "patient_360/Makefile", pattern: "dev-up:"}
  - grep: {file: "patient_360/Makefile", pattern: "dev-down:"}
  - grep: {file: "patient_360/Makefile", pattern: "uc_init.py"}
AC8:
  - grep: {file: "patient_360/Makefile", pattern: "ddl-apply:"}
  - grep: {file: "patient_360/Makefile", pattern: "beeline.*hive2://spark-thrift-server:10000|hive2://spark-thrift-server:10000"}
  - grep: {file: "patient_360/Makefile", pattern: "ddl/migrations/.*\\.sql|ddl/migrations"}
  - forbidden_grep: {file: "patient_360/Makefile", pattern: "liquibase", reason: "Liquibase retired — ddl-apply runs beeline over plain .sql per UPGRADE-NOTES"}
AC9:
  - manual: "Capture `docker compose ps` output (six services healthy incl. spark-thrift-server, otel-collector running) AND HTTP probes — `curl -fsS http://localhost:8081/health` (Airflow) returning 200 AND `curl -fsS http://localhost:13133/` (otel-collector, probed from host) returning 200 AND `make ddl-apply` (beeline) reporting UC tables created; paste all into the story verification log"
AC10:
  - grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "PATIENT360_PROJECT_ROOT"}
  - grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "AIRFLOW_CONFIGS_DIR|DQ_RULES_DIR|PATIENT360_WAREHOUSE_ROOT"}
AC11:
  - grep: {file: "patient_360/_infra/docker/Dockerfile.thrift", pattern: "/opt/spark/jars"}
  - grep: {file: "patient_360/_infra/docker/Dockerfile.thrift", pattern: "cp .*\\.jar .*/opt/spark/jars|/opt/spark/jars/"}
  - forbidden_grep: {file: "patient_360/_infra/docker/Dockerfile.thrift", pattern: "spark.jars.packages", reason: "runtime package resolution fails — spark user HOME=/nonexistent cannot write the ivy cache; jars MUST be build-time-resolved into /opt/spark/jars/"}
```


## How to Test (User)

### Prerequisites


- Docker Desktop installed and running

- STORY-01-001, STORY-01-005, STORY-01-006 done


### Steps


1. `cd patient_360 && make dev-up`

2. `docker compose -f _infra/docker/docker-compose.yml ps`

3. `curl -fsS http://localhost:8081/health`

4. `curl -fsS http://localhost:13133/`

5. `make dev-down`


### Expected outcome


- Six containers report `healthy` (incl. `spark-thrift-server`) and `otel-collector` reports `running`; `make ddl-apply` (beeline over `ddl/migrations/*.sql` in lexical order) completes and creates the UC tables

- Airflow `/health` returns 200; otel-collector health_check on `localhost:13133/` returns 200 (probed from host)

- `make dev-down` tears down cleanly with no dangling volumes


## Documentation Updates


- [x] Update patient_360/README.md § "Local Stack" with `make dev-up` / `make dev-down` flow and the six-service port table

User-Verified-By: Phani Vemuri 2026-05-11
