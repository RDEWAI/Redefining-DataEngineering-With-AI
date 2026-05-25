# STORY-08-001: Security & PHI audit (NFR-6 masking, NFR-7 audit trail)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-08: Hardening |
| **Story Type** | hardening |
| **Priority** | P1 |
| **Story Points** | 3 |
| **Sprint** | 11 |
| **Dependencies** | STORY-07-004 |
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

As a data engineer, I want audit the pipeline against NFR-6 (PHI masking at Silver) and NFR-7 (HIPAA audit trail via OpenLineage) so that we have evidence of PHI handling and lineage capture for HIPAA compliance.

## Description

Inspect Silver outputs and confirm `SSN`, `DRIVERS`, `PASSPORT` columns dropped per DMS §3 / LLD §5.2. Verify Marquez has job-level lineage events for every DAG run (NFR-7). Author `docs/security/phi-audit-2026.md` summarizing findings.

## Acceptance Criteria


- [ ] Silver outputs contain no PHI columns (SSN, DRIVERS, PASSPORT) [DMS §3, LLD §5.2]

- [ ] Marquez has lineage events for every recent DAG run (NFR-7 audit trail) [LLD §10, NFR-7]

- [ ] `docs/security/phi-audit-2026.md` published [DRD §7]


## Technical Notes

- **Upstream references**: DMS §3, LLD §5.2, §10; DRD §7
- **Implementation hints**: Use `DESCRIBE TABLE` against UC OSS for column lists.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| DMS | §3 Silver schemas |

| LLD | §5.2 PHI drop, §10 Lineage |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Integration | Silver column inspection | pytest -m integration patient_360/tests/security/test_phi_audit.py |



## Verification

```yaml
AC1:
  - pytest: {node: "patient_360/tests/security/test_phi_audit.py::test_no_phi_in_silver", marker: "integration"}
AC2:
  - manual: "Marquez UI — confirm lineage events for last 7 days"
AC3:
  - file_exists: "patient_360/docs/security/phi-audit-2026.md"
```


## How to Test (User)

### Prerequisites


- STORY-07-004 done


### Steps


1. `cd patient_360 && uv run pytest -m integration tests/security/test_phi_audit.py -v`


### Expected outcome


- All Silver tables verified PHI-free


## Documentation Updates


- [ ] Add patient_360/docs/security/phi-audit-2026.md

