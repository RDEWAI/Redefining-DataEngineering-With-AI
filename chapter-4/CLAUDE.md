# Chapter 4: Planning with Context — Multi-Agent Artifact Chain

## Overview

This chapter implements the full planning workflow as Claude Code Plugins,
each role producing a structured artifact that feeds the next.

**Artifact chain**: DRD → **HLD** → **DMS** → **STM** → **DQS** → **LLD**

## Plugins

### BA Plugin (from Chapter 3)

The plugin lives in `ba-plugin/` and is defined by `ba-plugin/.claude-plugin/plugin.json`.

- `ba-plugin/skills/` - Skills: create-drd, update-drd, validate-drd, approve-drd
- `ba-plugin/hooks/` - PostToolUse hook for automatic DRD validation
- `ba-plugin/scripts/` - Hook scripts (validate-drd-hook.py, enforce-readonly-queries.py)

### Architect Plugin

The plugin lives in `architect-plugin/` and is defined by
`architect-plugin/.claude-plugin/plugin.json`.

- `architect-plugin/skills/` - Skills: create-hld, update-hld, validate-hld, approve-hld
- `architect-plugin/hooks/` - PostToolUse hook for automatic HLD validation
- `architect-plugin/scripts/` - Hook scripts (validate-hld-hook.py, enforce-readonly-queries.py)

**Inputs**: Latest DRD from `outputs/drd/v{N}/` + `inputs/architect/v{N}/` (infrastructure constraints, team capabilities, technology catalog)

**Outputs**: HLD documents in `outputs/hld/v{N}/`

### Data Modeler Plugin

The plugin lives in `data-modeler-plugin/` and is defined by
`data-modeler-plugin/.claude-plugin/plugin.json`.

- `data-modeler-plugin/skills/` - Skills: create-dms, update-dms, validate-dms, approve-dms
- `data-modeler-plugin/hooks/` - PostToolUse hook for automatic DMS validation
- `data-modeler-plugin/scripts/` - Hook scripts (validate-dms-hook.py, enforce-readonly-queries.py)

**Inputs**: Latest HLD from `outputs/hld/v{N}/` + DRD from `outputs/drd/v{N}/` + `inputs/dms/v{N}/`

**Outputs**: DMS documents in `outputs/dms/v{N}/`

### Mapping Analyst Plugin

The plugin lives in `mapping-analyst-plugin/` and is defined by
`mapping-analyst-plugin/.claude-plugin/plugin.json`.

- `mapping-analyst-plugin/skills/` - Skills: create-stm, update-stm, validate-stm, approve-stm
- `mapping-analyst-plugin/hooks/` - PostToolUse hook for automatic STM validation
- `mapping-analyst-plugin/scripts/` - Hook scripts (validate-stm-hook.py, enforce-readonly-queries.py)

**Inputs**: Latest DMS from `outputs/dms/v{N}/` + HLD from `outputs/hld/v{N}/` + `inputs/stm/v{N}/` (transformation standards, code system mappings)

**Outputs**: STM Excel workbooks (.xlsx) in `outputs/stm/v{N}/`

**Note**: STM output is **.xlsx** (Excel workbook with 8 sheets), not markdown. Uses **openpyxl** for generation and validation.

### DQ Engineer Plugin

The plugin lives in `dq-engineer-plugin/` and is defined by
`dq-engineer-plugin/.claude-plugin/plugin.json`.

- `dq-engineer-plugin/skills/` - Skills: create-dqs, update-dqs, validate-dqs, generate-se-rules, approve-dqs
- `dq-engineer-plugin/hooks/` - PostToolUse hook for automatic DQS validation
- `dq-engineer-plugin/scripts/` - Hook scripts (validate-dqs-hook.py, enforce-readonly-queries.py)

**Inputs**: Latest STM from `outputs/stm/v{N}/` + DMS from `outputs/dms/v{N}/` + DRD from `outputs/drd/v{N}/` + `inputs/dqs/v{N}/` (DQ standards, SLA definitions, SE config template)

