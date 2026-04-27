---
name: create-scaffold
description: >
  Generates the foundation layer of a cookiecutter-chapter project:
  directory tree via cookiecutter render, pyproject.toml, Makefile,
  docker-compose, cross-cutting utility modules under `src/<project>/utils/`,
  StructType schema contracts, and test-harness scaffolding. Foundation
  assets that every other generator (create-dag, create-ingestion,
  create-pipeline) assumes exist. Project-agnostic: all project-specific
  facts (table lists, module names, interface contracts) are read from the
  current run's LLD / DMS / story file at runtime.
  Use when the user asks to:
  - Scaffold the project / bootstrap the chapter
  - Implement a foundation-layer story (utility modules, config loader,
    contracts, docker-compose)
argument-hint: "[STORY-NN-NNN | 'full']"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion, Skill
context: fork
---

# Create Project Scaffold

You generate the foundation that every other create-* skill assumes exists:
the directory tree, Python packaging, developer tooling, and a handful of
utility modules. This is the first skill any new cookiecutter-chapter project runs.

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

Before any code generation, load the latest coding-patterns handbook:

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

If `AGE_DAYS > 30` (per `freshness_policy: warn-after-30-days`), pause and call **AskUserQuestion**:

- **Question**: "Libraries in `LIBRARIES.md` were last verified $LAST_VERIFIED ($AGE_DAYS days ago). How should I proceed?"
- **Options**:
  - `Refresh now` — invoke `/developer-plugin:refresh-libraries`, then resume this skill with the updated versions.
  - `Proceed with cached versions` — continue; add a stale-cache warning to the References trailer.
  - `Cancel` — abort cleanly, no partial output.

If `LIBRARIES.md` is missing, halt and tell the user to run `/developer-plugin:refresh-libraries` to initialize the catalogue.

### References trailer (in output)

Every run MUST emit a `### References` section citing the consumed docs + LIBRARIES.md vintage. If the user chose "Proceed with cached versions", prepend: `⚠ Library versions cached $AGE_DAYS days ago; run /developer-plugin:refresh-libraries to refresh.`

## Domain of Ownership

This skill owns the project's **foundation layer** — project-agnostic
assets that sit below per-layer code and are the same shape regardless of
the data domain:

| Owned path pattern                                                       | What lives here                                                |
|--------------------------------------------------------------------------|----------------------------------------------------------------|
| `pyproject.toml`, `Makefile`, `CLAUDE.md`, `README.md`, `.gitignore`     | Project root metadata (README.md = how-to-use guide)           |
| `src/<project_name>/utils/**`                                            | Cross-cutting utility modules (whatever LLD §2.3 enumerates)   |
| `src/<project_name>/{bronze,silver,gold}/__init__.py`                    | Empty package markers for the layer skills to fill             |
| `contracts/**` (excluding `contracts/dq/**`)                             | StructType contracts, one per DMS §2 table                     |
| `tests/conftest.py`, `tests/utils/**`, per-layer `tests/<L>/conftest.py` | Shared test fixtures; per-module utility tests                 |
| `_infra/docker/**`, `docker-compose.yml`                                 | Local dev stack (cookiecutter baseline + LLD §9.3 Compose Services) |
| `_infra/ci/.github/workflows/{lint,unit-test,integration-test}.yml`      | Skeleton CI workflows calling `make lint`/`make test` targets  |
| `ddl/liquibase/master-changelog.xml`, `ddl/liquibase/changelogs/**`      | Liquibase root + one changelog per Bronze table (DMS §2 count) |
| `tests/test_contracts.py`                                                | Closed-graph check that every contract's `ddl_path`/`dq_path` resolves |
| The initial `uvx cookiecutter` render                                    | One-time bootstrap when `project_root` is missing              |

It does **not** own: `src/<project_name>/{bronze,silver,gold}/*.py`
(create-ingestion / future silver/gold skills), `airflow/dags/**`
(create-dag), `airflow/jobs/**` (create-dag — per-task entry-script
wrappers auto-generated from LLD §4.2; the directory itself ships from
the cookiecutter as `.gitkeep`), `airflow/configs/**` + `dq_rules/**`
(create-ingestion), advanced `.github/workflows/**` (deploy/release) +
`_infra/cd/**` (create-pipeline), `contracts/dq/**`
(create-ingestion, synced from DQS).

