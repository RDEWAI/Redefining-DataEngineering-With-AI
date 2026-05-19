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


## Technical Notes

- **Upstream references**: LLD §1, §6.1, §8.6, §8.6.1, §9.1
- **Implementation hints**: `make dev-bootstrap` = `dev-up && wait-for-uc && uc-init && seed && smoke-spark && smoke-se`. The SE smoke test must write to a temp Delta table and assert the SE stats table populated.

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
