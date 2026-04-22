# Chapter 5: Story-Driven Implementation — Developer Agent

## Overview

Chapter 5 implements the Developer Agent as a Claude Code Plugin, translating
approved LLD artifacts and Scrum stories into production-ready code: Airflow
DAGs, CI/CD pipeline configs, and the Bronze config-driven ingestion framework.

**Artifact chain (upstream)**: DRD → HLD → DMS → STM → DQS → LLD → Stories → **Code**

## Plugin

### Developer Plugin

Lives in `developer-plugin/` and is defined by `developer-plugin/.claude-plugin/plugin.json`.

- `developer-plugin/skills/create-dag/`, `update-dag/`, `validate-dag/`
- `developer-plugin/skills/create-pipeline/`, `update-pipeline/`, `validate-pipeline/`
- `developer-plugin/skills/create-ingestion/`, `update-ingestion/`, `validate-ingestion/`
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

## Story → Skill Map

| Epic | Skill to invoke |
|------|----------------|
| EPIC-01 — Airflow DAG | `/developer-plugin:create-dag` |
| EPIC-02 — Bronze Ingestion | `/developer-plugin:create-ingestion` |
| EPIC-03 — CI/CD Pipeline | `/developer-plugin:create-pipeline` |

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
