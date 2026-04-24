---
name: update-ingestion
description: >
  Updates the Bronze ingestion framework (runner, factory, spark-submit wrapper,
  and per-table YAML configs) to reflect changes in the latest LLD or STM.
  Applies minimal incremental edits — never rewrites unchanged files.
  Use when the user asks to:
  - Update, modify, or patch the ingestion code
  - Add, remove, or rename a Bronze table from configs
  - Reflect an LLD or STM change in the ingestion configs
  - Change empty-input behavior, retries, timeout, or DQ action for a table
argument-hint: "[table-name or config-file-path]"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, AskUserQuestion, Skill
context: fork
---

# Update Bronze Ingestion Framework

You are a senior Data Engineer. Your job is to apply targeted incremental
edits to the ingestion runner, factory, wrapper, or per-table YAML configs so
they stay in sync with the latest LLD and STM without breaking existing
pipeline runs.

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

Before editing ingestion code, load the latest coding-patterns handbook:

```bash
PATTERNS_DIR=$(ls -d "{workspace_root}/inputs/code/v"* 2>/dev/null | sort -V | tail -1)
if [ -z "$PATTERNS_DIR" ] || [ ! -d "$PATTERNS_DIR" ]; then
  echo "CRITICAL: inputs/code/v*/ not found. Run /developer-plugin:refresh-libraries to initialize the library cache."
  exit 1
fi
LIBRARIES_FILE="$PATTERNS_DIR/LIBRARIES.md"
```

**Required pattern docs for this skill:**

- `$PATTERNS_DIR/bronze-ingestion-pattern.md` — registry → factory → runner shape
- `$PATTERNS_DIR/spark-expectations-pattern.md` — SE YAML rule shape + runner wrapper
- `$PATTERNS_DIR/naming-conventions.md` — audit columns, table names
- `$PATTERNS_DIR/logging-error-handling.md` — module logger + fail-fast
- `$PATTERNS_DIR/LIBRARIES.md` — pinned PySpark / Delta / SE versions

### Library freshness check

```bash
LAST_VERIFIED=$(grep '^last_verified:' "$LIBRARIES_FILE" | awk '{print $2}')
TODAY=$(date -u +%Y-%m-%d)
AGE_DAYS=$(python3 -c "from datetime import date; print((date.fromisoformat('$TODAY') - date.fromisoformat('$LAST_VERIFIED')).days")
```

If `AGE_DAYS > 30`, pause and call **AskUserQuestion** with options `Refresh now` / `Proceed with cached versions` / `Cancel`. On Refresh, invoke `/developer-plugin:refresh-libraries` then resume.

### References trailer (in output)

Emit a `### References` section citing consumed pattern docs + LIBRARIES.md vintage. Add a stale-cache warning if the user opted to proceed with cached versions.

## Workflow

### Phase 0: Read Current State

1. Read the latest LLD:
   ```bash
   LATEST_LLD_DIR=$(ls -d {workspace_root}/inputs/lld/v* | sort -V | tail -1)
   ls -t "$LATEST_LLD_DIR"/LLD-*.md | grep -v '\.bak$' | head -1
   ```
2. Read the current ingestion artifacts:
   - `{project_root}/src/{project_name}/bronze/ingestion_runner.py`
   - `{project_root}/src/{project_name}/bronze/ingestion_factory.py`
   - `{project_root}/src/{project_name}/bronze/spark_submit_wrapper.py`
   - `{project_root}/src/{project_name}/utils/se_runner.py`
   - `{project_root}/airflow/configs/*.yml`
3. Diff LLD §2.3, §5.1, §7 against the generated files to compute the
   minimum set of edits. Produce a short change-set plan before editing.

### Phase 1: Classify the Update

Map the request to exactly one scenario:

