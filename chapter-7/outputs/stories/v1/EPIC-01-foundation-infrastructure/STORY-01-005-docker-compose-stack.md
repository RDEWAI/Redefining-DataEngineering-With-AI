# STORY-01-005: Build docker-compose service block — Unity Catalog OSS + unity-catalog-ui (with uc_init.py)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation & Infrastructure |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 2 |
| **Sprint** | 2 |
| **Dependencies** | STORY-01-001 |
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

As a platform engineer, I want the Unity Catalog OSS service block (server + UI) defined in the shared `docker-compose.yml` with a one-shot schema bootstrap, so that every developer and CI runner can talk to the same catalog the LLD targets.

## Description

Author the `unity-catalog` and `unity-catalog-ui` service entries in `_infra/docker/docker-compose.yml` (a shared file co-authored across STORY-01-005, STORY-01-006, STORY-01-007). The `unity-catalog` service runs the **UC 0.5.0** server image. UC 0.5.0 has no published server image, so it is **built from source** with the `/root/.cache` Dockerfile cache fix (UPGRADE-NOTES §4.4 — the upstream Dockerfile copies the build cache from `$HOME/.cache` but `sbt` running as root caches under `/root/.cache`, causing a `NoClassDefFoundError: io/vertx/core/Verticle` at startup), then published to a container registry and pulled here. The `unity-catalog-ui` service **builds from source** per LLD §9.1.1 (upstream reality: no versioned `-ui` image is published to Docker Hub; only `main` rolling tags exist). Clone `github.com/unitycatalog/unitycatalog` at tag `v0.5.0` into `_infra/docker/uc-source/` and declare `build: { context: _infra/docker/uc-source/ui/, dockerfile: Dockerfile }` for the UI service. Mount a shared `_delta_log` volume between the `unity-catalog`, `spark-thrift-server`, and Airflow/Spark containers so coordinated commits on SE's MANAGED audit tables work (UPGRADE-NOTES §4.5, §7). Map the UI port `3000:3000` (upstream default). Provide `scripts/uc_init.py` that creates UC catalog `unity` and schemas `bronze` / `silver` / `gold`, idempotent on re-run, invoked once after the UC server reports healthy. Each schema is created with a **top-level `storage_root` managed location** (sent as a top-level field, NOT nested under `properties` — UPGRADE-NOTES §4.5) so that on UC 0.5.0 the spark-expectations MANAGED `_stats`/`_error` audit tables can be created with coordinated commits against a shared `_delta_log` volume. Add a `healthcheck:` block to each service so `docker compose ps` reports `healthy`. The combined `make dev-up` / `make dev-down` Makefile targets land in STORY-01-007.

## Acceptance Criteria


- [ ] `_infra/docker/docker-compose.yml` declares `unity-catalog` (UC **0.5.0** server image — built from source with the `/root/.cache` Dockerfile fix per UPGRADE-NOTES §4.4, published to a registry and pulled here) and `unity-catalog-ui` (`build:` context `_infra/docker/uc-source/ui/`) per LLD §9.1.1; `_infra/docker/uc-source/` is a clone of `unitycatalog/unitycatalog` at tag `v0.5.0`. The `unity-catalog` service mounts a shared `_delta_log` volume with the Spark/Thrift containers for coordinated commits on SE's MANAGED audit tables [LLD §9.1.1; UPGRADE-NOTES §2, §4.4, §7]

- [x] Both UC services declare a `healthcheck:` block such that `docker compose ps` reports `healthy` within 60s of start [LLD §9.1.1]

- [ ] `scripts/uc_init.py` creates UC catalog `unity` and schemas `bronze` / `silver` / `gold` (idempotent on re-run), each schema created with a **top-level `storage_root` managed location** (sent as a top-level field in the create-schema request, NOT nested under `properties`) so UC 0.5.0 can host SE's MANAGED `_stats`/`_error` audit tables with coordinated commits [LLD §1; UPGRADE-NOTES §4.5, §7]

- [x] **Definition of Done** evidence captured in the Verification block: (a) `docker compose ps` output showing `unity-catalog` and `unity-catalog-ui` both `healthy`, AND (b) HTTP probe `curl -fsS http://localhost:8080/api/2.1/unity-catalog/catalogs` returns 200 with `unity` listed [LLD §1, §9.1.1]


