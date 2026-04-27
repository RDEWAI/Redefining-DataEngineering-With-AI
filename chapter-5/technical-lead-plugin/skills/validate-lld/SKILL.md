---
name: validate-lld
description: >
  Validates a Low-Level Design (LLD) document against completeness and quality
  standards. Checks all 14 required sections, upstream artifact references,
  DAG specification, code architecture, configuration schema, and traceability.
  Reports issues as CRITICAL, WARNING, or INFO with suggested fixes.
  Also known as: LLD review, implementation design audit, tech spec validation.
  Input formats: LLD Markdown (.md) file.
  Output format: Validation report with severity-ranked findings.
  Use when the user asks to:
  - Validate, check, review, verify, or audit an LLD
  - Assess LLD completeness or implementation quality
  - Find issues or gaps in a low-level design document
  - Run quality checks on an LLD before development
  - "Check if the LLD is ready for the development team"
argument-hint: "[lld-file-path]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion, Skill
hooks:
  before:
    - matcher: Bash
      script: "${CLAUDE_PLUGIN_ROOT}/scripts/enforce-readonly-queries.py"
---

# Validate Low-Level Design Document

You are a senior Technical Lead. You sit downstream of the Business Analyst
(DRD), Data Architect (HLD), Data Modeler (DMS), Mapping Analyst (STM), and
DQ Engineer (DQS). Your job is to ensure Low-Level Design documents meet
completeness and quality standards before handoff to the development team.

## Step 1: Run the validator

Run the Python validator script on the specified file or all LLDs:

```bash
# Single file
uv run python technical-lead-plugin/skills/validate-lld/scripts/validate_lld.py $ARGUMENTS

# All LLDs in the latest version folder
LATEST_LLD_DIR=$(ls -d outputs/lld/v* | sort -V | tail -1)
uv run python technical-lead-plugin/skills/validate-lld/scripts/validate_lld.py --all "$LATEST_LLD_DIR"
```

## Step 2: Interpret results

The validator checks rules across three severity levels:

### CRITICAL (blocks downstream work)
- All 14 required sections present (Design Overview through Version History)
- Metadata complete (version, date, author, status, all 5 upstream refs)
- Design Overview exists with meaningful content (≥2 sentences)
- DAG Specification has task table with ≥3 data rows
- Task Implementation Details has per-task specs with ≥3 rows
- Configuration Schema has parameter table with ≥3 rows
- Upstream Artifact References cites all 5 upstream docs (DRD, HLD, DMS, STM, DQS)
- **§6 declares `local_executor_mode`** in a fenced YAML block, value ∈ {`in-airflow-local[*]`, `sidecar-spark`, `external-cluster`}. Without this, the runtime stack the bootstrap story smoke-tests is undefined.
- **Bronze runner contract is UC-wired** — §2 / §5 must use `UCSingleCatalog` + `saveAsTable("unity.bronze.<table>")`, NOT path-based Delta (`warehouse/{env}/bronze/...` or `format("delta").save(...)`). LLD Decision 15 forbids path-based Bronze writes; spokane's first green run revealed they leave Unity Catalog empty until manual `docker cp` + REST registration.
- **`spark-expectations` is not pinned below 2.10** anywhere in the LLD. The YAML rule loader (`spark_expectations.rules.load_rules_from_yaml`) was added in v2.10.0 (PR #300) — earlier 2.x releases break every generated `se_runner.py` and force a forbidden `BRONZE_SKIP_SE=1` bypass.

### WARNING (needs attention)
- Upstream traceability — at least 5 citations with § section references
- Error Handling covers retry, SE `_error` table (row_dq), SE stats table (agg_dq/query_dq), ingest DLQ (pre-validation only), and alerting
- Deployment mentions DEV and PROD environments
- Monitoring has specific metric names or metrics table
- DAG section has ≥1 Mermaid diagram
- Decision Log uses Options Considered / Rationale format
- Performance section has numeric values (MB, GB, seconds, partitions)
- **§6 split into §6.1–§6.5 subsections** (Compute & Local Executor Mode / Joins / Shuffle & Parallelism / Caching / Partition Tuning). Naming is load-bearing — downstream Scrum Master `STORIES-BOOTSTRAP-COVERAGE-001` and per-layer `performance-optimization` stories cite the subsection numbers.
- **§7 Configuration Schema declares the UC catalog block** — `catalog_uc_uri`, `catalog_bronze_catalog_name`, `catalog_bronze_schema`. Both underscore (`catalog_uc_uri`) and dotted (`catalog.uc_uri`) forms are accepted.
- **`LLD-PHASED-CONTRACT-001`** — §2 / §5 sections that mix bootstrap-mode prose (`soft-import`, `bootstrap mode`, `try/except ImportError`, `PENDING IMPLEMENTATION`) with fail-closed prose (`fail-closed`, `must be removed`, `hard error`) WITHOUT an explicit TEMP / `bootstrap phase only` callout fire WARNING. Spokane's STORY-02-001 vs STORY-02-004 collision (2026-04-26) was traced to LLD §2.3 reading like a permanent contract while §8.6 / Decision 14 carried the actual lifecycle — the scrum-master generated contradictory ACs from the unmarked §2.3 prose. §8 is exempt (it's the lifecycle owner by design).