| Scenario | Trigger | Action |
|----------|---------|--------|
| A. Add a new Bronze table | New row in LLD §5.1 not represented in `airflow/configs/` | Create `airflow/configs/{table}.yml`. Only touch runner/factory/wrapper if the contract changed. |
| B. Remove a Bronze table | Row dropped from LLD §5.1 | Delete the corresponding `airflow/configs/{table}.yml`. Leave runner untouched. |
| C. Rename a Bronze table | Table name changed in LLD §5.1 | Rename the YAML file; update references in contracts/dq_rules/DAG if needed (ask user first). |
| D. Change per-table knob | Retry, timeout, empty-input behavior, SE action, or quarantine path changed | Edit only the affected keys in `airflow/configs/{table}.yml`. |
| E. Runner/factory logic change | LLD §2.3 interface contract changed | Edit `ingestion_runner.py` / `ingestion_factory.py` / `spark_submit_wrapper.py` in place; preserve public function signatures unless the LLD explicitly renames them. |
| F. DQ rules refresh | New DQS version published under `{workspace_root}/inputs/dqs/v{N}/se-rules/` | Re-sync `dq_rules/{table}.yml` from `se-rules-synthea-{table}.yaml` for each changed table. Runner/configs stay untouched. |
| G. SE runner change | LLD §2.3 `se_runner.py` interface updated (new parameter, dq_env mapping change, quarantine routing change) | Edit `src/{project_name}/utils/se_runner.py`. Re-verify `_DQ_ENV_MAP`, `user_conf` wiring keys, and `_ensure_stats_table` logic. Update `run_inline_dq` call site in `ingestion_runner.py` if the `run_dq` signature changed. |

Ambiguous request? Call `AskUserQuestion` with the candidate scenarios as
options before editing.

### Phase 2: Apply Edits

- Use `Edit` (not `Write`) for existing files — preserve unrelated content.
- Bump the module header comment (or YAML `# updated: {YYYY-MM-DD}` marker)
  when editing a file, so reviewers can trace the change.
- Preserve task IDs and config keys unless the LLD explicitly renames them.
- Never change a table's `empty_input_behavior` from `fail` to a weaker value
  without user confirmation — the six critical tables (patients, encounters,
  allergies, organizations, providers, payers) must stay `fail` per LLD §5.1.
- Do not reintroduce the legacy config shape: `output_path` must be the Delta
  table root (no `ds={ds}/` suffix — the runner partitions by `ds`), and
  `metadata_columns` must contain `ds`, `_ingested_at`, and `_source_batch_id`
  (underscore prefix — matches DQS SE rules).
- `quarantine_path` in per-table YAML must follow `warehouse/{env}/quarantine/bronze/{table}/`
  (LLD §7). Do not use absolute paths or embed `ds=` here.
- When editing `se_runner.py`, never remove `_ensure_stats_table` or the
  `user_conf` keys that disable Kafka streaming and notifications — removing
  them causes Databricks secrets errors on local (non-Databricks) runs.

### Phase 2.5: Update Tests

Every code or config change must keep `tests/bronze/` green. Use this map:

| Scenario | Test impact |
|----------|-------------|
| A. Add a Bronze table | Add the table to `EXPECTED_TABLES` in `test_per_table_configs.py`; the parametrized sweep will auto-cover the new config. |
| B. Remove a Bronze table | Drop from `EXPECTED_TABLES`. |
| C. Rename a Bronze table | Update `EXPECTED_TABLES` and `CRITICAL_EMPTY_FAIL` if it applies. |
| D. Change a knob (retry/timeout/empty-input) | No test edit needed — the parametrized assertions re-run. |
| E. Runner/factory logic change | Add or update unit tests in `test_ingestion_runner.py` for the new branch; never leave a new conditional uncovered. |
| F. DQ rules refresh | No test edit needed — `test_per_table_configs.py::test_se_rules_have_three_envs` covers the schema. |
| G. SE runner change | Add or update tests in `test_ingestion_runner.py` covering the new branch (e.g. new `dq_env` mapping entry, changed `run_dq` call signature). |

Run `uv run pytest tests/bronze/ -v` locally before reporting completion.

### Phase 3: Validate

Invoke `/developer-plugin:validate-ingestion` on the edited files. Fix any
CRITICAL findings before reporting completion.

## Output Summary

Print a short change-set table: `File | Change type (added|edited|renamed|deleted) |
Reason (LLD §ref)` so the user sees exactly what moved.
