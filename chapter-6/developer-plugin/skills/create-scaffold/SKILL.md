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
| `ddl/migrations/**`                                                      | One plain dated `.sql` migration per Bronze table (DMS §2 count), applied in lexical order by `ddl-apply.sh` (no Liquibase) |
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
| Config schema                     | LLD §7 + `outputs/lld/v*/config/config-template.yaml`  |
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

In addition to the LLD-driven cross-check, the compose stack MUST emit
two services that back the external-table DDL workflow (Phase 2b):

- **`spark-thrift-server`** — a Spark Thrift Server (HiveServer2) wired
  with Delta + the UC named side catalog, exposing HiveServer2 on host
  port `:10000` and mounting the Delta **warehouse** volume (so the
  external-table `LOCATION` paths resolve in-container). Only Spark can
  execute Delta DDL, so the DDL applier targets this service. Wire its
  Spark config exactly as the canonical UC pattern (see the catalog
  learnings L-008/L-009): `spark_catalog=DeltaCatalog` plus a named
  `unity=UCSingleCatalog` side catalog (`uri`/`token`/`warehouse`,
  `defaultCatalog=unity`). Its readiness `healthcheck` MUST invoke `bash`
  explicitly — see L-011 (the `/dev/tcp` TCP probe is a bash builtin; the
  default `CMD-SHELL` runs `/bin/sh`/dash, which lacks it and fails the
  probe forever).
- **`ddl-apply`** — a one-shot service that applies the plain dated `.sql`
  migrations under `ddl/migrations/` against the Thrift Server via **beeline**
  (`beeline -u jdbc:hive2://spark-thrift-server:10000/unity`), NOT the Liquibase
  CLI — Liquibase cannot work on UC OSS + Spark Thrift (developer-plugin
  **L-015**: no Spark SQL dialect; Hive JDBC too incomplete; the only
  Delta-aware option `liquibase-databricks` requires Databricks compute).
  It reuses the Thrift image (which ships `beeline` and `python3`) and runs the
  applier `_infra/docker/ddl-apply.sh` with this contract:
  1. Glob `ddl/migrations/*.sql` and **sort lexically** — filenames are
     `<YYYYMMDD>_<L><NN>_<table>.sql` (L = layer digit: bronze=1, silver=2,
     gold=3), so a lexical sort yields the bronze→silver→gold apply order. NO
     master manifest, NO XML, NO regex extraction.
  2. For each file, env-substitute `${PATIENT360_WAREHOUSE_ROOT}` (beeline does
     not expand env vars), then apply via beeline invoked by its **absolute
     path** `"${SPARK_HOME:-/opt/spark}/bin/beeline"` — NOT bare `beeline` (the
     `apache/spark` image ships beeline under `$SPARK_HOME/bin` but not on
     `PATH`, so a bare call dies `beeline: command not found`). Use
     `--silent=true -f <file>`; `set -euo pipefail` so the one-shot is
     fail-closed. The `--` header lines (incl. `-- rollback: DROP ...`) are SQL
     comments and are ignored.
  The `ddl-apply` compose service mounts `ddl/migrations/` + the applier and
  runs `bash ddl-apply.sh`; `depends_on: { spark-thrift-server:
  { condition: service_healthy } }`. `CREATE TABLE IF NOT EXISTS` makes
  re-apply idempotent. Back it with a `make ddl-apply` target. Pre-create all
  external tables with `make ddl-apply` BEFORE the pipeline runs; the runtime
  never creates tables.

Pin both services' image versions from `$PATTERNS_DIR/LIBRARIES.md` (or
stop with CRITICAL if LIBRARIES.md has no entry). If a compose template
block ships these services already, extend it rather than duplicate.

If §9 lacks a `Compose Services` heading, ship the baseline as-is and
emit a WARNING pointing the user at the create-lld §9 guidance.

**Branch F — ROUTE-OUT.**

If a candidate path matches another skill's domain, print
`ROUTE-TO: create-<kind> <path>` to stdout and move on. Never generate
outside the Owned path patterns table.

### Phase 2b: Hydrate per-table DDL migrations (plain .sql)

