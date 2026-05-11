# STORY-01-009: SE runner — diagnostic import (try/except + re-raise)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation & Infrastructure |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 2 |
| **Sprint** | 3 |
| **Dependencies** | STORY-01-002 |
| **Status** | Done |

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

As a data engineer, I want `ingestion_runner.py` to catch any ImportError on `se_runner` and emit a clear diagnostic log line before re-raising, so that a missing or broken Spark Expectations install produces a readable operator signal in addition to the stack trace, while preserving fail-closed semantics.

## Description

Implement the diagnostic import pattern from LLD §8.6 + §13 Decision 14 (Resolved 2026-05-11): `ingestion_runner.py` wraps `from patient_360.utils import se_runner` in `try / except ImportError`, logs `se_runner not available — fail-closed; deployment is broken: <error>` at ERROR level, and **re-raises** the ImportError. There is no soft-degradation path — the try/except exists purely to surface a human-readable diagnostic line before the stack trace. Missing-SE is a deploy error, not a runtime condition; STORY-01-010 ships `se_runner.py` + `reconciliation.py` so the import succeeds under normal conditions.

## Acceptance Criteria


- [x] `ingestion_runner.py` wraps `from patient_360.utils import se_runner` in `try / except ImportError` [LLD §8.6]

- [x] On ImportError, the runner logs `se_runner not available` at ERROR level **and re-raises** (fail-closed; pipeline aborts) [LLD §8.6, STORY-01-010 AC5]

- [x] Missing-SE ImportError routes to PagerDuty `p360-critical` (CRITICAL) per LLD §8.5 — alert wiring exercised via the alerting framework, not new code in `ingestion_runner.py` [LLD §8.5, §8.6]


## Technical Notes

- **Upstream references**: LLD §8.6, §13 Decision 14
- **Implementation hints**: The try/except exists for diagnostics only — it MUST re-raise so STORY-01-010's fail-closed contract holds. Test that the log line is emitted AND that ImportError still propagates out of the module.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §8.6 SE Bootstrap Mode, §13 Decision 14 |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Unit | ImportError on `se_runner` emits ERROR-level diagnostic AND re-raises (fail-closed preserved) | pytest patient_360/tests/bronze/test_ingestion_runner_failclosed_unit.py |



## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/bronze/ingestion_runner.py"
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "except ImportError"}
AC2:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "se_runner not available"}
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: "raise"}
AC3:
  - manual: "CRITICAL alert routing to PagerDuty p360-critical for missing-SE verified at runtime via LLD §8.5 alerting wiring"
```


## How to Test (User)

### Prerequisites


- STORY-01-002 done


### Steps


1. `cd patient_360 && uv run pytest tests/bronze/test_ingestion_runner_failclosed_unit.py -v`


### Expected outcome


- Test passes: log captures the ERROR-level `se_runner not available — fail-closed; deployment is broken: ...` line AND the ImportError still propagates out of the runner


## Documentation Updates


- [x] N/A — diagnostic-only wrapper; user-facing fail-closed documentation lands with STORY-01-010 (README "Data Quality" section, bootstrap runbook)


User-Verified-By: Phani Vemuri 2026-05-11
