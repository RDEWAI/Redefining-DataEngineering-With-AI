# STORY-04-008: Implement transform_claims_silver (fact)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-04: Silver Facts |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 3 |
| **Sprint** | 7 |
| **Dependencies** | STORY-04-001 |
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

As a data engineer, I want transform `unity.bronze.synthea_claims` into `clinical_claims` (or `billing_claims`) Silver fact table so that Gold tables can join the claims fact to current-version dimensions.

## Description

Implement `src/patient_360/silver/transform_claims.py` per LLD §5.2. Reads `unity.bronze.synthea_claims` (UC-managed), enriches via FK joins to Silver dims (`is_current=TRUE`), applies STM Tab:Bronze-to-Silver transforms, then `insertInto`s the Liquibase-pre-created `unity.silver.billing_claims` UC table — `df.write.mode("overwrite").insertInto("unity.silver.billing_claims")` under dynamic partition overwrite (`spark.sql.sources.partitionOverwriteMode=dynamic`; idempotent per-`ds`, NOT `replaceWhere` which `insertInto` silently ignores — re-runs would append/double) (Decision 12/15 re-adopted 2026-06-18; never `saveAsTable`/path-based `.save`) (LLD §3.3). Inline SE per `dq_rules/billing_claims.yml`. Empty-input behavior: `fail` for `encounters` and `allergies` (LLD §5.2), `write_empty` otherwise.

## Acceptance Criteria


- [ ] `transform_claims.py` reads `unity.bronze.synthea_claims` (UC-managed) [LLD §5.2]

- [ ] FK join uses `is_current = TRUE` filter on dim before broadcast (LLD §6.2) [LLD §6.2]

- [ ] Output written via `df.write.mode("overwrite").insertInto("unity.silver.billing_claims")` (pre-created UC table); idempotency via dynamic partition overwrite (`spark.sql.sources.partitionOverwriteMode=dynamic`), NOT `replaceWhere` (`insertInto` silently ignores it — re-runs would append/double); no `saveAsTable`/path-based `.save` (LLD §4.5 idempotency, Decision 12/15) [LLD §3.3, §4.5, §13 Decision 15]

- [ ] Inline SE invoked from `dq_rules/billing_claims.yml` [LLD §5.2, §5.4; DQS §2]

- [ ] Unit tests cover happy path, FK orphan rejection, and empty-input behavior [LLD §2.4]


## Technical Notes

- **Upstream references**: LLD §5.2, §5.4, §6.2; DMS §3; STM Tab:Bronze-to-Silver; DQS §2
- **Implementation hints**: Use `F.broadcast(dim_df.filter(F.col('is_current')))` for dim joins. Schema target from DMS §3.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| DMS | §3 Silver schema for claims |

| LLD | §5.2 transform_claims_silver |

| STM | Tab:Bronze-to-Silver (claims) |

| DQS | §2 row_dq + agg_dq for claims |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Unit | transform_claims happy path + edge cases | pytest patient_360/tests/silver/test_transform_claims_unit.py |



## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/silver/transform_claims.py"
  - grep: {file: "patient_360/src/patient_360/silver/transform_claims.py", pattern: "unity.bronze.synthea_claims"}
AC2:
  - grep: {file: "patient_360/src/patient_360/silver/transform_claims.py", pattern: "is_current"}
AC3:
  - grep: {file: "patient_360/src/patient_360/silver/transform_claims.py", pattern: "mode\\(['\"]overwrite['\"]\\)\\.insertInto|\\.insertInto"}
  - forbidden_grep: {file: "patient_360/src/patient_360/silver/transform_claims.py", pattern: "replaceWhere", reason: "insertInto silently ignores replaceWhere — re-runs append/double. Idempotency is dynamic partition overwrite per LLD §13 Decision 15 (re-adopted 2026-06-18)"}
  - grep: {file: "patient_360/src/patient_360/silver/transform_claims.py", pattern: "insertInto.*unity\\.silver\\.billing_claims|unity\\.silver\\.billing_claims"}
  - forbidden_grep: {file: "patient_360/src/patient_360/silver/transform_claims.py", pattern: "saveAsTable|\\.save\\(\\s*f?['\"].*warehouse", reason: "Silver facts insertInto pre-created unity.silver.<table>; no saveAsTable/path-based .save per LLD §13 Decision 12/15 (re-adopted 2026-06-18)"}
AC4:
  - grep: {file: "patient_360/src/patient_360/silver/transform_claims.py", pattern: "se_runner|run_dq"}
AC5:
  - pytest: {node: "patient_360/tests/silver/test_transform_claims_unit.py"}
```


## How to Test (User)

### Prerequisites


- Dependencies satisfied


### Steps


1. `cd patient_360 && uv run pytest tests/silver/test_transform_claims_unit.py -v`


### Expected outcome


- All unit tests pass


## Documentation Updates


- [ ] N/A — internal silver fact transform module

