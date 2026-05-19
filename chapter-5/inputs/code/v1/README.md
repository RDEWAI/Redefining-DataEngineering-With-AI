---
Version: 1.0
Status: Approved
Created: 2026-04-24
Owner: Data Engineering Platform
---

# Coding Patterns & Library Standards Handbook

This handbook defines the coding standards, architectural patterns, and
pinned library versions the **developer-plugin** applies when generating
scaffolds, ingestion frameworks, Airflow DAGs, Spark Declarative Pipelines,
and CI/CD pipelines for any project.

It is the developer-plugin's equivalent of what `inputs/lld/v{N}/` is for
the `technical-lead-plugin` and `inputs/dqs/v{N}/` is for the
`dq-engineer-plugin`: a generic, reusable source of truth, **not** a
project-specific specification.

## How the developer-plugin consumes this folder

Every `create-*`, `update-*`, and `implement-stories` skill in
`chapter-5/developer-plugin/` resolves the latest version of this handbook
with:

```bash
PATTERNS_DIR=$(ls -d "$WORKSPACE_ROOT"/inputs/code/v* | sort -V | tail -1)
```

Each skill then reads the specific pattern docs relevant to what it is
generating (e.g. `create-ingestion` reads `bronze-ingestion-pattern.md` +
`spark-expectations-pattern.md`; `create-scaffold` reads
`project-structure.md` + `makefile-conventions.md` + `LIBRARIES.md`).

Before any `create-*` or `update-*` skill generates code it runs the
**library-freshness check** described in
`chapter-5/developer-plugin/skills/refresh-libraries/SKILL.md`. If the
`last_verified` date in `LIBRARIES.md` is older than the
`freshness_policy` window (default 30 days), the skill calls
`AskUserQuestion` with three options — **Refresh now**, **Proceed with
cached versions**, or **Cancel**.

## Index

### Foundation

| File | Scope |
|---|---|
| [`LIBRARIES.md`](LIBRARIES.md) | Pinned latest versions + authoritative docs URLs; updated by `refresh-libraries` skill. |
| [`project-structure.md`](project-structure.md) | Medallion directory tree, mandatory dirs, rationale. |
| [`dependency-management.md`](dependency-management.md) | `pyproject.toml`, dependency groups, UV workflow. |
| [`makefile-conventions.md`](makefile-conventions.md) | Standard `make` targets and naming rules. |
| [`docker-compose-conventions.md`](docker-compose-conventions.md) | Services, volumes, ports, health-check conventions. |
| [`naming-conventions.md`](naming-conventions.md) | Module / table / column / config-key naming. |
| [`logging-error-handling.md`](logging-error-handling.md) | Structured logging + fail-fast error handling. |

### Layer patterns

| File | Scope |
|---|---|
| [`bronze-ingestion-pattern.md`](bronze-ingestion-pattern.md) | Registry-driven factory, schema-first read, partitioned Delta write. |
| [`silver-transform-pattern.md`](silver-transform-pattern.md) | SCD Type 2 with Delta `MERGE INTO`, config-driven natural key / tracked columns. |
| [`gold-aggregation-pattern.md`](gold-aggregation-pattern.md) | Wide consumer-layer joins with `coalesce` fallbacks. |

### Orchestration

| File | Scope |
|---|---|
| [`spark-declarative-pipelines.md`](spark-declarative-pipelines.md) | `@dp.table` / `@dp.materialized_view` convention + `spark-pipeline.yml`. |
| [`airflow-dag-pattern.md`](airflow-dag-pattern.md) | DAG factory, TaskGroup per source, SparkSubmitOperator wrapper. |

### Platform

| File | Scope |
|---|---|
| [`unity-catalog-pattern.md`](unity-catalog-pattern.md) | UC OSS bootstrap, `UCSingleCatalog`, path-based writes + `CREATE TABLE IF NOT EXISTS`. |
| [`openlineage-marquez-pattern.md`](openlineage-marquez-pattern.md) | OpenLineage listener + Marquez backend configuration. |
| [`spark-expectations-pattern.md`](spark-expectations-pattern.md) | Declarative DQ rule files, action semantics, runner wiring. |

### Quality

| File | Scope |
|---|---|
| [`test-pattern.md`](test-pattern.md) | `DeltaCatalog` + temp-warehouse `pytest` fixture, integration marker. |
| [`ci-cd-pattern.md`](ci-cd-pattern.md) | GitHub Actions lint → test → package → deploy workflow shape. |

### Illustrative snippets

Short (≤40 lines) code fragments in [`scripts/`](scripts/) that each pattern
doc references. Snippets use generic placeholders (`{project}`, `{table}`,
`{schema}`) and are safe to copy as starting points.

## Change policy

- **Pattern docs** — edit in place when the convention evolves; bump the
  file-level version in frontmatter. Major restructures create a new
  `v{N+1}/` folder.
- **`LIBRARIES.md`** — **never hand-edited**. Always regenerate via
  `/developer-plugin:refresh-libraries`, which updates the `last_verified`
  date and per-row versions atomically.
- **Snippets** — keep ≤40 lines; move longer examples to a pattern doc's
  "Illustrative snippet" section with excerpts.

## Source of the patterns

Patterns are distilled from the `/mvp/` reference implementation in this
repository — a Spark 4.1 + Delta + Unity Catalog OSS + Marquez + Spark
Expectations Medallion pipeline. Project-specific names
(`patient_360`, Synthea table names, healthcare domain terms) have been
replaced with generic placeholders throughout.

Each pattern doc's **References** section cites the `/mvp` files it was
distilled from, so you can trace the convention back to a working example.
