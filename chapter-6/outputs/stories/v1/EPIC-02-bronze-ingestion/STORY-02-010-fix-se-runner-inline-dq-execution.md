# STORY-02-010: Fix SE runner so inline DQ actually executes

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 5 |
| **Dependencies** | STORY-01-010, STORY-02-001, STORY-02-005 |
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

As a data engineer, I want `se_runner.run_dq(...)` to pass the rule-matching
identifiers Spark Expectations actually filters on — so that the inline DQ gate
selects the intended per-table rule set and physically validates Bronze/Silver
data, instead of silently matching **zero** rules and reporting a green run that
never checked anything (the §13 Decision 16 silent-DQ no-op class).

## Description

Fix `src/patient_360/utils/se_runner.py` to honor the **SE rule-matching &
isolation contract** in LLD §2.3 (v1.20, 2026-06-20). The inline SE gate
had never executed: `se_runner` passed mismatched identifiers, so Spark
Expectations matched **zero** rules and silently validated nothing on **every**
Bronze and Silver run (every "green" run reported `0 rules evaluated` — the §13
Decision 16 silent-failure class; see also §13 Decision 12/14/15). Spark
Expectations filters its rule set on the tuple `(product_id, table_name)`. The
prior bug passed the bare **physical** table name (e.g. `synthea_patients`) for
**both** `product_id` and `target_table`, which selects zero rules and makes the
DQ gate a no-op.

`run_dq` MUST:
1. Pass `SparkExpectations(product_id=<rules YAML top-level `product_id` field>,
   ...)` — e.g. `patient-360` — read from the resolved rules file, **not** the
   physical table name.
2. Pass `with_expectations(target_table=<rules YAML `dq_env.<ENV>.table_name`>,
   ...)` — the value `generate-se-rules` now emits **BARE** (physical table name,
   no catalog/schema prefix, e.g. `synthea_patients`) — the same value SE matches
   against.
3. Before `with_expectations`, register a bare-name **TEMP VIEW** for every
   `unity.{bronze,silver,gold}.<t>` table referenced by the rule set, then register
   the in-flight DataFrame **last** under its own bare name
   (`createOrReplaceTempView`), so cross-table referential `query_dq` SQL (authored
   against bare names) resolves under `spark.sql.defaultCatalog=unity`.
4. Address the SE **stats** AND **error** tables as **per-table MANAGED Unity
   Catalog tables** by a 3-part FQN — `unity.<schema>.<table>_stats` and
   `unity.<schema>.<table>_error` — derived from the FQN `target_table`
   (`stats_table=f"{se_target_table}_stats"`; SE derives `_error` as
   `f"{target_table}_error"`). Both writers are MANAGED (`format("delta")` with
   **NO** `.option("path", ...)`); SE creates them via `saveAsTable` on first run
   as `catalogManaged` tables in the schema `storage_root` (set by
   `scripts/uc_init.py`) — SE-owned, NOT pre-created in Liquibase. A single shared
   `bronze_se_stats` / `bronze_se_error` name collides on per-table schema
   (`DELTA_*` merge conflict); the per-table FQN prevents this. This is the §13
   Decision 12 (corrected 2026-06-20) MANAGED-audit-table design, valid on
   **UC 0.5.0** + delta-spark 4.1 coordinated commits.

The existing `run_dq` signature, the `dq_env` → SE `dq_env` mapping table
(`_DQ_ENV_MAP`), and the fail-closed import contract (§8.6 / Decision 14) are
**unchanged**. The downstream
`create-ingestion` / `update-ingestion` Area-G generator regenerates
`se_runner.py` against this contract.

## Acceptance Criteria


- [ ] **AC1** — `run_dq` constructs `SparkExpectations(product_id=...)` from the rules YAML's top-level `product_id` field (e.g. `patient-360`), **NOT** the bare/physical table name; the `product_id` argument must never be set to the `table` parameter value [LLD §2.3 "SE rule-matching & isolation contract" (v1.20), §13 Decision 12/14/15/16]

