---
skill: pr-process
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# pr-process — Skill-Creator Eval

## What this skill should do

Drive the full PR lifecycle for a story branch and tear down the sandbox on approval.

## Scenarios

### S1 — Story mode, happy path

**Setup**:
- Clean git tree on feature branch ahead of `origin/main` by ≥1 commit.
- Story file at `outputs/stories/EPIC-01-foundation/STORY-01-001-*.md` with `Status: Approved`.
- `make lint` and `make test` green.

**Invoke**: `/developer-plugin:pr-process STORY-01-001`

**Expected**:
- Prints `RESOLVED TARGET: STORY-01-001 (source: …)` as the first line.
- Phase 1 readiness aggregator runs all 6 script gates, prints PASS per gate (the 7th — `/developer-plugin:validate-stories` — runs at Skill level after the aggregator).
- Phase 2 opens a PR via `gh pr create`, body renders from `pr_body.md.j2`, body ends with `<!-- pr-process: managed -->`.
- Phase 3 polls; on APPROVED + green checks proceeds to Phase 4.
- Phase 4 invokes `teardown_drivers/local_docker.sh --check` then `--dry-run` then `--destroy`. Final JSON summary recorded at `outputs/pr-process/STORY-01-001.teardown.json`.
- Phase 5 verifies ACs are still green; emits OK trailer.

### S2 — Readiness fails: lint red

**Setup**: Same as S1 but `make lint` exits 1.

**Expected**:
- Phase 1 emits `CRITICAL make_lint: …` with the last 10 lines of stderr.
- **No** PR is opened (`gh pr create` is never called).
- Skill exits non-zero, no learnings entry appended (lint failure is an expected red gate).

### S3 — Sandbox missing: no driver match

**Setup**: Same as S1 but `_infra/docker/docker-compose.yml` does not exist (e.g. a project that doesn't use the local stack).

**Expected**:
- Phase 4 reports WARNING `no driver matched`; **no** destroy runs.
- PR is **not** auto-merged; user is told to add a driver or pick one manually.

### S4 — Attach mode

**Invoke**: `/developer-plugin:pr-process 42` (a PR number).

**Expected**:
- Mode dispatch routes to Phase 3 directly; Phases 1+2 skipped.
- Polls PR #42; on APPROVED runs Phase 4 normally.

### S5 — User asked to forget mid-flight

**Setup**: During Phase 3 the user says "abort, don't tear down".

**Expected**:
- Skill stops at Phase 4 gate; no destroy runs; logs the abort to the
  learnings queue with `pattern: "respect explicit abort"`.

## Trigger disambiguation

The skill description must beat these neighbours on the following prompts:

| Prompt | Expected | Beats |
|---|---|---|
| "open a PR and destroy the sandbox" | pr-process | create-pipeline (which generates pipelines, not PRs) |
| "tear down the local docker stack on approval" | pr-process | update-pipeline (which edits workflows) |
| "check the story is shippable" | pr-process | validate-stories (which only validates story markdown, not git/PR state) |

The current SKILL.md description leads with "Drives the full pull-request
lifecycle … pluggable sandbox-teardown driver". Words "PR", "lifecycle",
"sandbox", "teardown", "approval", "destroyed", "STORY-NN-NNN" all appear
in the first 200 chars — high lexical match for the prompts above.

## Description quality checks

- [x] First sentence states the skill's job (≤25 words).
- [x] Modes block enumerated (Story / Attach).
- [x] Project-agnostic claim explicit ("read from workspace discovery + the active teardown-pattern.md at runtime").
- [x] "Use when the user asks to:" block has 3+ concrete phrases.
- [x] Argument hint clear (`[STORY-NN-NNN | <pull_number>]`).

## Argument-hint clarity

`[STORY-NN-NNN | <pull_number>]` — two disjoint shapes, both regex-matchable. The skill's Phase 0.a does the dispatch.

## Phase coverage

| Phase | Present? | Notes |
|---|:-:|---|
| 0.a — Argument resolution | ✅ | Standard shared resolver. |
| 1 — Readiness gate | ✅ | 7 named gates, JSON aggregator. |
| 2 — Open PR | ✅ | Template + labels resolved from epic. |
| 3 — Drive review | ✅ | State table covers CHANGES_REQUESTED routing. |
| 4 — Teardown | ✅ | Pluggable driver, check/dry-run/destroy contract. |
| 5 — AC self-check | ✅ | Mandatory before reporting OK. |

## Known weaknesses (track in future passes)

- Live trigger eval not yet run; static eval only checks lexical match.
- No coverage of multi-driver disambiguation prompt (chapter-6 only
  ships one driver, so this is theoretical).
