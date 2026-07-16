# STORY-01-004: Author table contracts and DQ rule pointers for all 13+13+3 tables

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation & Infrastructure |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 2 |
| **Dependencies** | STORY-01-001 |
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

As a data engineer, I want have one `contracts/{table}.yml`, `contracts/dq/{table}.yml`, and `dq_rules/{table}.yml` per table so that ingestion runner, SE runner, and the `.sql` DDL migrations all resolve their inputs by table-name convention.

## Description

Author 13 Bronze + 13 Silver + 3 Gold table contract files declaring `layer`, `schema`, owner, `ddl_path`, `dq_path`, plus 13 Silver + 3 Gold DQ rule YAMLs (Bronze rules ship with STORY-02-005). Each `contracts/dq/{table}.yml` carries `completeness_min`, `validity_min`, `freshness_max_hours` thresholds for reconciliation tasks per LLD §5.5.

## Acceptance Criteria


- [x] 29 `contracts/{table}.yml` files (13 Bronze + 13 Silver + 3 Gold) exist with `ddl_path` + `dq_path` pointers [LLD §2.1, §2.3]

- [x] 29 `contracts/dq/{table}.yml` pointer files declare `completeness_min` / `validity_min` / `freshness_max_hours` [LLD §5.5]

- [x] Per-table contracts cite their DMS schema section (Bronze: DMS §2; Silver: DMS §3; Gold: DMS §4) [DMS §2-4]

- [x] Contract test `tests/test_contracts.py` parses every contract and resolves `ddl_path`+`dq_path` [LLD §2.4]


## Technical Notes

- **Upstream references**: LLD §2.1, §2.3, §5.5; DMS §2-4
- **Implementation hints**: Author by Bronze/Silver/Gold layer; reuse a Jinja template for the contract skeleton.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| DMS | §2 Bronze, §3 Silver, §4 Gold schemas |

| LLD | §2.1 Project Structure, §5.5 Reconciliation |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Contract | every contract parses + DQ pointer resolves | pytest patient_360/tests/test_contracts.py |



## Verification

```yaml
AC1:
  - file_count: {glob: "patient_360/contracts/*.yml", equals: 29}
AC2:
  - file_count: {glob: "patient_360/contracts/dq/*.yml", equals: 29}
AC3:
  - grep_count: {glob: "patient_360/contracts/*.yml", pattern: "dms_section:", equals: 29}
AC4:
  - pytest: {node: "patient_360/tests/test_contracts.py"}
```


## How to Test (User)

### Prerequisites


- STORY-01-001 done


### Steps


1. `cd patient_360 && ls contracts/*.yml | wc -l`

2. `uv run pytest tests/test_contracts.py -v`


### Expected outcome


- 29 contract files listed

- Contract tests pass


## Documentation Updates


- [x] N/A — internal-only metadata files

