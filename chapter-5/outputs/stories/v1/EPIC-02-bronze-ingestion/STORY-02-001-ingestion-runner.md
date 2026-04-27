# STORY-02-001: Bronze ingestion runner + soft-import SE (bootstrap mode)

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Ingestion Layer |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 5 |
| **Sprint** | 1 |
| **Dependencies** | STORY-01-002, STORY-01-003 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want a generic `ingestion_runner.py` that reads a per-table YAML config, executes the standard read→transform→SE→write pattern, and writes Delta to UC, so that all 13 Bronze tables share a single implementation.

## Description

Implement `patient_360/src/patient_360/bronze/ingestion_runner.py` exposing a `main(--config-path, --env, --ds)` CLI. It reads `airflow/configs/{table}.yml`, loads the source DataFrame from DuckDB, applies schema enforcement against the contract, calls SE for inline row_dq + agg_dq (soft-imported in this bootstrap story; STORY-02-004 will remove the soft-import), then writes Delta with `replaceWhere ds = '{ds}'` and `saveAsTable("unity.bronze.{table}")` per Decision 15. **Bootstrap-only:** the SE import uses `try/except ImportError` and logs `WARNING: se_runner not available` per LLD §8.6 — STORY-02-004 supersedes this.

## Acceptance Criteria

- [ ] `patient_360/src/patient_360/bronze/ingestion_runner.py` exists with `--config-path`, `--env`, `--ds` CLI flags [LLD §2.3, §5.1]
- [ ] Runner reads YAML config and resolves source via DuckDB read [LLD §5.1]
- [ ] Runner writes Delta to `unity.bronze.{table}` via `saveAsTable` per Decision 15 [LLD §5.1]
- [ ] Runner soft-imports `se_runner` and logs `WARNING: se_runner not available` in bootstrap mode [LLD §8.6]
- [ ] Empty-input behavior honors per-table YAML override (`fail` for patients/encounters/allergies/orgs/providers/payers; `write_empty` default) [LLD §5.1, Decision 11]

## Technical Notes

- **Upstream references**: LLD §2.3 (module interfaces), §5.1 (Bronze tasks), §8.6 (SE bootstrap mode), Decision 11 (empty-input), Decision 15 (UC saveAsTable)
- **Implementation hints**: Use `argparse`. Wrap SE import in `try/except ImportError`; log warning and pass DataFrame through unchanged when bootstrap. Use `df.write.format("delta").option("replaceWhere", f"ds='{ds}'").saveAsTable(f"unity.bronze.{table}")`.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §2.3, §5.1, §8.6, Decision 11, Decision 15 |
| DMS | §3 Bronze schemas |
| STM | Source-to-Bronze |
| DQS | §2 row_dq (referenced via SE) |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | argparse + config load + replaceWhere SQL | `pytest patient_360/tests/bronze/test_ingestion_runner_unit.py` |
| Contract | Empty-input override per-table | `pytest patient_360/tests/bronze/test_empty_input_behavior.py` |

## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/bronze/ingestion_runner.py"
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: '--config-path'}
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: '--ds'}
AC2:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: 'duckdb'}
AC3:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: 'unity.bronze'}
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: 'saveAsTable'}
AC4:
  - grep: {file: "patient_360/src/patient_360/bronze/ingestion_runner.py", pattern: 'WARNING: se_runner not available'}
AC5:
  - pytest: {node: "patient_360/tests/bronze/test_empty_input_behavior.py"}
```

## How to Test (User)

### Prerequisites

- STORY-01-001..004 complete
- `make dev-setup` completed
- DuckDB synthea source seeded

### Steps

1. `cd patient_360 && uv run python src/patient_360/bronze/ingestion_runner.py --config-path airflow/configs/patients.yml --env dev --ds 2026-04-27`
2. `cd patient_360 && uv run pytest tests/bronze/test_ingestion_runner_unit.py -v`

### Expected outcome

- Step 1 prints `WARNING: se_runner not available` and `wrote N rows to unity.bronze.synthea_patients`
- Step 2 all unit tests pass

## Documentation Updates

- [ ] Update `patient_360/README.md` § "Run Bronze ingestion" with the runner command
