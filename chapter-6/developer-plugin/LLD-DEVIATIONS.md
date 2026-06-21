# LLD Deviations — Developer Plugin

Documented, intentional departures from the published LLD where the LLD's
literal text cannot be implemented against the runtime stack the project
actually runs on (PySpark 4 + Delta + Spark Expectations + Airflow 3.x +
**Unity Catalog OSS as the runtime catalog**, with tables pre-created as
EXTERNAL Delta by the beeline `ddl-apply` one-shot). Each entry is the single
source of truth for why generated code differs from the LLD.

Authoritative upstream: LLD §13 **Decision 12** (Unity Catalog named
side-catalog; tables addressed by 3-part FQN `unity.<schema>.<table>`,
pre-created EXTERNAL Delta, written via `insertInto` / SCD2 `MERGE INTO`) and
DMS §3/§6. The committed chapter-6 code follows them.

**UC 0.5.0 note (2026-06-20):** the EXTERNAL + `insertInto` rule applies to
**business** tables. The re-enabled spark-expectations `_error`/`_stats` audit
tables are **MANAGED** `catalogManaged` tables created by SE's `saveAsTable`
against a 3-part FQN (`unity.<schema>.<table>_error`). This is supported on UC
0.5.0 (the 0.4.0 prohibition was an empty-namespace `fullTableNameForApi`
defect on bare names, not an RTAS refusal — see `create-ingestion` se_runner
spec). Business tables remain EXTERNAL by design.

## #1 — RETIRED (2026-06-19): SCD2 helper is now UC-named, not path-based

> **Status: RETIRED.** This deviation documented the *old* path-based Silver
> write (`target_path` filesystem path, `MERGE INTO delta.\`<path>\``). Silver
> was regenerated onto Unity Catalog (Decision 12) on 2026-06-19, so the code
> now **matches** the LLD and there is no longer a deviation. Kept as a
> historical marker.

The SCD2 helper signature is `apply_scd2(df, *, target_table, natural_keys,
hash_columns, effective_date)` where **`target_table` is the 3-part named UC
FQN `unity.silver.<dim>`** (NOT a filesystem path). The dimension table is
**pre-created** as EXTERNAL Delta by the beeline `ddl-apply` one-shot (DDL
owned by `create-silver`/`update-silver`, IL-018), and the helper MERGEs into
it via `DeltaTable.forName(spark, target_table)` — never `forPath`, never
`saveAsTable`-create. This is exactly LLD §5.2 + Decision 12, so the prior
"path-based" rationale no longer applies. `validate-silver` R10 requires the
kwarg name `target_table` and a `unity.silver.*` FQN.

## #2 — SCD2 metadata columns (DMS §3, not the SKILL's generic set)

The create-silver SKILL Phase 2 sketch and the `validate-silver` R7 check
reference a generic SCD2 column set (`surrogate_key`, `natural_key`,
`effective_date`, `expiry_date`, `record_hash`, `dw_created_at`,
`dw_updated_at`).

**Deviation**: the authoritative Silver column contract is **DMS §3 / §6**,
which uses `effective_from`, `effective_to`, `is_current`, `_record_hash`
and **no `surrogate_key`** (the natural business key is the merge key). The
generated SCD2 helper and dimension schemas follow DMS §3 verbatim. R7 is
therefore expected to emit WARNINGs about the absent generic columns; those
are advisory and overridden by the DMS contract. The `_record_hash`
separator is a single `|` to match the STM Bronze-to-Silver
`SHA256(CONCAT_WS('|', ...))` expressions.

## #3 — DQ-gate / empty-input are two distinct gates

`run_dq`'s `action_if_failed` (LLD §5.4: `fail | drop | ignore`) is the
Spark-Expectations failure response. It is independent of the LLD §5.2
empty-input policy (`Fail task` vs `Write empty`), which is enforced
separately in the transform before SE runs. The two must not be conflated.

## #4 — `reference_organizations.revenue` precision: STM v3 wins over DMS §3.11

**DMS §3.11** declares `revenue` as `DECIMAL(12,2)`. The approved **STM v3
Tab:Bronze-to-Silver** (pinned in `outputs/dev-lock.yaml`) declares
`CAST(REVENUE AS DECIMAL(14,2))`. The two upstream artifacts conflict.

**Resolution**: `transform_organizations.py` and
`contracts/reference_organizations.yml` cast/type `revenue` to
`DECIMAL(14,2)`, following the **STM** transformation expression — STM is the
authoritative source for the cast per the `update-silver` per-table diff
rules (STM rule change → transformation-logic drift). The scale (2) is
unchanged, so no existing-row rounding behaviour changes; only precision
widens 12 → 14 (non-narrowing, Delta-schema compatible).

**Recommended remediation**: run a `/data-modeler-plugin:update-dms` cycle to
set DMS §3.11 `revenue` to `DECIMAL(14,2)` so DMS and STM reconcile. A
related, code-immaterial mismatch exists on `state` (DMS `VARCHAR(2)` vs STM
v3 `VARCHAR(50)`); both map to Spark `string`, so no transform change.