The cookiecutter template ships an empty `ddl/migrations/` directory (no
Liquibase, no `master-changelog.xml` — see developer-plugin L-015). After the
render and before Phase 3, populate it from DMS §2.

1. **Extract Bronze table names from DMS §2.** Read the latest
   `outputs/dms/v*/DMS-*.md`. In §2, each Bronze table has a `### <table>`
   heading and a column table that follows. Collect every table name under
   §2's Bronze subsection (the DMS makes this explicit with a
   `## 2. Bronze Layer` or similar heading). If the DMS layout varies,
   fall back to scanning for `bronze.<table>` references — but DMS §2 is
   the authoritative source.

2. **Render one plain-SQL migration per table** at
   `ddl/migrations/<YYYYMMDD>_1<NN>_<table>.sql` (`<YYYYMMDD>` = creation date;
   `1<NN>` = layer digit `1` (bronze) + 2-digit intra-layer alpha sequence, so
   a lexical sort yields bronze→silver→gold across layers). Tables are
   pre-created as **EXTERNAL Delta**: the name is the 3-part
   `unity.<schema>.<table>` (UC named catalog), and the DDL carries an explicit
   `LOCATION '<warehouse path>'` under the warehouse root — so the runtime never
   creates tables and never uses `saveAsTable`. Columns are stubbed as `STRING`
   — full schema accuracy is `update-scaffold sync-contracts`' job. The first
   lines are `--` comment headers (beeline ignores them); the rollback is a
   `-- rollback: DROP TABLE ...` comment:

   ```sql
   -- migration: <YYYYMMDD>_1<NN>_<table>
   -- layer: bronze  table: unity.<schema>.<table>
   -- ${PATIENT360_WAREHOUSE_ROOT} is substituted by ddl-apply.sh before beeline -f.
   -- rollback: DROP TABLE IF EXISTS unity.<schema>.<table>

   CREATE TABLE IF NOT EXISTS unity.<schema>.<table> (
       -- Columns stubbed; run update-scaffold sync-contracts to populate from DMS.
       ds DATE NOT NULL,
       _ingested_at TIMESTAMP NOT NULL,
       _source_batch_id STRING NOT NULL,
       _source_file STRING
   ) USING DELTA
   LOCATION '<warehouse path>'
   PARTITIONED BY (ds)
   ```

   These external-table migrations are **not** applied by the runtime.
   They are applied by the `ddl-apply` one-shot via **beeline** against the
   **Spark Thrift Server** (HiveServer2 on `:10000`) by a `make ddl-apply`
   step — only Spark can execute Delta DDL — pre-creating every table before
   the pipeline runs. The Liquibase CLI is NOT used (developer-plugin **L-015**:
   Liquibase cannot work on UC OSS + Spark Thrift). The `.sql` files ARE the
   DDL source of truth; the applier globs+sorts `ddl/migrations/*.sql`,
   env-substitutes `${PATIENT360_WAREHOUSE_ROOT}`, and runs each via
   `beeline -f`. See Branch E for the `spark-thrift-server` + `ddl-apply`
   compose services that back `make ddl-apply`.

3. **No master manifest.** The dated/sequenced filenames ARE the ordering (a
   lexical sort of `ddl/migrations/*.sql` yields bronze→silver→gold). Do NOT
   create `ddl/liquibase/master-changelog.xml` or any Liquibase plumbing.

This keeps Phase 2b project-agnostic — the table list and count come from
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

### Active Learnings

