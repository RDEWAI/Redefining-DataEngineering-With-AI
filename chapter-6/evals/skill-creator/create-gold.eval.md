---
skill: create-gold
status: filled
version: "1.0"
last_reviewed: 2026-05-25
---

# create-gold — Skill-Creator Eval

## What this skill should do

Generate the Gold layer (consumer aggregates) from approved LLD §5.3, DMS §4, STM Silver-to-Gold, and DQS §2-3 Gold rules.

## Scenarios

### S1 — Story mode, single Gold table

**Invoke**: `/developer-plugin:create-gold STORY-05-002` (scope: `patient_summary`).

**Expected**:
- Phase 0 confirms upstream artifacts `Approved`.
- Emits `src/patient_360/gold/build_patient_summary.py` reading from Silver, writing Delta to `gold/patient_summary/`.
- Emits `contracts/patient_summary.yml` with DMS §4 columns verbatim.
- Emits `dq_rules/patient_summary.yml` (`agg_dq` + `query_dq` from DQS §3).
- Wires `gold_aggregations` TaskGroup in `airflow/dags/patient360_hourly_v1.py` with `silver_facts >> gold_aggregations >> reconciliation_gold`.
- Phase 7 validate-gold returns PASS.

### S2 — Full mode

**Invoke**: `/developer-plugin:create-gold full` → emits all 3 Gold tables (`patient_summary`, `patient_clinical_history`, `patient_billing_summary`) in topo order.

### S3 — Hard rules

- Never invents columns: every Gold column traces to DMS §4 or a documented derivation in STM.
- DQ gate runs BEFORE the write (per LLD §8.2).
- Never reads from Bronze directly — Gold reads only from Silver (LLD §5.3).
- Phase-1 has exactly 3 Gold tables; the skill MUST refuse to add a 4th without an LLD update.

## Trigger disambiguation

| Prompt | Expected | Beats |
|---|---|---|
| "build the patient_summary table" | create-gold | create-silver |
| "generate the consumer-facing aggregates" | create-gold | create-silver, create-ingestion |
| "implement the silver-to-gold transform" | create-gold | create-silver |

## Description quality checks

- [x] Lists the 3 Phase-1 Gold tables explicitly.
- [x] Cites LLD §5.3 / DMS §4 / STM Silver-to-Gold / DQS §2-3.
- [x] Project-agnostic claim explicit.

## Known weaknesses

- No e2e eval yet — needs a frozen LLD fixture with Gold tables defined.
- `wait_for_silver_complete` sensor pattern isn't yet asserted in the eval.
