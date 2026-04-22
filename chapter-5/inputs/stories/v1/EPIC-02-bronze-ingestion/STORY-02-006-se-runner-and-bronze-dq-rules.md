# STORY-02-006: Implement SE Runner, Per-Table DQ Rules, and Quarantine

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02: Bronze Layer -- Config-Driven Ingestion |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 8 |
| **Sprint** | Sprint 3 |
| **Dependencies** | STORY-02-002 |
| **Status** | To Do |

## User Story

As a data quality engineer, I want `se_runner.py` implemented with the full interface (env/dq_env mapping, quarantine path, bootstrap mode) and per-table `dq_rules/{table}.yml` files so that inline row_dq and agg_dq validation executes within each Bronze ingestion task and is safe to promote to STAGING.

## Description

Implement `src/patient_360/utils/se_runner.py` (currently marked `[PENDING IMPLEMENTATION]` in LLD §2.3). The runner wraps spark-expectations for inline DQ validation. Call signature: `run_dq(df, table, env, action_if_failed, dq_rules_dir)`. The `env` parameter must be mapped to the SE `dq_env` value (DEV → DEV, STAGING → QA, PROD → PROD) before passing to spark-expectations. DQ rules are discovered by table name convention from `dq_rules/{table}.yml` (the `dq_rules_dir / f"{table}.yml"` path). Rejections with `action_if_failed: drop` are routed to `warehouse/{env}/quarantine/bronze/{table}/` (from `ingestion.quarantine_path` config parameter). Three action modes: fail, drop, ignore.

Create all 13 per-table DQ rule files at `dq_rules/{table}.yml` covering DQ-FLD-001 through DQ-FLD-045. Each file follows the SE rule schema (`rule_type: row_dq | agg_dq`, `rule`, `description`, `error_drop_threshold`).

Once this story is complete, remove the soft-import `try/except ImportError` block from `ingestion_runner.py` — the bootstrap fallback must be eliminated before STAGING promotion (LLD §8.5, Decision 14).

## Acceptance Criteria

- [ ] `src/patient_360/utils/se_runner.py` implemented with signature `run_dq(df, table, env, action_if_failed, dq_rules_dir)` [LLD §2.3]
- [ ] `env` parameter mapped to SE `dq_env`: DEV→DEV, STAGING→QA, PROD→PROD before calling spark-expectations [LLD §2.3, §5.4]
- [ ] DQ rules discovered by convention from `dq_rules_dir / f"{table}.yml"` [LLD §2.3]
- [ ] `action_if_failed: fail` raises exception halting the task [LLD §5.4]
- [ ] `action_if_failed: drop` quarantines failing rows to `warehouse/{env}/quarantine/bronze/{table}/` (resolved from `ingestion.quarantine_path` config) [LLD §5.4, §8.2]
- [ ] `action_if_failed: ignore` logs violations and emits metrics without blocking [LLD §5.4]
- [ ] All 13 per-table `dq_rules/{table}.yml` files created covering DQ-FLD-001 to DQ-FLD-045 [DQS §2]
- [ ] Critical table rules (patients, encounters, allergies, organizations, providers, payers) use `action_if_failed: fail` [DQS §2, DRD §1.3]
- [ ] Soft-import `try/except ImportError` block removed from `ingestion_runner.py` [LLD §8.5]
- [ ] DQ pass/fail metrics emitted via OpenTelemetry [LLD §5.4]
- [ ] Bootstrap mode warning (`WARNING: se_runner not available`) no longer appears in logs after this story is merged [LLD §8.5]

## Out of Scope

- `reconciliation.py` (cross-table query_dq) — covered in STORY-02-007
- Silver/Gold DQ rules (handled in EPIC-03/04/05)
- Dead-letter writer for schema/FK rejections (handled in STORY-02-008)

## Technical Notes

- **Upstream references**: LLD §2.3 (se_runner contract), LLD §5.4 (Inline SE Validation + dq_env mapping table), LLD §7.1 (`storage.quarantine_path`, `ingestion.quarantine_path`), LLD §8.5 (Bootstrap mode degradation), LLD §13 Decision 14 (STAGING promotion checklist), DQS §2 (Bronze DQ rules)
- **Developer plugin**: Use `developer-plugin:create-ingestion STORY-02-006` (story mode) to generate `se_runner.py` and sync `dq_rules/*.yml` files.
- **Implementation status (commit c6cbd6a, 2026-04-21)**: `src/patient_360/utils/se_runner.py` has been implemented with full SE 2.10 integration: `_DQ_ENV_MAP` (DEV→DEV, STAGING→QA, PROD→PROD), quarantine routing via `WrappedDataFrameWriter`, stats table pre-registration (`_ensure_stats_table`), Kafka streaming disabled, all notification flags off for local/non-Databricks runs. All 13 `dq_rules/{table}.yml` files are present from DQS v2 SE rule files.
- **Remaining open AC**: The `try/except ImportError` bootstrap block in `ingestion_runner.py` (lines ~265-270) has **not** been removed. This is the sole remaining acceptance criterion for this story. Until removed, ingestion silently degrades to pass-through DQ in environments where the import fails.
- **STAGING promotion blocker**: STORY-07-003 (Environment Promotion) cannot include STAGING promotion until the soft-import fallback is removed from `ingestion_runner.py` [LLD §8.5, Decision 14].

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §2.3 (se_runner), §5.4 (Inline SE + dq_env), §7.1 (quarantine params), §8.5 (bootstrap), §13 Decision 14 |
| DMS | §4 (Bronze table schemas for rule context) |
| STM | -- |
| DQS | §2 (Bronze rules DQ-FLD-001 to DQ-FLD-045) |
