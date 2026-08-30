---
name: update-scaffold
description: >
  Updates an existing project scaffold: adds missing directories/modules,
  patches pyproject.toml / Makefile / docker-compose when the LLD changes,
  and brings StructType schema contracts in sync with a revised DMS. Never
  deletes files. Use when the user asks to:
  - Refresh scaffold after LLD revision
  - Sync contracts/ against a new DMS version
  - Add a new foundation module to an existing project
argument-hint: "[STORY-NN-NNN | 'sync-contracts' | 'sync-infra' | 'sync-template' | 'sync-env' | 'sync-liquibase']"
allowed-tools: Read, Edit, Write, Grep, Glob, Bash, AskUserQuestion
context: fork
---

# Update Project Scaffold

This skill patches existing scaffold files in place. It is the safer
counterpart to `create-scaffold` — use it when `{project_root}/` already
exists and you just need to add, reconcile, or refresh a foundation piece.

## Workspace Discovery

Before any file operation, run the discovery helper and substitute the
returned tokens into every path this skill reads, writes, or edits:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py --mode discover
```

The JSON output supplies `{workspace_root}`, `{project_root}`,
`{project_name}`, `{stories_dir}`, and `{learnings_queue}`. The plugin is
project-agnostic — never hardcode project or chapter names in edits.

## Coding Patterns & Libraries Handbook

Before patching any scaffold file, load the latest coding-patterns handbook:

```bash
PATTERNS_DIR=$(ls -d "{workspace_root}/inputs/code/v"* 2>/dev/null | sort -V | tail -1)
if [ -z "$PATTERNS_DIR" ] || [ ! -d "$PATTERNS_DIR" ]; then
  echo "CRITICAL: inputs/code/v*/ not found. Run /developer-plugin:refresh-libraries to initialize the library cache."
  exit 1
fi
LIBRARIES_FILE="$PATTERNS_DIR/LIBRARIES.md"
```

**Required pattern docs for this skill:**

- `$PATTERNS_DIR/project-structure.md` — medallion tree + mandatory dirs
- `$PATTERNS_DIR/makefile-conventions.md` — required Make targets
- `$PATTERNS_DIR/docker-compose-conventions.md` — UC + Marquez stack
- `$PATTERNS_DIR/dependency-management.md` — UV + pyproject.toml layout
- `$PATTERNS_DIR/naming-conventions.md` — file / module naming rules
- `$PATTERNS_DIR/LIBRARIES.md` — pinned library versions

### Library freshness check

```bash
LAST_VERIFIED=$(grep '^last_verified:' "$LIBRARIES_FILE" | awk '{print $2}')
TODAY=$(date -u +%Y-%m-%d)
AGE_DAYS=$(python3 -c "from datetime import date; print((date.fromisoformat('$TODAY') - date.fromisoformat('$LAST_VERIFIED')).days")
```

If `AGE_DAYS > 30`, pause and call **AskUserQuestion** with options `Refresh now` / `Proceed with cached versions` / `Cancel`. If the user picks Refresh, invoke `/developer-plugin:refresh-libraries` and resume.

### References trailer (in output)

Emit a `### References` section citing the consumed pattern docs + LIBRARIES.md vintage. Add `⚠ Library versions cached $AGE_DAYS days ago; run /developer-plugin:refresh-libraries to refresh.` if the user proceeded with stale cache.

## When to use vs create-scaffold

| Situation                                       | Skill             |
|-------------------------------------------------|-------------------|
| `{project_root}/` does not exist                | `create-scaffold` |
| Directory tree absent                           | `create-scaffold` |
| Everything present, need to add one module      | `update-scaffold` |
| DMS revised → need to regenerate schema YAMLs   | `update-scaffold` (`sync-contracts`) |
| LLD §9.1 changed infra layout                   | `update-scaffold` (`sync-infra`)     |
| Cookiecutter template updated upstream          | `update-scaffold` (`sync-template`)  |
| Runtime prerequisites drifted (Java, uv, docker)| `update-scaffold` (`sync-env`)       |
| New layer DDL added | the layer skill emits its own `ddl/migrations/*.sql`; no master to sync (Liquibase removed, L-015) |

## Workflow

### Phase 0: Resolve Target

