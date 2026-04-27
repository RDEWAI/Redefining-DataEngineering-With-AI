# STORY-02-004: se_runner.py fail-closed implementation (post-bootstrap)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion Layer |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 2 |
| **Dependencies** | STORY-02-001 |
| **Status** | To Do |

<!--
  Phased contract supersession: This story removes the bootstrap soft-import added in STORY-02-001.
  Per scrum-master phased-contract policy, this story has explicit Depends-On to STORY-02-001 so the
  AC4 grep_absent for the bootstrap warning is interpreted as superseding STORY-02-001's grep for it.
-->

## User Story

As a Data Engineer, I want `se_runner.py` shipped fail-closed and the bootstrap soft-import removed from `ingestion_runner.py` so that DQ silently skipping is impossible — every ingestion task fails closed on missing SE.

## Description

Implement `patient_360/src/patient_360/utils/se_runner.py` exposing `run_dq(spark, df, table, env, action_if_failed_default)` that wires `WrappedDataFrameWriter(...).with_expectations(...)` against the SE rules in `dq_rules/{table}.yml`, enables `se.enable.error.table=true` and `se.enable.stats.table=true` per LLD §8.2 / §8.3, and maps `--env` (DEV/STAGING/PROD) to SE `dq_env` (DEV/QA/PROD) per §5.4. Then **remove the soft-import** from `ingestion_runner.py` so a missing `se_runner` is a hard error per LLD §8.6 fail-closed contract and Decision 16 SE-RUN-EVIDENCE.

## Acceptance Criteria

- [ ] `patient_360/src/patient_360/utils/se_runner.py` exposes `run_dq(...)` invoking `with_expectations(...)` [LLD §5.4, §8.6.1]
- [ ] `se_runner.py` enables `se.enable.error.table=true` and `se.enable.stats.table=true` [LLD §8.2, §8.3]
- [ ] `ingestion_runner.py` imports `se_runner` directly (no try/except ImportError) — fail-closed [LLD §8.6]
- [ ] `ingestion_runner.py` does **not** contain the bootstrap warning string `WARNING: se_runner not available` [LLD §8.6 — supersedes STORY-02-001 AC4]
- [ ] `BRONZE_SKIP_SE` and equivalent bypass env-vars are not referenced anywhere [LLD §8.6.1, Decision 16]
- [ ] `patient_360/tests/utils/test_se_runner_unit.py` exercises `run_dq` against a mocked SE [LLD §5.4]

## Technical Notes

- **Upstream references**: LLD §5.4 (inline SE flow), §8.2 (`_error` table), §8.3 (stats table), §8.6 (bootstrap → fail-closed transition), §8.6.1 (SE-RUN-EVIDENCE), Decision 16 (SE mandatory, no opt-out)
- **Implementation hints**: This is the fail-closed half of the phased contract opened by STORY-02-001. Once this story merges, the bootstrap warning string MUST disappear from the codebase. The `Depends-On: STORY-02-001` header marks this supersession for the validator.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §5.4, §8.2, §8.3, §8.6, §8.6.1, Decision 16 |
| DMS | — |
| STM | — |
| DQS | §2-4 SE rule sets |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | run_dq calls with_expectations and configures error+stats tables | `pytest patient_360/tests/utils/test_se_runner_unit.py` |
| Integration | end-to-end SE run lands rows in bronze_se_stats | `pytest -m integration patient_360/tests/integration/test_se_runner_integration.py` |
| Contract | ingestion_runner has no soft-import warning | `! grep "se_runner not available" patient_360/src/patient_360/bronze/ingestion_runner.py` |

## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/utils/se_runner.py"
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: 'with_expectations'}
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: 'def run_dq'}
AC2:
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: 'enable.error.table'}
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: 'enable.stats.table'}
AC3:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: 'from patient_360.utils.se_runner import|from \.\.utils\.se_runner'}
AC4:
  - manual: "grep absent — `! grep 'WARNING: se_runner not available' patient_360/src/patient_360/bronze/ingestion_runner.py`"
AC5:
  - manual: "grep absent — `! grep -r BRONZE_SKIP_SE patient_360/src patient_360/airflow`"
AC6:
  - pytest: {node: "patient_360/tests/utils/test_se_runner_unit.py"}
```

## How to Test (User)

### Prerequisites

- STORY-02-001 complete and merged
- STORY-01-006 runtime-bootstrap completed (docker stack + UC + SE smoke pass)

### Steps

1. `cd patient_360 && uv run pytest tests/utils/test_se_runner_unit.py -v`
2. `! grep "se_runner not available" patient_360/src/patient_360/bronze/ingestion_runner.py`
3. `! grep -r BRONZE_SKIP_SE patient_360/src patient_360/airflow`
4. `cd patient_360 && uv run pytest -m integration tests/integration/test_se_runner_integration.py -v`

### Expected outcome

- Step 1 unit tests pass
- Step 2 exits 0 (no match — string absent)
- Step 3 exits 0 (no bypass env-var present)
- Step 4 integration test passes; bronze_se_stats has ≥1 row for the run

## Documentation Updates

- [ ] N/A — internal utility module; the runtime-bootstrap and integration-test stories own user-facing docs
