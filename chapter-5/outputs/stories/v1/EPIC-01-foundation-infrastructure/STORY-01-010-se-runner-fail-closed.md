# STORY-01-010: SE runner & reconciliation modules — fail-closed implementation

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation & Infrastructure |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 3 |
| **Dependencies** | STORY-01-002 |
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

As a data engineer, I want a shipped `se_runner.py` and `reconciliation.py` so that bronze ingestion enforces inline DQ on every load and reconciliation can verify SE run-evidence — making the single-state fail-closed import contract operationally real (LLD §8.6 + §13 Decision 14).

## Description

Implement `src/patient_360/utils/se_runner.py` (LLD §2.3) wrapping `WrappedDataFrameWriter(...).with_expectations(...)` with `se.enable.error.table=true` and `se.enable.stats.table=true` per LLD §8.2-§8.3. Map `--env` to SE `dq_env` (DEV→DEV, STAGING→QA, PROD→PROD). Also implement `src/patient_360/utils/reconciliation.py` per LLD §2.3 / §5.5 with the SE-RUN-EVIDENCE query from §8.6.1. The diagnostic `try/except ImportError` wrapper in `ingestion_runner.py` (STORY-01-009) stays in place — it is part of the single-state fail-closed contract per LLD §8.6 + §13 Decision 14 (Resolved 2026-05-11). This story verifies that with `se_runner.py` present the import succeeds and `run_dq` runs inline, and that with `se_runner` removed the runner still re-raises ImportError (fail-closed).

## Acceptance Criteria


- [x] `se_runner.py` exists and exposes `run_dq(df, table, env, action_if_failed, dq_rules_dir)` [LLD §2.3]

- [x] `run_dq` calls `WrappedDataFrameWriter(...).with_expectations(...)` with `se.enable.error.table=true` and `se.enable.stats.table=true` [LLD §8.2, §8.3]

- [x] `run_dq` maps `env=DEV→dq_env=DEV`, `STAGING→QA`, `PROD→PROD` [LLD §2.3, §5.4]

- [x] `ingestion_runner.py` contains exactly one `try / except ImportError` around the `se_runner` import that logs at ERROR (`se_runner not available — fail-closed; deployment is broken: <error>`) and re-raises — and does NOT contain any `WARNING`-level soft-degradation branch [LLD §8.6]

- [x] With `se_runner` removed from the module path, ingestion fails closed: unit test asserts ImportError propagates out of `ingestion_runner.py` [LLD §8.6, §13 Decision 14]

- [x] `reconciliation.py` queries `bronze_se_stats` for `meta_dq_run_id == run_id` and fails-closed when count = 0 [LLD §8.6.1, §5.5]


## Technical Notes

- **Upstream references**: LLD §2.3, §5.4, §5.5, §8.2, §8.3, §8.6, §8.6.1, §13 Decision 14
- **Implementation hints**: Use `spark-expectations>=2.10`. Pass `target_and_error_table_writer` configured for Delta+Snappy. The diagnostic `try/except ImportError` block in `ingestion_runner.py` (STORY-01-009) MUST stay in place; verify it logs at ERROR and re-raises — no `WARNING`-level branch.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §2.3, §5.4, §5.5, §8.2-§8.6.1, §13 Decision 14 |

| DQS | §2-4 SE rules |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Unit | se_runner contract + dq_env mapping | pytest patient_360/tests/utils/test_se_runner_unit.py |

| Unit | ingestion_runner without soft-import fails-closed on missing SE | pytest patient_360/tests/bronze/test_ingestion_runner_failclosed_unit.py |

| Integration | SE run-evidence reconciliation query passes for populated stats | pytest -m integration patient_360/tests/utils/test_reconciliation_integration.py |



## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/utils/se_runner.py"
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "def run_dq"}
AC2:
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "with_expectations"}
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "enable.error.table"}
AC3:
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "STAGING.*QA|dq_env"}
AC4:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "except ImportError"}
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "se_runner not available"}
  - grep_absent: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "WARNING.*se_runner"}
AC5:
  - pytest: {node: "patient_360/tests/bronze/test_ingestion_runner_failclosed_unit.py"}
AC6:
  - file_exists: "patient_360/src/patient_360/utils/reconciliation.py"
  - grep: {file: "patient_360/src/patient_360/utils/reconciliation.py", pattern: "bronze_se_stats|meta_dq_run_id"}
```


## How to Test (User)

### Prerequisites


- STORY-01-002 done — cross-layer utilities (config, logging) in place

- STORY-01-006 done — local stack up and SE smoke green


### Steps


1. `cd patient_360 && uv run pytest tests/utils/test_se_runner_unit.py tests/bronze/test_ingestion_runner_failclosed_unit.py -v`

2. `uv run pytest -m integration tests/utils/test_reconciliation_integration.py -v`

3. `grep -E 'except ImportError|se_runner not available' src/patient_360/bronze/ingestion_runner.py` — confirms diagnostic try/except is in place

4. `grep -E 'WARNING.*se_runner' src/patient_360/bronze/ingestion_runner.py && echo 'FAIL: soft-degradation branch present' || echo 'fail-closed contract: OK'`


### Expected outcome


- All unit and integration tests pass

- Step 3 prints both `except ImportError` and `se_runner not available` lines

- Step 4 prints `fail-closed contract: OK`


## Documentation Updates


- [x] Update patient_360/README.md § "Data Quality" with the fail-closed SE behavior and the SE run-evidence gate

- [x] Update patient_360/docs/runbooks/bootstrap.md to document the single-state fail-closed import contract (no soft-degradation path; missing-SE is a deploy error)

