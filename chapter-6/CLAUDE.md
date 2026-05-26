# Chapter 6: Silver and Gold Layer Implementation (Atomic)

## Overview

Chapter 6 extends the Patient 360 Medallion pipeline by implementing the
**Silver** and **Gold** layers on top of the Bronze framework delivered in
chapter-5.

Chapter 6 is **atomic** — it ships its own copy of the developer-plugin
extended with Silver and Gold skills. It does NOT source any plugin from
chapter-5. Planning artifacts (LLD, DMS, STM, DQS) are read by file path
from `chapter-4/outputs/` (artifact reuse — not plugin reuse).

- **Silver** — SCD Type 2 dimensions and cleansed clinical/reference/billing facts
- **Gold** — business-facing aggregates and patient-360 summary tables

**Artifact chain**: DRD → HLD → DMS → STM → DQS → LLD → Stories → **Code (Bronze → Silver → Gold)**

> Chapter-4 is the canonical home for the planning plugins (DRD → LLD).
> Chapter-5 hosts its own developer-plugin focused on Bronze + scaffolding.
> Chapter-6 ships an atomic developer-plugin that supersets chapter-5
> (same Bronze + scaffolding skills, plus new Silver and Gold skills).
> The two developer-plugins share the same name and cannot be installed
> simultaneously — pick one chapter at a time.

## Plugin

Chapter-6 ships exactly one plugin: `developer-plugin` under
`chapter-6/.claude-plugin/marketplace.json` (`rdewai-chapter6-plugins`).

### developer-plugin (Bronze + Silver + Gold)

Inherited from chapter-5 (unchanged behavior):
`create-scaffold`, `update-scaffold`, `validate-scaffold`,
`create-dag`, `update-dag`, `validate-dag`,
`create-ingestion`, `update-ingestion`, `validate-ingestion`,
`create-pipeline`, `update-pipeline`, `validate-pipeline`,
`implement-stories`, `validate-stories`, `complete-stories`,
`refresh-libraries`, `apply-learnings`.

New in chapter-6 (Silver and Gold layers):
`create-silver`, `update-silver`, `validate-silver`,
`create-gold`, `update-gold`, `validate-gold`.

New in chapter-6 v2.1 (post-DE-work lifecycle):
`pr-process` — opens a PR from a story branch, drives review/approval,
and tears down the developer sandbox via a pluggable driver
(`local-docker` shipped; the driver contract in
[`inputs/code/v1/teardown-pattern.md`](inputs/code/v1/teardown-pattern.md)
shows how to add `cloud-databricks` / `cloud-eks` drivers).

The CI/CD trio (`create-pipeline` / `update-pipeline` / `validate-pipeline`)
was extended to own three new workflow files that pair with `pr-process`:

- `_infra/ci/.github/workflows/pr-preview.yml` — PR-triggered preview deploy + always-teardown
- `_infra/ci/.github/workflows/sandbox-cleanup.yml` — calls the same teardown driver on `pull_request: closed`
- `_infra/ci/.github/workflows/promote.yml` — tag-driven promote with required-reviewer environment gate

(`apply-learnings` carries chapter-6 changes: single
`memory/developer/learnings-queue.jsonl` queue, plus cross-reference to
`developer-plugin/LLD-DEVIATIONS.md` so corrections that imply an LLD
adjustment are surfaced to the Technical Lead.)

## Installing the plugin

Chapter-6 is atomic — install chapter-4 planning + chapter-6 developer-plugin only.
DO NOT install the chapter-5 marketplace concurrently — it ships a
`developer-plugin` with the same name and would collide on the slash-command
namespace.

From the repo root:

```bash
# Planning plugins (DRD → LLD) — chapter-4
/plugin marketplace add ./chapter-4
/plugin install ba-plugin@rdewai-plugins
/plugin install architect-plugin@rdewai-plugins
/plugin install data-modeler-plugin@rdewai-plugins
/plugin install mapping-analyst-plugin@rdewai-plugins
/plugin install dq-engineer-plugin@rdewai-plugins
/plugin install technical-lead-plugin@rdewai-plugins

# Developer plugin (Bronze + Silver + Gold) — chapter-6
/plugin marketplace add ./chapter-6
/plugin install developer-plugin@rdewai-chapter6-plugins
```

Or from `chapter-6/`, run `make install-plugins`.

## Directory Layout