**Workflow ownership split with create-pipeline**: create-scaffold owns
the three *skeleton* workflow YAMLs that call `make lint`/`make test` —
those come from the cookiecutter template and are identical across
projects. create-pipeline owns every other workflow file and is free to
*edit* the three skeletons to add deploy steps; it should never
re-create them from scratch.

## Deliverable Resolution Protocol

**No Story → Deliverable Map is hardcoded.** The current run's story file
is the single source of truth for which paths to emit.

1. **Story mode** (`STORY-NN-NNN`): read the story file at
   `{stories_dir}/v*/EPIC-*/STORY-NN-NNN-*.md`. Parse the Acceptance
   Criteria section. Each backtick-quoted path or identifier is a candidate
   deliverable. For each candidate:
   - If it matches an owned path pattern above → generate it.
   - If it matches another skill's domain → print
     `ROUTE-TO: create-<kind>` for that path and exit cleanly; the
     orchestrator will dispatch the right skill. Do NOT raise an error.
   - If it's an identifier (no `/` or file extension) → treat as a
     module name under `src/<project_name>/utils/` by default; LLD §2.3
     may override its location.

2. **Full / auto mode**: enumerate every un-Done story in the latest
   backlog whose classifier kind is `scaffold`
   (`status_rollup.py --mode classify --story <id>`), topologically sorted
   by `Depends On`. Run each through Story mode.

## Source-of-Truth Reads at Runtime

The skill NEVER hardcodes table lists, module names, project names, or
story IDs. At each generation step it reads:

| Fact needed                       | Where to read it                                                    |
|-----------------------------------|---------------------------------------------------------------------|
| Project name, chapter name        | Discovery helper (`--mode discover` → `project_name`)               |
| Directory tree                    | LLD §2.1                                                            |
| Utility module interface contracts| LLD §2.3                                                            |
| Config schema                     | LLD §7 + `outputs/lld/v*/config/config-template.yaml`               |
| Table list (for contracts)        | LLD §5.1 Bronze Task Table; DMS §2 layer schemas                    |
| StructType column definitions     | DMS §2 (the ONLY source — do not invent columns)                    |
| Infra stack                       | LLD §9.1                                                            |

If a reader's project has 4 tables instead of 13, or is called `claims_hub`
instead of `patient_360`, or uses different utility module names, the skill
works unchanged because every project-specific fact is read at runtime.

## Pattern Handbook Lookup

For each deliverable path, look up the matching pattern doc under
`$PATTERNS_DIR/` (e.g. `config-loader-pattern.md`,
`structured-logging-pattern.md`, `scd2-pattern.md`,
`structtype-contracts.md`, `docker-compose-conventions.md`). The pattern
doc tells the skill **how** to generate; the LLD/DMS/story tells it
**what** to generate. If no pattern matches, fall back to the LLD §2.3
interface contract for that module and generate a minimal compliant
implementation.

## Workflow

### Phase 0: Resolve Target

**FIRST — resolve the effective argument. Do this before any other Phase 0 step.**

The argument passed via the `Skill` tool may not reach this forked subagent.
Check these sources in order; stop at the first non-empty hit:

1. `$SKILL_ARG` environment variable.
2. `{workspace_root}/.skill-arg` file — read its contents, then delete
   it so it is consumed at most once.
3. The conversational argument supplied to the skill.
4. **Auto-mode default** — if `$CLAUDE_AUTO_MODE=1` OR
   `{workspace_root}/.auto-mode` exists → use the skill's full-mode default
   (**run every un-Done story whose classifier kind is `scaffold`, topo-sorted by `Depends On`, no story ID**).
5. Only if ALL four above are empty, ask the user via `AskUserQuestion`.

You MUST NOT ask the user until sources 1–4 have been checked. Auto-mode
detection is a hard override — if the marker exists, proceed with full
mode and do not ask.

Mechanical resolver (copy-paste; `$USER_ARG` is the conversational arg):

