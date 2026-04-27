# EPIC-01: Foundation & Runtime Bootstrap

| Field | Value |
|-------|-------|
| **LLD Section** | §2.1, §6.1, §1 |
| **Epic Scope** | foundation |
| **Stories** | 6 |
| **Total Points** | 23 |
| **Sprints** | 1 |
| **Status** | To Do |

## Objective

Stand up the project scaffold (cookiecutter render → `patient_360/`), shared utilities, schema contracts, configuration loader, and the local docker-compose runtime (Airflow + Unity Catalog OSS local + Marquez/Grafana) so every downstream layer epic has a working foundation. Includes the mandatory runtime-bootstrap story that verifies JDK 17, docker stack, UC catalog/schemas, source seed, and Spark/SE end-to-end smoke per LLD §6.1 and §8.6.1.

## Scope

### In Scope
- Cookiecutter scaffold render to `patient_360/` (LLD §2.1)
- `pyproject.toml`, `Makefile`, `uv` setup (LLD §2.1)
- Cross-layer utilities under `src/patient_360/utils/` — `pipeline_config`, `logging_config`, `delta_helpers`, `metrics`, `scd2`, `derived_fields`, `code_systems` (LLD §2.3)
- Per-table StructType schema contracts (`contracts/`) seeded from DMS
- Docker compose stack: UC OSS local, Marquez, Grafana, Prometheus (LLD §1, §9.1)
- Runtime bootstrap (JDK 17, UC catalog + bronze/silver/gold schemas, Synthea source seed, SE end-to-end smoke)

### Out of Scope
- Bronze ingestion runner (EPIC-02)
- Silver/Gold transforms (EPIC-03/04/05)
- CI/CD pipeline workflows (EPIC-07)

## Stories

| ID | Title | Type | Points | Sprint | Dependencies |
|----|-------|------|--------|--------|-------------|
| STORY-01-001 | Render cookiecutter scaffold and pyproject/Makefile | build | 3 | 1 | — |
| STORY-01-002 | Implement pipeline_config loader and logging utilities | build | 3 | 1 | STORY-01-001 |
| STORY-01-003 | Generate per-table StructType schema contracts from DMS | build | 5 | 1 | STORY-01-001 |
| STORY-01-004 | Implement scd2 / derived_fields / delta_helpers utilities | build | 5 | 1 | STORY-01-002 |
| STORY-01-005 | Stand up docker-compose stack (UC OSS, Marquez, Grafana) | build | 3 | 1 | STORY-01-001 |
| STORY-01-006 | Runtime bootstrap — JDK17, UC schemas, source seed, SE smoke | runtime-bootstrap | 5 | 1 | STORY-01-005, STORY-01-002 |

## Acceptance Criteria (Epic-Level)

- [ ] `patient_360/` directory tree exists with all paths in LLD §2.1 [LLD §2.1]
- [ ] `make dev-setup` succeeds and `uv run pytest --collect-only` exits 0 [LLD §2.1]
- [ ] `docker compose -f patient_360/_infra/docker/docker-compose.yml up -d` succeeds and UC OSS `/catalogs` returns 200 [LLD §1, §9.5]
- [ ] UC catalog `unity` exists with `bronze`, `silver`, `gold` schemas [LLD §1]
- [ ] `with_expectations(...)` invoked end-to-end against ≥1 Bronze table during `make smoke-se`; `bronze_se_stats` populated [LLD §8.6.1]

## Risks & Assumptions

- Sam R. at 50% allocation — keep STORY-01-006 owned by Alex/Jordan since it blocks every layer
- Local-only architecture — no cloud-dependent setup needed [LLD Decision 12]
- Synthea source already loaded into DuckDB at chapter-2 path; bootstrap re-uses it
