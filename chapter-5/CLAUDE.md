# Chapter 5: Story-Driven Implementation — Developer Agent

## Overview

Chapter 5 implements the Developer Agent as a Claude Code Plugin, translating
approved LLD artifacts and Scrum stories into production-ready code: Airflow
DAGs, CI/CD pipeline configs, and the Bronze config-driven ingestion framework.

**Artifact chain (upstream)**: DRD → HLD → DMS → STM → DQS → LLD → Stories → **Code**

## Plugin

### Developer Plugin

Lives in `developer-plugin/` and is defined by `developer-plugin/.claude-plugin/plugin.json`.

- `developer-plugin/skills/create-scaffold/`, `update-scaffold/`, `validate-scaffold/`
- `developer-plugin/skills/create-dag/`, `update-dag/`, `validate-dag/`
- `developer-plugin/skills/create-pipeline/`, `update-pipeline/`, `validate-pipeline/`
- `developer-plugin/skills/create-ingestion/`, `update-ingestion/`, `validate-ingestion/`
- `developer-plugin/skills/implement-stories/` — orchestrate create-/update- skills across stories/epics/sprints
- `developer-plugin/skills/validate-stories/` — verify story/epic ACs via heuristic scan + downstream validator
- `developer-plugin/skills/complete-stories/` — hard-gated completion; flips Status only when every child + AC is Done
- `developer-plugin/skills/apply-learnings/` — apply corrections from learnings queue
- `developer-plugin/hooks/` — PreToolUse (destructive-op guard) + PostToolUse (auto-validate + learnings)
- `developer-plugin/scripts/` — hook scripts (enforce-readonly-queries, validate-output-hook, check-learnings-queue)

## Installing the Plugin

From the repo root:
```bash
/plugin marketplace add ./chapter-5
/plugin install developer-plugin@rdewai-chapter5-plugins
```

## Directory Layout

- `inputs/lld/v{N}/` — approved LLD (source of truth for code generation)
- `inputs/stories/v{N}/` — sprint backlog (BACKLOG index + EPIC/STORY files)
- `inputs/dqs/v{N}/se-rules/` — Spark Expectations YAML rule files per table
- `inputs/stm/v{N}/` — Source-to-Target Mapping workbook (column reference)
- `patient_360/` — generated project code
  - `src/patient_360/bronze/` — ingestion_runner, ingestion_factory, spark_submit_wrapper
  - `src/patient_360/utils/` — se_runner (Spark Expectations wrapper)
  - `airflow/dags/` — generated Airflow DAG files
  - `airflow/configs/` — per-table YAML ingestion configs
  - `contracts/` — StructType schema YAML files (owned by Data Modeler)
  - `dq_rules/` — Spark Expectations YAML rule files (synced from inputs/dqs/)
  - `_infra/ci/` — CI/CD pipeline configs (GitHub Actions / GitLab CI)
  - `tests/bronze/` — unit and integration tests for the ingestion framework
- `developer-plugin/` — Developer Agent plugin
- `memory/developer/` — learnings queue (learnings-queue.jsonl)

## Story → Skill Map (content-based classification)

The plugin is project-agnostic. Story and epic numbers are NOT stable across
projects — `EPIC-02` may be ingestion in one project and something else in
another. Each story is classified from its acceptance-criteria content:

| `skill_kind` classifier verdict | Triggers on AC content referencing…                                           | Generator triplet                                         |
|---------------------------------|-------------------------------------------------------------------------------|-----------------------------------------------------------|
| `scaffold`                      | `pyproject.toml`, `Makefile`, `src/<name>/utils/`, `contracts/`, `dq_rules/`, DDL, docker | `create-scaffold` / `update-scaffold` / `validate-scaffold` |
| `dag`                           | `airflow/dags/<name>.py`, `TaskGroup`, `@dag`, `default_args`                 | `create-dag` / `update-dag` / `validate-dag`              |
| `ingestion`                     | `airflow/configs/<table>.yml`, `src/<name>/bronze/`, `ingestion_runner`, `se_runner`, `empty_input_behavior`, `spark_expectations` | `create-ingestion` / `update-ingestion` / `validate-ingestion` |
| `pipeline`                      | `.github/workflows/`, `_infra/ci/…`, `.gitlab-ci.yml`                        | `create-pipeline` / `update-pipeline` / `validate-pipeline` |
| `unknown`                       | No rule matched — orchestrator asks the user to override or tighten the story | —                                                         |

For story/epic/sprint orchestration, prefer the three story-lifecycle skills
over invoking generators directly:

- `/developer-plugin:implement-stories STORY-NN-NNN|EPIC-NN|'Sprint N'` —
  classifies each story, dispatches to the correct create-*/update-* skill
  (topo-sorted by `Depends On`); never edits story markdown.
- `/developer-plugin:validate-stories <same-arg>` — read-only AC compliance
  report; combines heuristic scan with the matching `validate-*` skill.
- `/developer-plugin:complete-stories <same-arg>` — atomic hard gate; flips
  Story/Epic Status and ticks ACs only when every child story + AC passes.
  Edits nothing if any target in the set blocks.

### Workspace Discovery (no dispatch yaml)

The story-lifecycle skills discover the workspace automatically: starting
from CWD they walk upward to find a directory with both `inputs/stories/`
and a cookiecutter-style project (`pyproject.toml` + `src/<name>/`). That
anchor supplies the `{workspace_root}`, `{project_root}`, `{project_name}`,
`{stories_dir}`, and `{learnings_queue}` paths used throughout every
skill. No config file, no epic mapping — the agent reads each story and
classifies it at runtime.

Inspect the resolved paths with:

```bash
python3 chapter-5/developer-plugin/skills/validate-stories/scripts/status_rollup.py --mode discover

# Classify a specific story:
python3 chapter-5/developer-plugin/skills/validate-stories/scripts/status_rollup.py --mode classify --story STORY-02-002
```

## Upstream Approval Gate

`create-dag` and `create-ingestion` require the LLD to have `Status: Approved`
(or `Updated - Pending Review` with explicit user consent). Use the
`technical-lead-plugin:approve-lld` skill from Chapter 4 to approve the LLD.

## Learnings & Corrections Protocol

After ANY user correction during skill execution, the agent MUST immediately
append to the learnings queue:

```bash
echo '{"skill": "{skill-name}", "date": "{YYYY-MM-DD}", "correction": "{what}", "pattern": "{rule}", "status": "pending"}' \
  >> chapter-5/memory/developer/learnings-queue.jsonl
```

At the end of any skill session where the learnings queue has pending entries,
run `/developer-plugin:apply-learnings` before finishing.

## Key Commands

```bash
make dev-setup   # Install dependencies in patient_360/
make test        # Run all tests (patient_360/)
make lint        # Run ruff on src/
```
