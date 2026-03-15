---
name: update-hld
description: >
  Updates an existing High-Level Design document with new information.
  Reads the existing HLD and merges updated DRD requirements, infrastructure
  changes, technology decisions, or capacity revisions. Preserves unchanged
  content, increments version, and adds change log entries. Use when the
  user asks to update, revise, or modify an existing HLD.
argument-hint: "[path-to-existing-hld]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion
---

# Update High-Level Design Document

> **Skill Inheritance**: This skill inherits behavioral rules from
> `architect-agent.md`. The traceability enforcement, database gate,
> pitfall prevention, and session memory requirements apply during
> skill execution. If this skill's instructions conflict with agent
> rules, the agent's rules take precedence.

You are a Data Architect Agent. Update an existing HLD with new information
provided by the user.

## Step 1: Read the existing HLD

If the user specifies an HLD path via `$ARGUMENTS`, read that file. Otherwise,
discover the latest HLD:

```bash
LATEST_HLD_DIR=$(ls -d chapter-4/outputs/hld/v* | sort -V | tail -1)
ls -t "$LATEST_HLD_DIR"/HLD-*.md | head -1
```

Read the most recently modified HLD in the latest version folder.

## Step 2: Understand the changes and assess impact

The user will provide one or more of:
- Updated DRD (new requirements or changed business rules)
- Changed infrastructure constraints
- Revised team capabilities
- New technology options or deprecations
- Updated capacity projections
- Changed regulatory requirements
- Feedback from HLD review gate

Call the `AskUserQuestion` tool to clarify if the user's intent is ambiguous:

```json
{
  "questions": [
    {
      "question": "What specific change should I apply to the HLD?",
      "header": "Change Type",
      "multiSelect": true,
      "options": [
        { "label": "DRD updates", "description": "Updated DRD requirements or business rules" },
        { "label": "Constraints", "description": "Changed infrastructure constraints" },
        { "label": "Technology", "description": "New technology decision or deprecation" },
        { "label": "Capacity", "description": "Revised capacity or regulatory requirements" }
      ]
    }
  ]
}
```

### Assess impact across HLD sections

An update to one section often has ripple effects:

- **New DRD requirement** → check Layer Specs (can architecture support it?),
  Technology (does current stack handle it?), Capacity (volume impact?)
- **Changed constraint** → check Technology (still viable?), Layer Specs
  (boundaries still correct?), CDC (approach still valid?)
- **New technology** → check team capabilities, integration points,
  capacity (cost impact?), DR (backup strategy still valid?)

Use `AskUserQuestion` to ask about affected sections the user did not
address. Ask section-by-section.

### Enforce traceability on updates

| Vague Update | Your Follow-Up |
|---|---|
| "Switch to Spark" | "Which DRD requirement drives this? What about current team capabilities?" |
| "Add streaming" | "What latency does the DRD require? Which consumers need sub-batch freshness?" |
| "Update capacity" | "What are the new volume projections? What scaling triggers should change?" |
| "Better security" | "Which specific compliance requirement is not met? What sensitive data needs additional protection?" |

## Step 2.5: Database verification (if capacity/CDC affected)

If the update affects capacity planning or CDC strategy, re-verify
source data volumes using read-only queries. See create-hld SKILL.md
Step 1.7 for the database gate protocol.

## Step 3: Merge changes

- **Preserve all existing content** that has not changed
- **Never remove content** without explicit user approval
- For contradictions, use `AskUserQuestion` to present both versions
- **Re-verify traceability**: Every design decision in the updated HLD
  must still cite a DRD requirement. If a DRD reference is stale,
  update or remove it.
- Mark uncertain items with `[NEEDS VERIFICATION]`

### Cross-section consistency check

After merging, verify:
1. Layer specs still align with technology choices
2. Capacity projections match current volumes
3. CDC strategy matches source system capabilities
4. Security architecture covers all DRD regulatory requirements
5. DR strategy aligns with current SLA targets

## Step 4: Update version tracking

In the metadata table:
- Increment the minor version (1.0 → 1.1 → 1.2)
- Update **Last Modified** to today's date
- Set **Status** to "Updated - Pending Review"

In the Version History section, add:

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| {new version} | {today} | Architect Agent | {brief description} |

## Step 5: Validate and report

Run the validator:

```bash
uv run python chapter-4/architect-plugin/skills/validate-hld/scripts/validate_hld.py chapter-4/outputs/hld/{filename}.md
```

Report: changes made, contradictions found, remaining open items,
validation summary.

## Step 6: Session memory

**Always write session notes.** Write to
`chapter-4/architect-plugin/memory/session-{YYYY-MM-DD}.md`:

- What was updated (HLD filename, version change)
- Changes made (bulleted list)
- Design decisions changed and rationale
- DRD traceability updates
- Remaining open items
