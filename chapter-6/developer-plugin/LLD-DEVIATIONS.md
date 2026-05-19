# LLD Deviations & Adjustments — Silver/Gold Plugin

Tracks every place where the `silver-gold-plugin` skills implement something
differently from the published LLD
(`chapter-4/outputs/lld/v1/LLD-2026-05-12-patient-360.md`). Each item should
either be accepted (LLD edited to match) or rejected (skill changed to match
LLD). Status: **PENDING REVIEW**.

| # | LLD location | LLD says | Plugin does | Reason | Recommended LLD edit |
|---|---|---|---|---|---|
| 1 | §2.3 `src/patient_360/utils/scd2.py` | `apply_scd2(df, natural_keys, hash_columns, effective_date)` — 4 params; output is "Delta MERGE INTO result (rows inserted, rows closed)" | `apply_scd2(df, target_path, natural_keys, hash_columns, effective_date)` — 5 params; returns `{"rows_inserted", "rows_closed", "rows_unchanged"}` | The LLD signature has no `target_path` argument, so the function cannot locate which Delta table to MERGE INTO. The Spark session is derived internally via `df.sparkSession`. | Update §2.3 Input list to include `target_path` (str). Document the returned metrics dict in the Output line. |
| 2 | §5.2 "DQ Check" column | Conflates two gates in one cell: "Inline SE: ... action_if_failed=<fail\|drop\|ignore>; empty-input: <fail\|write_empty>" | Splits into two independent fields in per-table YAML: `empty_input_behavior` (fail / write_empty) and `se_action_if_failed` (fail / drop / ignore) | They are different gates. SE rule violations and empty-source detection are evaluated at different points in the task; mixing them in one config field makes the runtime behavior ambiguous. | Split §5.2 "DQ Check" into two columns: `empty_input_behavior` and `se_action_if_failed`. Update §2.3 per-table YAML schema accordingly. |
| 3 | §5.2 Silver table names | Domain-prefixed (`clinical_patients`, `reference_organizations`, `billing_claims`, …) | Same | Need to verify DMS §3 uses the same convention; if DMS uses bare names (`patients`), the silver-creation skill will fail traceability checks. | Open: confirm DMS §3 alignment. If DMS uses bare names, fix DMS; otherwise the LLD is consistent. |
| 4 | §2.3 DQ rule file naming | `dq_rules/{table}.yml` (no prefix, underscored, `.yml`) | Copies verbatim from `chapter-4/outputs/dqs/v*/se-rules/<table>.yaml` (with `se-rules-` prefix in upstream filenames) | The `dq-engineer-plugin:generate-se-rules` skill emits files prefixed `se-rules-` with `.yaml` extension, but the LLD's runtime convention is unprefixed `.yml`. The silver-creation skill includes a copy + rename step. | Either: (a) standardize the generator to emit `dq_rules/{table}.yml` directly, or (b) document the rename step in LLD §2.3 next to the runtime path convention. Option (a) is cleaner. |
| 5 | §2.3 surrogate-key strategy | Not specified | `xxhash64(natural_key, effective_date)` OR `max(surrogate_key) + row_number()` from target — explicitly NOT `monotonically_increasing_id()` | `monotonically_increasing_id()` is non-deterministic across runs and per-executor — it will produce different surrogate keys on every retry, breaking SCD2 history. | Add a sentence to §2.3 `scd2.py` Responsibility specifying deterministic surrogate-key generation and explicitly forbidding `monotonically_increasing_id()`. |

## How to resolve

Treat this file as the canonical agenda for the next LLD update cycle.
For each row:

1. **Decide direction**: accept the plugin behavior (edit LLD) or reject it
   (edit the plugin).
2. **Apply the change**: if LLD edit, use `technical-lead-plugin:update-lld`
   to record the version bump and put the deviation under "Change Log" in
   the new LLD revision.
3. **Update this file**: mark the row Resolved/Rejected with a date and a
   pointer to the LLD revision that closed it.

## Conventions

- Every new deviation MUST be logged here before the skill emits any code
  that conflicts with the LLD.
- Plugins MUST NOT silently deviate from the LLD — if a skill chooses an
  alternate implementation, the rationale belongs in this file.
- This file is reviewed in every Silver/Gold session-end summary.