- **L-008** (2026-05-12): Always: NEVER bind `spark_catalog` to `UCSingleCatalog` — UC is ALWAYS a named SIDE catalog alongside DeltaCatalog. Wire `spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension`, `spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog`, AND a named side catalog `spark.sql.catalog.unity=io.unitycatalog.spark.UCSingleCatalog` with `spark.sql.catalog.unity.uri=<UC_URI env>`, `spark.sql.catalog.unity.token=""`, `spark.sql.catalog.unity.warehouse=unity`, and `spark.sql.defaultCatalog=unity`. ALSO set `spark.sql.sources.partitionOverwriteMode=dynamic` so `df.write.mode("overwrite").insertInto(table)` replaces ONLY the partitions present in the DataFrame — this is the required idempotent per-`ds` Bronze/Silver write semantics; without it, pipeline re-runs double the data (LLD v1.14 §13 Decision 15). Unity Catalog is now the catalog (tables referenced as `unity.<schema>.<table>`); there is NO Hive metastore / Derby in this wiring.
- **L-010** (2026-06-20): On UC 0.5.0, the re-enabled spark-expectations error/stats tables are MANAGED `catalogManaged` Delta tables created by `saveAsTable` against an FQN. For that to work `build_spark_session` and the server must support coordinated commits: keep the `spark_catalog=DeltaCatalog` + `unity=UCSingleCatalog` side-catalog wiring above (the connector handles the commit-coordination handshake at delta-spark 4.1+/UC 0.5.0), and `scripts/uc_init.py` MUST create the catalog/schemas WITH a managed location — otherwise managed `saveAsTable` fails with `FAILED_PRECONDITION: Neither catalog nor schema has managed location configured`. **CRITICAL (verified live on UC 0.5.0):** the schema managed location MUST be sent as the **TOP-LEVEL `storage_root` field** in the CreateSchema REST payload (`{"name": ..., "catalog_name": ..., "storage_root": "file:///.../<schema>"}`) — NOT under `properties` (a `properties.storage_root` is free-form metadata that UC 0.5.0's Delta managed-table API ignores, so createStagingTable still errors). Verified: `POST /schemas` with a top-level `storage_root` returns it populated; under `properties` the top-level field stays `null`. The UC server and Spark must share the warehouse filesystem (shared compose volume) so the coordinator and the writer see the same `_delta_log`. Business Bronze/Silver/Gold tables stay EXTERNAL + `insertInto` (unchanged); only the SE `_error`/`_stats` tables are managed.
- **L-014** (2026-06-20): Unity Catalog has **no released server Docker image for 0.5.0** — it must be built from source. The upstream UC repo `Dockerfile` (root) is **broken for the runtime classpath**: its base stage runs `sbt package` as **root**, so coursier caches every dependency jar under `/root/.cache/coursier`, and `server/target/classpath` references those by ABSOLUTE `/root/.cache/...` paths — but the runtime stage only copies `$HOME/.cache` (`/home/unitycatalog/.cache`, which is empty). Result: the server starts then dies with `NoClassDefFoundError: io/vertx/core/Verticle` (or any dep). FIX: in the runtime stage add `COPY --from=base /root/.cache /root/.cache` and `RUN chmod o+x /root && chmod -R a+rX /root/.cache` (the non-root `unitycatalog` user must be able to read them). Build once, then **push to the repo's own registry** (e.g. `ghcr.io/<org>/<repo>:uc-server-v0.5.0`) and point compose `image:` at it (pull-only, no `build:`) — the "ship-it-ourselves" pattern; from-source build is then a one-time cost, not every `dev-up`. NOTE: this patch lives on the cloned `uc-source/` tree, so a `uc-ui-source` re-clone overwrites it — apply it as a post-clone patch step or a thin wrapper Dockerfile so the build stays reproducible.
- **L-015** (2026-06-20): Do NOT use Liquibase for DDL on a Unity Catalog OSS + Spark Thrift Server stack — it cannot work, proven empirically against the live stack. (1) Core Liquibase has **no Spark SQL dialect**, and the Apache Hive JDBC driver leaves core JDBC methods (`getURL()`, most `DatabaseMetaData`) unimplemented, so vanilla Liquibase can't connect or maintain `DATABASECHANGELOG`. (2) The only Delta/UC-aware option, the official `liquibase-databricks` extension, is welded to the **Databricks JDBC driver**, which `NullPointerException`s in `DatabricksConnectionContext.buildCompute()` parsing any URL without a Databricks `httpPath` (`/sql/1.0/warehouses/<id>`) — it structurally requires Databricks compute and cannot target a local Spark Thrift Server. Liquibase only fits if the project runs on **Databricks** (SQL warehouse). On OSS, emit DDL as **plain dated `.sql` migration files** (`ddl/migrations/<YYYYMMDD>_<NNN>_<table>.sql`, sorted bronze→silver→gold) and apply them in order via `beeline -f` (env-substituting `${PATIENT360_WAREHOUSE_ROOT}`) — NO Liquibase XML, NO regex-on-XML extraction. Each layer skill emits its own `.sql`; the applier globs+sorts and applies. Do not reintroduce `ddl/liquibase/` or `master-changelog.xml`.
- **L-016** (2026-06-21): When authoring `utils/delta_helpers.py` (Branch B), do NOT emit the `replace_where_write` / `write_silver_delta` / `_external_table_path` helpers — they are SUPERSEDED dead code with zero callers. Business tables are EXTERNAL + `df.write.mode("overwrite").insertInto(...)` (bronze + silver facts) or `apply_scd2`/`DeltaTable.forName` MERGE (silver dims); the external-table `LOCATION` lives in the plain `.sql` migrations, not computed in code. `.saveAsTable` on a business table is forbidden (it's reserved ONLY for the managed SE `_error`/`_stats` audit tables). Emit only what is actually used: `build_spark_session`, `read_bronze_delta`, `_resolve_uc_warehouse`, plus the catalog constants. Also: NEVER hand-author un-owned convenience scripts under `scripts/` (e.g. a `bsql.sh` spark-sql shell) — they fall outside the generator model and rot (the deleted `bsql.sh` still wired `catalogImplementation=hive` + `jdbc:derby`, the pre-UC metastore L-009 forbids, so it couldn't even see `unity.*` tables). If a SQL dev-shell is needed, emit it UC-wired (`spark_catalog=DeltaCatalog` + `unity=UCSingleCatalog` + `defaultCatalog=unity` + the UC connector jar) or just shell out to `beeline` against the spark-thrift-server like `ddl-apply.sh`.
- **L-009** (2026-05-12): Always: Do NOT set `spark.sql.catalogImplementation=hive` and do NOT emit any `jdbc:derby:` ConnectionURL — the Derby/Hive-metastore wiring is removed entirely. State persists in Unity Catalog (the `unity` side catalog) plus the external Delta tables' on-disk `_delta_log`; pre-create those tables via the plain-`.sql` `make ddl-apply` (beeline) against the Spark Thrift Server (see Phase 2b + Branch E; Liquibase removed, L-015).
- **L-010** (2026-05-12): Always: Add a PATIENT360_PROJECT_ROOT env var and an _anchor_relative helper in the runner that joins relative YAML paths against it. docker-compose env block must export this var to /opt/patient_360 (or whatever the in-container project root is).
- **L-011** (2026-06-19): NEVER write a container `healthcheck` whose `test` relies on a bash-only builtin (most commonly the `/dev/tcp/<host>/<port>` TCP probe) under the `CMD-SHELL` form. `CMD-SHELL` runs the string through the image's `/bin/sh`, which on Debian/Ubuntu images (e.g. the `apache/spark` base) is **dash** — dash has no `/dev/tcp`, so the probe exits 1 on every run and the container is pinned in `health: starting` forever (never flips to `healthy`). Any dependent service wired with `depends_on: { condition: service_healthy }` then never starts, and the failure looks like a generic "stuck starting" with no hint at the shell. Fix: invoke bash EXPLICITLY via the exec form — `test: ["CMD", "bash", "-c", "(exec 3<>/dev/tcp/localhost/10000) 2>/dev/null || exit 1"]` — and confirm the base image actually ships `bash` before emitting it. Root cause: the `spark-thrift-server` healthcheck used `["CMD-SHELL", "(exec 3<>/dev/tcp/localhost/10000) ..."]`; verified empirically that `sh -c` fails (`cannot create /dev/tcp/...: Directory nonexistent`) while `bash -c` succeeds, so thrift never went healthy and the `ddl-apply` one-shot never fired.
- **L-012** (2026-06-19; **SUPERSEDED by L-015** — Liquibase is now removed entirely, not just bypassed; kept for the `getURL()`/`DATABASECHANGELOG` evidence): NEVER apply Delta DDL to a Spark Thrift Server with the **Liquibase CLI** — use a **beeline one-shot** instead. Liquibase 4.x calls `DatabaseMetaData.getURL()` during connection setup, and EVERY open-source Apache Hive JDBC driver (verified through `hive-jdbc` 4.0.1) throws `SQLFeatureNotSupportedException: Method not supported` for `getURL()` (`HiveDatabaseMetaData.getURL()`); the only driver that implements it is Cloudera's proprietary one (not on Maven Central, license click-through → not reproducible). The community `liquibase-hive` extensions (`maketubo` built for LB 3.8.4, `xiananliu/liquibase-ext-hive2` for LB 4.8.0) do NOT intercept that call against LB 4.29, and even past `getURL()` Spark SQL cannot host Liquibase's `DATABASECHANGELOG`/`...LOCK` tracking tables (no `UPDATE`/`SELECT ... FOR UPDATE`). Therefore the `ddl-apply` compose service and the `make ddl-apply` target MUST apply the changelog SQL via `beeline -u jdbc:hive2://spark-thrift-server:10000/unity` (the Spark/Thrift image already ships `beeline`), reusing the Thrift image rather than pulling `liquibase/liquibase`. Keep the Liquibase XML changelogs as the DDL **source of truth** — the applier extracts and runs their embedded `<sql>` CDATA. `CREATE TABLE IF NOT EXISTS` keeps re-apply idempotent without changelog tracking. Root cause: the rendered compose shipped a `liquibase/liquibase:4.29` one-shot that exited 1 with "Driver class could not be determined"; adding the Hive driver then surfaced the `getURL()` wall, proven unfixable with OSS components this session.

- **L-001** (2026-05-11): Always emit integration tests (any test that imports `pyspark`, boots a `SparkSession`, requires Docker, or talks to UC OSS / Marquez) under `tests/integration/<layer>/`, NEVER under `tests/<layer>/` alongside unit tests. The `@pytest.mark.integration` marker is required but NOT sufficient — the path itself encodes the contract so `pytest tests/<layer>/` is unambiguously unit-only. The generated `Makefile` MUST declare `make test` as `uv run pytest -m "not integration" tests/` and a separate `make integration-test` as `uv run pytest -m integration tests/integration/`. When generating story ACs that gate on the test suite, assert `make test` exit 0 — not bare `pytest tests/<layer>/` — so the AC tracks the Make-target contract and cannot be poisoned by an integration test sitting in a unit-test directory. Root cause: STORY-01-010's `test_reconciliation_integration.py` was emitted at `tests/utils/`, which made bare `pytest tests/utils/` fail-red whenever the local PySpark/Py4J versions drifted, even though no unit code was broken.

- **L-002** (2026-05-11): Always pin the Debian release explicitly in container base images. NEVER emit floating tags such as `python:3.12-slim`, `debian:slim`, `ubuntu:latest`, or any tag that omits the distro release codename — use the release-pinned form: `python:3.12-slim-bookworm`, `debian:12-slim`, `ubuntu:24.04`. When the LLD pins a system package (JDK version, Spark version, glibc), the Dockerfile MUST pin the base distro release that ships that package, and the skill MUST verify the package exists in the chosen release before emitting the `FROM` line. Root cause: STORY-01-007's `Dockerfile.airflow` used `FROM python:3.12-slim`; when Debian 13 (trixie) became the default slim base, `apt-get install openjdk-17-jdk-headless` started failing with exit 100 because trixie replaced openjdk-17 with openjdk-21. The break was masked for weeks by stale local layer caches, then surfaced on the first clean rebuild. LLD §6.1 pins JDK 17, so the correct base is `python:3.12-slim-bookworm` (Debian 12, where openjdk-17 is still available).

- **L-003** (2026-05-11): When fetching pinned versions of Apache project releases (Spark, Kafka, Flink, Hadoop, etc.) in a Dockerfile or installer, NEVER use `https://dlcdn.apache.org/` — that mirror only carries the currently-supported releases, so pins to older versions silently start 404-ing the moment Apache rotates them. ALWAYS use `https://archive.apache.org/dist/` for version-pinned downloads; the archive preserves every historical release. Additionally, verify the exact artifact name for the target version against the archive directory listing before emitting the URL — naming conventions change across major versions (Spark 3.x ships `-bin-hadoop3-scala2.13.tgz`, but Spark 4.x drops the `-scala2.13` suffix because Scala 2.13 is the only build). The skill MUST `curl -sI` the resolved URL during generation and fail loudly if it returns 404, rather than emitting an untested URL. Root cause: STORY-01-007's `Dockerfile.airflow` fetched `https://dlcdn.apache.org/spark/spark-4.0.0/spark-4.0.0-bin-hadoop3-scala2.13.tgz` — Spark 4.0.0 had rolled off dlcdn (mirror now serves 3.5.8 / 4.0.2 / 4.1.1) AND the `-scala2.13` suffix doesn't exist in the 4.x naming scheme.

- **L-004** (2026-05-11): Always render scaffold files BY APPLYING the cookiecutter template, NEVER by re-deriving them inline from the LLD. Any file whose path has a corresponding source under `inputs/lld/v*/templates/cookiecutter-chapter/{{cookiecutter.chapter_name}}/{{cookiecutter.project_name}}/...` MUST be produced by cookiecutter variable substitution on that source — not by the skill authoring a parallel implementation. After every `create-scaffold` run the skill MUST diff every rendered file against the post-substitution template and FAIL LOUDLY if any path under the template exists in `<project>/` with materially different content. Root cause: `create-scaffold` emitted a custom `Dockerfile.airflow` (FROM `python:3.12-slim`, manual Spark binary download from dlcdn) that diverged from the canonical template (FROM `apache/airflow:3.2.1-python3.11`, install `pyspark` via pip with no binary download). The custom file carried both L-002 and L-003 bugs; the template did not. The divergence was invisible until `make dev-up` actually ran, because neither the skill nor any downstream validator compared rendered output against the template source.

- **L-005** (2026-05-11): When emitting host-port mappings in a Dockerfile or `docker-compose.yml` for a project that may be developed on macOS, NEVER bind host ports 5000 or 7000 — Apple's AirPlay Receiver and AirTunes claim those ports by default on macOS 12+ and the user cannot reclaim them without disabling AirPlay system-wide. Choose a non-reserved host port (5001+, 7001+) and document the mapping inline with a comment. Prefer the parameterized form `"${SERVICE_HOST_PORT:-5001}:5000"` so developers can override via `.env` without editing the compose file. This rule applies to ANY service whose canonical default port is 5000 or 7000 (Marquez API, Flask default, Python `http.server` default). Root cause: `patient_360/_infra/docker/docker-compose.yml` mapped Marquez API to `5000:5000` — the template already mapped `5001:5000` to dodge AirPlay, but the skill's rendered file diverged (same class as L-004). `make dev-up` failed with `bind: address already in use`.

- **L-006** (2026-05-11): When emitting a healthcheck for a vendor service (Airflow, Marquez, Unity Catalog, Postgres, etc.), pin the health URL to the version-specific path documented for the pinned image — and verify it returns 200 against that image BEFORE writing the compose. For Airflow specifically: 1.x/2.x served `/health`, 3.x serves `/api/v2/monitor/health` (the v1 API was removed and `/health` returns 404). Whenever the LLD pins an Airflow major version >=3, the healthcheck MUST use the v2 monitor endpoint. As a general rule, NEVER copy a healthcheck URL from older docs without re-verifying against the pinned image — vendors routinely renumber API paths across majors, and Docker silently keeps the container in `unhealthy` state when the check 404s. The compose-up wait then blocks for the full healthcheck retry window, fails closed, and the user sees a generic "unhealthy" with no hint that the URL is the problem. Root cause: both the cookiecutter template and the rendered `patient_360` compose used the Airflow 2.x `/health` path against an Airflow 3.2.1 image; verified empirically that `/health => 404`, `/api/v2/monitor/health => 200`.

- **L-013** (2026-06-19): The `airflow` compose service MUST bind-mount the pipeline env-config directory `_infra/cd/config` into the container at `${PATIENT360_PROJECT_ROOT}/_infra/cd/config` (e.g. `- ../../_infra/cd/config:/opt/patient_360/_infra/cd/config:ro`). The Silver (and Gold) transforms call `utils/pipeline_config.load_config(env)`, which resolves `${PATIENT360_PROJECT_ROOT}/_infra/cd/config/<ENV>.yaml` (override: `PIPELINE_CONFIG_DIR`). Bronze never called `load_config`, so the original mount set (`src`, `contracts`, `dq_rules`, `scripts`, `data`, `uc-warehouse`) omitted it — and the gap stayed invisible until the first Silver DAG task ran, which died with `FileNotFoundError: .../\_infra/cd/config/DEV.yaml`. ALWAYS include this mount when the project has Silver/Gold layers (or set `PIPELINE_CONFIG_DIR` on the service to a mounted path). The cookiecutter template's `docker-compose.yml` airflow `volumes:` block should carry it so rendered + sync-infra output keeps it. Root cause: `_infra/` is not under any of the originally-mounted subtrees, so `/opt/patient_360/_infra` did not exist in the airflow container even though the config files existed on the host.

- **L-007** (2026-05-11): NEVER pin `pyspark==4.0.0` — that exact release ships a regression in `pyspark/core/context.py:309` that calls `accumulators._start_update_server(auth_token)` with one argument, while the function signature in `pyspark/accumulators.py:357` requires `(auth_token, is_unix_domain_sock, socket_path=None)`. Every `SparkSession.builder.getOrCreate()` raises `TypeError: _start_update_server() missing 1 required positional argument: 'is_unix_domain_sock'`. The bug blocks unit tests, integration tests, `make smoke-se`, and the runtime Bronze DAG. **Fixed upstream in 4.0.1; verified working in 4.0.2** (PySpark + spark-expectations + delta-spark 4.0.0 all coexist cleanly with a Spark 4.0.0 JVM). This project is now on the **Spark 4.1 line — pin `pyspark==4.1.1`** (required by the UC 0.5.0 connector `unitycatalog-spark_4.1_2.13`, which is published only against Spark 4.1; pyspark/delta-spark/connector are version-locked). **NOT 4.1.2** — `delta-spark==4.3.0` declares `requires_dist: pyspark<=4.1.1,>=4.0.1`, so 4.1.2 breaks `uv sync`/`uv lock`; always read delta-spark's PyPI `requires_dist` pyspark cap before pinning. `pyspark==4.0.2` applies only to legacy projects pinned to a Spark 4.0.x JVM. Regardless of line, always run via `spark-submit` (never in-process `python`) so the Python client and JVM jars stay on the same build — that skew, not the pin alone, is what surfaced the 4.0.0 `_start_update_server` `TypeError`. Before emitting any PySpark pin in Dockerfile / pyproject.toml / LIBRARIES.md, the skill MUST install the pin in a throwaway venv and execute `python -c 'from pyspark.sql import SparkSession; SparkSession.builder.master(\"local[1]\").getOrCreate().stop()'` — if SparkContext init raises, reject the pin. Important: this regression is the *real* root cause of what L-001 misdiagnosed as "Py4J version drift" — the marker-based unit/integration split in L-001 only hides the symptom; integration runs, `make smoke-se`, and the Bronze DAG still die until the PySpark pin is bumped off 4.0.0. Also: do NOT speculate about pyspark constraints from sibling libraries without verifying PyPI `requires_dist` — the working-branch LIBRARIES.md claimed `spark-expectations 2.10.0 declares pyspark[connect]<=4.0.0,>=3.0.0` to justify staying on 4.0.0, but PyPI metadata shows no such constraint; that note was speculative.
- **L-017** (2026-06-21): The scaffold has NO lint gate — `make lint` (ruff `select=[E,F,I,UP]`, line-length 100) was silently red because generators (this skill + create/update silver/ingestion) shipped UP037 (quoted `-> "F.Column"`), UP035 (`from typing import Mapping` not `collections.abc`), E501 (>100-char signatures in `utils/metrics.py`, long `F.expr` SQL strings) and I001/E402/F401 import debt that accumulated across regens. The CI workflow references in the scaffold call `make lint` but no GENERATOR runs it before reporting done. As the FINAL step of EVERY code-emitting generator, ALWAYS run `uv run ruff check --fix src/ tests/ && uv run ruff format src/ tests/` and confirm `make lint` exits 0 — `ruff format` auto-resolves UP037/UP035/I001 and explodes long signatures; for an unavoidable long SQL string, split it across implicitly-concatenated string literals.
