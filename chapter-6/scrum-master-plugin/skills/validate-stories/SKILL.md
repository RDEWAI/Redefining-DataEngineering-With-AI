---
name: validate-stories
description: >
  Validates a Sprint Backlog against completeness and quality standards.
  Checks the backlog index, epic files, and story files for required sections,
  upstream traceability, dependency consistency, sprint allocation, and story
  quality. Reports issues as CRITICAL, WARNING, or INFO with suggested fixes.
  Also known as: backlog review, story quality check, sprint plan audit.
  Input formats: Stories output directory containing BACKLOG, EPIC, and STORY files.
  Output format: Validation report with severity-ranked findings.
  Use when the user asks to:
  - Validate, check, review, verify, or audit the backlog
  - Assess story completeness or sprint plan quality
  - Find issues or gaps in the stories
  - Run quality checks on stories before sprint planning
argument-hint: "[stories-directory-path]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion, Skill
hooks:
  before:
    - matcher: Bash
      script: "${CLAUDE_PLUGIN_ROOT}/scripts/enforce-readonly-queries.py"
---

# Validate Sprint Backlog

You are a Scrum Master responsible for decomposing technical designs into
implementable work items. You sit at the end of the artifact chain — consuming
the LLD (and all upstream artifacts) and producing a Sprint Backlog of Epics
and Stories.

## Step 1: Run the validator

Run the Python validator script on the stories directory:

```bash
# All files in the latest version folder
LATEST_STORIES_DIR=$(ls -d outputs/stories/v* | sort -V | tail -1)
uv run python scrum-master-plugin/skills/validate-stories/scripts/validate_stories.py --all "$LATEST_STORIES_DIR"
```

## Step 2: Interpret results

The validator checks rules across three severity levels:

### CRITICAL (blocks sprint execution)
- `STORIES-STRUCT-001`: Backlog index file missing or lacks required sections
- `STORIES-STRUCT-002`: No epic directories exist
- `STORIES-STRUCT-003`: Epic has zero story files
- `STORIES-STRUCT-004`: Story missing required section (User Story, Acceptance Criteria, or Dependencies)
- `STORIES-STRUCT-005`: Epic missing required section (Objective or Stories table)
- `STORIES-META-001`: Backlog metadata incomplete (version, date, author, status, LLD reference)
- `STORIES-FORMAT-001`: User story does not follow "As a... I want... So that..." format
- `STORIES-AC-001`: Story has fewer than 3 acceptance criteria
- `STORIES-CLOSURE-001`: Layer epic (LLD §5.1 / §5.2 / §5.3) has no `performance-optimization` story
- `STORIES-CLOSURE-002`: Layer epic has no `integration-test` story
- `STORIES-CLOSURE-003`: Integration-test story AC is missing "Airflow DAG" or "Unity Catalog" wording — local integration testing means triggering the layer DAG on local Airflow against UC OSS local and validating data in UC local
- `STORIES-CLOSURE-004`: Integration-test story does not depend on a `performance-optimization` story from the same epic — closure order is perf BEFORE integration-test
- `STORIES-BOOTSTRAP-001`: Backlog has no `runtime-bootstrap` story — every backlog must include ≥1 such story (typically EPIC-01) covering JDK 17 verification, `docker compose up`, UC OSS catalog/schemas creation, source-data seeding, and a smoke curl against the UC API
- `STORIES-INTEGRATION-AUTOMATED-001`: An `integration-test` story has 0 automated verifiers (every spec in `## Verification` is `manual:` or the block is missing) — without an automated verifier, the test is a checklist, not a gate. Add at least one `pytest:` (or `validator:` / `grep:`) verifier so `verify_acs.py` and `complete-stories` can prove the layer DAG actually ran and data landed in UC OSS local
- `STORIES-TESTING-001`: Story is missing a populated `## Testing` section. Every story must declare what coverage exists (Unit / Contract / Integration / Smoke / DQ / Benchmark) so the developer-plugin can wire verifiers and the user can see the test posture at a glance
- `STORIES-USER-TEST-001`: Story of type `build`, `integration-test`, or `runtime-bootstrap` is missing a populated `## How to Test (User)` section. The user must be able to verify Done independently with prerequisites + exact commands + expected output
- `STORIES-DOCS-001` (CRITICAL for `runtime-bootstrap`/`integration-test`/`release`): Story is missing a `## Documentation Updates` AC list. Stories that change how the project runs must enumerate which README/runbook sections must be updated
- `STORIES-AC-CONTRADICTION-001`: Two stories assert mutually exclusive things on the same file/pattern (one story's `grep` matches another story's `grep_absent` for the same `file` + `pattern`), both stories cite the same LLD § section in their `## Acceptance Criteria`, AND no `Dependencies` edge orders them. Without ordering, both ACs cannot be true. **Spokane case (2026-04-26):** STORY-02-001 AC4 grep'd for `'WARNING: se_runner not available'` while STORY-02-004 AC4 grep_absent'd the same string in the same runner — both citing §8.6 — and the user had to hand-edit the bootstrap story to mark its AC superseded. Fix: add a `| **Dependencies** | <bootstrap_story_id> |` line to the fail-closed-side story's metadata. The phased-contract guard in `create-stories` Step 2.5 emits the edge automatically — manual fixes are needed only on hand-edited backlogs.
- `STORIES-SE-COVERAGE-001`: Build stories that wire Spark Expectations (`SparkExpectations`, `WrappedDataFrameWriter`, `with_expectations`, `se_runner.run_dq`) without a runtime-bootstrap AC that verifies SE runs **end-to-end**. Importing the package alone is insufficient — spokane shipped a "DQ-wired" pipeline where `with_expectations(...)` was never invoked against real data. Bootstrap must contain ≥1 AC mentioning `with_expectations`, the SE stats table (`bronze_se_stats`), `dq_pass_rate`, or an SE error table. DQ is mandatory; `BRONZE_SKIP_SE=1` and similar bypasses are explicitly forbidden (LLD §8.6.1, Decision 16).
- `STORIES-INTEGRATION-SE-001`: Integration-test stories on a layer epic (LLD §5.1/§5.2/§5.3) that trigger a Bronze/Silver/Gold DAG MUST also assert SE runtime artifacts (stats / error table / `dq_pass_rate`). DAG-ran ≠ SE-ran. The story's `## Acceptance Criteria` or `## Verification` block must mention `bronze_se_stats` (or the configured layer SE stats table), `<table>_error`, `dq_pass_rate`, `meta_dq_run_id`, or a pytest verifier such as `test_se_stats_populated` / `test_dq_pass_rate`. Pair with the existing `STORIES-CLOSURE-003` (Airflow DAG + Unity Catalog) and `STORIES-INTEGRATION-AUTOMATED-001` (≥1 non-manual verifier) — the three rules together close the silent-DQ failure mode (LLD §8.6.1, Decision 16).

### WARNING (needs attention)
- `STORIES-TRACE-001`: Story lacks upstream artifact reference — citations must match
  pattern `\[(?:LLD|DMS|DQS|STM|HLD|DRD) §\d+\.\d+\]`
- Dependency consistency — referenced STORY IDs actually exist
- Sprint allocation — all stories assigned to a sprint
- Story point estimates present for all stories
- No orphaned stories — every story belongs to an epic
- Dependency graph present in backlog (Mermaid diagram)
- `STORIES-CLOSURE-005`: Layer epic has no `deploy-validation` story and its Objective is missing the explicit "Deploy: N/A — layer completes at integration-test" note — closure intent unclear
- `STORIES-CLOSURE-006`: Trailing epic (Release / Hardening) contains a layer-specific `performance-optimization` or `integration-test` story — closure work leaked out of its layer epic
- `STORIES-USER-TEST-001` (WARNING for non-required types): Story type other than build/integration-test/runtime-bootstrap is missing a `## How to Test (User)` section — non-blocking but recommended
- `STORIES-DOCS-001` (WARNING for `build` stories that create files under `src/`/`airflow/`/`_infra/`): A build story creating runtime files lists no documentation updates — runbook drift is likely

