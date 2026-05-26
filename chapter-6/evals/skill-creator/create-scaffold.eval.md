---
skill: create-scaffold
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# create-scaffold — Skill-Creator Eval

## What this skill should do

Generate the foundation layer: directory tree, pyproject.toml, Makefile, docker-compose, cross-cutting utils, StructType schema contracts, test-harness scaffolding.

## Scenarios

### S1 — Fresh project

**Invoke**: `/developer-plugin:create-scaffold full`.

**Expected**:
- Renders cookiecutter template into `<project>/`.
- Emits `pyproject.toml` with pinned LIBRARIES.md versions.
- Emits `Makefile` with `dev-setup`, `test`, `lint`, `validate-*` targets.
- Emits `_infra/docker/docker-compose.yml` per docker-compose-conventions.md.
- Emits skeleton workflow files: `lint.yml`, `unit-test.yml`, `integration-test.yml` (NOT pr-preview/sandbox-cleanup/promote — those are `create-pipeline`).
- Emits StructType contracts from DMS schemas.

### S2 — Story mode (one new module)

**Invoke**: `/developer-plugin:create-scaffold STORY-01-002` → adds only the module/utility named by the story's deliverables.

### S3 — Hard rules

- Ownership split with create-pipeline: only the THREE skeleton workflows above; everything else is create-pipeline's domain.
- Never overwrites user-edited files (detected by checking git modification time vs scaffold-generation timestamp).

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "scaffold the project skeleton" | create-scaffold | create-pipeline |
| "generate pyproject.toml and Makefile" | create-scaffold | create-ingestion |
| "drop in docker-compose for the local stack" | create-scaffold | create-pipeline |

## Description quality checks

- [x] Cookiecutter pattern explicit.
- [x] Ownership split with create-pipeline documented.

## Known weaknesses

- Cookiecutter template versioning isn't surfaced — re-runs may silently use a stale template.
