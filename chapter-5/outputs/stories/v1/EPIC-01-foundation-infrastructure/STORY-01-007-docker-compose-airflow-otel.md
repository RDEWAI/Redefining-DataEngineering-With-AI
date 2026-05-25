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

Author the `airflow` and `otel-collector` service entries in `_infra/docker/docker-compose.yml` (the shared file is now complete after this story). Author `_infra/docker/Dockerfile.airflow` that bundles Airflow 3.2.1, Spark 4.0.0 (`local[2]` executor), JDK 17, and `spark-expectations>=2.10` per LLD §6.1. Pin `otel/opentelemetry-collector-contrib:0.107.0` per LLD §9.1.1. Wire `airflow` `depends_on:` UC OSS and Marquez with `condition: service_healthy`, and otel-collector with `condition: service_started`. **Do NOT add a `healthcheck:` block to `otel-collector`** — the `otel/opentelemetry-collector-contrib` image is distroless (no `/bin/sh`, no `wget`, no `curl`), so any in-container probe will fail with `exec: "/bin/sh": stat /bin/sh: no such file or directory`. The collector's own `health_check` extension on `:13133` is reachable from the host for verification. Add the `dev-up` / `dev-down` targets to the project `Makefile` — `dev-up` brings the full stack up, waits for all healthcheck-bearing services healthy, and runs `scripts/uc_init.py` once.

## Acceptance Criteria


- [x] `_infra/docker/Dockerfile.airflow` installs JDK 17, Spark 4.0.0, Airflow 3.2.1, and `spark-expectations>=2.10` per LLD §6.1 [LLD §6.1]

- [x] `_infra/docker/docker-compose.yml` declares `airflow` (built from `Dockerfile.airflow`) and `otel-collector` (`otel/opentelemetry-collector-contrib:0.107.0`) per LLD §9.1.1 [LLD §9.1.1]

- [x] `airflow` declares `depends_on:` `unity-catalog` and `marquez` with `condition: service_healthy`, and `otel-collector` with `condition: service_started` (otel image is distroless — see Description) [LLD §9.1.1]

- [x] `airflow` declares a `healthcheck:` block such that `docker compose ps` reports it `healthy` within 120s of start. `otel-collector` MUST NOT declare a `healthcheck:`; verify it via `curl localhost:13133/` from the host [LLD §9.1.1]

- [x] `make dev-up` brings the full six-service stack up, waits for healthy, runs `scripts/uc_init.py`, and exits 0; `make dev-down` tears it down cleanly [LLD §9.3]

- [x] **Definition of Done** evidence captured in the Verification block: (a) `docker compose ps` output showing the five healthcheck-bearing services (`unity-catalog`, `unity-catalog-ui`, `marquez-db`, `marquez`, `airflow`) `healthy` and `otel-collector` `running`, AND (b) HTTP probe `curl -fsS http://localhost:8081/health` (Airflow webserver) returning 200 AND `curl -fsS http://localhost:13133/` (otel-collector health_check extension, probed from host) returning 200 [LLD §6.1, §9.1.1]

- [ ] The `airflow` service block exports `PATIENT360_PROJECT_ROOT` (and the derived `AIRFLOW_CONFIGS_DIR`, `DQ_RULES_DIR`, `PATIENT360_WAREHOUSE_ROOT`) so every Airflow task resolves paths against the project root rather than CWD (LLD §9.1 — 2026-05-12 pivot) [LLD §9.1]

- [ ] `Dockerfile.airflow` contains a `USER root` block AFTER the JDK install but BEFORE the `USER airflow` pip install that runs `RUN mkdir -p /opt/patient_360/warehouse && chown -R airflow:root /opt/patient_360 && chmod 775 /opt/patient_360`. Without this, the airflow user cannot create `${PATIENT360_PROJECT_ROOT}/warehouse/{env}/` at runtime — Docker auto-creates bind-mount-point parents as root, so the project-root dir is unwritable by uid 50000. Reproduced 2026-05-22: Derby fails with `Failed to create database '/opt/patient_360/warehouse/dev/metastore_db'`. See LLD-DEVIATIONS row 7. [LLD §9.1]


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
  - grep_count: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "condition: service_healthy", at_least: 2}
  - grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "condition: service_started"}
AC4:
  - grep_count: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "healthcheck:", equals: 5}
  - forbidden_grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "otel-collector:[\\s\\S]{0,400}healthcheck:", reason: "otel-collector image is distroless; in-container healthcheck cannot succeed"}
  - manual: "docker compose ps shows airflow 'healthy' and otel-collector 'running'; curl localhost:13133/ from host returns 200"
AC5:
  - grep: {file: "patient_360/Makefile", pattern: "dev-up:"}
  - grep: {file: "patient_360/Makefile", pattern: "dev-down:"}
  - grep: {file: "patient_360/Makefile", pattern: "uc_init.py"}
AC6:
  - manual: "Capture `docker compose ps` output (five services healthy, otel-collector running) AND HTTP probes — `curl -fsS http://localhost:8081/health` (Airflow) returning 200 AND `curl -fsS http://localhost:13133/` (otel-collector, probed from host) returning 200; paste all into the story verification log"
AC7:
  - grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "PATIENT360_PROJECT_ROOT"}
  - grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "AIRFLOW_CONFIGS_DIR|DQ_RULES_DIR|PATIENT360_WAREHOUSE_ROOT"}
AC8:
  - grep: {file: "patient_360/_infra/docker/Dockerfile.airflow", pattern: "chown -R airflow:root /opt/patient_360"}
  - grep: {file: "patient_360/_infra/docker/Dockerfile.airflow", pattern: "mkdir -p /opt/patient_360/warehouse"}
  - grep: {file: "patient_360/_infra/docker/Dockerfile.airflow", pattern: "chmod 775 /opt/patient_360"}
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


- Five containers report `healthy` and `otel-collector` reports `running` in `docker compose ps`

- Airflow `/health` returns 200; otel-collector health_check on `localhost:13133/` returns 200 (probed from host)

- `make dev-down` tears down cleanly with no dangling volumes


## Documentation Updates


- [x] Update patient_360/README.md § "Local Stack" with `make dev-up` / `make dev-down` flow and the six-service port table

User-Verified-By: Phani Vemuri 2026-05-11