```
chapter-6/
├── developer-plugin/           # Atomic copy of chapter-5 developer-plugin + silver/gold skills
│   ├── skills/
│   │   ├── create-scaffold/    │  ├── create-silver/     <- NEW
│   │   ├── update-scaffold/    │  ├── update-silver/     <- NEW
│   │   ├── validate-scaffold/  │  ├── validate-silver/   <- NEW
│   │   ├── create-dag/         │  ├── create-gold/       <- NEW
│   │   ├── update-dag/         │  ├── update-gold/       <- NEW
│   │   ├── validate-dag/       │  ├── validate-gold/     <- NEW
│   │   ├── create-ingestion/   │  ├── apply-learnings/
│   │   ├── update-ingestion/   │  ├── implement-stories/
│   │   ├── validate-ingestion/ │  ├── validate-stories/
│   │   ├── create-pipeline/    │  ├── complete-stories/
│   │   ├── update-pipeline/    │  └── refresh-libraries/
│   │   └── validate-pipeline/
│   ├── scripts/                # Hook scripts + utilities (resolve_versions, verify_acs, …)
│   ├── hooks/hooks.json
│   ├── agents/
│   └── LLD-DEVIATIONS.md       # Tracks LLD adjustments triggered by chapter-6 work
├── patient_360/                # Generated project code (extended from chapter-5 baseline)
│   └── src/patient_360/{bronze,silver,gold,utils}/
├── memory/developer/           # Single learnings queue (mirrors chapter-5 convention)
├── inputs/                     # Per-role user-provided inputs
├── outputs/                    # Plugin output artifacts (if any)
├── tests/                      # Plugin unit tests
└── Makefile, CLAUDE.md, pyproject.toml, .claude-plugin/marketplace.json
```

### Cross-chapter artifact references (read-only)

Chapter-6 reads planning artifacts and stories by file path — no plugin
install needed from chapter-4 or chapter-5 at runtime:

- LLD / DMS / STM / DQS → `chapter-4/outputs/{lld,dms,stm,dqs}/v*/`
- Stories → `chapter-5/outputs/stories/v*/` (or chapter-6 generates new
  stories via the inherited `implement-stories` flow — TBD)

These are file references, not plugin dependencies. Each chapter remains
atomic in its plugin code.

## Silver Layer Scope

Per LLD §2.2, §5.2, §6.4, and DMS §3:

- **Pattern**: Bronze → Silver via PySpark + Delta `MERGE INTO` for SCD2
- **SCD2 dimensions**: `clinical_patients`, `reference_organizations`,
  `reference_providers`, `reference_payers`
- **Cleansed facts**: `clinical_encounters`, `clinical_conditions`,
  `clinical_medications`, `clinical_observations`, `clinical_allergies`,
  `clinical_immunizations`, `clinical_procedures`, `clinical_careplans`,
  `billing_claims`
- **DQ gate**: Spark-Expectations `row_dq` + `agg_dq` runs BEFORE the
  MERGE; failures route to `<table>_error` (LLD §8.2)
- **Reusable helper**: `src/patient_360/utils/scd2.py::apply_scd2(df,
  target_path, natural_keys, hash_columns, effective_date)` —
  returns `{rows_inserted, rows_closed, rows_unchanged}` metrics dict.
  Spark session derived from `df.sparkSession`. Caller runs DQ before
  the call.

## Gold Layer Scope

Per LLD §2.3, §5.3, §6.5, and DMS §4:

- **Pattern**: Silver → Gold via PySpark joins/aggregations writing Delta tables
- **Phase 1 Gold tables**: `patient_summary` (search card),
  `patient_clinical_history` (full profile), `patient_billing_summary`
- **DQ gate**: `agg_dq` / `query_dq` rules verify business invariants

## LLD Deviations

`developer-plugin/LLD-DEVIATIONS.md` tracks every place where the
chapter-6 plugin implements something differently from the published LLD.
Three deviations have already been folded into LLD v1.13 (2026-05-19):

1. `scd2.py` signature corrected to include `target_path`
2. §5.2 "DQ Check" column note: `empty_input_behavior` and
   `se_action_if_failed` are independent gates
3. Surrogate-key strategy: deterministic only, `monotonically_increasing_id()`
   forbidden

## Artifact Status Lifecycle

Same 3-state lifecycle as chapters 4–5: `Draft → Updated - Pending Review → Approved`.

## Upstream Approval Gate

Before any chapter-6 `create-silver` or `create-gold` skill runs, the
upstream LLD, DMS, STM, DQS, and Stories backlog MUST be `Approved`.
No override.

## Learnings & Corrections Protocol

After any user correction, append to the learnings queue:

```bash
echo '{"skill": "{skill-name}", "date": "{YYYY-MM-DD}", "correction": "{what}", "pattern": "{rule}", "status": "pending"}' \
  >> memory/developer/learnings-queue.jsonl
```

At session end with pending entries, run `/developer-plugin:apply-learnings`.

Corrections whose underlying issue indicates an LLD bug MUST also be logged
in `developer-plugin/LLD-DEVIATIONS.md` so the Technical Lead can fold them
into the next LLD revision.

## Key Commands

```bash
make dev-setup         # Install dependencies (uv sync)
make install-plugins   # Install chapter-4 planning + chapter-6 developer-plugin (atomic)
make test              # Run all tests
make validate-silver   # Validate Silver layer artifacts
make validate-gold     # Validate Gold layer artifacts
make lint              # Run ruff linter
make format            # Auto-format code
make clean             # Remove caches
```