**Outputs**: DQS documents in `outputs/dqs/v{N}/` + Spark-Expectations YAML rules in `outputs/dqs/v{N}/se-rules/`

**Note**: DQS has **4 skills** (3 core + 1 bonus). The `generate-se-rules` skill converts DQS rules to per-table **Spark-Expectations YAML** files compatible with spark-expectations >= 2.6.0.

### Technical Lead Plugin

The plugin lives in `technical-lead-plugin/` and is defined by
`technical-lead-plugin/.claude-plugin/plugin.json`.

- `technical-lead-plugin/skills/` - Skills: create-lld, update-lld, validate-lld, generate-config-template, approve-lld
- `technical-lead-plugin/hooks/` - PostToolUse hook for automatic LLD validation
- `technical-lead-plugin/scripts/` - Hook scripts (validate-lld-hook.py, enforce-readonly-queries.py)

**Inputs**: All 5 upstream artifacts (DRD, HLD, DMS, STM, DQS) + `inputs/lld/v{N}/` (development standards, infrastructure specs, orchestration patterns)

**Outputs**: LLD documents in `outputs/lld/v{N}/` + config templates in `outputs/lld/v{N}/config/` + DAG definitions in `outputs/lld/v{N}/dag/` + implementation sequence in `outputs/lld/v{N}/impl-sequence.md`

**Note**: LLD has **5 skills** (3 core + 1 bonus + apply-learnings). The create-lld workflow auto-generates 3 derived artifacts: **config template** (from §7), **DAG definition YAML + Mermaid diagram** (from §4), and **implementation sequence** (from §2/§4/§9/§12). The LLD is a **hub document** — it references upstream artifacts by section number instead of duplicating content.

> **Story generation has moved to chapter-5.** The Scrum Master plugin that produces the Sprint Backlog (epics + stories) now lives in `chapter-5/scrum-master-plugin/` alongside the Developer plugin that consumes it.

## Installing Plugins

From the repo root:
```bash
/plugin marketplace add ./chapter-4
/plugin install ba-plugin@rdewai-plugins
/plugin install architect-plugin@rdewai-plugins
/plugin install data-modeler-plugin@rdewai-plugins
/plugin install mapping-analyst-plugin@rdewai-plugins
/plugin install dq-engineer-plugin@rdewai-plugins
/plugin install technical-lead-plugin@rdewai-plugins
```

## Directory Layout

- `inputs/drd/v{N}/` - BA Agent input documents (folder-versioned)
- `inputs/architect/v{N}/` - Architect Agent input documents (folder-versioned)
- `inputs/dms/v{N}/` - Data Modeler input documents (folder-versioned)
- `inputs/stm/v{N}/` - Mapping Analyst input documents (folder-versioned)
- `inputs/dqs/v{N}/` - DQ Engineer input documents (folder-versioned)
- `outputs/drd/v{N}/` - Generated DRD files (folder-versioned)
- `outputs/hld/v{N}/` - Generated HLD files (folder-versioned)
- `outputs/dms/v{N}/` - Generated DMS files (folder-versioned)
- `outputs/stm/v{N}/` - Generated STM Excel workbooks (folder-versioned)
- `outputs/dqs/v{N}/` - Generated DQS files + SE rules YAML (folder-versioned)
- `inputs/lld/v{N}/` - Technical Lead input documents (folder-versioned)
- `outputs/lld/v{N}/` - Generated LLD files + config templates + DAG definitions + impl sequence (folder-versioned)
- `ba-plugin/` - BA Agent plugin
- `architect-plugin/` - Architect Agent plugin
- `data-modeler-plugin/` - Data Modeler Agent plugin
- `mapping-analyst-plugin/` - Mapping Analyst Agent plugin
- `dq-engineer-plugin/` - DQ Engineer Agent plugin
- `technical-lead-plugin/` - Technical Lead Agent plugin
- `tests/` - All unit tests

