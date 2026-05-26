---
skill: complete-stories
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# complete-stories — Skill-Creator Eval

## What this skill should do

Mark Scrum stories Done; roll epic/backlog status up once every child story is complete. Blocks on unchecked AC, open dependency, missing deliverable, or open epic AC.

## Scenarios

### S1 — Single story Done

**Invoke**: `/developer-plugin:complete-stories STORY-03-005`.

**Expected**:
- Verifies every AC checkbox is checked.
- Verifies dependencies are Done.
- Edits (not writes) the story metadata: `Status: Done`.
- Rolls epic status to In-Progress (or Done if all child stories done).

### S2 — AC unchecked → blocked

**Expected**: CRITICAL — "STORY-03-005 AC3 unchecked; refusing to mark Done".

### S3 — Dependency not Done

**Setup**: STORY-03-005 depends on STORY-03-003 which is Status: In-Progress.

**Expected**: CRITICAL — "dependency STORY-03-003 not Done".

### S4 — Epic-level AC still open

**Expected**: CRITICAL — "EPIC-03 has open epic AC: <text>; refusing to roll epic up".

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "mark story 03-005 done" | complete-stories | validate-stories |
| "close out epic 03" | complete-stories | validate-stories |
| "finalize sprint 3" | complete-stories | implement-stories |

## Description quality checks

- [x] Edit (not Write) claim explicit.
- [x] All 4 blocker conditions enumerated.

## Known weaknesses

- Doesn't currently emit a celebratory log line — easy enhancement.