## Technical Notes

- **Upstream references**: LLD §1, §9.1, §9.1.1
- **Implementation hints**: `docker-compose.yml` is the shared file across the three split stories — author only the UC service blocks here. Use the official `healthcheck:` Docker syntax with a curl/wget probe against `:8080/api/2.1/unity-catalog/catalogs`. Keep `uc_init.py` invocation outside compose (called from `make dev-up` in STORY-01-007 after wait-for-healthy).
- **Upstream-reality note**: UC 0.5.0 has no published server OR UI image. Build both from source against the cloned tree at tag `v0.5.0`, applying the `/root/.cache` Dockerfile cache fix for the server (UPGRADE-NOTES §4.4) and publishing the server image to a registry. Mirror the upstream `compose.yaml` pattern (`github.com/unitycatalog/unitycatalog/compose.yaml`). Recommended clone command in your Makefile or scaffold step: `git clone --depth 1 --branch v0.5.0 https://github.com/unitycatalog/unitycatalog _infra/docker/uc-source/` (skip if directory exists). Port maps 3000:3000 (not 3001) to match upstream default. **Why 0.5.0:** UC 0.4.0 could not create SE's MANAGED `_error`/`_stats` audit tables (empty-namespace `fullTableNameForApi` AIOOBE on bare names + no managed-location support); 0.5.0 fixes name qualification and supports `catalogManaged` tables with coordinated commits (UPGRADE-NOTES §1.1–§1.2).

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §1, §9.1, §9.1.1 |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Smoke | UC catalog/schemas exist after uc_init | pytest patient_360/tests/bootstrap/test_uc_health.py |



## Verification

```yaml
AC1:
  - file_exists: "patient_360/_infra/docker/docker-compose.yml"
  - grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "unitycatalog.*0\\.5\\.0|:v0\\.5\\.0"}
  - grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "build:\\s*$|context:\\s*.*uc-source/ui"}
  - grep: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "_delta_log"}
  - file_exists: "patient_360/_infra/docker/uc-source/ui/Dockerfile"
AC2:
  - grep_count: {file: "patient_360/_infra/docker/docker-compose.yml", pattern: "healthcheck:", at_least: 2}
  - manual: "docker compose ps shows unity-catalog and unity-catalog-ui both 'healthy'"
AC3:
  - file_exists: "patient_360/scripts/uc_init.py"
  - grep: {file: "patient_360/scripts/uc_init.py", pattern: "bronze.*silver.*gold|create_schema"}
  - grep: {file: "patient_360/scripts/uc_init.py", pattern: "storage_root"}
AC4:
  - manual: "Capture `docker compose ps` output (both services healthy) AND `curl -fsS http://localhost:8080/api/2.1/unity-catalog/catalogs` returning 200 with `unity` listed; paste both into the story verification log"
```


## How to Test (User)

### Prerequisites


- Docker Desktop installed and running

- STORY-01-001 done


### Steps


1. One-time: `git clone --depth 1 --branch v0.5.0 https://github.com/unitycatalog/unitycatalog patient_360/_infra/docker/uc-source/` (skip if dir exists)

2. `cd patient_360 && docker compose -f _infra/docker/docker-compose.yml up -d --build unity-catalog unity-catalog-ui` (first run builds the UI image; subsequent runs reuse it)

2. `docker compose -f _infra/docker/docker-compose.yml ps`

3. `python scripts/uc_init.py`

4. `curl -fsS http://localhost:8080/api/2.1/unity-catalog/catalogs`


### Expected outcome


- Both `unity-catalog` and `unity-catalog-ui` containers report `healthy` in `docker compose ps`

- `uc_init.py` exits 0 and creates `unity` catalog with `bronze` / `silver` / `gold` schemas

- `curl` returns HTTP 200 listing the `unity` catalog


## Documentation Updates


- [x] Update patient_360/README.md § "Local Stack — Unity Catalog" with service ports and `uc_init.py` flow

User-Verified-By: Phani Vemuri 2026-05-11