```bash
resolve_skill_arg() {
  if [ -n "$SKILL_ARG" ]; then echo "$SKILL_ARG"; return; fi
  if [ -f "{workspace_root}/.skill-arg" ]; then
    cat "{workspace_root}/.skill-arg"; rm -f "{workspace_root}/.skill-arg"; return
  fi
  # caller supplies conversational arg as $1
  if [ -n "$1" ]; then echo "$1"; return; fi
  if [ "$CLAUDE_AUTO_MODE" = "1" ] || [ -f "{workspace_root}/.auto-mode" ]; then
    echo "__AUTO__"; return
  fi
  echo ""
}
RESOLVED_ARG=$(resolve_skill_arg "$USER_ARG")
```

If `$RESOLVED_ARG` is `__AUTO__` or matches the full-mode pattern (empty or
`full`), proceed without asking — treat it as **full mode**.

**Step 1 — Detect mode from the resolved argument:**

**Single story mode** (`STORY-NN-NNN`):
- Normalize argument (uppercase, zero-padded).
- Read the story file at `{stories_dir}/v*/EPIC-*/STORY-NN-NNN-*.md`.
- Parse its Acceptance Criteria; extract every backtick-quoted path or
  identifier as a candidate deliverable.
- For each candidate, apply the Deliverable Resolution Protocol above
  (emit if owned; ROUTE-TO if owned by another skill; otherwise treat
  identifier as a `src/<project_name>/utils/` module per LLD §2.3).
- If EVERY candidate routes out (story classifies to another kind), print
  `ROUTE-TO: create-<kind>` once and exit cleanly.

**Full mode** (`full`, `__AUTO__`, or empty after resolution):
- Enumerate every un-Done story under the latest backlog whose classifier
  kind is `scaffold`. Topo-sort by `Depends On` and run each through
  Story mode.

### Phase 0.5: Path Scoping (optional, set by the orchestrator)

If `{workspace_root}/.skill-paths` exists, read it — each non-empty line
is a path in scope for THIS invocation. Process ONLY those paths; ignore
other paths the story AC names (they belong to other skills and the
orchestrator will dispatch them separately). Delete `.skill-paths` after
consuming it. When the file is absent (direct human invocation), fall
through to the standard Phase 2 loop that scans every candidate
deliverable against the Domain of Ownership.

### Phase 1: Pre-flight

Resolve upstream versions via the shared helper (uses `outputs/dev-lock.yaml`
when present, otherwise falls back to latest `v{N}`):

```bash
eval "$(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/resolve_versions.py --export)"
LATEST_LLD_DIR="${LATEST_LLD_DIR:-$(ls -d {workspace_root}/outputs/lld/v* | sort -V | tail -1)}"
```

- Read the latest LLD (`$LATEST_LLD_DIR/LLD-*.md`, under `{workspace_root}/outputs/lld/v*/`) for the canonical directory tree (§2.1), Makefile targets (§9.3), and Decision 13 (cookiecutter).
- Check which deliverables already exist on disk. If ALL exist → tell the user to use `update-scaffold` instead and exit.
- Check that the cookiecutter template path exists
  (`{workspace_root}/outputs/lld/v*/templates/cookiecutter-chapter/` or the repo-root
  `templates/cookiecutter-chapter/`).

#### Phase 1.5 — Environment Preflight

Before any code generation, verify the reader's machine has the runtime
prerequisites the generated code will depend on. Requirements are read at
runtime — NEVER hardcoded:

| Requirement        | How to determine the required version                                                                                         |
|--------------------|-------------------------------------------------------------------------------------------------------------------------------|
| Python             | LLD §9.1 runtime / `$PATTERNS_DIR/LIBRARIES.md` `python` row / `pyproject.toml` `requires-python`                             |
| Java (JDK)         | The highest Spark major pinned in `$PATTERNS_DIR/LIBRARIES.md` (Spark 4.x requires JDK 17+; Spark 3.x requires JDK 8/11/17). If the LLD §9.1 names Spark explicitly, that overrides. |
| `uv`               | Always required (project uses `uv sync` for env management).                                                                  |
| Docker / compose   | Only if `_infra/docker/**` or `docker-compose.yml` is in the story's deliverable set or in LLD §9.1.                          |
| Node / other       | Only if LLD §9.1 names them.                                                                                                  |

