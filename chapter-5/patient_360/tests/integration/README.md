# Integration tests

Marked `@pytest.mark.integration` so they're excluded from the default
unit run. Run explicitly:

```bash
cd patient_360
uv run pytest -m integration tests/integration/ -v
```

## Prerequisites

- Local docker stack up: `docker compose -f _infra/docker/docker-compose.yml up -d`
- Unity Catalog OSS reachable at `http://localhost:8080`
- Airflow CLI on PATH (`pip install apache-airflow` or run inside the airflow container)
- DuckDB source seeded: `make seed-source-data`

## Bronze end-to-end (`test_bronze_uc.py`)

Triggers `patient360_hourly_v1`, waits for completion, then asserts:

- All 13 `unity.bronze.synthea_*` tables landed in UC
- `bronze_se_stats` has ≥ 1 row for the run's `meta_dq_run_id`
- Per-table `<table>_error` tables created by SE for the 6 critical tables
- `reconciliation_bronze` succeeded (no `SE_RUN_MISSING_FOR_DS`)
- Source-vs-Bronze row counts match within ±1 % (DQS §4)
