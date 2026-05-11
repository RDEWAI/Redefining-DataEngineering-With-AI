# STORY-01-009: SE runner — bootstrap phase (soft-import with WARNING log)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation & Infrastructure |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 2 |
| **Sprint** | 3 |
| **Dependencies** | STORY-01-002 |
| **Status** | To Do |

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

As a data engineer, I want have ingestion_runner soft-import `se_runner` while it is pending implementation so that downstream Bronze stories can ship before se_runner.py is fully built without crashing on import.

## Description

Implement the *bootstrap phase* of the SE bootstrap mode lifecycle described in LLD §8.6 + §13 Decision 14: `ingestion_runner.py` wraps `from patient_360.utils import se_runner` in `try/except ImportError` and logs `WARNING: se_runner not available` when the import fails. DataFrame passes through without DQ validation in this transitional state. This story is ordered first; STORY-01-010 supersedes the soft-import once `se_runner.py` ships.

## Acceptance Criteria


- [ ] `ingestion_runner.py` wraps `import se_runner` in `try/except ImportError` [LLD §8.6]

- [ ] On ImportError, the runner logs `WARNING: se_runner not available` and continues [LLD §8.6]

- [ ] Bootstrap mode is active **only** until STORY-01-010 ships; alert routes to Slack `#data-alerts-{env}` (WARNING) per LLD §8.5 [LLD §8.5, §8.6]


## Technical Notes

- **Upstream references**: LLD §8.6, §13 Decision 14
- **Implementation hints**: This is a TEMP measure. Do not write tests that lock in the WARNING wording — STORY-01-010 will remove it. The fail-closed steady state is owned by STORY-01-010.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §8.6 SE Bootstrap Mode, §13 Decision 14 |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Unit | soft-import path emits WARNING and proceeds | pytest patient_360/tests/bronze/test_ingestion_runner_bootstrap_unit.py |



## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/bronze/ingestion_runner.py"
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "except ImportError"}
AC2:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "se_runner not available"}
AC3:
  - pytest: {node: "patient_360/tests/bronze/test_ingestion_runner_bootstrap_unit.py"}
```


## How to Test (User)

### Prerequisites


- STORY-01-002 done


### Steps


1. `cd patient_360 && uv run pytest tests/bronze/test_ingestion_runner_bootstrap_unit.py -v`


### Expected outcome


- Test passes; log captures the WARNING message


## Documentation Updates


- [ ] N/A — internal transitional state; documentation comes with STORY-01-010