**Phase 0.a — Argument resolution (mandatory, runs first).** The Skill-tool
argument frequently fails to reach forked subagents. Resolve the target by
checking these sources in order — DO NOT ask the user until all four are
empty:

1. `$SKILL_ARG` environment variable.
2. `{workspace_root}/.skill-arg` file — read its contents, then delete the
   file so it is consumed at most once.
3. The conversational argument supplied to the skill (the user message).
4. `$CLAUDE_AUTO_MODE=1` or `{workspace_root}/.auto-mode` marker → resolve
   to the first un-Done foundation story in backlog order.

Mechanical resolver (copy-paste; `$USER_ARG` is the conversational arg):

```bash
resolve_skill_arg() {
  if [ -n "$SKILL_ARG" ]; then echo "$SKILL_ARG"; return; fi
  if [ -f "{workspace_root}/.skill-arg" ]; then
    cat "{workspace_root}/.skill-arg"; rm -f "{workspace_root}/.skill-arg"; return
  fi
  if [ -n "$1" ]; then echo "$1"; return; fi
  if [ "$CLAUDE_AUTO_MODE" = "1" ] || [ -f "{workspace_root}/.auto-mode" ]; then
    echo "__AUTO__"; return
  fi
  echo ""
}
RESOLVED_ARG=$(resolve_skill_arg "$USER_ARG")
```

If the conversational argument is a verbose prompt rather than a bare token,
extract the first match of `STORY-\d{2}-\d{3}|sync-(contracts|infra|template|env)`
from it before falling through.

**Resolution-source banner (mandatory, every run).** Print as the first line
of skill output, before any other work:

```
RESOLVED TARGET: <STORY-NN-NNN | sync-*> (source: <SKILL_ARG | .skill-arg | conversational | __AUTO__>)
```

Only if `$RESOLVED_ARG` is empty after all four sources — ask via
`AskUserQuestion` which target applies.

**Phase 0.b — Target semantics:**

- `STORY-NN-NNN` — read the story's AC; for each backtick-quoted path that
  falls under create-scaffold's *Domain of Ownership*, update it in place.
  Route ROUTE-TO for paths owned by other skills.
- `sync-contracts` — rewrite every `contracts/{table}.yml`. Bronze
  contracts (`contracts/synthea_*.yml`) get their `columns:` populated
  from the actual source schema via
  `patient_360/scripts/sync_bronze_contracts.py` — Bronze is a landing
  zone, so the source (DuckDB `synthea.*` tables, loaded by chapter-2's
  `make load-raw-data`) is the StructType source of truth, not the DMS.
  Silver / Gold contracts (`clinical_*`, `reference_*`, `billing_*`,
  `patient_*`) keep using DMS §3 / §4 as their schema source. See
  Phase 0.7 below.
- `sync-infra` — reconcile `_infra/docker/`, `pyproject.toml`, `Makefile`, and the
  Spark/Delta **version tokens** against the latest LLD §9 AND `LIBRARIES.md`. The version
  tokens are easy to miss because they live in files this mode otherwise treats as opaque —
  reconcile ALL of these to the `LIBRARIES.md` pins (NOT the cookiecutter template, which may
  be stale), reading the Spark line from the PySpark row and the Delta line from the
  `delta-spark` row:
  - `_infra/docker/docker-compose.yml` — service image tags.
  - `pyproject.toml` — runtime + dev dependency pins.
  - `Makefile` — `UC_UI_REF` and any version vars.
  - `_infra/docker/Dockerfile.airflow` — the `pyspark==<ver>` pip pin (use the EXACT pyspark
    patch from `LIBRARIES.md`, e.g. 4.1.1 — NOT 4.1.2, which `delta-spark==4.3.0` caps out).
  - `_infra/docker/Dockerfile.thrift` — the `FROM apache/spark:<ver>-...` base image, the
    `spark-examples_2.13-<ver>.jar` path, and the `ARG DELTA_VERSION` / `ARG UC_SPARK_VERSION`
    + the `--packages` connector coordinate (`unitycatalog-spark_4.1_2.13` on the 4.1 line).
  Report each token as PATCHED or MATCH explicitly; do NOT report a blanket "infra MATCH"
  without having grepped these specific lines (see L-001).
- `sync-template` — reconcile against an updated cookiecutter-chapter
  template. See Phase 0.5 below.
