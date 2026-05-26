---
skill: apply-learnings
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# apply-learnings — Skill-Creator Eval

## What this skill should do

Convert pending entries from `memory/developer/learnings-queue.jsonl` into absolute-directive rules in the relevant skill's `Active Learnings` section.

## Scenarios

### S1 — Single pending entry

**Setup**: queue has one entry: `{"skill":"create-silver","date":"2026-05-23","correction":"used monotonically_increasing_id","pattern":"never monotonically_increasing_id for SCD2","status":"pending"}`.

**Expected**:
- Reflects: "the correction was about SCD2 surrogate keys".
- Abstracts: "non-determinism in surrogate keys breaks SCD2 idempotency".
- Generalises: "NEVER use monotonically_increasing_id for SCD2 surrogate keys; use xxhash64 or row_number()".
- Writes the rule into `developer-plugin/skills/create-silver/SKILL.md` § Active Learnings as `L-NNN`.
- Marks the queue entry `status: applied`.

### S2 — Multiple entries grouped by skill

**Expected**: groups entries per skill, processes per-skill in one pass, never lets two L-NNN rules collide on the same number.

### S3 — Entry that implies LLD change

**Expected**: also appends to `developer-plugin/LLD-DEVIATIONS.md` so the Technical Lead can fold the deviation into the next LLD revision.

### S4 — Hard rules

- Never deletes a pending entry without writing the corresponding rule (atomic update).
- Never renumbers existing L-NNN entries.
- Always uses absolute directives ("MUST" / "NEVER" / "ALWAYS").

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "apply the pending learnings" | apply-learnings | refresh-libraries |
| "convert the corrections into rules" | apply-learnings | refresh-libraries |
| "process the learnings queue" | apply-learnings | (none — distinctive verbiage) |

## Description quality checks

- [x] Reflect-Abstract-Generalize-Write pattern named.
- [x] LLD-DEVIATIONS.md cross-reference explicit.

## Known weaknesses

- Doesn't deduplicate rules; if the same correction is filed twice, two L-NNN entries appear.
