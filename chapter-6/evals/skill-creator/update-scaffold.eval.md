---
skill: update-scaffold
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# update-scaffold — Skill-Creator Eval

## What this skill should do

Update an existing project scaffold (directories, pyproject.toml, Makefile, docker-compose, schema contracts) without deleting files.

## Scenarios

### S1 — sync-contracts (DMS changed)

**Invoke**: `/developer-plugin:update-scaffold sync-contracts`.

**Expected**: regenerates StructType schemas under `src/<project>/contracts/` from the latest DMS, preserves user-added comments where possible.

### S2 — sync-infra (docker-compose drift)

**Invoke**: `/developer-plugin:update-scaffold sync-infra` → reconciles `_infra/docker/docker-compose.yml` against docker-compose-conventions.md (pinned image tags, named volumes, port map).

### S3 — sync-template (cookiecutter bump)

**Invoke**: `/developer-plugin:update-scaffold sync-template` → applies cookiecutter delta; flags any user-edited file before overwriting.

### S4 — Hard rules

- Never deletes a file.
- Always uses Edit (not Write) for files that may have been edited by the user.

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "regenerate the StructType contracts from the DMS" | update-scaffold | update-silver |
| "bump the docker-compose service tags" | update-scaffold | update-pipeline |
| "sync the project to the latest cookiecutter" | update-scaffold | create-scaffold |

## Description quality checks

- [x] Five sync modes documented.
- [x] "Never deletes" claim explicit.

## Known weaknesses

- Conflict resolution (user edited a file the skill wants to overwrite) is binary — Phase 2 should add a 3-way-merge offer.