Probe each with a shell check. Gather all failures, then present them in
ONE `AskUserQuestion` call (do not ask one-by-one). Example probes:

```bash
# Python
python3 -c "import sys; v=sys.version_info; exit(0 if (v.major,v.minor)>=(3,10) else 1)"
# Java — parse from `java -version` stderr; compare to required major.
JAVA_V=$(java -version 2>&1 | awk -F\" '/version/{print $2}' | cut -d. -f1)
# `1.8` → 8 on older JDKs; treat 1.x as x.
[ "$JAVA_V" = "1" ] && JAVA_V=$(java -version 2>&1 | awk -F\" '/version/{print $2}' | cut -d. -f2)
# uv
command -v uv >/dev/null
# docker (only if required)
command -v docker >/dev/null && docker compose version >/dev/null 2>&1
```

If any probe fails, call **AskUserQuestion ONCE** with a compact summary:

```
Environment preflight found issues:

  ✗ Java 8 detected — Spark <version> requires JDK <min>+
  ✗ docker compose not installed (required for _infra/docker/*)

What would you like to do?

  [Install now]  Print the exact OS-appropriate command(s) and run them (macOS: `brew install openjdk@17`; Debian/Ubuntu: `sudo apt install openjdk-17-jdk`; …). Claude will print the commands and ask for confirmation before running anything with `sudo`.
  [I'll install manually]  Print the commands; skip execution. Abort the scaffold run.
  [Proceed anyway]  Accept the risk; tests that need the missing runtime will fail. A warning is appended to the References trailer.
  [Cancel]  Abort the scaffold run.
```

Platform detection rules (for command suggestions):

- `uname -s` = `Darwin` and `brew` available → Homebrew commands.
- `uname -s` = `Linux` + `/etc/os-release` ID in `{debian, ubuntu}` → `apt` commands.
- `uname -s` = `Linux` + ID in `{fedora, rhel, centos}` → `dnf` / `yum`.
- Windows (WSL or native) → winget / scoop commands; for native,
  recommend `https://adoptium.net/` for a JDK.
- Unknown platform → print generic guidance + the upstream vendor link.

**Do NOT silently install.** Every install command that requires `sudo`
or modifies PATH / shell rc files must be shown to the user and confirmed
(a second AskUserQuestion at install time is acceptable). Read-only probes
and user-level installs (`brew install`, `uv tool install`) may proceed
after the initial Install now confirmation.

If the user chooses **Install now**, after each install, re-probe to
confirm. If a probe still fails post-install, stop with CRITICAL citing
the failing probe and its stderr.

If the user chooses **Proceed anyway**, record a learnings queue entry
noting the skipped preflight so future runs can detect the pattern.

### Phase 2: Generate

Phase 2 is a generic loop over the candidate deliverables extracted from
the story AC (Phase 0 Step 1). For each candidate path, match it against
the **Owned path patterns** table in *Domain of Ownership* and dispatch to
the matching generation branch below.

**Branch A — Bootstrap (cookiecutter render).**

Fire once, when `project_root` is missing or empty:

```bash
uvx cookiecutter "$COOKIECUTTER_TEMPLATE" --overwrite-if-exists \
  chapter_name="$CHAPTER_NAME" project_name="$PROJECT_NAME" \
  python_version="$PY_VERSION"
```

`$PROJECT_NAME`, `$CHAPTER_NAME`, `$PY_VERSION` come from the discovery
helper, the workspace marker `.workspace.yaml` if present, or — if still
missing — an `AskUserQuestion` prompt. NEVER default to a specific project
name in code. `$COOKIECUTTER_TEMPLATE` is located under
`{workspace_root}/outputs/lld/v*/templates/cookiecutter-chapter/` or the
repo-root `templates/cookiecutter-chapter/`.

After render, verify every path from LLD §2.1 exists. For any missing
directory, create it with `.gitkeep`. For any missing `__init__.py` in a
Python package dir, write an empty file.

