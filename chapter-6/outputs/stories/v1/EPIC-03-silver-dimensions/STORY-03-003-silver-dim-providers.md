# STORY-03-003: Implement transform_providers_silver (SCD2 dimension)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-03: Silver Dimensions (SCD Type 2) |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 5 |
| **Dependencies** | STORY-01-003, STORY-02-008 |
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

As a data engineer, I want transform the bronze `unity.bronze.synthea_providers` UC table into Silver dimension `unity.silver.reference_providers` with SCD Type 2 so that the providers dimension preserves history and Gold tables get the latest version via `is_current=TRUE`.

## Description

Implement `src/patient_360/silver/transform_providers.py` per LLD §5.2 / DMS §6. Reads the bronze table via `spark.read.table("unity.bronze.synthea_providers")` (Decision 12 & 15 re-adopted 2026-06-18 — UC is the runtime catalog), drops PHI columns per DMS §3 (LLD §5.2), applies derived fields, then calls `apply_scd2(...)` from `utils/scd2.py` which `MERGE INTO`s the `ddl/migrations/*.sql`-pre-created `unity.silver.reference_providers` UC table (`DeltaTable.forName`, not a filesystem path). PHI fields like `SSN`, `DRIVERS`, `PASSPORT` (where applicable) MUST be dropped at this Silver boundary (LLD §5.2, NFR-6). Inline SE via `se_runner.run_dq(...)`.

## Acceptance Criteria


- [ ] `transform_providers.py` reads via `spark.read.table("unity.bronze.synthea_providers")` and SCD2-`MERGE INTO`s the pre-created `unity.silver.reference_providers` UC table (Decision 12 & 15 re-adopted 2026-06-18 — UC is the runtime catalog) [LLD §5.2]

- [ ] PHI columns dropped at Silver boundary per DMS §3 / NFR-6 [DMS §3, LLD §5.2]

- [ ] `apply_scd2(...)` invoked with natural keys + hash columns from DMS §6 [DMS §6, LLD §5.2]

- [ ] Inline SE called with rules from `dq_rules/reference_providers.yml`; `action_if_failed: fail` per LLD §5.4 [LLD §5.2, §5.4; DQS §2]

- [ ] Unit tests cover hash-changed / hash-same / new-record / PHI-dropped scenarios [LLD §2.4]


## Technical Notes

- **Upstream references**: LLD §5.2, §5.4, §13 Decisions 12 & 15 (re-adopted 2026-06-18 — UC runtime catalog); DMS §3, §6; STM Tab:Bronze-to-Silver
- **Implementation hints**: Reuse `apply_scd2` from `utils/scd2.py` (STORY-01-003); it `MERGE INTO`s the named `unity.silver.reference_providers` table via `DeltaTable.forName(spark, "unity.silver.reference_providers")`. The table is pre-created by the `ddl/migrations/*.sql` migrations (`make ddl-apply`, beeline against the Spark Thrift Server); SCD2 dims have no `ds` partition per LLD §3.3.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| DMS | §3 Silver schema for providers, §6 SCD2 hash columns |

| LLD | §5.2 transform_providers_silver |

| STM | Tab:Bronze-to-Silver (providers) |

| DQS | §2 row_dq + agg_dq for providers |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Unit | transform_providers SCD2 + PHI drop | pytest patient_360/tests/silver/test_transform_providers_unit.py |

| Contract | contracts/reference_providers.yml parses | pytest patient_360/tests/test_contracts.py |



## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/silver/transform_providers.py"
  - grep: {file: "patient_360/src/patient_360/silver/transform_providers.py", pattern: "unity\\.bronze\\.synthea_providers"}
  - grep: {file: "patient_360/src/patient_360/silver/transform_providers.py", pattern: "unity\\.silver\\.reference_providers"}
AC2:
  - grep: {file: "patient_360/src/patient_360/silver/transform_providers.py", pattern: "drop.*SSN|PHI|drop_phi"}
AC3:
  - grep: {file: "patient_360/src/patient_360/silver/transform_providers.py", pattern: "apply_scd2"}
AC4:
  - grep: {file: "patient_360/src/patient_360/silver/transform_providers.py", pattern: "se_runner|run_dq"}
AC5:
  - pytest: {node: "patient_360/tests/silver/test_transform_providers_unit.py"}
```


## How to Test (User)

### Prerequisites


- STORY-01-003 done; STORY-02-008 done


### Steps


1. `cd patient_360 && uv run pytest tests/silver/test_transform_providers_unit.py -v`


### Expected outcome


- All SCD2 unit tests pass (hash-change closes existing row + inserts new)


## Documentation Updates


- [ ] N/A — internal silver dim transform module

