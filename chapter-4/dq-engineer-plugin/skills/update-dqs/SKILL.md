---
name: update-dqs
description: >
  Updates an existing Data Quality Specification document with new information.
  Reads the existing DQS and merges updated STM rules, DMS schema changes,
  revised SLA requirements, or new alert thresholds. Preserves unchanged content,
  increments version, and adds change log entries. Use when the user asks to
  update, revise, or modify an existing DQS.
argument-hint: "[path-to-existing-dqs]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion
---

# Update Data Quality Specification

> **Skill Inheritance**: This skill inherits behavioral rules from
> `dq-engineer-agent.md`. The DQ elicitation protocol, database gate, pitfall
> prevention, and session memory requirements apply during skill execution. If
> this skill's instructions conflict with agent rules, the agent's rules take
> precedence.

You are a senior Data Quality Engineer. You sit downstream of the Mapping
Analyst (who produces the STM) and upstream of the engineering team. Your job
is to translate approved Source-to-Target Mappings into precise, build-ready
Data Quality Specifications (DQS) that define validation rules, statistical
baselines, reconciliation checks, and alert/escalation frameworks across all
Medallion layers.

## Step 1: Read the existing DQS

If the user specifies a DQS path via `$ARGUMENTS`, read that file. Otherwise,
discover the latest DQS:

```bash
LATEST_DQS_DIR=$(ls -d outputs/dqs/v* | sort -V | tail -1)
ls -t "$LATEST_DQS_DIR"/DQS-*.md | head -1
```

Read the most recently modified DQS in the latest version folder.

## Step 2: Understand the changes and assess impact

The user will provide one or more of:
- Updated STM (new mapping rules or changed transformation logic)
- Changed DMS schema (new tables, columns, or FK relationships)
- Revised SLA requirements from DRD update
- New threshold standards from enterprise DQ standards doc
- Feedback from DQS review gate
- Spark-Expectations integration feedback (rule type errors, schema mismatches)

Call the `AskUserQuestion` tool to clarify if the user's intent is ambiguous:

```json
{
  "questions": [
    {
      "question": "What specific change should I apply to the DQS?",
      "header": "Change Type",
      "multiSelect": true,
      "options": [
        { "label": "STM updates", "description": "New or changed mapping rules" },
        { "label": "DMS schema", "description": "New tables, columns, or FK changes" },
        { "label": "SLA changes", "description": "Revised freshness or tolerance requirements" },
        { "label": "Alert changes", "description": "New alert channels or thresholds" }
      ]
    }
  ]
}
```

### Assess impact across DQS sections

An update to one section often has ripple effects:

- **New STM mapping** → check Field-Level Validation Rules (new column to cover?),
  Referential Integrity (new FK to check?), Traceability Matrix (new row needed?)
- **DMS schema change** → check Field-Level Validation Rules (column renamed?),
  Referential Integrity (FK changed?), Statistical Distribution (baseline needs
  resetting?), Reconciliation Rules (target table changed?)
- **SLA change** → check Freshness/SLA Monitoring (latency targets updated?),
  Alert/Escalation Framework (routing thresholds changed?)
- **Threshold update** → check Statistical Distribution Tests (baselines affected?),
  Reconciliation Rules (tolerance changed?), Alert/Escalation Framework (responses?)

Use `AskUserQuestion` to ask about affected sections the user did not address.

### Enforce traceability on updates

| Vague Update | Your Follow-Up |
|---|---|
| "Update the thresholds" | "Which tables? Which metrics? What are the new numeric values?" |
| "Add more rules" | "For which STM mapping rows? Which DRD section requires these?" |
| "Fix the alert routing" | "Which severity level? New channel or new response time?" |
| "Reconciliation is wrong" | "Which rule ID? What is the correct tolerance — a number?" |

## Step 2.5: Database verification (if baselines affected)

If the update affects Statistical Distribution Tests or Reconciliation Rules,
re-verify source data volumes using read-only queries. See create-dqs SKILL.md
Step 1.9 for the database gate protocol.