**Branch B — Utility module (`src/<project_name>/utils/<name>.py`).**

For each utility module in the candidate list, look up its interface
contract in LLD §2.3 (Module Interface Contracts). Generate:

- Module docstring summarising its LLD §2.3 responsibility.
- Public function signatures matching the LLD interface. Use frozen
  dataclasses for config objects.
- Minimal but complete implementation following the matching pattern doc
  in `$PATTERNS_DIR/` — e.g. `config-loader-pattern.md`,
  `structured-logging-pattern.md`, `scd2-pattern.md`,
  `spark-expectations-pattern.md`, `observability-pattern.md`.
- Matching `tests/utils/test_<name>.py` with unit tests that cover every
  AC bullet in the story file.

Do NOT invent behaviour beyond the LLD §2.3 contract. If the LLD is silent
on a detail, defer to the pattern doc; if the pattern doc is also silent,
stop with CRITICAL and cite the missing spec.

**Branch C — Test harness bootstrap (one-time).**

If `tests/conftest.py` does not exist, create it with shared fixtures
(temp dir, Spark session factory, DuckDB connection). Add per-layer
`tests/{bronze,silver,gold}/conftest.py` stubs that re-export only the
fixtures each layer needs. Layer names come from the LLD §2.1 tree — do
not assume `{bronze,silver,gold}` if the project uses different names.

**Branch D — StructType schema contracts (`contracts/<table>.yml`).**

For **every** table declared in DMS §2 (Bronze/Silver/Gold layer schemas
— count and names are read at runtime, never hardcoded), emit
`contracts/<table>.yml` with the StructType-compatible schema from DMS.

If `{workspace_root}/outputs/dms/v*/` contains no DMS markdown, fail with
CRITICAL:

```
CRITICAL: no DMS found under {workspace_root}/outputs/dms/v*/.
  Generate the DMS via /data-modeler-plugin:create-dms before scaffolding.
```

Do NOT invent columns; if DMS is missing a column for a declared table,
stop with CRITICAL naming the table.

**Branch E — Infra (`_infra/docker/**`, `docker-compose.yml`).**

The cookiecutter ships a baseline `_infra/docker/docker-compose.yml`
with the standard local-dev services (UC, Marquez, Airflow, OTEL —
project-agnostic, image versions pinned from `$PATTERNS_DIR/LIBRARIES.md`).
Cross-check against LLD §9's **Compose Services** table (find by heading
text, anywhere within §9 — typically under §9.1 Scaffold Infrastructure
Layout or §9.3 Docker depending on the LLD's chosen layout):

- For every service in the LLD table NOT present in the baseline compose,
  append a service block. Pin its image version from
  `$PATTERNS_DIR/LIBRARIES.md` (or stop with CRITICAL if LIBRARIES.md has
  no entry for that image).
- For every service in the baseline compose NOT listed in the LLD table,
  leave it in place (over-provisioning is fine; validate-scaffold reports
  it as INFO not FAIL).
- Do NOT remove services from the baseline.

If §9 lacks a `Compose Services` heading, ship the baseline as-is and
emit a WARNING pointing the user at the create-lld §9 guidance.

**Branch F — ROUTE-OUT.**

If a candidate path matches another skill's domain, print
`ROUTE-TO: create-<kind> <path>` to stdout and move on. Never generate
outside the Owned path patterns table.

### Phase 2b: Hydrate per-table Liquibase changelogs

The cookiecutter template ships `ddl/liquibase/master-changelog.xml` with
an empty `<include>` list and an empty `ddl/liquibase/changelogs/`
directory. After the render and before Phase 3, populate both from DMS §2.

1. **Extract Bronze table names from DMS §2.** Read the latest
   `outputs/dms/v*/DMS-*.md`. In §2, each Bronze table has a `### <table>`
   heading and a column table that follows. Collect every table name under
   §2's Bronze subsection (the DMS makes this explicit with a
   `## 2. Bronze Layer` or similar heading). If the DMS layout varies,
   fall back to scanning for `bronze.<table>` references — but DMS §2 is
   the authoritative source.

