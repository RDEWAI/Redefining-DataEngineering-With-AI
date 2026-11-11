# sre-plugin

Day-2 operations for the Patient 360 pipeline: one skill, `rca`, that turns an
alert into an evidence-cited root-cause analysis without touching the stack.

```
/sre-plugin:rca latest                                   # newest failed task in Airflow
/sre-plugin:rca patient360_hourly_v1/reconciliation_bronze
/sre-plugin:rca inputs/alerts/v1/ALERT-20261014T153012Z-reconciliation_bronze.json
/sre-plugin:rca --text "SE_RUN_MISSING_FOR_DS=2026-10-14 ..."   # pasted error
```

## What it does

1. **Intake** (`skills/rca/scripts/find_alert.py`): normalises the target into
   an alert JSON (see `inputs/alerts/v1/README.md` for the contract), classifies
   it against LLD §8.5, writes `outputs/rca/v1/<alert_id>/alert.json`.
2. **Evidence** (`collect_evidence.py`): one deterministic, read-only pass over
   Airflow (run, task instances, task log incl. Spark driver output), docker
   (`ps`, service log tails), Unity Catalog health, Spark Expectations
   `_stats`/`_error` tables via beeline, Delta history, Marquez, and a snapshot
   of the configs in force. Each surface is independent; what could not be
   collected is recorded in `evidence/manifest.json`.
3. **Analysis** (the skill, in Claude): hypothesis table → verdicts with
   evidence citations → root cause (`CONFIRMED` or `INDETERMINATE` with missing
   evidence named) → blast radius → remediation split into operator recovery,
   permanent fix routed via `DELIVERABLE-OWNERS.yaml` to a
   `/developer-plugin:update-*` skill, and prevention → severity check against
   LLD §8.5/§8.7.
4. **Self-check** (`check_report.py`): the report must cite existing evidence
   for every verdict, name a real owner skill, and never filter SE evidence by
   the data `ds`.

## Read-only guarantee

`hooks/hooks.json` runs `scripts/enforce-readonly-queries.py` before every
Bash call and denies container lifecycle commands, Airflow clears/triggers,
non-GET calls to the Airflow API, and mutating SQL. The collector itself
refuses any beeline statement that is not `SELECT`/`SHOW`/`DESCRIBE`.

## Layout

```
sre-plugin/
├── .claude-plugin/plugin.json
├── hooks/hooks.json
├── scripts/            enforce-readonly-queries.py · resolve_skill_arg.sh · discover_workspace.py · check-learnings-queue.py
├── skills/rca/         SKILL.md · RCA_template.j2 · scripts/{find_alert,collect_evidence,check_report,rca_common}.py · tests/ · examples/
└── evals/              trigger-rca · trigger-no-skill · rca-offline-se-evidence-missing (+ fixtures/se-missing)
```

## Running

```bash
cd chapter-7
uv run pytest sre-plugin -v           # unit tests (no stack needed)
make rca ALERT=latest                 # intake + evidence only, needs the DEV stack up
make eval-sre-trigger                 # routing evals
make eval-sre-rca                     # offline RCA eval on the tracked fixture bundle
```

Live loop: `make -C patient_360 dev-up`, break a run (for example pause the UC
container and trigger the DAG), then `/sre-plugin:rca latest`.

## Known limits on this stack

- Airflow task logs are not volume-mounted, so they are fetched through the
  REST API and are lost if the container is recreated.
- Marquez receives no OpenLineage events (no transport configured) and OTel
  exports to the debug exporter only; both surfaces report `unavailable`.
- `meta_dq_run_date` on SE stats is the wall-clock run date, not the data
  `ds`. The collector never filters on it and the self-check rejects reports
  that do.

## Automated loop (alert → incident → RCA → note)

`/sre-plugin:rca` is also run without anyone typing it. The pipeline DAG's
`on_failure_callback` (`utils/alerting.py`, rule DAG-ALERT-001) opens an incident
in Keep (DEV compose, `:3010`) or PagerDuty (PROD); the incident webhook reaches
`service/rca_runner.py` (`make rca-runner`), which writes the alert to
`inputs/alerts/v1/`, runs the skill headless with this plugin and its read-only
hook loaded, and posts the root cause, owner skill, self-check result and report
path as a note on the incident. It never acknowledges or resolves anything. See
`service/README.md` for the diagram, env vars and the PagerDuty setup.
