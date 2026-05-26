---
skill: refresh-libraries
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# refresh-libraries — Skill-Creator Eval

## What this skill should do

Re-verify every row in `inputs/code/v*/LIBRARIES.md` against context7 / PyPI / GitHub releases; show diff; ask user approval; rewrite with fresh `last_verified:` timestamp.

## Scenarios

### S1 — All libraries up to date

**Invoke**: `/developer-plugin:refresh-libraries all`.

**Expected**:
- Reads every library row.
- Queries upstream for each.
- Diff is empty.
- Updates only `last_verified:` to today's date; bumps file's minor version.

### S2 — One library has a new patch

**Expected**:
- Prints a diff: `pyspark: 4.0.2 → 4.0.3`.
- Calls AskUserQuestion(`Apply` / `Skip` / `Cancel`).
- On Apply: rewrites the row, updates last_verified, optionally also bumps `pyproject.toml` pin (separate AskUserQuestion).

### S3 — Single library

**Invoke**: `/developer-plugin:refresh-libraries pyspark` → verifies just that row.

### S4 — Hard rules

- Never auto-applies bumps without user approval.
- Never edits `pyproject.toml` without a second AskUserQuestion (LIBRARIES.md is the catalog; pyproject is the binding — two separate decisions).
- Always cites the upstream source it consulted (context7 doc id, PyPI JSON URL, etc.).

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "refresh the library versions" | refresh-libraries | apply-learnings |
| "check if pyspark has a new version" | refresh-libraries | (none — distinctive) |
| "bump the libraries.md file" | refresh-libraries | update-scaffold |

## Description quality checks

- [x] Three upstream sources documented (context7, PyPI, GitHub).
- [x] AskUserQuestion approval gate explicit.

## Known weaknesses

- Context7 may not have every library; fallback to PyPI works but is silent — the eval should require an INFO message naming the source per row.
