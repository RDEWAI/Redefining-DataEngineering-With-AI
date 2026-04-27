# EPIC-02: Bronze Ingestion Layer

| Field | Value |
|-------|-------|
| **LLD Section** | §5.1 |
| **Epic Scope** | layer |
| **Stories** | 7 |
| **Total Points** | 31 |
| **Sprints** | 2 |
| **Status** | To Do |

<!-- Bronze layer epic — closure sequence required: build → performance-optimization → integration-test -->

## Objective

Build the config-driven Bronze ingestion framework: generic `ingestion_runner.py`, `ingestion_factory.py` (TaskGroup factory), `spark_submit_wrapper.py`, 13 per-table YAML configs (`airflow/configs/{table}.yml`), 13 per-table SE rule YAMLs (`dq_rules/{table}.yml`), inline SE validation via `se_runner.py` (fail-closed post-bootstrap per §8.6.1), `reconciliation_bronze` task, and the Bronze layer Airflow DAG fragment landing in Unity Catalog OSS local. Closes itself with perf tuning (replaceWhere + shuffle.partitions per §6.3/§6.5) and a local-DAG + UC integration test.

**Deploy Scope**: Layer-scoped — see deploy-validation? No. N/A — layer completes at integration-test; system-wide deploy handled in trailing release epic.

## Scope

### In Scope
- 13 Bronze YAML configs (one per source table) per LLD §4.2 / Decision 7
- Generic `ingestion_runner.py`, `ingestion_factory.py`, `spark_submit_wrapper.py` per LLD §2.3
- `se_runner.py` (fail-closed post-bootstrap; soft-import bootstrap variant during STORY-02-001 only) per §8.6
- `reconciliation_bronze` query_dq task per §5.5
- Bronze TaskGroup in `airflow/dags/patient360_hourly_v1.py`
- Inline SE row_dq + agg_dq + `<table>_error` table per §8.2
- Per-table `dq_rules/{table}.yml` SE rule files (13)
- Bronze perf tuning (replaceWhere + shuffle.partitions) per §6.3, §6.5
- Local DAG trigger + UC validation integration test per §2.4

### Out of Scope
- Silver/Gold transforms (EPIC-03/04/05)
- CI/CD workflows (EPIC-07)
- Schema migrations / Liquibase (EPIC-07)

## Stories

| ID | Title | Type | Points | Sprint | Dependencies |
|----|-------|------|--------|--------|-------------|
| STORY-02-001 | Bronze ingestion runner + soft-import SE (bootstrap mode) | build | 5 | 1 | STORY-01-002, STORY-01-003 |
| STORY-02-002 | TaskGroup factory and SparkSubmit wrapper | build | 5 | 1 | STORY-02-001 |
| STORY-02-003 | Generate 13 per-table Bronze YAML configs | build | 5 | 2 | STORY-02-001 |
| STORY-02-004 | se_runner.py fail-closed implementation (post-bootstrap) | build | 5 | 2 | STORY-02-001 |
| STORY-02-005 | reconciliation_bronze query_dq task with SE-evidence gate | build | 3 | 2 | STORY-02-004, STORY-02-003 |
| STORY-02-006 | Bronze perf — replaceWhere partition pruning + shuffle tuning | performance-optimization | 3 | 2 | STORY-02-005 |
| STORY-02-007 | Integration test — trigger bronze DAG on Airflow local against UC OSS local | integration-test | 5 | 2 | STORY-02-006 |

## Layer Closure Sequence

Stories below must execute in this order (enforced by dependencies):

1. **Build** → all `build` stories complete before perf starts.
2. **Performance Optimization** (LLD §6 derived):
   - STORY-02-006: Bronze perf — replaceWhere partition pruning + shuffle tuning
3. **Local Integration Testing** (trigger layer DAG on local Airflow, validate data in UC OSS local):
   - STORY-02-007: Integration test — trigger bronze DAG on Airflow local against UC OSS local
4. **Deployment Validation** (optional — only if LLD prescribes layer-scoped deploy work):
   - _N/A — layer moves to Done after integration testing; system-wide deploy in trailing release epic._

## Acceptance Criteria (Epic-Level)

- [ ] All 13 Bronze tables land in `unity.bronze.synthea_*` Delta tables on local UC OSS [LLD §5.1, Decision 15]
- [ ] Inline SE produces `bronze_se_stats` rows and `<table>_error` tables for the run [LLD §8.6.1]
- [ ] `reconciliation_bronze` fails-closed when `bronze_se_stats` has 0 rows for current `meta_dq_run_id` [LLD §8.6.1]
- [ ] Bronze TaskGroup runtime < 5 minutes on DEV [LLD §4.4]
- [ ] After STORY-02-004 ships, the soft-import warning string `WARNING: se_runner not available` is **absent** from `ingestion_runner.py` (fail-closed) [LLD §8.6]

## Risks & Assumptions

- **Phased contract**: STORY-02-001 emits the bootstrap soft-import; STORY-02-004 removes it. STORY-02-004 has `Depends-On: STORY-02-001` to mark supersession (per scrum-master phased-contract policy).
- Alex must own STORY-02-001/004 (Spark expertise) — Sam R. blocked from these.
- `BRONZE_SKIP_SE=1` and similar bypasses are explicitly forbidden [LLD Decision 16].