- [ ] **AC2** — `run_dq` calls `with_expectations(target_table=<dq_env.<ENV>.table_name from the resolved rules YAML>, ...)` — the BARE physical table name that `generate-se-rules` now emits — resolving `<ENV>` through the existing `_DQ_ENV_MAP` (DEV→DEV / STAGING→QA / PROD→PROD) [LLD §2.3 (v1.20), §13 Decision 12/14/15/16]

- [ ] **AC3** — Before `with_expectations`, `run_dq` registers a bare-name TEMP VIEW (`createOrReplaceTempView`) for every `unity.{bronze,silver,gold}.<t>` table referenced by the rule set, and registers the in-flight DataFrame **last** under its own bare name, so referential `query_dq` SQL resolves unqualified identifiers under `spark.sql.defaultCatalog=unity` [LLD §2.3 (v1.20), §13 Decision 12/16]

- [ ] **AC4** — `run_dq` addresses the SE stats table AND the SE error table as **per-table MANAGED Unity Catalog tables** by 3-part FQN — `unity.<schema>.<table>_stats` (passed as `stats_table=f"{se_target_table}_stats"`) and `unity.<schema>.<table>_error` (SE derives `f"{target_table}_error"` from the FQN `target_table`); both writers are MANAGED (`format("delta")` with **NO** `.option("path", ...)`). It must **not** write either to a single shared `bronze_se_stats` / `bronze_se_error` name, and must **not** write either to a path-based `warehouse/{env}/_se/<table>/{stats,errors}` location [LLD §2.3 (v1.20), §13 Decision 12 (corrected 2026-06-20), §8.2/§8.3]

- [ ] **AC5** — An integration smoke test proves SE selects `> 0` rules for a table that has rules, and that a `row_dq` rule with `action_if_failed: drop` physically removes the offending rows from the validated DataFrame for a table that has such a rule [LLD §2.3 (v1.20), §8.6 / §13 Decision 16]

- [ ] **AC6** — `run_dq` signature, `_DQ_ENV_MAP`, and the fail-closed import contract (§8.6 / Decision 14) are preserved unchanged. (The SE-output storage shape is **not** preserved: the prior path-based design is superseded by per-table MANAGED UC tables per AC4 — see §13 Decision 12 correction 2026-06-20.) [LLD §2.3 (v1.20), §8.6, §13 Decision 14]

- [ ] **AC7** — `run_dq` sets `user_conf["se.enable.error.table"] = True` AND `user_conf["se.enable.stats.table"] = True`. On **UC 0.5.0** SE creates both audit tables as MANAGED UC tables via `saveAsTable` addressed by the per-table 3-part FQN (`unity.<schema>.<table>_error` / `_stats`); the MANAGED `_error` table is the primary rejected-row audit trail. The earlier "disable the error table because `UCSingleCatalog` rejects RTAS/CTAS `saveAsTable`" rationale is **withdrawn** — that was a misdiagnosis: the UC-0.4.0 failure was an **empty-namespace `fullTableNameForApi` defect on bare names** (AIOOBE on a length-0 namespace under spark-submit), NOT an RTAS refusal, and the FQN `target_table` (AC2) avoids it. The `row_dq` `drop` action removes failing rows from the output AND those rows land in the `_error` table. Verification grep over `src/patient_360/utils/se_runner.py`: `se.enable.error.table` set to `True`, `se.enable.stats.table` set to `True` [LLD §2.3 (v1.20), §13 Decision 12 (corrected 2026-06-20), §8.2]

- [ ] **AC8** — `run_dq` is column-stable: it captures `input_cols = df.columns` BEFORE `with_expectations` and returns `validated.select(*input_cols)`, so the run-tracking columns Spark Expectations APPENDS (`meta_dq_run_id`, `meta_dq_run_datetime`) are dropped and the returned DataFrame schema equals the input schema. This lets any caller (e.g. Bronze `write_bronze` → `insertInto(unity.bronze.<table>)`) write the validated DataFrame straight to the pre-created target table without a Delta schema mismatch (`_LEGACY_ERROR_TEMP_DELTA_0007` — target has neither column); the run-tracking values persist in the SE stats table, not the data table. Silver previously dodged this only by re-`select(OUTPUT_COLUMNS)`; fixing it at the single source (`run_dq`) makes the contract hold for all callers. Verification grep over `src/patient_360/utils/se_runner.py`: `select(*input_cols)` (or equivalent input-column projection) present at the `run_dq` return [LLD §2.3 (v1.20), §13 Decision 12/16]


