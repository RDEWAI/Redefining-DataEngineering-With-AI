---
name: validate-ingestion
description: >
  Validates the Bronze ingestion framework for correctness against LLD §2.3
  and §5.1. Runs static checks on the ingestion runner, factory, SparkSubmit
  wrapper, and per-table YAML configs. Reports findings as CRITICAL / WARNING /
  INFO.
  Use when the user asks to:
  - Validate, check, or lint the ingestion code
  - Verify every Bronze table has a config file
  - Confirm per-table configs match the LLD empty-input / retry / DQ spec
argument-hint: "[file-or-dir-path]"
allowed-tools: Read, Bash, Grep, Glob
---

# Validate Bronze Ingestion Framework

You are a senior Data Engineer. Validate the ingestion artifacts and report findings.

## Workspace Discovery

Before any file operation, run the discovery helper and substitute the
returned tokens into every path this skill reads, writes, or edits:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/validate-stories/scripts/status_rollup.py --mode discover
```

The JSON output supplies `{workspace_root}`, `{project_root}`,
`{project_name}`, `{stories_dir}`, and `{learnings_queue}`. The plugin is
project-agnostic — never hardcode project or chapter names in edits.

## Coding Patterns Handbook

Load the pattern docs this skill checks against (read-only; no freshness prompt):

```bash
PATTERNS_DIR=$(ls -d "{workspace_root}/inputs/code/v"* 2>/dev/null | sort -V | tail -1)
if [ -z "$PATTERNS_DIR" ] || [ ! -d "$PATTERNS_DIR" ]; then
  echo "WARNING: inputs/code/v*/ not found — pattern-conformance checks will be INDETERMINATE."
fi
```

**Pattern docs consulted:**

- `$PATTERNS_DIR/bronze-ingestion-pattern.md` — expected runner/factory shape
- `$PATTERNS_DIR/spark-expectations-pattern.md` — expected SE rule + runner shape
- `$PATTERNS_DIR/test-pattern.md` — expected test fixtures

### References trailer (in output)

Cite each pattern doc consulted, e.g. `Checked against inputs/code/v1/bronze-ingestion-pattern.md §2`.

## Phase 0.a — Argument Resolution (mandatory, runs first)

The Skill-tool argument frequently fails to reach forked subagents. Resolve
the target via the shared resolver, which checks four sources in order:
`$SKILL_ARG` → `{workspace_root}/.skill-arg` → conversational arg → auto-mode.

```bash
read -r RESOLVED_ARG RESOLVED_SOURCE < <(
  WORKSPACE_ROOT="{workspace_root}" \
    bash "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_skill_arg.sh" "$USER_ARG" | \
    paste -sd' ' -
)
```

Print this banner as the **first line** of skill output:

```
RESOLVED TARGET: <value> (source: <SKILL_ARG | .skill-arg | conversational | __AUTO__>)
```

If `$RESOLVED_SOURCE == EMPTY`, fall through to the skill's existing
clarification step (typically `AskUserQuestion`). DO NOT ask the user before
running this resolver.

## Step 1: Run the validator

```bash
uv run python ${CLAUDE_PLUGIN_ROOT}/skills/validate-ingestion/scripts/validate_ingestion.py \
  --project-root {project_root} \
  --lld "$(ls -t {workspace_root}/../chapter-4/outputs/lld/v*/LLD-*.md | grep -v '\.bak$' | head -1)"
```

The script returns a non-zero exit code if any CRITICAL issues are found.

## Checks

### CRITICAL (must fix before merge)
- Python syntax errors in `ingestion_runner.py`, `ingestion_factory.py`,
  `spark_submit_wrapper.py` (`python -m py_compile`)
- Missing required module (`ingestion_runner.py` / `ingestion_factory.py` /
  `spark_submit_wrapper.py`) under `src/{project_name}/bronze/`
- LLD §5.1 lists a Bronze table with no matching
  `airflow/configs/{table}.yml`
- A YAML config references a `dq_rules/{table}.yml` that does not exist
- A YAML config references a `contracts/{table}.yml` that does not exist
- Per-table YAML missing required keys: `table`, `source`, `schema_ref`,
  `output_path`, `empty_input_behavior`, `dq_rules_table`
- A table that LLD §5.1 flags with `empty_input_behavior: fail` has a
  YAML config declaring a different behaviour (read the LLD §5.1 table at
  validation time — no critical-table list is hardcoded)
- Per-table YAML `output_path` embeds `ds=` (runner partitions by `ds`; the
  path must be the Delta table root, not a partition directory)
- Per-table YAML `metadata_columns` missing any of `ds`, `_ingested_at`,
  `_source_batch_id` — the DQS SE rules reference the underscored names
- Hardcoded credentials, connection strings, or absolute filesystem paths
  in runner / factory / wrapper
- `pyproject.toml` runtime dependencies missing any of `pyspark`,
  `delta-spark`, `spark-expectations`, or `pyyaml`
- Any of the three required test modules missing:
  `tests/bronze/test_ingestion_runner.py`,
  `tests/bronze/test_per_table_configs.py`,
  `tests/bronze/test_validate_ingestion.py`
- `contracts/{table}.yml` `ddl_path` or `dq_path` missing or points to a file
  that does not exist on disk (LLD §2.3)
- `ingestion_runner.py` still contains the `try/except ImportError`
  soft-import block around `se_runner` while `se_runner.py` is shipped —
  ingestion must fail closed post-implementation (LLD §8.5)

### WARNING (should fix)
- `empty_input_behavior` missing (falls back to default but should be explicit)
- `retries` or `timeout_minutes` missing from a per-table YAML
- `pyproject.toml` dev dependency `apache-airflow-providers-apache-spark`
  missing — the Airflow factory cannot build SparkSubmitOperator in tests
- Runner imports symbols it does not use
- YAML config file whose `table:` key does not match its filename
- Extra YAML config files with no row in LLD §5.1
- `metadata_columns` contains legacy `ingested_at` (without underscore) —
  should be renamed to `_ingested_at`
- `contracts/{table}.yml` `schema.columns` includes runtime metadata columns
  (`ds`, `_ingested_at`, `_source_batch_id`) — these are added by the runner,
  not declared in the business contract (LLD §2.3)

### INFO (good to know)
- Module missing a module-level docstring
- YAML config missing a `# updated:` trailer
- Runner `action_if_failed` defaults to `ignore` rather than `fail`/`drop`
- `ingestion_runner.py` soft-import bootstrap block present but `se_runner.py`
  not yet shipped (expected during bootstrap mode, LLD §8.5)

## Output Format

```
CRITICAL: [count] issue(s)
  - [file]: [description]

WARNING: [count] issue(s)
  - [file]: [description]

INFO: [count] item(s)
  - [file]: [description]

Result: PASS / FAIL
```

`FAIL` when CRITICAL count > 0, otherwise `PASS`.
