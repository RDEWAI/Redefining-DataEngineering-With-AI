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

## Step 1: Run the validator

```bash
uv run python chapter-5/developer-plugin/skills/ingestion/validate-ingestion/scripts/validate_ingestion.py \
  --project-root chapter-5/patient_360 \
  --lld "$(ls -t chapter-5/inputs/lld/v*/LLD-*.md | grep -v '\.bak$' | head -1)"
```

The script returns a non-zero exit code if any CRITICAL issues are found.

## Checks

### CRITICAL (must fix before merge)
- Python syntax errors in `ingestion_runner.py`, `ingestion_factory.py`,
  `spark_submit_wrapper.py` (`python -m py_compile`)
- Missing required module (`ingestion_runner.py` / `ingestion_factory.py` /
  `spark_submit_wrapper.py`) under `src/patient_360/bronze/`
- LLD §5.1 lists a Bronze table with no matching
  `airflow/configs/{table}.yml`
- A YAML config references a `dq_rules/{table}.yml` that does not exist
- A YAML config references a `contracts/{table}.yml` that does not exist
- Per-table YAML missing required keys: `table`, `source`, `schema_ref`,
  `output_path`, `empty_input_behavior`, `dq_rules_table`
- Critical table (patients, encounters, allergies, organizations, providers,
  payers) has `empty_input_behavior` other than `fail`
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

### INFO (good to know)
- Module missing a module-level docstring
- YAML config missing a `# updated:` trailer
- Runner `action_if_failed` defaults to `ignore` rather than `fail`/`drop`

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
