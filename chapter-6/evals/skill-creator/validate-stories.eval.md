---
skill: validate-stories
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# validate-stories — Skill-Creator Eval

## What this skill should do

Verify code implementation satisfies every AC of one or more Scrum stories (and every epic AC). Combines static AC scan + downstream validator runs.

## Scenarios

### S1 — Single story, all ACs pass

**Invoke**: `/developer-plugin:validate-stories STORY-03-005`.

**Expected**:
- Reads the story's `## Verification` block.
- For each AC: static heuristic (keyword/path) + invokes downstream validator (validate-silver / validate-ingestion / validate-dag).
- Returns PASS with `N/N ACs green`.

### S2 — One AC fails

**Expected**: CRITICAL per failing AC: `CRITICAL STORY-NN-NNN AC<N>: <check.spec> — <check.detail>`.

### S3 — Manual AC indeterminate

**Expected**: INFO line (manual checks can't fail mechanically).

### S4 — Epic-level ACs

**Invoke**: `/developer-plugin:validate-stories EPIC-03` → validates epic-level ACs after all stories pass.

### S5 — Plan JSON update

**Expected**: updates `<story>.plan.json` (written by implement-stories); never edits story markdown.

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "verify story 03-005 is implemented" | validate-stories | validate-silver |
| "check the epic 03 ACs are all green" | validate-stories | validate-silver |
| "did we satisfy every AC" | validate-stories | validate-stories (scrum-master variant — see CLAUDE.md namespace note) |

## Description quality checks

- [x] Combines static + downstream-validator approach explicit.
- [x] Plan-JSON-update claim explicit.

## Known weaknesses

- Namespace collision with `scrum-master-plugin:validate-stories` — users must qualify (`/developer-plugin:validate-stories`).
- Static heuristic is keyword-based; structural verifier is the planned upgrade.
