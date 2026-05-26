---
skill: create-dag
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# create-dag — Skill-Creator Eval

## What this skill should do

Generate an Airflow DAG from the LLD and pipeline configs. Outputs a production-ready DAG file under `airflow/dags/`.

## Scenarios

### S1 — Fresh DAG from approved LLD

**Invoke**: `/developer-plugin:create-dag`.

**Expected**:
- Reads `outputs/lld/v*/LLD-*.md` and the per-layer configs.
- Emits `airflow/dags/<project>_hourly_v1.py` with TaskGroups for bronze / silver_dimensions / silver_facts / gold / reconciliation.
- Uses `SparkSubmitOperator` exclusively (IL-011).
- Sets `max_active_tasks=1`, `catchup=False` (IL-014).
- Resolves DAG via `DagContext.get_current()` and passes `dag=` explicitly to TaskGroups (IL-013).

### S2 — Hard rules

- Never invents task IDs; reads from LLD §5.x.
- Never sets `driver_cores` directly on SparkSubmitOperator (forwards via `spark.driver.cores`; IL-012).

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "generate the airflow DAG from the LLD" | create-dag | create-ingestion |
| "scaffold the medallion pipeline DAG" | create-dag | create-pipeline (CI ≠ DAG) |
| "wire up the airflow orchestration" | create-dag | create-scaffold |

## Description quality checks

- [x] States it reads LLD + configs.
- [x] Aliases documented (dag generation, pipeline scaffolding, airflow pipeline creation).

## Known weaknesses

- Production cadence ≠ dev cadence; the skill doesn't auto-generate the production DAG variant with raised concurrency.
