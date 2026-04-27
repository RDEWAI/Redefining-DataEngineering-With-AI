# chapter-5 — Full-Chain Workspace

Self-contained workspace for the full data-engineering pipeline:
DRD → HLD → DMS → STM → DQS → LLD → Stories → Code.

See `CLAUDE.md` for the plugin layout, install commands, and chapter
conventions.

## Verifying Bronze layer

After running the Bronze stories (EPIC-02), confirm end-to-end against
the local docker stack:

```bash
cd patient_360
docker compose -f _infra/docker/docker-compose.yml up -d
airflow dags trigger patient360_hourly_v1 --conf '{"ds": "2026-04-27"}'
airflow dags list-runs -d patient360_hourly_v1     # poll until success
curl -sS 'http://localhost:8080/api/2.1/unity-catalog/tables?catalog_name=unity&schema_name=bronze' | jq '.tables | length'
uv run pytest -m integration tests/integration/test_bronze_uc.py -v
```

Expected:

- 13 `unity.bronze.synthea_*` tables registered in UC
- `bronze_se_stats` has ≥ 1 row for the run's `meta_dq_run_id`
- `reconciliation_bronze` succeeded (no `SE_RUN_MISSING_FOR_DS`)
- Integration tests pass (DAG trigger, UC tables, SE artefacts,
  reconciliation, row-count parity)

For per-task developer commands, see `patient_360/README.md` §
"Run Bronze ingestion".
