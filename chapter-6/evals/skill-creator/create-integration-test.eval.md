---
skill: create-integration-test
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# create-integration-test — Skill-Creator Eval

## What this skill should do

Generate per-layer integration tests that trigger the Airflow DAG against the local docker-compose stack and assert end-to-end DQ.

## Scenarios

### S1 — Silver integration test

**Invoke**: `/developer-plugin:create-integration-test STORY-03-099`.

**Expected**:
- Emits `tests/integration/silver/test_silver_e2e.py` marked `@pytest.mark.e2e`.
- Triggers the silver TaskGroup via Airflow REST API.
- Asserts Delta tables exist with expected row counts; queries Marquez for lineage; queries Spark Expectations stats table for DQ pass rate.

### S2 — Hard rules

- Always tagged `@pytest.mark.e2e` (excluded from `make test` default).
- References `docker-compose.yml` ports from `inputs/code/v*/docker-compose-conventions.md`, never hardcoded.
- Asserts Unity Catalog tables registered (matches LLD Decision 17).

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "write the end-to-end test for silver" | create-integration-test | create-deploy-validation |
| "integration test that hits airflow and marquez" | create-integration-test | create-silver |
| "e2e test the silver dag" | create-integration-test | validate-dag |

## Description quality checks

- [x] Specifies local docker-compose stack (Airflow + UC + Marquez).
- [x] Lists the assertions (existence, row counts, lineage, DQ).

## Known weaknesses

- No retry logic for flaky Marquez ingestion — Phase 2 should add a polling helper.
