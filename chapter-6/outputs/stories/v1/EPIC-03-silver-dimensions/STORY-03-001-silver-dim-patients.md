# STORY-03-001: Implement transform_patients_silver (SCD2 dimension)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-03: Silver Dimensions (SCD Type 2) |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 5 |
| **Dependencies** | STORY-01-003 |
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

As a data engineer, I want transform `unity.bronze.synthea_patients` into Silver dimension `clinical_patients` with SCD Type 2 so that the patients dimension preserves history and Gold tables get the latest version via `is_current=TRUE`.

## Description

Implement `src/patient_360/silver/transform_patients.py` per LLD §5.2 / DMS §6. Reads `unity.bronze.synthea_patients` (UC-managed), drops PHI columns per DMS §3 (LLD §5.2), applies derived fields, then calls `apply_scd2(...)` from `utils/scd2.py`. PHI fields like `SSN`, `DRIVERS`, `PASSPORT` (where applicable) MUST be dropped at this Silver boundary (LLD §5.2, NFR-6). Output table: `clinical_patients` for patients, `reference_patients` otherwise. Inline SE via `se_runner.run_dq(...)`.

## Acceptance Criteria


- [ ] `src/patient_360/silver/transform_patients.py` reads `unity.bronze.synthea_patients` (UC-managed; LLD §13 Decision 15) [LLD §5.2, §13]

- [ ] PHI columns dropped at Silver boundary per DMS §3 / NFR-6 [DMS §3, LLD §5.2]

- [ ] `apply_scd2(...)` invoked with natural keys + hash columns from DMS §6 [DMS §6, LLD §5.2]

- [ ] Inline SE called with rules from `dq_rules/clinical_patients.yml`; `action_if_failed: fail` per LLD §5.4 [LLD §5.2, §5.4; DQS §2]

- [ ] Unit tests cover hash-changed / hash-same / new-record / PHI-dropped scenarios [LLD §2.4]

- [ ] `_bronze_path()` and `_silver_target_path()` (or equivalent path helpers) in `src/patient_360/silver/transform_patients.py` MUST emit ABSOLUTE paths anchored on `PATIENT360_PROJECT_ROOT` (e.g. `f'{os.environ.get("PATIENT360_PROJECT_ROOT", ".")}/warehouse/{env}/bronze/...'`). NEVER return a bare relative path — Airflow spark-submit CWD (/opt/airflow) is unpredictable and will 404. Enforces LLD v1.15 §9.1. [LLD §9.1; LLD-DEVIATIONS row 9]

- [ ] `transform_patients.transform()` MUST NOT pass `dq_rules_dir` as a relative-path kwarg to `run_dq()` — either pass an absolute path resolved against `PATIENT360_PROJECT_ROOT`, or (preferred) OMIT the kwarg entirely so `se_runner._resolve_dq_rules_dir()` falls back to the `DQ_RULES_DIR` env var which docker-compose anchors at `/opt/patient_360/dq_rules`. See LLD-DEVIATIONS row 9. [LLD §5.2, §9.1; LLD-DEVIATIONS row 9]

- [ ] `src/patient_360/silver/transform_patients.py` MUST NOT call `CREATE TABLE`, `CREATE SCHEMA`, or any catalog-level DDL. Only path-based `.save(<absolute_path>)` writes via DeltaCatalog. Table visibility in UC is established at deploy time by `make bootstrap-uc` (per LLD v1.16 §13 Decision 17), not at runtime. [LLD v1.16 §13 Decision 17; LLD-DEVIATIONS row 10 (forward ref)]

- [ ] `src/patient_360/utils/scd2.py::apply_scd2` MUST NOT call `CREATE TABLE`. The `target_table` keyword argument is REMOVED from the signature per LLD v1.16 §2.3. First-run cold-warehouse handling stays — but uses `.format("delta").mode("overwrite").save(target_path)` only. MERGE statements use ``delta.`<target_path>` `` syntax (path-based) instead of fully-qualified table names. [LLD v1.16 §2.3, §13 Decision 17; LLD-DEVIATIONS row 10 (forward ref)]

- [ ] Unit test in `tests/silver/test_transform_patients.py` greps the implementation files and FAILS if the strings `CREATE TABLE`, `CREATE SCHEMA`, or `saveAsTable(` appear anywhere in `transform_patients.py` or `scd2.py`. Lock-in test that prevents regression of the direct-edits. [LLD v1.16 §13 Decision 17; LLD-DEVIATIONS row 10 (forward ref)]

- [ ] `src/patient_360/silver/transform_patients.py` MUST dedupe its source DataFrame to exactly one row per natural key (`patient_id`) BEFORE invoking `apply_scd2`. Recommended pattern: `row_number() OVER (PARTITION BY patient_id ORDER BY <ordering_column> DESC) == 1`, keeping the latest per-patient snapshot. The ordering column SHOULD be the bronze partition column `ds` (ISO date string, lexicographic ordering matches chronological), falling back to `_ingested_at` if `ds` is missing. Without this, MERGE INTO fails with `DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE` once the silver Delta exists (bronze accumulates one snapshot per `ds` partition; same patient appears N times across N partition days). Caller-deduplicates-before-MERGE is the apply_scd2 contract per DMS §6 and LLD v1.18 §2.3. [DMS §6; LLD v1.18 §2.3]