### INFO (suggestions for improvement)
- Placeholder text remaining ([TBD], [TODO])
- Estimation support tables populated
- Technical notes present in stories
- Traceability matrix populated in backlog

## Backlog Sections Reference

A complete backlog contains:

**BACKLOG index (7 sections)**:
- Executive Summary, Epic Overview, Dependency Graph, Sprint Plan,
  Traceability Matrix, Risks & Assumptions, Version History

**Each EPIC file**:
- Objective, Scope, Stories table, Acceptance Criteria, Risks

**Each STORY file**:
- User Story, Description, Acceptance Criteria, Technical Notes, Estimation Support
- **Testing** — table of automated coverage rows (Unit / Integration / Smoke / DQ / Benchmark) per story type, each row mapping to a verifier in `## Verification`
- **How to Test (User)** — prerequisites + exact commands + expected output a human can run on their own machine (CRITICAL for build / integration-test / runtime-bootstrap)
- **Documentation Updates** — list of specific README / runbook sections this story must change (CRITICAL for runtime-bootstrap / integration-test / release)

## Step 2.5: Fix CRITICAL issues before presenting

If the validator reports CRITICAL issues, **fix them using the Edit tool
before presenting results to the user**. For content requiring user
judgment, use `AskUserQuestion`.

After fixing, re-run the validator to confirm CRITICALs are resolved.

## Step 3: Report findings

Call `AskUserQuestion` to ask which warnings the user wants fixed:

```json
{
  "questions": [
    {
      "question": "The validator found warnings. Which would you like me to fix?",
      "header": "Warnings",
      "multiSelect": false,
      "options": [
        { "label": "Fix all", "description": "Fix all warnings now" },
        { "label": "High-priority", "description": "Fix only traceability and dependency warnings" },
        { "label": "Report only", "description": "Leave warnings for later, just report them" }
      ]
    }
  ]
}
```

Format as a checklist:

```
Validation Results for outputs/stories/v1/

CRITICAL (must fix):
- [x] All critical issues have been auto-fixed

WARNING (should fix):
- [ ] STORY-02-003: Missing upstream traceability references
- [ ] Sprint 3: Over-allocated (45 pts vs 35 pt velocity)

INFO (nice to have):
- [ ] STORY-01-002: Estimation support table empty

Summary: 0 critical (fixed), 2 warnings, 1 info
```

## Step 4: Session memory

**Always write session notes.** Write to
`memory/stories/session-{YYYY-MM-DD}.md`:

- What was validated (backlog directory)
- CRITICAL/WARNING/INFO counts (before and after fixes)
- Fixes applied
- Remaining issues

### Correction Capture (MANDATORY)

After EVERY user correction — whether they edit the artifact, ask you to change
something, or reject a section — you MUST append a learning entry BEFORE continuing:

```bash
echo '{"skill": "validate-stories", "date": "{YYYY-MM-DD}", "correction": "{what the user said or changed}", "pattern": "{generalized rule}", "status": "pending"}' >> memory/stories/learnings-queue.jsonl
```


## Final Step: Apply Learnings

After validation completes, if `memory/stories/learnings-queue.jsonl` has pending entries,
invoke `/scrum-master-plugin:apply-learnings` before finishing.

## Learnings & Corrections

> **Meta-rules for adding learnings:**
> 1. Each learning MUST be an absolute directive ("Always X", "Never Y")
> 2. Lead with the problem, then the fix: "When X happens, do Y"
> 3. Include a concrete command or example, not just prose
> 4. One learning per bullet — no compound rules
> 5. Delete learnings that contradict each other; keep the newer one
> 6. Maximum 20 learnings per skill — if at capacity, merge related items

### Active Learnings

_No learnings recorded yet. Learnings are added when corrections occur during skill execution._
