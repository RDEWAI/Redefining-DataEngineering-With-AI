# rca-runner — incident webhook → headless `/sre-plugin:rca` → note on the incident

This closes the loop around the `rca` skill. Nobody types a command: a DAG task
fails, an incident opens, the RCA agent investigates, and its evidence-backed
cause is on the incident before the on-call engineer picks up the page.

```
Airflow task fails (retries exhausted)
  └─ default_args.on_failure_callback = patient_360.utils.alerting.on_task_failure   (DAG-ALERT-001)
       build_alert(context) → {dag_id, run_id, task_id, try_number, ds, env, message = exception + §8.5 log markers}
       sink.open(alert)      ALERT_SINK = keep | pagerduty | file | none    (never raises)

Keep (DEV, compose)                              PagerDuty (PROD)
  POST /alerts/event  fingerprint=dag_id/run_id    POST /v2/enqueue  dedup_key=dag_id/run_id
  POST /incidents + /incidents/{id}/alerts         PagerDuty opens the incident
  workflow rca-on-incident (incident created)      webhook subscription incident.triggered
        └─ POST http://host.docker.internal:8090/webhook/keep         POST https://<tunnel>/webhook/pagerduty

rca-runner (this directory; stdlib only; runs on the host)
  verify (Keep/generic: X-RCA-Token · PagerDuty: X-PagerDuty-Signature HMAC-SHA256)
  normalise → one alert (Keep: GET /incidents/{id}/alerts for the labels · PD: GET /incidents/{id}/alerts → custom_details)
  dedup on dag_id/run_id (in flight or journaled → 202 duplicate)
  write inputs/alerts/v1/ALERT-<id>.json  (+ incident_id, incident_url, incident_provider, dedup_key)
  claude -p "/sre-plugin:rca inputs/alerts/v1/ALERT-<id>.json" --plugin-dir sre-plugin --allowedTools … --output-format json
  parse "Root cause:" / "Owner:" / "Report:" / "Self-check:" from .result
  add_note(incident)  — never acknowledge, never resolve; a note is posted even when the run failed
  journal outputs/rca/v1/runs.jsonl
```

## Run it (DEV)

```bash
cd chapter-7/patient_360 && make dev-up          # now includes keep-backend (:8085) + keep-frontend (:3010)
cd chapter-7 && make rca-runner                  # host process on :8090, uses your Claude Code login
```

Then break a run and watch: `docker stop patient_360-uc` (not `pause`: a
paused container drops packets and Spark waits on timeouts for 10+ minutes;
a stopped one refuses connections and the task fails fast), trigger the DAG,
wait for an `ingest_*` task to exhaust its retries (about 5 minutes with
DEV retries), then `docker start patient_360-uc`. Keep (`make keep-ui`) shows
one incident; the runner posts the result as an incident comment (read it in
the UI, or `GET /alerts/<incident_id>/audit`, which is where Keep stores
incident comments).

Live run on 2026-10-15: `ingest_allergies` failed after 4 tries → incident →
webhook → `claude -p` 716 s / $4.06 → `Root cause: CONFIRMED` (Unity Catalog
not bootstrapped, then container stopped), `No code change required`,
self-check PASS, 0 permission denials, note posted.

Without a stack: `make rca-runner-smoke` posts a synthetic alert to a dry-run
runner and asserts a journaled run. `python3 sre-plugin/service/rca_runner.py
--once alert.json` processes one generic alert synchronously (real `claude`).

## Configuration (env; `_infra/docker/.env.example` lists the compose side)

| Variable | Default | Used by |
|---|---|---|
| `ALERT_SINK` | `keep` (compose) / `monitoring.alerting_sink` in `_infra/cd/config/<ENV>.yaml` | callback |
| `KEEP_API_URL` / `KEEP_API_KEY` / `KEEP_UI_URL` | `http://keep-backend:8080` in Airflow, `http://localhost:8085` on the host / `keep-dev-key` / `http://localhost:3010` | callback, runner |
| `PAGERDUTY_ROUTING_KEY` | — | callback (`ALERT_SINK=pagerduty`) |
| `RCA_WEBHOOK_URL` / `RCA_WEBHOOK_TOKEN` | `http://host.docker.internal:8090/webhook/keep` / `dev-token` | Keep workflow (rendered by `make keep-workflows`), runner |
| `PAGERDUTY_WEBHOOK_SECRET` / `PAGERDUTY_API_KEY` / `PAGERDUTY_FROM_EMAIL` | — | runner (PD signature, notes API) |
| `RCA_RUNNER_PORT` / `RCA_MAX_BUDGET_USD` / `RCA_MAX_TURNS` / `RCA_TIMEOUT_S` | `8090` / `5` / `60` / `1800` | runner |
| `AIRFLOW_API`, `UC_URI`, `MARQUEZ_API`, `PATIENT360_ENV` | sre-plugin defaults (host ports) | passed through to the skill |

## PagerDuty setup (PROD path)

1. Service → Integrations → Events API v2 → copy the integration key into `PAGERDUTY_ROUTING_KEY`; set `ALERT_SINK=pagerduty`.
2. Developer Tools → Generic Webhooks (v3) → subscription on the service for `incident.triggered`, URL `https://<your-host>/webhook/pagerduty`, copy the signing secret into `PAGERDUTY_WEBHOOK_SECRET`.
3. A REST API key with `incidents.write` into `PAGERDUTY_API_KEY`, and the user email the notes are attributed to into `PAGERDUTY_FROM_EMAIL`.
4. For a laptop DEV test of this path, expose the runner with a tunnel (for example `cloudflared tunnel --url http://localhost:8090`).

Keep and PagerDuty share everything after the webhook; only `normalise_*` and `add_note` differ.

## Verified facts (2026-10-15)

- Keep `keep-api`/`keep-ui` 0.54.3 run natively on arm64; `KEEP_WORKFLOWS_DIRECTORY` provisions the workflow at startup; the `incident / created` trigger fires for incidents created through `POST /incidents`; the inline `http` provider needs no provider config; Keep does **not** template `{{ env.* }}` in workflow YAML, hence the `.tmpl` + `make keep-workflows`; the webhook fires **before** the alert is linked, hence the runner polls `GET /incidents/{id}/alerts`; `POST /incidents/{id}/comment` needs `{"comment", "status": "firing"}`.
- Claude Code 2.1.286: `claude -p "/sre-plugin:rca <file>" --plugin-dir sre-plugin … --output-format json` runs the forked skill end to end (offline fixture: 328 s, $3.09) and returns the fixed-prefix summary lines in `.result`. Plugin `hooks.json` hooks run in `-p` mode, but only if the hook script is executable and its deny JSON carries `hookSpecificOutput.hookEventName`; both were defects in the first cut of sre-plugin and are now unit-tested. `--bare` needs `ANTHROPIC_API_KEY`; the host runner deliberately omits it so the subscription login and the plugin hook are used.
- Airflow 3.2.1: task logs live at `/opt/airflow/logs/dag_id=…/run_id=…/task_id=…/attempt=N.log`; the callback reads that tail best-effort for §8.5 markers and falls back to the operator exception.

## Not done

Auto-acknowledge/resolve, Slack delivery, SLA-miss alerts, and a containerised runner (the host process is the DEV default so that `claude` uses your login and `docker compose logs` works without socket plumbing).
