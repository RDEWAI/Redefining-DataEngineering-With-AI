---
skill: implement-stories
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# implement-stories — Skill-Creator Eval

## What this skill should do

Orchestrate downstream create-/update- skills per story. Dispatches by epic; never edits story markdown directly.

## Scenarios

### S1 — Single story (silver)

**Invoke**: `/developer-plugin:implement-stories STORY-03-005`.

**Expected**: parses story header → routes to `/developer-plugin:create-silver STORY-03-005` (or update-silver if module exists).

### S2 — Comma-list

**Invoke**: `/developer-plugin:implement-stories STORY-02-001,STORY-02-002,STORY-02-003`.

**Expected**: dispatches each in order; halts the batch if any story fails its AC self-check.

### S3 — Epic (topo-sorted)

**Invoke**: `/developer-plugin:implement-stories EPIC-03` → topo-sorts by Depends On, dispatches.

### S4 — Sprint label

**Invoke**: `/developer-plugin:implement-stories Sprint 3` → reads sprint metadata, dispatches all stories tagged with the sprint.

### S5 — Hard rules

- Never edits story markdown.
- Always writes a `.plan.json` per story (read by validate-stories).
- Routes by epic-NN prefix: EPIC-02 → bronze, EPIC-03 silver-dim, EPIC-04 silver-fact, EPIC-05 gold (per LLD §5.x).
- Stops the batch on the first AC self-check FAIL — does not continue blindly.

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "implement story 03-005" | implement-stories | create-silver |
| "do all the stories in epic 04" | implement-stories | create-silver |
| "work on sprint 3" | implement-stories | create-silver |

## Description quality checks

- [x] Lists all 4 input forms.
- [x] "Never edits story markdown" claim explicit.

## Known weaknesses

- Topo sort assumes Depends-On graph is acyclic; doesn't detect cycles → loops indefinitely if one exists.
