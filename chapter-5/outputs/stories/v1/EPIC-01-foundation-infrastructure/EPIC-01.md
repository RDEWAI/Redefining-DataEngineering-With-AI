# EPIC-01: Foundation & Infrastructure

| Field | Value |
|-------|-------|
| **LLD Section** | §2.1, §6.1, §9.1, §8.6 |
| **Epic Scope** | foundation |
| **Stories** | 10 |
| **Total Points** | 37 |
| **Sprints** | 1-3 |
| **Status** | Done |

<!--
  Epic Scope vocabulary:
    - layer      → medallion layer epic (Bronze/Silver Dims/Silver Facts/Gold). MUST include closure sequence: performance-optimization → integration-test → (optional) deploy-validation.
    - foundation → scaffold/infra epic (no closure sequence required).
    - crosscut   → cross-layer concerns (observability, release, hardening).
-->

## Objective

Provide the project scaffold, cross-layer utilities, contracts, docker-compose stack, and SE fail-closed import contract (`se_runner.py` + diagnostic `try/except ImportError` re-raise; reconciliation runner). Every downstream epic depends on this foundation.



## Scope

### In Scope

- Cookiecutter scaffold render and pyproject/Makefile

- Cross-layer utility modules (config, logging, metrics, delta_helpers, scd2, derived_fields)

- Contract YAMLs and DQ pointer files (29 + 29)

- docker-compose local stack — split into three service-grouped stories: (1) UC OSS + unity-catalog-ui with `uc_init.py` schema bootstrap, (2) Marquez + marquez-db (postgres), (3) Airflow (locally built `Dockerfile.airflow`) + otel-collector with shared `make dev-up` / `make dev-down` Makefile targets. Every docker-compose service ships a `healthcheck:` block; each story's DoD requires `docker compose ps healthy` AND a service-specific HTTP/CLI probe captured in the verification log

- Runtime bootstrap with SE end-to-end smoke (LLD §8.6.1)

- SE runner (`se_runner.py`) + reconciliation runner (`reconciliation.py`) with a single-state fail-closed import contract; diagnostic `try/except ImportError` in `ingestion_runner.py` logs at ERROR and re-raises (LLD §8.6, §13 Decision 14)


### Out of Scope

- Per-Bronze-table ingestion code (EPIC-02)

- Layer-specific perf tuning (EPIC-02 / -03 / -04 / -05)


## Stories

| ID | Title | Type | Points | Sprint | Dependencies |
|----|-------|------|--------|--------|-------------|

| STORY-01-001 | Scaffold patient_360 project from cookiecutter template | build | 3 | 1 | None |

| STORY-01-002 | Implement cross-layer utilities (config loader, logging, metrics, delta_helpers) | build | 5 | 1 | STORY-01-001 |

| STORY-01-003 | Implement shared SCD2, derived_fields, and code_systems utilities | build | 5 | 2 | STORY-01-002 |

| STORY-01-004 | Author table contracts and DQ rule pointers for all 13+13+3 tables | build | 5 | 2 | STORY-01-001 |

| STORY-01-005 | docker-compose service block — Unity Catalog OSS + unity-catalog-ui (with uc_init.py) | build | 2 | 2 | STORY-01-001 |

| STORY-01-006 | docker-compose service block — Marquez + marquez-db (postgres) | build | 2 | 2 | STORY-01-001 |

| STORY-01-007 | docker-compose service block — Airflow (Dockerfile.airflow) + otel-collector + Makefile dev-up/dev-down | build | 3 | 2 | STORY-01-001, STORY-01-005, STORY-01-006 |

| STORY-01-008 | Bootstrap local dev runtime (JDK / Docker / UC / Spark / SE end-to-end) | runtime-bootstrap | 5 | 2 | STORY-01-005, STORY-01-006, STORY-01-007 |

| STORY-01-009 | SE runner — diagnostic ImportError try/except (log + re-raise) | build | 2 | 3 | STORY-01-002 |

| STORY-01-010 | SE runner & reconciliation modules — fail-closed implementation | build | 5 | 3 | STORY-01-002 |




## Acceptance Criteria (Epic-Level)


- [x] All 10 EPIC-01 stories Done with green tests [LLD §2.4]

- [x] `make dev-bootstrap && make smoke-se` succeeds end-to-end on a clean laptop [LLD §1, §6.1, §8.6.1]

- [x] `bronze_se_stats` populated from the smoke run; reconciliation_bronze fail-closed query verified [LLD §8.6.1]


## Risks & Assumptions


- Single-state fail-closed import contract (LLD §8.6 + §13 Decision 14): STORY-01-009 wires the diagnostic `try/except ImportError` (logs at ERROR + re-raises) and STORY-01-010 ships `se_runner.py` + `reconciliation.py`. Neither story introduces a soft-degradation path — missing-SE is a deploy error. Stories are complementary (no ordering dependency); however, STORY-01-010 unit tests assert that `ingestion_runner.py` still propagates ImportError, so both must be merged together to keep the runner consistent.

- Shared `docker-compose.yml` co-authorship: STORY-01-005, STORY-01-006, and STORY-01-007 all edit the same file; merge serially in dependency order. The full six-service stack is only validated end-to-end in STORY-01-007 (which lands `make dev-up` / `make dev-down`).

- JDK 17 / Docker Desktop dependency risks: bootstrap fails-closed if either is missing.

