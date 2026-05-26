---
skill: validate-scaffold
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# validate-scaffold — Skill-Creator Eval

## What this skill should do

Read-only validation of project scaffold vs LLD (directory tree, Make targets, infra) and DMS (StructType contracts). Runs scaffold smoke tests.

## Scenarios

### S1 — Clean scaffold

**Expected**: PASS, "uv sync OK, imports OK, pytest --collect-only OK".

### S2 — Missing Make target

**Expected**: CRITICAL — "Makefile missing target: validate-silver".

### S3 — Schema drift

**Expected**: CRITICAL — "src/<project>/contracts/patients.py StructType field count ≠ DMS §3.patients".

### S4 — uv sync fails

**Expected**: CRITICAL — "uv sync exit 1; LIBRARIES.md likely out of date or pyproject.toml malformed".

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "smoke test the scaffold" | validate-scaffold | validate-ingestion |
| "is the project Makefile complete" | validate-scaffold | validate-pipeline |
| "check the StructType contracts" | validate-scaffold | validate-silver |

## Description quality checks

- [x] Smoke-test claim explicit (uv sync, import, pytest --collect-only).
- [x] Read-only claim explicit.

## Known weaknesses

- Smoke tests can take 30s+ on cold caches — Phase 2 should add a `--fast` mode that skips uv sync.