## Technical Notes

- **Upstream references**: LLD §2.3, §5.2, §5.4, §13 Decision 17 (v1.16); DMS §3, §6; STM Tab:Bronze-to-Silver
- **Implementation hints**: Reuse `apply_scd2` from `utils/scd2.py` (STORY-01-003). Output target is `warehouse/{env}/silver/clinical/clinical_patients/` (SCD2 dims have no `ds` partition per LLD §3.3).
- **Decision 17 (v1.16) — Runtime must stay path-based**: UC table registration moves to deploy time (`make bootstrap-uc`). Runtime Spark writers (`transform_patients.py`, `scd2.py`) are FORBIDDEN from catalog DDL — `.save(target_path)` only, MERGE via ``delta.`<target_path>` ``. The `target_table` kwarg on `apply_scd2` is removed. Pairs with STORY-01-008 AC9-AC14 (the deploy-time toolchain).

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| DMS | §3 Silver schema for patients, §6 SCD2 hash columns |

| LLD | §5.2 transform_patients_silver |

| STM | Tab:Bronze-to-Silver (patients) |

| DQS | §2 row_dq + agg_dq for patients |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Unit | transform_patients SCD2 + PHI drop | pytest patient_360/tests/silver/test_transform_patients_unit.py |

| Contract | contracts/clinical_patients.yml parses | pytest patient_360/tests/test_contracts.py |



## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/silver/transform_patients.py"
  - grep: {file: "patient_360/src/patient_360/silver/transform_patients.py", pattern: "unity.bronze.synthea_patients"}
AC2:
  - grep: {file: "patient_360/src/patient_360/silver/transform_patients.py", pattern: "drop.*SSN|PHI|drop_phi"}
AC3:
  - grep: {file: "patient_360/src/patient_360/silver/transform_patients.py", pattern: "apply_scd2"}
AC4:
  - grep: {file: "patient_360/src/patient_360/silver/transform_patients.py", pattern: "se_runner|run_dq"}
AC5:
  - pytest: {node: "patient_360/tests/silver/test_transform_patients_unit.py"}
AC6:
  - required_grep: {file: "patient_360/src/patient_360/silver/transform_patients.py", pattern: "PATIENT360_PROJECT_ROOT"}
  - forbidden_grep: {file: "patient_360/src/patient_360/silver/transform_patients.py", pattern: "\"warehouse/{env.lower\\(\\)}/bronze\""}
AC7:
  - forbidden_grep: {file: "patient_360/src/patient_360/silver/transform_patients.py", pattern: "dq_rules_dir=Path\\(cfg\\.get"}
AC8:
  - forbidden_grep: {file: "patient_360/src/patient_360/silver/transform_patients.py", pattern: "CREATE TABLE"}
  - forbidden_grep: {file: "patient_360/src/patient_360/silver/transform_patients.py", pattern: "CREATE SCHEMA"}
  - forbidden_grep: {file: "patient_360/src/patient_360/silver/transform_patients.py", pattern: "saveAsTable\\("}
AC9:
  - forbidden_grep: {file: "patient_360/src/patient_360/utils/scd2.py", pattern: "CREATE TABLE"}
  - forbidden_grep: {file: "patient_360/src/patient_360/utils/scd2.py", pattern: "saveAsTable\\("}
  - forbidden_grep: {file: "patient_360/src/patient_360/utils/scd2.py", pattern: "target_table\\s*[:=]"}
  - required_grep: {file: "patient_360/src/patient_360/utils/scd2.py", pattern: "\\.save\\("}
AC10:
  - pytest: {node: "patient_360/tests/silver/test_transform_patients.py"}
  - required_grep: {file: "patient_360/tests/silver/test_transform_patients.py", pattern: "CREATE TABLE|saveAsTable"}
AC11:
  - file_exists: "patient_360/src/patient_360/silver/transform_patients.py"
  - required_grep: {file: "patient_360/src/patient_360/silver/transform_patients.py", pattern: "dropDuplicates|row_number"}
  - required_grep: {file: "patient_360/src/patient_360/silver/transform_patients.py", pattern: "patient_id"}
  - pytest: {node: "patient_360/tests/silver/test_transform_patients_unit.py::test_source_dedup_keeps_one_per_natural_key"}