## Versioning Convention

All inputs and outputs use **folder-based versioning** (`v1/`, `v2/`, etc.).
The latest version folder is the source of truth for that component. Agents
auto-discover the latest version via:

```bash
ls -d {path}/v* | sort -V | tail -1
```

### Update Versioning Rules (3 Scenarios)

When an update skill is invoked, it MUST follow one of these three scenarios:

**Scenario A — Cross-version (v1 → v2)**
- **Trigger**: `inputs/{role}/v{N+1}/` exists but `outputs/{artifact}/v{N+1}/` does not, OR user explicitly requests a new version.
- **Action**: Create `outputs/{artifact}/v{N+1}/`, copy latest artifact from v{N} with today's date in filename, rename the original as `.bak`, apply incremental edits. Set metadata version to `{N+1}.0`, status to `Draft`.

**Scenario B — Same version, different date**
- **Trigger**: Latest artifact filename date ≠ today (e.g., `DRD-2026-02-10-...md` but today is `2026-03-31`).
- **Action**: Copy old file to new file with today's date, rename old as `.bak`, apply incremental edits. Bump minor version (e.g., 1.1 → 1.2). One active artifact file per version folder.

**Scenario C — Same version, same date (re-run)**
- **Trigger**: Latest artifact filename date = today.
- **Action**: Edit in-place, bump minor version (e.g., 1.1 → 1.2). No `.bak` created.

**Decision flowchart:**
```
update-{artifact} invoked
  ├─ v{N+1} input exists AND v{N+1} output missing? → Scenario A
  ├─ artifact date ≠ today? → Scenario B
  └─ artifact date = today → Scenario C
```

### Artifact Status Lifecycle

All artifacts use a 3-state status tracked in the metadata table:

```
Draft  →  Updated - Pending Review  →  Approved
  ↑              ↑                        │
  └──────────────┴── (update cycles) ─────┘
```

- **Draft**: Set on initial creation
- **Updated - Pending Review**: Set after any update (minor version bump)
- **Approved**: Set explicitly via `approve-{artifact}` skill — requires user/stakeholder sign-off

### Upstream Approval Gate

Before creating a downstream artifact, ALL required upstream artifacts MUST have `Status: Approved`. This is enforced in Phase 0 of each create skill.

| create-* Skill | Required Approved Upstream Artifacts |
|---|---|
| create-drd | None (first in chain) |
| create-hld | DRD |
| create-dms | DRD, HLD |
| create-stm | DRD, HLD, DMS |
| create-dqs | DRD, DMS, STM |
| create-lld | DRD, HLD, DMS, STM, DQS |

If any upstream artifact is not `Approved`, the create skill MUST stop and inform the user which artifacts need approval. This gate has no override.

## Learnings & Corrections Protocol

After ANY user correction during skill execution, the agent MUST immediately
append to the role's learnings queue:

```bash
echo '{"skill": "{skill-name}", "date": "{YYYY-MM-DD}", "correction": "{what}", "pattern": "{rule}", "status": "pending"}' >> memory/{role}/learnings-queue.jsonl
```

**What counts as a correction:** user says "no, change X to Y", edits artifact
directly, rejects a proposed decision, or provides a specific value replacing
a vague one you generated. When in doubt, append — false positives are filtered
during apply-learnings.

At the end of any skill session where the learnings queue has pending entries,
run `/apply-learnings` before finishing.

## Key Commands

```bash
make dev-setup      # Install dependencies
make test           # Run all tests
make validate-drd   # Validate all DRDs in outputs/drd/
make validate-hld   # Validate all HLDs in outputs/hld/
make validate-dms   # Validate all DMSs in outputs/dms/
make validate-stm   # Validate all STMs in outputs/stm/
make validate-dqs   # Validate all DQSs in outputs/dqs/
make validate-lld       # Validate all LLDs in outputs/lld/
make lint               # Run linter
```
