---
name: generate-se-rules
description: >
  Converts a Data Quality Specification (DQS) markdown document into per-table
  Spark-Expectations YAML rule files. Reads the DQS, groups rules by target
  table, and generates one YAML file per table compatible with
  spark-expectations >= 2.6.0.
  Also known as: SE rules generation, Spark-Expectations config, DQS-to-YAML
  conversion, quality rules export.
  Input formats: DQS Markdown (.md) file.
  Output format: Per-table YAML files in outputs/dqs/v{N}/se-rules/.
  Use when the user asks to:
  - Generate SE rules or Spark-Expectations YAML
  - Convert DQS to YAML rule files
  - Produce Spark-Expectations configs from a DQS
  - Export quality rules for spark-expectations framework
  - "Create the SE YAML files from the DQS"
argument-hint: "[path-to-dqs-file]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion, Skill
context: fork
hooks:
  before:
    - matcher: Bash
      script: "${CLAUDE_PLUGIN_ROOT}/scripts/enforce-readonly-queries.py"
  after:
    - matcher: "Write|Edit"
      script: "${CLAUDE_PLUGIN_ROOT}/scripts/validate-dqs-hook.py"
---

# Generate Spark-Expectations Rules from DQS

You are a senior Data Quality Engineer with deep knowledge of the
spark-expectations (spark_expectations) framework >= 2.6.0. Your job is to
convert a structured DQS markdown document into per-table Spark-Expectations
YAML rule files, one file per target table, following the exact SE schema.

## Spark-Expectations Schema Knowledge

Spark-Expectations (spark_expectations) rules are organized by table and rule
type. Each rule entry has these 17 columns (15 per-rule + product_id and
table_name at top/dq_env level):

| Column | Type | Description |
|--------|------|-------------|
| `product_id` | string | Product/pipeline identifier |
| `table_name` | string | Fully qualified table name (schema.table) |
| `rule_type` | string | `row_dq`, `agg_dq`, or `query_dq` |
| `rule` | string | Unique rule identifier (matches DQ-xxx-nnn) |
| `column_name` | string | Column being checked (row_dq) or `""` (agg/query) |
| `expectation` | string | SQL expression to evaluate |
| `action_if_failed` | string | `ignore`, `drop` (row_dq only), or `fail`. dq_env provides fallback default; per-rule overrides |
| `tag` | string | Category tag for dashboards |
| `description` | string | Human-readable rule description |
| `enable_for_source_dq_validation` | boolean | Run rule on source data (before row filtering). True for query_dq reconciliation |
| `enable_for_target_dq_validation` | boolean | Run rule on target data (after row filtering). Usually true |
| `is_active` | boolean | Enable/disable rule without deletion |
| `enable_error_drop_alert` | boolean | Alert when dropped rows exceed threshold. True for STA/REC rules |
| `error_drop_threshold` | integer | Integer percentage (e.g., 5 = alert if >5% of rows dropped) |
| `query_dq_delimiter` | string | Delimiter for query_dq SQL (usually `"@"`) |
| `enable_querydq_custom_output` | boolean | Emit custom output for query_dq |
| `priority` | string | Controls notification routing: `high` → all channels incl. PagerDuty, `low` → Slack only |

### Rule Type Constraints

**row_dq** (per-row validation):
- Used for: NOT NULL, FORMAT, RANGE, ENUM, UNIQUENESS checks (DQ-FLD)
- `column_name`: the column being validated
- `expectation`: Boolean column expression passed to `F.expr()`. Must return true/false
  per row. NO SELECT subqueries, NO CASE WHEN. Use simple predicates: `col IS NOT NULL`,
  `col > 0`, `lower(trim(col)) in ('a','b')`. Complex checks → use `query_dq` instead.
- `action_if_failed`: `"ignore"` for WARNING, `"drop"` (row_dq only) or `"fail"` for CRITICAL
- `enable_for_source_dq_validation`: usually `false` (validate target)
- `enable_for_target_dq_validation`: usually `true`

**agg_dq** (aggregate validation):
- Used for: row count checks, null rate tests, distribution checks (DQ-STA)
- `column_name`: `""` (aggregate across table)
- `expectation`: Must match SE regex: `agg_func(col) operator value` or
  `agg_func(col) op val and agg_func(col) op val` (range format).
  Valid: `count(*) > 0`, `sum(sales) > 10000`, `count(*) > 40000 and count(*) < 60000`.
  Invalid: CASE WHEN inside aggregate. Complex → move to `query_dq`.
- `action_if_failed`: `"ignore"` for WARNING, `"fail"` for CRITICAL
- `enable_error_drop_alert`: `true` for statistical checks

