---
name: apply-learnings
description: >
  Reviews pending corrections from the silver-gold-plugin learnings queues
  and applies them as generalized rules to the relevant skill's Learnings &
  Corrections section. Uses the Reflect-Abstract-Generalize-Write pattern to
  convert raw user corrections into absolute directives that improve future
  skill execution.
  Use when the user asks to:
  - Apply learnings or corrections
  - Review the learnings queue
  - Improve silver/gold skills from past feedback
  - "What corrections have accumulated?"
argument-hint: ""
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion
---

# Apply Learnings (Silver/Gold)

Process pending corrections from the chapter-6 silver-gold-plugin learnings
queues and apply them as generalized rules to the relevant skill files.

## Workspace Discovery

Chapter-6's developer-plugin uses a single learnings queue at
`chapter-6/memory/developer/learnings-queue.jsonl` — every skill in this
plugin (Bronze, Silver, Gold, scaffold/dag/ingestion/pipeline) writes to
and reads from the same file. This mirrors chapter-5's developer-plugin
convention.

```bash
WORKSPACE_ROOT="$(cd "$(dirname "${CLAUDE_PLUGIN_ROOT:-.}")" && pwd)"
# WORKSPACE_ROOT points at chapter-6.

LEARNINGS_QUEUE="$WORKSPACE_ROOT/memory/developer/learnings-queue.jsonl"
```

Chapter-6 ships its own copy of the developer-plugin (atomicity); the
chapter-5 queue at `chapter-5/memory/developer/learnings-queue.jsonl` is
NEVER read by this skill — corrections there belong to chapter-5's plugin
instance. If a chapter-5 learning applies to a chapter-6 skill, the
operator copies it into the chapter-6 queue manually as a new pending
entry; this skill never auto-promotes across chapters.

## Step 1: Read the Learnings Queue

```bash
cat "$LEARNINGS_QUEUE" 2>/dev/null
```

If empty or contains no `"status": "pending"` entries, report "No pending
learnings to apply" and stop.

## Step 2: Group by Skill

Parse each JSONL line and group entries by the `skill` field. Valid skill
names for this plugin include every skill under
`chapter-6/developer-plugin/skills/`, including the silver/gold additions:

- Silver/Gold: `create-silver`, `update-silver`, `validate-silver`,
  `create-gold`, `update-gold`, `validate-gold`
- Bronze + scaffolding (inherited from chapter-5): `create-scaffold`,
  `update-scaffold`, `validate-scaffold`, `create-dag`, `update-dag`,
  `validate-dag`, `create-ingestion`, `update-ingestion`,
  `validate-ingestion`, `create-pipeline`, `update-pipeline`,
  `validate-pipeline`
- Story orchestration: `implement-stories`, `validate-stories`,
  `complete-stories`, `refresh-libraries`
- This skill: `apply-learnings`

If a pending entry names a skill outside this set, surface a warning and
leave it pending.

Display a summary to the user:

```
Pending learnings:
- create-silver: 3 corrections
- validate-gold: 1 correction
```

## Step 3: Process Each Correction

For each pending correction, apply the **Reflect-Abstract-Generalize-Write**
pattern:

### 3a. Reflect
What exactly was corrected? Quote the user's original correction.

### 3b. Abstract
Is this specific to one case, or does it apply generally? Consider:
- Does it apply to all Silver/Gold tables or just one?
- Is it a style preference or a correctness issue?
- Could it conflict with existing learnings (including the
  `### Inherited Learnings` block carried over from chapter-5)?
- Does the underlying issue indicate the LLD itself needs an update? If
  yes, the learning MUST be paired with a row in
  `chapter-6/silver-gold-plugin/LLD-DEVIATIONS.md`.

### 3c. Generalize
Write the learning as an absolute directive following the meta-rules:
1. Start with "Always" or "Never"
2. Lead with the problem, then the fix
3. Include a concrete command or example
4. One rule per bullet
5. Cite the LLD section that the rule defends, where applicable

### 3d. Confirm with User
Use `AskUserQuestion` to show the proposed learning and ask if it should be
applied:

```
Proposed learning for create-silver:
- **L-003** (2026-05-19): Always derive `record_hash` on the SOURCE side
  before invoking apply_scd2 — the helper computes it internally for the
  matched-vs-source comparison, but downstream readers (reconciliation,
  audit) expect the column already present on the source DataFrame.
  Verify via `assert "record_hash" in source_df.columns` before the merge.

Apply this learning? [Yes / No / Edit]
```

## Step 4: Write Approved Learnings

For each approved learning:

1. Read the target skill file:
   `${CLAUDE_PLUGIN_ROOT}/skills/{skill-name}/SKILL.md`

2. Find the `### Active Learnings` section under `## Learnings &
   Corrections` (create it if absent). Active Learnings are kept SEPARATE
   from `### Inherited Learnings` so the operator can distinguish locally
   discovered rules from chapter-5 carry-overs.

3. Determine the next learning ID (L-001, L-002, …) by counting existing
   entries in **Active Learnings only** (ignore Inherited).

4. Append the new learning bullet after any existing Active entries.

5. Use the Edit tool to make the change.

## Step 5: Update the Queue

After all learnings are processed, update the source queue file
(`$SILVER_QUEUE` or `$GOLD_QUEUE`):
- Change `"status": "pending"` to `"status": "applied"` with an
  `"applied_date"` field set to today
- Change `"status": "pending"` to `"status": "rejected"` with a
  `"rejected_reason"` field for rejected entries

## Step 6: Report

Summarize what was done:
- Number of learnings applied per skill
- Number rejected (with reasons)
- Any conflicts with existing learnings that were resolved
- Any entries that triggered a corresponding `LLD-DEVIATIONS.md` row —
  flag these for the next `/technical-lead-plugin:update-lld` cycle