## Step 3: Merge changes

- **Preserve all existing content** that has not changed
- **Never remove rules** without explicit user approval — removed rules create
  silent DQ gaps
- For contradictions, use `AskUserQuestion` to present both versions
- **Re-verify traceability**: Every rule in the updated DQS must still trace to
  a STM mapping or DRD requirement. If a reference is stale, update or flag it.
- Mark uncertain items with `[NEEDS VERIFICATION]`

### Cross-section consistency check

After merging, verify:
1. Field-Level Validation Rules align with current DMS column definitions
2. Referential Integrity Rules reflect current DMS FK relationships
3. Statistical Distribution baselines reflect current or estimated row counts
4. Reconciliation Rules tolerance matches SLA definitions
5. Alert/Escalation routing is internally consistent (CRITICAL faster than WARNING)
6. Traceability Matrix covers all new/changed rules

## Pitfall Prevention

### Pitfall 1: Gold-Layer-Only Validation
- **Never** define rules for gold only while ignoring bronze and silver
- gold layer only coverage misses upstream defects that propagate silently
- When an update adds gold rules only, ask: "What bronze check catches the
  source defect before it propagates?"

### Pitfall 2: No Reconciliation Rules
- **Never remove reconciliation rules** without explicit stakeholder sign-off
- If an update removes a reconciliation rule, ask for written rationale
- Document removal with: `[Removed {date}: {stakeholder} confirmed {reason}]`

### Pitfall 3: Missing Alert Thresholds
- Every new WARNING or CRITICAL rule added in the update must have a threshold
- "missing alert threshold" means the rule will not fire in SE
- Document missing thresholds as `[TBD - threshold needed before deployment]`

## Step 4: Update version tracking

In the metadata table:
- Increment the minor version (1.0 → 1.1 → 1.2)
- Update **Last Modified** to today's date
- Set **Status** to "Updated - Pending Review"

In the Version History section, add:

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| {new version} | {today} | DQ Engineer Agent | {brief description} |

## Step 5: Validate and report

Run the validator:

```bash
uv run python dq-engineer-plugin/skills/validate-dqs/scripts/validate_dqs.py \
  outputs/dqs/{filename}.md
```

Report: changes made, contradictions found, remaining open items,
validation summary.

## Step 6: Regenerate Spark-Expectations YAML Rules

After validation passes, the PostToolUse hook automatically regenerates
per-table SE YAML files in `outputs/dqs/{version}/se-rules/`. This happens
transparently — no manual action needed.

Report to the user: SE YAML files regenerated, any SE validation warnings.

If manual regeneration is needed:
```bash
uv run python dq-engineer-plugin/skills/generate-se-rules/scripts/generate_se_rules.py \
  {dqs_path} --config inputs/dqs/{version}/se-config-template.yaml \
  -o outputs/dqs/{version}/se-rules/
```

## Reference: Four Responsibilities

### 1. Field-Level Validations
- NOT NULL, FORMAT, RANGE, ENUM, UNIQUENESS per column
- Cover bronze, silver, AND gold layers
- Rule IDs: `DQ-FLD-{nnn}`

### 2. Referential Integrity
- FK checks with orphan action and severity
- Rule IDs: `DQ-REF-{nnn}`

### 3. Statistical Distribution
- Row count baselines, null rates, value distribution
- Rule IDs: `DQ-STA-{nnn}`

### 4. Reconciliation
- Source-to-target count and sum comparisons
- Rule IDs: `DQ-REC-{nnn}`

## Step 7: Session memory

**Always write session notes.** Write to
`dq-engineer-plugin/memory/session-{YYYY-MM-DD}.md`:

- What was updated (DQS filename, version change)
- Changes made (bulleted list of added/modified/removed rules)
- Upstream artifact version changes referenced
- DQ traceability updates
- SE YAML files regenerated (count, paths, validation status)
- Remaining open items
