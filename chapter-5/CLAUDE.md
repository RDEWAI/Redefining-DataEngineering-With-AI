# Chapter 5: Full-Chain Workspace — Planning + Story-Driven Implementation

## Overview

Chapter 5 is a **workspace** that runs the entire data-engineering pipeline
end-to-end — from an initial business request through generated code. It
ships two implementation-phase plugins: the Scrum Master (story decomposition)
and the Developer (code generation). The six planning plugins (DRD → LLD)
are sourced directly from `chapter-4/` — one canonical implementation, used
from both chapters.

**Artifact chain**: DRD → HLD → DMS → STM → DQS → LLD → **Stories** → **Code**

> Chapter-4 is the canonical home for the planning plugins (DRD → LLD).
> Chapter-5 reuses them and adds the Scrum Master and Developer plugins for
> the full implementation loop.

## Plugins

Chapter-5 ships two plugins (`scrum-master-plugin`, `developer-plugin`) under
`chapter-5/.claude-plugin/marketplace.json` (`rdewai-chapter5-plugins`).
The six upstream planning plugins (DRD → LLD) come from
`chapter-4/.claude-plugin/marketplace.json` (`rdewai-plugins`).

### Planning plugins (DRD → LLD) — sourced from chapter-4

| Plugin | Artifact | Skills |
|---|---|---|
| `ba-plugin` | DRD (markdown) | create-drd, update-drd, validate-drd, approve-drd |
| `architect-plugin` | HLD (markdown) | create-hld, update-hld, validate-hld, approve-hld |
| `data-modeler-plugin` | DMS (markdown) | create-dms, update-dms, validate-dms, approve-dms |
| `mapping-analyst-plugin` | STM (**.xlsx**) | create-stm, update-stm, validate-stm, approve-stm |
| `dq-engineer-plugin` | DQS (markdown + SE YAML) | create-dqs, update-dqs, validate-dqs, generate-se-rules, approve-dqs |
| `technical-lead-plugin` | LLD (markdown + config + DAG + impl-sequence) | create-lld, update-lld, validate-lld, generate-config-template, apply-learnings, approve-lld |

The chapter-5 workspace still uses the same `inputs/{role}/v{N}/` and
`outputs/{artifact}/v{N}/` folder-versioned layout — only the plugin code
lives in chapter-4.

### Scrum Master plugin (Sprint Backlog)

`scrum-master-plugin/` decomposes the approved LLD into a Sprint Backlog of
epics and user stories.

- **Skills**: create-stories, update-stories, validate-stories, approve-stories
- **Inputs**: all 6 upstream artifacts + `inputs/stories/v{N}/` (team capacity, story standards)
- **Outputs**: `outputs/stories/v{N}/` (BACKLOG index + EPIC and STORY markdown files)
- **Story IDs**: `STORY-{NN}-{NNN}` (2-digit epic + 3-digit story)

### Developer plugin (Code)

`developer-plugin/` reads approved Stories + LLD and emits Airflow DAGs,
CI/CD pipeline configs, and the Bronze config-driven ingestion framework.

- **Skills**: create-scaffold/update/validate, create-dag/update/validate, create-pipeline/update/validate, create-ingestion/update/validate, implement-stories, validate-stories, complete-stories, apply-learnings, refresh-libraries
- **Inputs**: `outputs/lld/v{N}/`, `outputs/stories/v{N}/`, `outputs/dqs/v{N}/se-rules/`, `outputs/stm/v{N}/` (read directly from upstream plugins) + `inputs/code/v{N}/` (coding-pattern + library-version handbook — developer-specific)
- **Outputs**: generated project code under `patient_360/`

## Installing the plugins

From the repo root:

```bash
# Planning plugins (DRD → LLD) — single source of truth in chapter-4
/plugin marketplace add ./chapter-4
/plugin install ba-plugin@rdewai-plugins
/plugin install architect-plugin@rdewai-plugins
/plugin install data-modeler-plugin@rdewai-plugins
/plugin install mapping-analyst-plugin@rdewai-plugins
/plugin install dq-engineer-plugin@rdewai-plugins
/plugin install technical-lead-plugin@rdewai-plugins

# Implementation plugins (Stories + Code) — chapter-5
/plugin marketplace add ./chapter-5
/plugin install scrum-master-plugin@rdewai-chapter5-plugins
/plugin install developer-plugin@rdewai-chapter5-plugins
```

## Directory Layout

### Plugins

Local to chapter-5:
- `scrum-master-plugin/`
- `developer-plugin/`

Sourced from `chapter-4/`:
- `ba-plugin/`, `architect-plugin/`, `data-modeler-plugin/`,
  `mapping-analyst-plugin/`, `dq-engineer-plugin/`, `technical-lead-plugin/`

### Workspace data

Inputs (folder-versioned `v{N}/`):
- `inputs/drd/`, `inputs/architect/`, `inputs/dms/`, `inputs/stm/`, `inputs/dqs/` — per-role user-provided inputs for the planning plugins
- `inputs/lld/`, `inputs/stories/` — per-role user-provided inputs (team capacity, standards) for technical-lead-plugin / scrum-master-plugin
- `inputs/code/` — developer-plugin's own inputs: coding-pattern handbook + `LIBRARIES.md` version catalogue

Note: the developer-plugin reads upstream artifacts (LLD, Stories, DQS, STM)
directly from `outputs/{artifact}/v{N}/`. It only keeps its own
`inputs/code/v{N}/` for developer-specific inputs.

