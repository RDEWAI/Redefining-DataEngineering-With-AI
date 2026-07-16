# STORY-05-004: Performance: cache shared Silver inputs + broadcast small dims for Gold builds

| Field | Value |
|-------|-------|
| **Epic** | EPIC-05: Gold Consumer Tables |
| **Story Type** | performance-optimization |
| **Priority** | P2 |
| **Story Points** | 2 |
| **Sprint** | 8 |
| **Dependencies** | STORY-05-001, STORY-05-002, STORY-05-003 |
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

As a data engineer, I want apply LLD §6.4 caching strategy and §6.2 broadcast hints to all 3 Gold builders so that `clinical_patients` and `clinical_encounters` are read once per DAG run, not three times.

## Description

Cache `clinical_patients (is_current=TRUE)` (~5,767 rows) and `clinical_encounters` (~340K rows) across the 3 Gold tasks per LLD §6.4. Use F.broadcast() on `reference_payers` (10 rows) for billing_summary.

## Acceptance Criteria


- [ ] `clinical_patients` and `clinical_encounters` cached once per DAG run per LLD §6.4 [LLD §6.4]

- [ ] `reference_payers` broadcast in build_billing_summary [LLD §6.2, §6.4]

- [ ] Benchmark: 3 Gold tasks parallel runtime <= 6 min on DEV [LLD §4.4]


## Technical Notes

- **Upstream references**: LLD §4.4, §6.2, §6.4
- **Implementation hints**: Use `df.persist(StorageLevel.MEMORY_AND_DISK)` and lift caching above the gold builders to a shared loader.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §6.2, §6.4 |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Benchmark | 3 gold tasks parallel runtime | pytest -m benchmark patient_360/tests/gold/test_gold_perf.py |



## Verification

```yaml
AC1:
  - grep_count: {glob: "patient_360/src/patient_360/gold/build_*.py", pattern: 'persist|cache\(', equals: 3}
AC2:
  - grep: {file: "patient_360/src/patient_360/gold/build_patient_billing_summary.py", pattern: "broadcast"}
AC3:
  - pytest: {node: "patient_360/tests/gold/test_gold_perf.py", marker: "benchmark"}
```


## How to Test (User)

### Prerequisites


- STORY-05-001, STORY-05-002, STORY-05-003 done


### Steps


1. `cd patient_360 && uv run pytest -m benchmark tests/gold/test_gold_perf.py -v`


### Expected outcome


- Benchmark under 6 min


## Documentation Updates


- [ ] N/A — internal tuning