- `sync-env` — re-run the environment preflight (Java/Python/uv/docker
  versions) from `create-scaffold` Phase 1.5 and offer install prompts
  if prerequisites drifted (e.g. `LIBRARIES.md` bumped Spark major →
  JDK bump needed). No code files are touched in this mode.
- `sync-liquibase` — **DEPRECATED / no-op (Liquibase removed, developer-plugin
  L-015).** There is no `master-changelog.xml`, `liquibase.properties`, or
  `ddl/liquibase/` — DDL lives as plain dated `.sql` under `ddl/migrations/`
  and the dated/sequenced filenames ARE the ordering (no manifest to
  reconcile). If invoked, print that no action is needed and exit. See
  Phase 0.6.

### Phase 0.5: `sync-template` mode

Upstream cookiecutter-chapter releases new layers, new Makefile targets,
or renames directories. This mode reconciles an **existing** project
against the current template without destroying user edits.

1. **Locate the template**: `{workspace_root}/outputs/lld/v*/templates/cookiecutter-chapter/`
   or repo-root `templates/cookiecutter-chapter/`. Capture its version
   (prefer a `VERSION` file inside the template or the git SHA of its
   directory).
2. **Render into a throwaway directory** with the same cookiecutter
   variables the original project was rendered with (read from
   `{project_root}/.cookiecutter.json` if present, else prompt).
3. **Three-way diff**:
   - `NEW_ONLY` — paths in the new render but not in the current project
     → offer to add (AskUserQuestion: Add all / Pick individually / Skip).
   - `MISSING_FROM_NEW` — paths present locally but dropped upstream →
     flag for the user; never delete (Hard Rule 1).
   - `DIFFERS` — path exists in both but content differs → show a diff.
     If the local file has no human edits per `git blame`, offer to patch;
     otherwise require explicit AskUserQuestion confirmation per file.
4. **Non-code assets** (`Makefile`, `pyproject.toml`, `.gitignore`,
   `docker-compose.yml`, `README.md`, `CLAUDE.md`): attempt a **key-merge**
   rather than a full overwrite. For Makefile, add missing targets without
   touching existing ones; for `pyproject.toml`, add missing `[project]` /
   `[tool.*]` sections and dependencies; for `.gitignore`, append missing
   lines. For `README.md` / `CLAUDE.md`, if the file is missing write it
   from the template; if it exists, diff against the template and prompt
   via AskUserQuestion before overwriting (users commonly personalize
   these).
5. **Record** the template version that was applied so the next
   `sync-template` run can detect no-op cases.

### Phase 0.6: `sync-liquibase` mode — DEPRECATED (no-op)

Liquibase was REMOVED (developer-plugin **L-015**: it cannot work on UC OSS +
Spark Thrift — no Spark SQL dialect, incomplete Hive JDBC, and the
`liquibase-databricks` extension needs Databricks compute). There is no
`master-changelog.xml`, no `liquibase.properties`, and no `ddl/liquibase/`.
DDL lives as plain dated `.sql` migrations under `ddl/migrations/`
(`<YYYYMMDD>_<L><NN>_<table>.sql`, L = layer digit bronze=1/silver=2/gold=3);
`ddl-apply.sh` globs+sorts them — the filenames ARE the apply order, so there
is nothing to reconcile. If `sync-liquibase` is invoked, report "no action
needed (Liquibase removed; see L-015)" and exit. Per-table `.sql` content is
owned by the layer skill (`update-ingestion`/`create-ingestion` for Bronze,
`create-silver`/`update-silver` for Silver, `create-gold` for Gold).
**There is nothing to reconcile.** The old logic (aggregating per-table XML
changelogs into a `master-changelog.xml` and emitting `liquibase.properties`)
is gone with Liquibase. Per-table `.sql` migrations are owned by the layer
skills and the dated/sequenced filenames are the ordering. If `sync-liquibase`
is invoked, print `no action needed (Liquibase removed; see L-015)` and exit 0.
If a stale `ddl/liquibase/` directory or `master-changelog.xml` is found on
disk, flag it INFO (it should be deleted; DDL belongs under `ddl/migrations/`).

### Phase 0.7: `sync-contracts` mode

The 13 Bronze contracts (`contracts/synthea_*.yml`) are populated from the
**source** schema, not the DMS — Bronze is a landing zone that mirrors
the source as-is. The DMS only specifies the columns that survive into
Silver/Gold, so it cannot drive Bronze StructType.