2. **Render one changelog per table** at
   `ddl/liquibase/changelogs/<table>.xml`. Use this template (columns
   stubbed as `STRING` — full schema accuracy is `update-scaffold
   sync-contracts`' job):

   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <databaseChangeLog
       xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog
           http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-4.20.xsd">

     <changeSet id="create-bronze-<table>" author="<project_name>">
       <sql splitStatements="false"><![CDATA[
   CREATE TABLE IF NOT EXISTS bronze.<table> (
       -- Columns stubbed; run update-scaffold sync-contracts to populate from DMS.
       ds DATE NOT NULL,
       _ingested_at TIMESTAMP NOT NULL,
       _source_batch_id STRING NOT NULL,
       _source_file STRING
   ) USING DELTA
   PARTITIONED BY (ds)
   ]]></sql>
     </changeSet>

   </databaseChangeLog>
   ```

3. **Rewrite `ddl/liquibase/master-changelog.xml`** so the top-level
   `<databaseChangeLog>` contains one
   `<include file="changelogs/<table>.xml" relativeToChangelogFile="true"/>`
   per table, sorted alphabetically. Preserve the existing XML header and
   schema declarations.

This keeps Phase 4b project-agnostic — the table list and count come from
the DMS at runtime, never hardcoded.

### Phase 3: Smoke Tests

```bash
cd "$PROJECT_ROOT"
uv sync --all-extras
uv run pytest tests/ --collect-only -q
```

Plus an **import smoke** that imports each utility module that was just
generated (discover them from the candidate list, don't hardcode names):

```bash
for m in "${GENERATED_UTIL_MODULES[@]}"; do
  uv run python -c "import ${PROJECT_NAME}.utils.${m}"
done
```

All checks must succeed. A failure blocks completion — report it with the
failing command and stderr.

### Phase 3.5: Verification Compliance Self-Check (MANDATORY before reporting OK)

The story's `## Verification` block is the contract. After every prior
phase has emitted its files, run the AC verifier against the target
story and refuse to declare OK if any mechanical verifier still fails.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/../scripts/verify_acs.py STORY-NN-NNN --json
```

(For batch / multi-story dispatch, run once per story.)

Parse the JSON output. For each AC in `acs[]`:

- `status == "FAIL"` and at least one check has a non-`manual` kind
  that failed → emit one CRITICAL line per failing check:
  `CRITICAL STORY-NN-NNN AC<N>: <check.spec> — <check.detail>`
  Then **stop**. Do NOT mark the plan task `done`. Do NOT print the
  OK trailer. The orchestrator's Phase 2 Step 3.5 reads this and halts
  the story.
- `status == "FAIL"` but every failing check is `manual:` → INFO only
  (manual checks can't fail mechanically; treat as author note).
- `status == "PASS"` / `INDETERMINATE` → continue.
- `has_verification == false` → emit one WARNING line
  `STORY-NN-NNN: no Verification block — generation completed without
  AC compliance check.` Then continue.

This phase is the **only** place this skill flips its overall result
from OK to FAILED. Skills that ignore it leave gaps the orchestrator
cannot see.

### Phase 4: Output Summary

Print a per-story row: `STORY-NN-NNN | N files created | OK / FAIL` for
every story processed, followed by a ROUTE-TO section listing any paths
that were deferred to other skills.

End with: `Next: /developer-plugin:validate-scaffold <same-arg>`.

## Hard Rules

1. Never overwrite a non-template file without AskUserQuestion confirmation.
2. StructType schemas MUST come from DMS — no invented columns or types.
3. Do not touch `airflow/dags/` — that belongs to `create-dag`.
4. Do not touch `src/{project_name}/bronze/` — that belongs to `create-ingestion`.
5. The `dq_rules/` directory is created empty; SE rules are owned by the DQ Engineer plugin.

## Edge Cases

- **Cookiecutter template missing** — fall back to hand-created directory tree per LLD §2.1; warn the user.
- **Partial scaffold already exists** — create only the missing pieces; never overwrite existing Python modules.
- **DMS file not found for a table** — stop with CRITICAL listing the missing table(s).
- **`uv sync` fails** — surface the stderr; do not retry silently.

## Learnings & Corrections

_No learnings recorded yet._