**query_dq** (cross-table SQL):
- Used for: FK reconciliation, source-to-target count checks (DQ-REF, DQ-REC)
- `column_name`: `""` (cross-table query)
- `expectation`: SE wraps this as `SELECT (expectation) AS OUTPUT` and casts result
  to int. Non-zero = pass, zero = fail. Must return a single scalar.
  Pattern: `CASE WHEN condition THEN 1 ELSE 0 END FROM (...) s, (...) t`
  Do NOT start with SELECT (SE adds that). Do NOT use WHERE to filter rows.
- `query_dq_delimiter`: `"@"` — used to split SQL if multi-statement
- `enable_querydq_custom_output`: `true` to emit reconciliation results

### Environment Config Structure (dq_env)

The SE config template defines per-environment settings:

```yaml
dq_env:
  DEV:
    table_name: dev_raw.patients
    action_if_failed: ignore
    enable_for_source_dq_validation: false
    enable_for_target_dq_validation: true
    is_active: true
    enable_error_drop_alert: false
    error_drop_threshold: 0
    priority: medium
  PROD:
    table_name: raw.patients
    action_if_failed: fail
    enable_for_source_dq_validation: true
    enable_for_target_dq_validation: true
    is_active: true
    enable_error_drop_alert: true
    error_drop_threshold: 2
    priority: high
```

### action_if_failed Constraints by Rule Type

| Severity | row_dq | agg_dq | query_dq |
|----------|--------|--------|----------|
| CRITICAL | `"fail"` | `"fail"` | `"fail"` |
| WARNING  | `"drop"` | `"ignore"` | `"ignore"` |
| INFO     | `"ignore"` | `"ignore"` | `"ignore"` |

---

## Step 1: Read the DQS

If the user specifies a DQS path via `$ARGUMENTS`, read that file. Otherwise,
discover the latest DQS:

```bash
LATEST_DQS_DIR=$(ls -d outputs/dqs/v* | sort -V | tail -1)
ls -t "$LATEST_DQS_DIR"/DQS-*.md | head -1
```

Read the DQS and extract all rules grouped by section:
- Section 2: Field-Level Validation Rules → `row_dq` candidates
- Section 3: Referential Integrity Rules → `query_dq` candidates
- Section 4: Statistical Distribution Tests → `agg_dq` candidates
- Section 5: Reconciliation Rules → `query_dq` candidates

## Step 2: Read the SE config template

Discover and read the SE config template:

```bash
ls -d inputs/dqs/v* | sort -V | tail -1
cat {latest_inputs_dir}/se-config-template.yaml
```

Extract:
- `product_id`: pipeline/product identifier
- `dq_env`: environment-specific settings (DEV/QA/PROD)
- `_generator.layer_schemas`: schema mapping (generator metadata, not SE output)

## Step 3: Group rules by table

Build a mapping of `{schema}.{table}` → list of rule entries.

For each rule in the DQS:
1. Extract `rule_id`, `table`, `column`, `expression`, `severity`, `layer`
2. Map to SE rule type:
   - DQ-FLD rules → `row_dq`
   - DQ-REF rules → `query_dq`
   - DQ-STA rules → `agg_dq`
   - DQ-REC rules → `query_dq`
3. Map severity to `action_if_failed`:
   - CRITICAL → `"fail"`
   - WARNING or INFO → `"ignore"`
4. Set `error_drop_threshold` from the DQS rule's tolerance value,
   or default from the SE config template for that environment

If a rule's table is ambiguous (e.g., no schema prefix), use `AskUserQuestion`
to clarify before generating:

```json
{
  "questions": [
    {
      "question": "Rule DQ-FLD-001 references table 'patients' without a schema. Which schema should this map to in SE rules?",
      "header": "Schema",
      "multiSelect": false,
      "options": [
        { "label": "bronze.patients", "description": "Raw ingestion layer" },
        { "label": "clinical.patients", "description": "Silver cleansed layer" },
        { "label": "analytics.patients", "description": "Gold analytical layer" }
      ]
    }
  ]
}
```

## Step 4: Generate YAML per table

For each unique table, produce a YAML file:

