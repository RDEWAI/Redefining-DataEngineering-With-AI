# Alerts (input to `/sre-plugin:rca`)

Drop `ALERT-<ts>-<slug>.json` files here to hand a fired alert to the RCA
skill, or let the skill build one itself from Airflow (`latest`,
`dag_id/task_id`) or from pasted error text. Nothing on this stack delivers to
PagerDuty/Slack yet (LLD §8.5 channels are not provisioned), so the file is
the alert.

## Contract

```json
{
  "alert_id": "ALERT-20261014T153012Z-reconciliation_bronze",
  "fired_at": "2026-10-14T15:30:12+00:00",
  "env": "DEV",
  "condition": "Pipeline task failure after all retries",
  "failure_class": "SE run-evidence gate (§8.6 / Decision 16)",
  "severity": "CRITICAL",
  "channel": "PagerDuty p360-critical",
  "response_time": "15 min",
  "source": "airflow",
  "dag_id": "patient360_hourly_v1",
  "run_id": "scheduled__2026-10-14T15:00:00+00:00",
  "task_id": "reconciliation_bronze",
  "try_number": 3,
  "ds": "2026-10-14",
  "message": "SE_RUN_MISSING_FOR_DS=2026-10-14 meta_dq_run_id=20261014T150000 layer=bronze env=DEV"
}
```

Required: `alert_id`, `fired_at`, `env`, `condition`, `severity`, `source`
(`airflow` | `se` | `manual`), `message`. Airflow-sourced alerts also need
`dag_id` and `task_id`. Anything missing is derived where possible: `ds` from
`run_id`, `condition`/`severity`/`channel` from the message via the LLD §8.5
marker table in `sre-plugin/skills/rca/scripts/rca_common.py`. A minimal
hand-written alert is therefore just:

```json
{"task_id": "reconciliation_bronze", "run_id": "scheduled__2026-10-14T15:00:00+00:00",
 "message": "SE_RUN_MISSING_FOR_DS=2026-10-14 layer=bronze env=DEV"}
```

`condition` values are the row labels of LLD §8.5 (for example "UC OSS
unreachable after circuit-breaker retries", "Allergy DQ failure (any
clinical_allergies rule)", "Row count drop > 5% from baseline (query_dq)").

Optional incident fields, written by the rca-runner and shown in §1 of the report:
`incident_id`, `incident_url`, `incident_provider` (`keep` | `pagerduty`), `dedup_key`
(`<dag_id>/<run_id>`, one incident per DAG run), and `markers` (LLD §8.5 marker
lines the callback found in the task log). Unknown fields are rejected by
`find_alert.py`, so add new ones to `OPTIONAL_ALERT_FIELDS` in `rca_common.py`.