Steps:

1. **Locate the source DuckDB**. By convention it's
   `{repo_root}/data/duckdb/raw.db`, loaded by chapter-2's
   `make load-raw-data`. From the chapter workspace that's `../data/duckdb/raw.db`.
   If the file is missing, halt with a one-line message instructing the
   user to run `make load-raw-data` from the repo root first.

2. **Run the generator** (it walks `DESCRIBE synthea.<table>` for every
   `synthea_*.yml` under `contracts/`, maps DuckDB types to the
   contract type vocabulary, and rewrites the `columns:` block only —
   preserving every other field):

   ```bash
   uv run python patient_360/scripts/sync_bronze_contracts.py \
     --raw-db ../data/duckdb/raw.db \
     --contracts-dir patient_360/contracts
   ```

3. **Silver / Gold contracts** are still DMS-driven. Read the DMS §3
   (Silver) and §4 (Gold) tables and merge their column lists into the
   matching `contracts/{table}.yml` using the same `Edit`-only,
   field-preserving pattern. (Out of scope while only Bronze has shipped;
   add when Silver/Gold create-* skills land.)

4. **Report**: one row per contract (`UPDATED` / `matches` / `SKIP`).
   The generator already emits this format; capture and forward to the
   Phase 4 output.

### Phase 1: Diff

Compute the delta between what LLD/DMS says and what is on disk:

- List every target file and its status: `present-and-matches`, `present-and-differs`, or `missing`.
- Show the user the diff preview before any writes.

### Phase 2: Apply

- `missing` → `Write` the new file.
- `present-and-differs` → `Edit` with minimal context patches; never `Write` over a user-edited module without `AskUserQuestion` confirmation.
- `present-and-matches` → no-op.

### Phase 3: Smoke Tests

Same three commands as `create-scaffold` Phase 3 (`uv sync`, import check, `pytest --collect-only`).

### Phase 4: Output Summary

Per file: `PATH | MATCH / PATCHED / CREATED / SKIPPED`.

End with: `Next: /developer-plugin:validate-scaffold <same-arg>`.

## Hard Rules

1. Never delete a file. Renames are two steps: write the new path, tell the user to remove the old one.
2. Never overwrite a Python module whose `git blame` shows human edits without `AskUserQuestion` confirmation.
3. StructType schemas are derived from a canonical source, never invented:
   Bronze (`synthea_*`) ← DuckDB source via
   `scripts/sync_bronze_contracts.py`; Silver / Gold ← DMS §3 / §4.
4. Do not touch `airflow/dags/`, `src/{project_name}/bronze/`, or `dq_rules/`.
5. Do not author per-table Liquibase changelog content under
   `ddl/liquibase/changelogs/`. Those files are owned by layer skills
   (`update-ingestion` for Bronze; future silver/gold for those layers).
   This skill only owns `master-changelog.xml` and `liquibase.properties`.

## Edge Cases

- **File present but not tracked by git** (user's local work) → treat as user-edited; require confirmation.
- **DMS has new table not in `contracts/`** → create it.
- **Contract has table no longer in DMS** → flag, do not delete (Rule 1).

## Learnings & Corrections

### Active Learnings

- **L-001** (2026-06-20): `sync-infra` reconciles `docker-compose.yml`, `pyproject.toml`, and `Makefile`, but its scope does NOT cover the Dockerfile version tokens. After ANY Spark/pyspark version bump in LIBRARIES.md, ALWAYS also reconcile `Dockerfile.airflow` (the `pyspark==<ver>` pip pin), `Dockerfile.thrift` (`FROM apache/spark:<ver>-...` base image AND the `spark-examples_2.13-<ver>.jar` path) against the LIBRARIES.md Spark/Delta versions — sync-infra reports them as MATCH and leaves them stale, so they silently drift from `pyproject.toml`.
- **L-002** (2026-06-21): Regenerated scaffold Python (`utils/*.py` etc.) MUST pass `make lint` (ruff `select=[E,F,I,UP]`, line-length 100). Regen had no lint gate and shipped E501 (>100-char function signatures in `utils/metrics.py`) that silently red-lined `make lint`. As the FINAL step ALWAYS run `uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/` and confirm `make lint` exits 0 before reporting done — `ruff format` explodes over-long signatures across lines automatically.
