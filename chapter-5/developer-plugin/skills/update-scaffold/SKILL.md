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
| New layer changelogs added → master out of sync | `update-scaffold` (`sync-liquibase`) |

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
- `sync-infra` — reconcile `_infra/docker/`, `pyproject.toml`, and `Makefile` against the latest LLD §9.
- `sync-template` — reconcile against an updated cookiecutter-chapter
  template. See Phase 0.5 below.
- `sync-env` — re-run the environment preflight (Java/Python/uv/docker
  versions) from `create-scaffold` Phase 1.5 and offer install prompts
  if prerequisites drifted (e.g. `LIBRARIES.md` bumped Spark major →
  JDK bump needed). No code files are touched in this mode.
- `sync-liquibase` — reconcile the cross-layer Liquibase plumbing
  (`ddl/liquibase/master-changelog.xml`, `ddl/liquibase/liquibase.properties`)
  against DMS §2/§3/§4 and what is currently on disk under
  `ddl/liquibase/changelogs/`. See Phase 0.6 below.

### Phase 0.5: `sync-template` mode

Upstream cookiecutter-chapter releases new layers, new Makefile targets,
or renames directories. This mode reconciles an **existing** project
against the current template without destroying user edits.

1. **Locate the template**: `{workspace_root}/../chapter-4/outputs/lld/v*/templates/cookiecutter-chapter/`
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

### Phase 0.6: `sync-liquibase` mode

LLD §9.1 prescribes a **single project-wide** `master-changelog.xml`
aggregating every per-table changelog across Bronze + Silver + Gold, plus
a `liquibase.properties` connection-config file. Per-table changelog
content is owned by the *layer* skill that knows its DMS section
(`update-ingestion` for Bronze §2; future silver/gold skills for §3/§4).
This skill owns the aggregator + properties only.

1. **Resolve the DMS path via the shared helper** (no hardcoded
   chapter / project names):
   ```bash
   eval "$(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/resolve_versions.py --export)"
   LATEST_DMS=$(ls -t "$LATEST_DMS_DIR"/DMS-*.md 2>/dev/null | grep -v '\.bak$' | head -1)
   ```
2. **Read the DMS layer table inventory.** Parse DMS §2 (Bronze), §3
   (Silver), §4 (Gold). The per-layer table-name patterns (prefix,
   namespace, etc.) are declared in the DMS — never hardcode them. For
   each layer collect:
   - The set of table names under that layer.
   - The filename pattern used for that layer's Liquibase changelogs
     (taken from the DMS or from the `ddl_path` pointer in each
     `contracts/{table}.yml`).
3. **Discover layer changelogs on disk**:
   ```bash
   ls {project_root}/ddl/liquibase/changelogs/*.xml 2>/dev/null | sort
   ```
   Bucket each filename into a layer using the DMS-derived patterns
   from step 2. If a file matches no layer pattern, flag it INFO and
   leave it alone — never assume.
4. **Cross-check against DMS**: every table declared in DMS §2/§3/§4
   should have a matching per-table XML on disk. If any are missing,
   ROUTE-OUT a note pointing to the owning layer skill — do NOT
   fabricate the per-table content here.
5. **Idempotent merge of `master-changelog.xml`**:
   - If the file does not exist, write a fresh `<databaseChangeLog>`
     root with one `<include file="changelogs/{name}.xml"/>` line per
     XML found in step 3, ordered Bronze → Silver → Gold then
     alphabetical within each layer.
   - If the file exists, parse it, collect existing includes, and add
     missing entries only. Never reorder or delete user-authored
     includes (Hard Rule 1).
6. **`liquibase.properties`**: emit only if missing. Use placeholder
   `url`, `driver`, `username`, `password` keys keyed by env-var
   substitution (`${LIQUIBASE_DB_URL}` etc.) so secrets are not
   committed. Do not overwrite an existing file.
7. **Update the stale stub comment**: any layer changelog whose stub
   says `-- run update-scaffold sync-contracts to populate from DMS`
   has the wrong directive (scaffold doesn't have DMS schemas in
   scope). If found, REPLACE the directive with `-- run the matching
   layer skill (update-ingestion for Bronze §2; future silver/gold for
   §3/§4) to populate columns from DMS.` Do NOT modify any other
   content in the file.

This mode never touches `ddl/liquibase/changelogs/*.xml` per-table
content — that is layer-owned.

### Phase 0.7: `sync-contracts` mode

The 13 Bronze contracts (`contracts/synthea_*.yml`) are populated from the
**source** schema, not the DMS — Bronze is a landing zone that mirrors
the source as-is. The DMS only specifies the columns that survive into
Silver/Gold, so it cannot drive Bronze StructType.

Steps:

1. **Locate the source DuckDB**. By convention it's
   `{repo_root}/data/duckdb/raw.db`, loaded by chapter-2's
   `make load-raw-data`. From `chapter-5/` that's `../data/duckdb/raw.db`.
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

_No learnings recorded yet._
