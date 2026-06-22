# LLD Update Session — 2026-06-19 (se_runner SE rule-matching contract)

## What was updated
- File: outputs/lld/v1/LLD-2026-06-18-patient-360.md
- Version: 1.16 (Approved) -> 1.17 (Updated - Pending Review)
- Scenario C: same version folder (v1), same date (2026-06-19), in-place edit.

## Change made
Added an "SE rule-matching & isolation contract" subsection to the §2.3
`se_runner.py` / `run_dq` Module Interface Contract. Fixes the silent-DQ
no-op (§13 Decision 16 class): SE had matched ZERO rules because se_runner
passed mismatched identifiers, so no validation ran for any Bronze/Silver
table on any green run.

The new contract requires `run_dq` to:
1. Pass SE `product_id` = the rules YAML's `product_id` field (e.g.
   `patient-360`) and `with_expectations(target_table=...)` = the
   `dq_env.<ENV>.table_name` value (now emitted BARE by generate-se-rules).
   SE filters on `(product_id, table_name)`; passing the bare physical table
   name for BOTH selects zero rules and the gate silently does nothing.
2. Register bare-name TEMP VIEWS for every `unity.{bronze,silver,gold}.<t>`
   table the rule set references, in-flight df last under its own bare name,
   so cross-table query_dq referential SQL resolves under
   spark.sql.defaultCatalog=unity.
3. Write SE stats AND error Delta tables to per-table paths
   (`warehouse/{env}/_se/<table>/stats` and `.../<table>/errors`) — a single
   shared bronze_se_stats/_error path collides on per-table schema.

## Preserved unchanged
run_dq signature, _DQ_ENV_MAP (dq_env mapping table), path-based SE design
(Decision 12/15), fail-closed import contract (Decision 14, §8.6). No other
sections touched — interface-contract clarification only.

## Downstream ripple
- create-ingestion / update-ingestion (Area G) must regenerate
  `src/patient_360/utils/se_runner.py` against this contract.
- Pairs with task #21 (generate_se_rules.py emits BARE table_name) and
  task #22 (regenerate se-rules + dq_rules, re-test all silver tables).

## Validation
validate-lld: all checks passed, no issues. PostToolUse hook auto-validated
clean on every edit and regenerated config/, dag/, impl-sequence.md.

## Remaining open items
- Re-approval required (Status is Updated - Pending Review) before downstream
  stories re-cut.
- Implementation regen of se_runner.py not yet run.
