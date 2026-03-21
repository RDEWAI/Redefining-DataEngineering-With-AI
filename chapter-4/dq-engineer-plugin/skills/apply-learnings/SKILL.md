---
name: apply-learnings
description: >
  Reviews pending corrections from the learnings queue and applies them as
  generalized rules to the relevant skill's Learnings & Corrections section.
  Uses the Reflect-Abstract-Generalize-Write pattern to convert raw user
  corrections into absolute directives that improve future skill execution.
  Use when the user asks to:
  - Apply learnings or corrections
  - Review the learnings queue
  - Improve skills from past feedback
  - "What corrections have accumulated?"
argument-hint: ""
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion
---

# Apply Learnings

Process pending corrections from the learnings queue and apply them as
generalized rules to the relevant skill files.

## Step 1: Read the Learnings Queue

```bash
cat dq-engineer-plugin/memory/learnings-queue.jsonl
```

If the file is empty or contains no `"status": "pending"` entries, report
"No pending learnings to apply" and stop.

## Step 2: Group by Skill

Parse each JSONL line and group entries by the `skill` field. Display a
summary to the user:

```
Pending learnings:
- create-drd: 3 corrections
- validate-drd: 1 correction
```

## Step 3: Process Each Correction

For each pending correction, apply the **Reflect-Abstract-Generalize-Write** pattern:

### 3a. Reflect
What exactly was corrected? Quote the user's original correction.

### 3b. Abstract
Is this specific to one case, or does it apply generally? Consider:
- Does it apply to all artifacts or just this one?
- Is it a style preference or a correctness issue?
- Could it conflict with existing learnings?

### 3c. Generalize
Write the learning as an absolute directive following the meta-rules:
1. Start with "Always" or "Never"
2. Lead with the problem, then the fix
3. Include a concrete command or example
4. One rule per bullet

### 3d. Confirm with User
Use `AskUserQuestion` to show the proposed learning and ask if it should be applied:

```
Proposed learning for create-drd:
- **L-003** (2026-03-20): Always use explicit CAST expressions for type conversions — never rely on implicit casting. Example: `CAST(date_col AS DATE)` not just `date_col`.

Apply this learning? [Yes / No / Edit]
```

## Step 4: Write Approved Learnings

For each approved learning:

1. Read the target skill file:
   `dq-engineer-plugin/skills/{skill-name}/SKILL.md`

2. Find the `### Active Learnings` section

3. Determine the next learning ID (L-001, L-002, etc.) by counting existing entries

4. Append the new learning bullet after any existing entries (or replace the
   "_No learnings recorded yet_" placeholder if this is the first)

5. Use the Edit tool to make the change

## Step 5: Update the Queue

After all learnings are processed, update `dq-engineer-plugin/memory/learnings-queue.jsonl`:
- Change `"status": "pending"` to `"status": "applied"` for applied entries
- Change `"status": "pending"` to `"status": "rejected"` for rejected entries

## Step 6: Report

Summarize what was done:
- Number of learnings applied per skill
- Number rejected
- Any conflicts with existing learnings that were resolved