Outputs (folder-versioned `v{N}/`):
- `outputs/drd/`, `outputs/hld/`, `outputs/dms/`, `outputs/stm/`, `outputs/dqs/`, `outputs/lld/`
- `outputs/stories/` — BACKLOG index + EPIC/STORY markdown files

Session memory (cross-session persistence with learnings queues):
- `memory/{drd,hld,dms,stm,dqs,lld,stories,developer}/`

Generated project code:
- `patient_360/src/patient_360/bronze/`, `patient_360/src/patient_360/utils/`
- `patient_360/airflow/dags/`, `patient_360/airflow/configs/`
- `patient_360/contracts/`, `patient_360/dq_rules/`, `patient_360/_infra/ci/`
- `patient_360/tests/bronze/`

Tests:
- `tests/` — unit + integration tests for all 8 plugins

## Artifact Status Lifecycle

All artifacts use a 3-state status tracked in the metadata table:

```
Draft  →  Updated - Pending Review  →  Approved
  ↑              ↑                        │
  └──────────────┴── (update cycles) ─────┘
```

Each plugin has an `approve-{artifact}` skill that sets Status to `Approved`.

## Upstream Approval Gate

Before creating a downstream artifact, ALL required upstream artifacts MUST
have `Status: Approved`. This gate has no override.

| create-* Skill | Required Approved Upstream |
|---|---|
| create-drd | None (first in chain) |
| create-hld | DRD |
| create-dms | DRD, HLD |
| create-stm | DRD, HLD, DMS |
| create-dqs | DRD, DMS, STM |
| create-lld | DRD, HLD, DMS, STM, DQS |
| create-stories | DRD, HLD, DMS, STM, DQS, LLD |
| create-scaffold / create-dag / create-ingestion / create-pipeline | LLD (+ Stories for implement-stories) |

## Planning → Developer Handoff

The planning plugins (DRD … Stories) write into `outputs/{artifact}/v{N}/`.
The developer-plugin reads these upstream artifacts **directly** from
`outputs/{lld,stories,dqs,stm,dms}/v{N}/` — no copy step is required.

Under `chapter-5/`, `inputs/` is reserved for two categories:

- Per-role user-provided inputs to the planning plugins (team capacity,
  standards, catalogs).
- `inputs/code/v{N}/` — developer-plugin's own inputs (coding-pattern
  handbook + `LIBRARIES.md` version catalogue).

The developer-plugin never reads upstream artifacts from `inputs/`. Once a
planning artifact is `Approved` in `outputs/`, the developer-plugin picks it
up automatically.

## `validate-stories` namespace note

Two plugins ship a `validate-stories` skill with different purposes:

- `/scrum-master-plugin:validate-stories` — validates backlog markdown
  structure, story format, and upstream traceability.
- `/developer-plugin:validate-stories` — validates acceptance-criteria
  implementation by scanning generated code + running downstream `validate-*`
  skills.

Always use the fully qualified name (`<plugin>:validate-stories`) so the
right skill fires.

## Versioning Convention

All inputs and outputs use **folder-based versioning** (`v1/`, `v2/`, etc.).
The latest version folder is the source of truth for that component. Agents
auto-discover the latest version via:

```bash
ls -d {path}/v* | sort -V | tail -1
```

### Update Versioning Rules (3 Scenarios)

When an `update-*` skill is invoked, it MUST follow one of these three scenarios:

**Scenario A — Cross-version (v1 → v2)**
- **Trigger**: `inputs/{role}/v{N+1}/` exists but `outputs/{artifact}/v{N+1}/` does not, OR user explicitly requests a new version.
- **Action**: Create `outputs/{artifact}/v{N+1}/`, copy latest artifact from v{N} with today's date in filename, rename the original as `.bak`, apply incremental edits. Set metadata version to `{N+1}.0`, status to `Draft`.

**Scenario B — Same version, different date**
- **Trigger**: Latest artifact filename date ≠ today.
- **Action**: Copy old file to new file with today's date, rename old as `.bak`, apply incremental edits. Bump minor version.

**Scenario C — Same version, same date (re-run)**
- **Trigger**: Latest artifact filename date = today.
- **Action**: Edit in-place, bump minor version. No `.bak` created.

## Learnings & Corrections Protocol

After ANY user correction during skill execution, the agent MUST immediately
append to the role's learnings queue:

```bash
echo '{"skill": "{skill-name}", "date": "{YYYY-MM-DD}", "correction": "{what}", "pattern": "{rule}", "status": "pending"}' \
  >> memory/{role}/learnings-queue.jsonl
```

At the end of any skill session where the learnings queue has pending entries,
run the matching `/apply-learnings` skill (`technical-lead-plugin`,
`developer-plugin`) before finishing.

The planning plugins (sourced from chapter-4) resolve the chapter root via
`CHAPTER4_ROOT`, so their learnings queues live under `chapter-4/memory/`.
The chapter-5 plugins (`scrum-master`, `developer`) resolve via
`CHAPTER5_ROOT` and write to `chapter-5/memory/`.

## Key Commands

```bash
make dev-setup          # Install dependencies (uv sync)
make test               # Run all tests
make validate-drd       # Validate all DRDs in outputs/drd/
make validate-hld       # Validate all HLDs in outputs/hld/
make validate-dms       # Validate all DMSs in outputs/dms/
make validate-stm       # Validate all STMs in outputs/stm/
make validate-dqs       # Validate all DQSs in outputs/dqs/
make validate-lld       # Validate all LLDs in outputs/lld/
make validate-stories   # Validate all Backlogs in outputs/stories/
make lint               # Run ruff linter
make format             # Auto-format code
make clean              # Remove caches
```
