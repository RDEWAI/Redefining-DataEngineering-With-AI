---
name: refresh-libraries
description: >
  Re-verifies every row in `inputs/code/v*/LIBRARIES.md` against upstream sources
  (context7, PyPI JSON, GitHub releases), prints a diff, asks the user for
  approval via AskUserQuestion, and rewrites `LIBRARIES.md` with a fresh
  `last_verified` timestamp. Invoke standalone (`/developer-plugin:refresh-libraries`)
  or automatically from any create-*/update-* skill when the cached versions are
  stale. Use when the user asks to:
  - Refresh / bump / update library versions in the pattern handbook
  - Check if pinned libraries are current
  - Respond "Refresh now" to a staleness prompt from another skill
argument-hint: "[library-name | 'all']"
allowed-tools: Read, Write, Edit, Bash, AskUserQuestion, WebFetch
context: fork
---

# Refresh Library Versions

You re-verify the version catalogue in `inputs/code/v*/LIBRARIES.md` and rewrite
the file with today's `last_verified` timestamp after the user approves.

## Workspace Discovery

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/../scripts/check-learnings-queue.py --discover
```

The JSON supplies `{workspace_root}`, `{project_root}`, `{learnings_queue}`.

Then discover the latest pattern handbook:

```bash
PATTERNS_DIR=$(ls -d "${workspace_root}/inputs/code/v"* 2>/dev/null | sort -V | tail -1)
LIBRARIES_FILE="${PATTERNS_DIR}/LIBRARIES.md"
if [ ! -f "$LIBRARIES_FILE" ]; then
  echo "CRITICAL: ${LIBRARIES_FILE} not found. Cannot refresh a non-existent catalogue."
  exit 1
fi
```

## Workflow

### Phase 1 — Load current catalogue

Read `LIBRARIES.md`. Extract the frontmatter (`last_verified`,
`verified_by`, `freshness_policy`) and parse the body table into a
list of rows: `{library, version, docs_url, note}`.

### Phase 2 — Resolve latest versions

For each row, call the resolver script:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/refresh-libraries/scripts/refresh_libraries.py \
  --current "$LIBRARIES_FILE" \
  --filter "${1:-all}" \
  --out /tmp/refresh_libraries.diff.json
```

The script queries, in order of availability:

1. **context7** (`mcp__context7__resolve-library-id` →
   `mcp__context7__query-docs`) — primary source where supported.
2. **PyPI JSON API** — `https://pypi.org/pypi/{pkg}/json` for Python
   packages (PySpark, pytest, ruff, duckdb, pytest-mock,
   delta-spark, spark-expectations).
3. **GitHub releases** — `https://api.github.com/repos/{owner}/{repo}/releases/latest`
   for OSS projects (Unity Catalog, Marquez, OpenLineage, UV).
4. **Apache mirror / docs page** — Airflow.

The JSON output is the diff table:
`[{library, old_version, new_version, old_url, new_url, breaking_change_note}]`.

### Phase 3 — Present diff & ask approval

Render the diff as a markdown table for the user:

```
| Library                | Current  | Latest   | Breaking? |
|------------------------|----------|----------|-----------|
| PySpark [pipelines]    | 4.1.1    | 4.1.2    | no        |
| Delta Lake             | 4.2.0    | 4.2.0    | —         |
| pytest                 | 9.0.3    | 9.1.0    | no        |
| ...                    | ...      | ...      | ...       |
```

Then call **AskUserQuestion** with:
- **Question**: "Apply these library updates to `LIBRARIES.md`?"
- **Options**:
  - `Apply all updates` — accept every non-identical row.
  - `Select per library` — show a follow-up AskUserQuestion per updated row (yes / no).
  - `Cancel` — abort; leave `LIBRARIES.md` unchanged.

If the user selects per-library, iterate and record accepted rows.

### Phase 4 — Rewrite `LIBRARIES.md`

- Update accepted rows (version, docs URL, breaking-change note).
- Update frontmatter:
  - `last_verified: {today_YYYY-MM-DD}`
  - `verified_by: refresh-libraries`
- Preserve the table structure and any surrounding prose.
- Use `Write` (full rewrite) — not line-patching — so formatting is clean.

### Phase 5 — Log and return

Append to the learnings queue:

```bash
echo '{"skill":"refresh-libraries","date":"{today}","event":"catalogue-refreshed","applied":N,"invoked_by":"{caller_or_user}"}' \
  >> "{learnings_queue}"
```

Print a one-line summary:
`Refreshed N/M libraries. LIBRARIES.md last_verified = {today}.`

If invoked from another skill (e.g. `create-scaffold` after the user
chose "Refresh now" at the staleness prompt), return control to the
caller so it resumes using the updated versions.

## Hard Rules

1. **Never write without approval.** If the user cancels, the file stays unchanged.
2. **Preserve unresolved rows.** If a version cannot be resolved (network error, rate limit), leave the existing row intact and add an `⚠ unresolved {date}` note in the `Breaking-change notes` column; do not silently drop it.
3. **No version downgrades** unless the user explicitly approves; warn if the resolver returns a lower version than the current pin (usually a PyPI yank).
4. **Frontmatter is authoritative** for `freshness_policy`. Other skills read `last_verified` from here; never bypass it.

## Edge Cases

- **Network unavailable** — fall back to cached PyPI metadata in `~/.cache/uv/` where possible; else abort with instructions to retry.
- **context7 unavailable / missing library** — fall back to PyPI / GitHub releases automatically.
- **Major-version bump** — add a breaking-change note pointing to the upstream changelog; require explicit per-library approval even if the user picked "Apply all".
- **User ran `refresh-libraries` today already** — idempotent; diff is empty; report "No updates since last_verified".

## Learnings & Corrections

_No learnings recorded yet._