```yaml
# SE Rules for {schema}.{table}
# Generated from: {dqs_filename}
# Product: {product_id}
# Generated: {today}

product_id: {product_id}

dq_env:
  DEV:
    table_name: dev_{schema}.{table}
    action_if_failed: ignore
    enable_for_source_dq_validation: false
    enable_for_target_dq_validation: true
    is_active: true
    enable_error_drop_alert: false
    error_drop_threshold: 0
    priority: medium
  PROD:
    table_name: {schema}.{table}
    action_if_failed: fail
    enable_for_source_dq_validation: true
    enable_for_target_dq_validation: true
    is_active: true
    enable_error_drop_alert: true
    error_drop_threshold: 2
    priority: high

rules:
  - rule_type: "{row_dq|agg_dq|query_dq}"
    rule: "{DQ-xxx-nnn}"
    column_name: "{column or empty}"
    expectation: "{sql expression}"
    action_if_failed: "{ignore|drop|fail}"
    tag: "{category}"
    description: "{human-readable description}"
    enable_for_source_dq_validation: false
    enable_for_target_dq_validation: true
    is_active: true
    enable_error_drop_alert: {true|false}
    error_drop_threshold: {0.001}
    query_dq_delimiter: "@"
    enable_querydq_custom_output: {true|false}
    priority: "{low|medium|high}"
```

**Naming convention**: `se-rules-{table-name}.yaml`
(e.g., `se-rules-dim-patient.yaml`, `se-rules-fact-encounter.yaml`)

## Step 5: Use the script for bulk generation

For large DQS documents, use the Python script:

```bash
uv run python dq-engineer-plugin/skills/generate-se-rules/scripts/generate_se_rules.py \
  {dqs_path} \
  --config {se_config_path} \
  -o outputs/dqs/{version}/se-rules/
```

The script parses the DQS markdown, groups rules by table, and writes one YAML
per table.

## Step 6: Validate generated YAML inline

After generating each YAML file, perform inline validation:

1. **Schema check**: Does each rule entry have all 15 per-rule SE columns?
2. **rule_type constraint**: Is `action_if_failed` correct for each rule type?
3. **Threshold check**: Is `error_drop_threshold` a valid decimal (0.0 to 1.0)?
4. **Expression check**: Is the SQL expression non-empty and syntactically valid?
5. **Environment check**: Are DEV, QA, and PROD environments all present?
6. **SE compatibility**: Validate with `validate_se_yaml()` — port of SE's `flatten_rules_list()` checks

If any check fails, fix it before saving. Report issues to the user.

## Step 7: Save SE rule files

Save generated YAML files to:
```bash
outputs/dqs/{version}/se-rules/se-rules-{table-name}.yaml
```

Create the `se-rules/` subdirectory if it does not exist.

## Step 8: Session memory

**Always write session notes.** Write to
`memory/dqs/session-{YYYY-MM-DD}.md`:

- DQS file processed
- Tables covered (list)
- Rule count per rule type (row_dq, agg_dq, query_dq)
- SE YAML files generated (list)
- Validation results
- Any schema/expression issues found and fixed

### Correction Capture (MANDATORY)

After EVERY user correction — whether they edit the artifact, ask you to change
something, or reject a section — you MUST append a learning entry BEFORE continuing:

```bash
echo '{"skill": "generate-se-rules", "date": "{YYYY-MM-DD}", "correction": "{what the user said or changed}", "pattern": "{generalized rule}", "status": "pending"}' >> memory/dqs/learnings-queue.jsonl
```

**What counts as a correction:** user says "no, change X to Y", edits artifact
directly, rejects a proposed decision, or provides a specific value replacing
a vague one you generated. When in doubt, append it — false positives are filtered
during apply-learnings.


## Final Step: Apply Learnings

After SE rules generation completes, if `memory/dqs/learnings-queue.jsonl` has pending entries,
invoke `/dq-engineer-plugin:apply-learnings` before finishing.

## Learnings & Corrections

> **Meta-rules for adding learnings:**
> 1. Each learning MUST be an absolute directive ("Always X", "Never Y")
> 2. Lead with the problem, then the fix: "When X happens, do Y"
> 3. Include a concrete command or example, not just prose
> 4. One learning per bullet — no compound rules
> 5. Delete learnings that contradict each other; keep the newer one
> 6. Maximum 20 learnings per skill — if at capacity, merge related items

### Active Learnings

- **L-001** (2026-04-24): Always require fully-qualified `schema.table` references in `query_dq` expressions. Never accept unqualified table names (e.g., `clinical_patients`) — they must read as `clinical.clinical_patients`. When the SE validator flags unqualified tables in the generated YAML, surface the full list of offending DQ-REF rules and recommend running `/dq-engineer-plugin:update-dqs` to fix the DQS source before re-running generate-se-rules; do not silently rewrite expressions in the YAML.

<!-- Example format:
- **L-001** (2026-03-20): Always use CAST(col AS DATE) not TO_DATE(col) for date conversions.
- **L-002** (2026-03-21): Never generate placeholder SLA values — ask the user for specific numeric targets.
-->