## Technical Notes

- **Upstream references**: LLD §2.3 "SE rule-matching & isolation contract" (v1.20, corrected 2026-06-20), §8.2/§8.3 (MANAGED SE audit tables), §13 Decision 12 (corrected 2026-06-20), Decision 14, Decision 15, Decision 16
- **Root cause**: SE filters on `(product_id, table_name)`. Passing the bare physical table name for BOTH selected zero rules → DQ silently did nothing on every green run. Fix: `product_id` ← YAML `product_id`; `target_table` ← YAML `dq_env.<ENV>.table_name` (now emitted BARE by `generate-se-rules`).
- **Implementation hints**: Read `product_id` and `dq_env` from the per-table `dq_rules/{table}.yml` already loaded by `se_runner`. Map `env` → SE `dq_env` via the existing `_DQ_ENV_MAP`. Register bare-name temp views by walking the rule set's `unity.{bronze,silver,gold}.<t>` references and `createOrReplaceTempView("<t>")`; register the in-flight df last under its own bare name. Pass the SE stats table as the per-table FQN `stats_table=f"{se_target_table}_stats"` (→ `unity.<schema>.<table>_stats`) — a MANAGED `format("delta")` writer with **no** `.option("path", ...)`, NOT the shared `bronze_se_stats` constant and NOT the path-based `warehouse/{env}/_se/{table}/stats`. Set `user_conf["se.enable.error.table"] = True` and `user_conf["se.enable.stats.table"] = True`: on **UC 0.5.0** SE creates both audit tables as MANAGED `catalogManaged` UC tables via `saveAsTable` addressed by the per-table 3-part FQN (`unity.<schema>.<table>_error` / `_stats`) in the schema `storage_root`. The earlier "disable the error table — `UCSingleCatalog` rejects RTAS/CTAS `saveAsTable`" hint is **withdrawn**: that was a misdiagnosis. The real UC-0.4.0 failure was an **empty-namespace `fullTableNameForApi` defect** — a BARE error name (`synthea_patients_error`) under spark-submit (empty session current-database) split a length-0 namespace and crashed with `ArrayIndexOutOfBoundsException`. Passing the FQN `target_table` (AC2) gives SE a well-formed 3-part `_error` name and avoids the AIOOBE; UC 0.5.0 fixes the namespace handling AND supports managed `saveAsTable` creates (§13 Decision 12 correction, 2026-06-20). The `row_dq` `drop` removes failing rows from the output AND lands them in the MANAGED `_error` table. **Column stability (AC8)**: capture `input_cols = df.columns` BEFORE `with_expectations`, then `return validated.select(*input_cols)` — `with_expectations` APPENDS run-tracking columns (`meta_dq_run_id`, `meta_dq_run_datetime`) to its returned DataFrame; projecting back to the input columns drops them so the result schema equals the input schema and any caller (Bronze `write_bronze` → `insertInto(unity.bronze.<table>)`) writes straight to the pre-created table without Delta `_LEGACY_ERROR_TEMP_DELTA_0007`. Run-tracking values persist in the SE stats table, not the data table. Owner: Data Engineering. Generated/regenerated by the `create-ingestion`/`update-ingestion` Area-G generator.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|

| LLD | §2.3 (v1.20), §8.2/§8.3, §8.6, §13 Decision 12 (corrected 2026-06-20) /14/15/16 |

| DQS | §2-4 (per-table SE rules consumed by `run_dq`) |

| STM | Tab:Source-to-Bronze / Tab:Bronze-to-Silver (tables validated inline) |


## Testing

| Coverage | What | How |
|----------|------|-----|

| Unit | `product_id` / `target_table` identifier resolution, per-table SE path construction, bare-name temp-view registration | pytest patient_360/tests/utils/test_se_runner_unit.py |

| Integration | SE selects > 0 rules; `row_dq` drop rule physically removes rows | pytest patient_360/tests/integration/bronze/test_se_rule_matching.py |



## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/utils/se_runner.py"
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "product_id\\s*=\\s*[^,)]*product_id"}
  - forbidden_grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "SparkExpectations\\(\\s*product_id\\s*=\\s*table\\b", reason: "product_id must be the rules YAML product_id field, NOT the bare/physical table name — passing the table name for product_id selects ZERO rules (LLD §2.3 v1.20, §13 Decision 16)"}
AC2:
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "with_expectations\\("}
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "target_table\\s*="}
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "dq_env|table_name|_DQ_ENV_MAP"}
AC3:
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "createOrReplaceTempView"}
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "unity\\.(bronze|silver|gold)"}
AC4:
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "stats_table\\s*=\\s*f?['\"]?\\{?[a-zA-Z_]*target_table\\}?_stats"}
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "unity\\.(bronze|silver|gold)"}
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "_stats"}
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "_error"}
  - forbidden_grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "['\"]bronze_se_stats['\"]", reason: "SE stats/error must be PER-TABLE MANAGED UC tables unity.<schema>.<table>_stats|_error by 3-part FQN — a single shared bronze_se_stats name collides on per-table schema (LLD §2.3 v1.20, §13 Decision 12 corrected 2026-06-20)"}
  - forbidden_grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "_se/\\{?table", reason: "path-based warehouse/{env}/_se/<table>/{stats,errors} was a UC-0.4.0 workaround — retired; on UC 0.5.0 SE audit tables are MANAGED UC tables by FQN with no .option('path') (LLD §2.3 v1.20, §13 Decision 12 corrected 2026-06-20)"}
  - forbidden_grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "\\.option\\(\\s*['\"]path['\"]", reason: "MANAGED SE audit-table writers must NOT pass .option('path', ...) — they are catalog-managed by FQN (LLD §2.3 v1.20 item 3)"}
AC5:
  - pytest: {node: "patient_360/tests/integration/bronze/test_se_rule_matching.py"}
AC6:
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "_DQ_ENV_MAP"}
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "def run_dq\\("}
AC7:
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "se\\.enable\\.error\\.table['\"]\\s*\\]?\\s*=\\s*True"}
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "se\\.enable\\.stats\\.table['\"]\\s*\\]?\\s*=\\s*True"}
  - forbidden_grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "se\\.enable\\.error\\.table['\"]\\s*\\]?\\s*=\\s*False", reason: "the SE error table is RE-ENABLED on UC 0.5.0 — it writes as a MANAGED UC table by FQN; the earlier disable was a misdiagnosis of an empty-namespace defect as an RTAS refusal (LLD §2.3 v1.20, §13 Decision 12 corrected 2026-06-20)"}
AC8:
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "input_cols\\s*=\\s*[a-zA-Z_]*df\\.columns"}
  - grep: {file: "patient_360/src/patient_360/utils/se_runner.py", pattern: "\\.select\\(\\*input_cols\\)"}
```


## How to Test (User)

### Prerequisites


- STORY-01-010 done (`se_runner.py` shipped with the fail-closed import + path-based SE-stats contract)
- STORY-02-001 done (bronze runner calls `se_runner.run_dq(...)` inline)
- STORY-02-005 done (13 per-table Bronze SE rule YAMLs exist with `product_id` + `dq_env.<ENV>.table_name`)


### Steps


1. `cd patient_360 && uv run pytest tests/utils/test_se_runner_unit.py -v`
2. `cd patient_360 && uv run pytest tests/integration/bronze/test_se_rule_matching.py -v`


### Expected outcome


- SE selects `> 0` rules for a table that has rules (no more `0 rules evaluated`)
- A `row_dq` drop rule physically removes the offending rows from the validated output and lands them in the MANAGED `_error` table
- SE stats/error land as per-table MANAGED UC tables `unity.<schema>.<table>_stats` / `unity.<schema>.<table>_error` (3-part FQN, no `.option("path")`)


## Documentation Updates


- [x] Update patient_360/README.md § "Inline data quality (Spark Expectations)" noting that `run_dq` passes `product_id` (YAML) + bare `target_table` (`dq_env.<ENV>.table_name`) for rule matching, and writes per-table MANAGED UC SE stats/error tables `unity.<schema>.<table>_stats` / `_error` by 3-part FQN (UC 0.5.0; `se.enable.error.table` and `se.enable.stats.table` both `True`)
