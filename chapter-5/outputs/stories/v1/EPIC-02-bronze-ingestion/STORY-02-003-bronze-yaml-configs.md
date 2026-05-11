# STORY-02-003: Author 13 per-table Bronze ingestion YAML configs

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 3 |
| **Dependencies** | STORY-02-001 |
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

As a data engineer, I want have one declarative ingestion YAML per Bronze source table so that the factory can build all 13 Bronze tasks at DAG parse time without code changes.

## Description

Author 13 `airflow/configs/{table}.yml` files (one per Bronze table from LLD §5.1). Each declares `source_table` (e.g., `synthea.patients`), `schema_ref` (StructType class path), `output_table` (`unity.bronze.synthea_{table}`), `dq_rules_table` (defaults to table name; resolved to `dq_rules/{table}.yml`), `empty_input_behavior`, metadata columns, `timeout`, and `retries`. Critical tables (`patients`, `encounters`, `allergies`, `organizations`, `providers`, `payers`) override `empty_input_behavior` to `fail` per LLD §5.1; others default to `write_empty`.

## Acceptance Criteria


- [ ] 13 `airflow/configs/{table}.yml` files exist (one per LLD §5.1 Bronze task) [LLD §5.1]

- [ ] Six critical tables (`patients`, `encounters`, `allergies`, `organizations`, `providers`, `payers`) have `empty_input_behavior: fail` [LLD §5.1, DRD §1.3]

- [ ] All 13 configs declare `output_table: unity.bronze.synthea_{table}` (UC-managed write target) [LLD §13 Decision 15]

- [ ] Each YAML's `dq_rules_table` resolves to `dq_rules/{table}.yml` [LLD §2.3]


## Technical Notes

- **Upstream references**: LLD §5.1, §13 Decision 15
- **Implementation hints**: Generate via a small Jinja template + Python loop driven from the LLD §5.1 table list.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §5.1 Bronze Tasks |

| DMS | §2 Bronze schemas |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Contract | every YAML parses and references its DQ rules file | pytest patient_360/tests/bronze/test_configs_contract.py |



## Verification

```yaml
AC1:
  - file_count: {glob: "patient_360/airflow/configs/*.yml", equals: 13}
AC2:
  - grep_count: {glob: "patient_360/airflow/configs/*.yml", pattern: 'empty_input_behavior:\s*fail', equals: 6}
AC3:
  - grep_count: {glob: "patient_360/airflow/configs/*.yml", pattern: 'output_table:\s*unity.bronze', equals: 13}
AC4:
  - pytest: {node: "patient_360/tests/bronze/test_configs_contract.py"}
```


## How to Test (User)

### Prerequisites


- STORY-02-001 done


### Steps


1. `cd patient_360 && ls airflow/configs/*.yml | wc -l`

2. `uv run pytest tests/bronze/test_configs_contract.py -v`


### Expected outcome


- 13 config files listed

- Tests pass


## Documentation Updates


- [ ] Update patient_360/README.md § "Add a new Bronze table" with the YAML config schema

