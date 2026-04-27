# Bronze ingestion configs

One YAML per source table (LLD §5.1, Decision 7). The TaskGroup factory
(`src/patient_360/bronze/ingestion_factory.py`) scans this directory at
DAG parse time and emits one `SparkSubmitOperator` per file pointing at
`patient_360.bronze.ingestion_runner`.

## Per-table config schema

| Key | Type | Description |
|---|---|---|
| `table` | str | Bronze table name (`synthea_<x>`) — lands in `unity.bronze.<table>` |
| `target` | str | UC-managed write target. MUST start with `unity.bronze.synthea_` (Decision 15). |
| `source.schema` | str | Source schema (e.g. `synthea`). |
| `source.table` | str | Source table name. |
| `source.format` | str | `duckdb`, `csv`, `jdbc`, or `delta`. |
| `source.path` | str | (csv/duckdb file path) Optional for JDBC. |
| `schema_ref` | str | Path to the contract YAML defining StructType columns. |
| `metadata_columns` | list | Audit cols added by the runner: `ds`, `_ingested_at`, `_source_batch_id`. |
| `empty_input_behavior` | enum | `fail` (critical tables) or `write_empty` (default). |
| `dq_rules_table` | str | Convention key — runner loads `dq_rules/<dq_rules_table>.yml`. |
| `se_action_if_failed` | enum | `fail` / `drop` / `ignore` — fail-closed default for any rule that omits its own `action_if_failed`. |
| `quarantine_path` | str | Per-table SE drop-action path; `{env}` and `{table}` are templated. |
| `timeout_minutes` | int | LLD §4.2. |
| `retries` | int | LLD §8.1 (Bronze default = 3). |
| `retry_delay_seconds` | int | LLD §8.1 (Bronze default = 60). |

## Critical tables (`empty_input_behavior: fail`)

`patients`, `encounters`, `allergies`, `organizations`, `providers`,
`payers` — see LLD §5.1 + DRD §1.3 (allergies = safety-critical).

## Path resolution

The factory resolves the configs directory in this order:

1. Explicit `configs_dir=` kwarg.
2. `AIRFLOW_CONFIGS_DIR` env var (set by `_infra/docker/docker-compose.yml`).
3. `/opt/airflow/configs` (cookiecutter default).

Never hardcode `airflow/configs` — relative resolution breaks under
Airflow's `/opt/airflow/` working directory.
