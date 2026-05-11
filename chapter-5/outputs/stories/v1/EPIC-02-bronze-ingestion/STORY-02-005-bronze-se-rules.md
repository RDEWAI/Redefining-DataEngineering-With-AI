# STORY-02-005: Author 13 per-table Bronze SE rule YAMLs

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 4 |
| **Dependencies** | STORY-01-010 |
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

As a DQ engineer, I want have spark-expectations rule YAMLs for every Bronze table so that `se_runner.run_dq(...)` resolves rules by table-name convention and DQ runs inline per LLD §5.1.

## Description

Author 13 `dq_rules/synthea_{table}.yml` files mirroring DQS §2 row_dq + agg_dq rules and the per-rule SE schema (rule_type, rule, description, error_drop_threshold, action_if_failed). Cover DQ-FLD-001 through DQ-FLD-045 distributed by table per LLD §5.1 DQ Check column.

## Acceptance Criteria


- [ ] 13 `dq_rules/synthea_{table}.yml` files exist with SE rule schema [LLD §2.1, DQS §2]

- [ ] Each YAML has ≥1 row_dq and ≥1 agg_dq rule per DQS §2-3 [DQS §2-3]

- [ ] Critical-table YAMLs (patients, encounters, allergies, orgs, providers, payers) declare `action_if_failed: fail` for at least one CRITICAL rule [LLD §5.4]

- [ ] `se_runner` integration test loads each rules file and runs against a synthetic DataFrame [LLD §8.6.1]


## Technical Notes

- **Upstream references**: LLD §2.1, §5.1, §5.4, §8.6.1; DQS §2-3
- **Implementation hints**: Reuse the existing SE YAMLs already generated in `outputs/dqs/v2/se-rules/` as the upstream source of truth — copy and adapt to the per-table convention.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| DQS | §2 row_dq + agg_dq Bronze rules (DQ-FLD-001 to DQ-FLD-045) |

| LLD | §5.1 Bronze DQ Check column |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Contract | rule YAMLs parse + SE schema validation | pytest patient_360/tests/bronze/test_dq_rules_contract.py |

| Integration | se_runner loads + runs rules against synthetic DF | pytest -m integration patient_360/tests/bronze/test_dq_rules_se_integration.py |



## Verification

```yaml
AC1:
  - file_count: {glob: "patient_360/dq_rules/synthea_*.yml", equals: 13}
AC2:
  - grep_count: {glob: "patient_360/dq_rules/synthea_*.yml", pattern: 'rule_type:\s*row_dq', equals: 13}
AC3:
  - grep_count: {glob: "patient_360/dq_rules/synthea_*.yml", pattern: 'action_if_failed:\s*fail', equals: 6}
AC4:
  - pytest: {node: "patient_360/tests/bronze/test_dq_rules_se_integration.py", marker: "integration"}
```


## How to Test (User)

### Prerequisites


- STORY-01-010 done


### Steps


1. `cd patient_360 && ls dq_rules/synthea_*.yml | wc -l`

2. `uv run pytest tests/bronze/test_dq_rules_contract.py -v`


### Expected outcome


- 13 YAML files

- Contract tests pass


## Documentation Updates


- [ ] Update patient_360/README.md § "Data Quality" with the per-table rule YAML convention