### INFO (suggestions for improvement)
- Placeholder text remaining ([TBD], [TODO])
- Deployment mentions rollback procedures
- DAG section mentions critical path
- Config template YAML exists alongside LLD
- **§13 records Decision 15 (Bronze UC wiring) when §2/§5 reference `UCSingleCatalog` / `unity.bronze.<table>`.** Future maintainers need the rationale + trade-off so they don't drift back to path-based Delta.

## LLD Sections Reference

A complete LLD contains these 14 sections:
- **1. Design Overview**: Implementation approach, key decisions at a glance
- **2. Code Architecture**: Project structure, coding conventions, templates. **§2.3 Bronze runner contract** uses `UCSingleCatalog` + `saveAsTable("unity.bronze.<table>")` (Decision 15) — never path-based Delta.
- **3. File Formats & Storage Layout**: Storage format, compression, partitioning
- **4. DAG Specification**: Task inventory, dependencies, Mermaid diagram, scheduling. **§4.2 task-type set** drives `airflow/jobs/run_<task_type>.py` wrapper auto-generation.
- **5. Task Implementation Details**: Per-task I/O contracts, transform refs, DQ checks
- **6. Performance & Optimization**: **§6.1 Compute & Local Executor Mode** (mandatory `local_executor_mode` fenced YAML); §6.2 Joins; §6.3 Shuffle/Parallelism; §6.4 Caching; §6.5 Partition Tuning. Subsection numbering is load-bearing for downstream rules.
- **7. Configuration Schema**: Parameters with per-environment defaults. Catalog block: `catalog_uc_uri`, `catalog_bronze_catalog_name`, `catalog_bronze_schema`.
- **8. Error Handling**: Retry policies, SE `_error` table (row_dq), SE stats/detailed tables (agg_dq/query_dq), ingest DLQ (pre-validation only), alerting
- **9. Deployment**: Environments, promotion, rollback, health checks. `_infra/docker/Dockerfile.airflow` is required when `local_executor_mode` is `in-airflow-local[*]` or `sidecar-spark`.
- **10. Monitoring**: Metrics, dashboards, alerting rules
- **11. Upstream Artifact References**: Hub cross-reference to DRD, HLD, DMS, STM, DQS. `spark-expectations` row pins **>=2.10.0** (YAML rule loader floor).
- **12. Traceability Matrix**: Requirements → implementation mapping
- **13. Decision Log**: Options Considered, Rationale, Trade-off. **Decision 15** = Bronze UC wiring policy.
- **14. Version History**: Version tracking table

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
        { "label": "High-priority", "description": "Fix only high-priority warnings" },
        { "label": "Report only", "description": "Leave warnings for later, just report them" }
      ]
    }
  ]
}
```

Format as a checklist:

```
Validation Results for LLD-2026-03-22-patient-360.md

CRITICAL (must fix):
- [x] All critical issues have been auto-fixed

WARNING (should fix):
- [ ] DAG Specification: No Mermaid diagram for task dependencies
- [ ] Error Handling: Missing SE `_error` table reference for row_dq, or missing ingest DLQ scope statement

INFO (nice to have):
- [ ] Deployment: No rollback procedure described

Summary: 0 critical (fixed), 2 warnings, 1 info
```

## Step 4: Session memory

**Always write session notes.** Write to
`memory/lld/session-{YYYY-MM-DD}.md`:

- What was validated (LLD filename)
- CRITICAL/WARNING/INFO counts (before and after fixes)
- Fixes applied
- Remaining issues

### Correction Capture (MANDATORY)

After EVERY user correction — whether they edit the artifact, ask you to change
something, or reject a section — you MUST append a learning entry BEFORE continuing:

```bash
echo '{"skill": "validate-lld", "date": "{YYYY-MM-DD}", "correction": "{what the user said or changed}", "pattern": "{generalized rule}", "status": "pending"}' >> memory/lld/learnings-queue.jsonl
```

**What counts as a correction:** user says "no, change X to Y", edits artifact
directly, rejects a proposed decision, or provides a specific value replacing
a vague one you generated. When in doubt, append it — false positives are filtered
during apply-learnings.


## Final Step: Apply Learnings

After validation completes, if `memory/lld/learnings-queue.jsonl` has pending entries,
invoke `/technical-lead-plugin:apply-learnings` before finishing.

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

<!-- Example format:
- **L-001** (2026-03-20): Always re-run the validator after fixing CRITICAL issues — never assume the fix resolves all related checks.
- **L-002** (2026-03-21): Never skip Section 11 validation — missing upstream references indicate the LLD is not a proper hub document.
-->