```


## How to Test (User)

### Prerequisites


- STORY-01-003 done; STORY-02-008 done


### Steps


1. `cd patient_360 && uv run pytest tests/silver/test_transform_patients_unit.py -v`


### Expected outcome


- All SCD2 unit tests pass (hash-change closes existing row + inserts new)


## Documentation Updates


- [ ] N/A — internal silver dim transform module


## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-05-22 | Scrum Master Agent | Added two new acceptance criteria (AC6, AC7) capturing the LLD-DEVIATIONS row 9 retrofit. AC6 mandates that `_bronze_path()` and `_silver_target_path()` (or equivalent path helpers) in `src/patient_360/silver/transform_patients.py` MUST emit ABSOLUTE paths anchored on `PATIENT360_PROJECT_ROOT` (NEVER bare relative paths) — Airflow spark-submit CWD (`/opt/airflow`) is unpredictable and bare-relative paths 404. AC7 mandates that `transform_patients.transform()` MUST NOT pass `dq_rules_dir` as a relative-path kwarg to `run_dq()` — either resolve against `PATIENT360_PROJECT_ROOT`, or (preferred) OMIT the kwarg so `se_runner._resolve_dq_rules_dir()` falls back to the `DQ_RULES_DIR` env var (`/opt/patient_360/dq_rules`). Verification block extended: AC6 adds `required_grep` for `PATIENT360_PROJECT_ROOT` and `forbidden_grep` for the bare-relative form `"warehouse/{env.lower\(\)}/bronze"`; AC7 adds `forbidden_grep` for `dq_rules_dir=Path\(cfg\.get`. Retrofit for LLD-DEVIATIONS row 9 and the 2026-05-22 direct-edit fix (Silver SCD2 reads 404'd because path helpers returned relative paths; DQ rules skipped env-var fallback because the runner received an explicit relative `dq_rules_dir` kwarg). Scope, dependencies, sprint, status, and other ACs unchanged. |
| 2026-05-23 | Scrum Master Agent | Added three new acceptance criteria (AC8, AC9, AC10) for LLD v1.16 §13 Decision 17 — deploy-time UC table registration mandates that runtime Spark writers stay path-based. AC8 forbids `CREATE TABLE`, `CREATE SCHEMA`, and `saveAsTable(` in `src/patient_360/silver/transform_patients.py` (path-based `.save()` writes only via DeltaCatalog; UC visibility established at deploy time by `make bootstrap-uc`). AC9 forbids `CREATE TABLE`, `saveAsTable(`, and the `target_table` kwarg in `src/patient_360/utils/scd2.py` (kwarg removed per LLD v1.16 §2.3); requires `.save(` for first-run cold-warehouse overwrite; MERGE statements must use ``delta.`<target_path>` `` syntax. AC10 mandates a lock-in unit test in `tests/silver/test_transform_patients.py` that greps both files and FAILS if `CREATE TABLE`/`CREATE SCHEMA`/`saveAsTable(` appear — prevents regression of the direct-edit fix. Verification block extended with `forbidden_grep` / `required_grep` for each new AC. Cross-references LLD v1.16 §13 Decision 17 and `chapter-6/developer-plugin/LLD-DEVIATIONS.md` row 10 (forward reference). Pairs 1:1 with STORY-01-008 AC9-AC14 (deploy-time toolchain). User Story line still references `unity.bronze.synthea_patients` as the logical Bronze source — physically the runtime read is path-based (per LLD v1.12 + v1.16); the UC view is created at deploy time by Liquibase. Scope, dependencies, sprint, status, and other ACs unchanged. |
| 2026-05-23 | Scrum Master Agent | Added AC11 — source DataFrame MUST be deduped to one row per natural key (`patient_id`) before `apply_scd2`. Reproduced 2026-05-23 DAG retry (`manual_ld_20260523T222531Z`): `DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE` on second silver run (~80k bronze rows for ~6k distinct patients across N `ds` partitions). Root cause: `transform_patients.py` does NOT dedupe before MERGE; bronze accumulates one snapshot per `ds` partition so the same `patient_id` appears N times. First-run cold-warehouse path masks the bug because `apply_scd2` uses `.write.format("delta").mode("overwrite").save(target_path)` (no MERGE — accepts duplicates); every subsequent run hits MERGE and fails. `apply_scd2` itself is correct — DMS §6 + LLD v1.18 §2.3 specify dedup-before-MERGE is the caller's responsibility. Recommended pattern: `row_number() OVER (PARTITION BY patient_id ORDER BY ds DESC) == 1`; fallback ordering by `_ingested_at` when `ds` is missing. Verification block extended: `required_grep` for `dropDuplicates|row_number` and `patient_id` in `transform_patients.py`; new pytest node `tests/silver/test_transform_patients_unit.py::test_source_dedup_keeps_one_per_natural_key` (3-row DataFrame with 2 rows sharing the same patient_id → asserts deduped output has exactly 1 row, latest by `ds`). Cross-references DMS §6 (SCD2 caller-deduplicates-before-MERGE contract) and LLD v1.18 §2.3 (`apply_scd2` Responsibility row). AC1–AC10 unchanged. Scope, dependencies, sprint, status unchanged. |
