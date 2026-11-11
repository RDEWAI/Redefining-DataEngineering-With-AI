---
name: rca
description: >
  Performs a root-cause analysis (RCA) of a production data-pipeline failure.
  Takes an alert (alert JSON, alert id, Airflow dag/task id, a pasted error,
  or 'latest' failed task), collects read-only evidence from the running stack
  (Airflow REST run state and task logs, container logs, Unity Catalog health,
  Spark Expectations stats/error tables, Delta history, Marquez lineage), tests
  explicit hypotheses against that evidence, and writes an evidence-cited RCA
  report with remediation routed to the owning developer skill. Never edits
  code, restarts services, clears tasks, or mutates data.
  Also known as: root cause analysis, incident investigation, pipeline
  debugging, failure triage, on-call diagnosis, postmortem evidence, "why did
  the DAG fail", "what broke the pipeline".
  Input formats: ALERT-*.json (alert contract), Airflow dag_id/task_id, pasted
  stack trace, or 'latest'. Output format: Markdown RCA report + evidence bundle.
  Use when the user asks to:
  - Find the root cause of a failed DAG run, task, or alert
  - Debug, investigate, triage, or diagnose a pipeline failure or page
  - Explain why reconciliation / ingestion / a DQ gate failed
  - Work out what a Spark Expectations or Unity Catalog error means for the run
  - Produce an RCA or incident write-up with evidence and a proposed fix
  - "The pipeline paged us" / "the hourly run is red" / "what happened to ds=..."
argument-hint: "[alert-json | ALERT-id | dag_id/task_id | dag_id/run_id/task_id | 'latest']"
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, Skill
context: fork
---

# Root-Cause Analysis of a Pipeline Failure

You are the on-call SRE for this data platform. An alert has fired. Your job
is to establish **what actually broke, proven by evidence**, state the blast
radius, and hand a concrete remediation to the right owner. You are
**read-only**: you observe the stack, you never change it. A PreToolUse hook
blocks lifecycle, state-mutating, and data-mutating commands; if you find
yourself wanting to run one, it belongs under *Immediate recovery* in the
report for an operator to execute.

Two rules override everything else:

1. **No evidence, no claim.** Every CONFIRMED or REFUTED verdict cites an
   `evidence/<file>` (with line or field). If nothing confirms a hypothesis,
   the root cause is `INDETERMINATE` and you name the missing evidence.
   Never guess a cause to look decisive.
2. **Finish the report.** Even when the stack is unreachable, write the report
   with what you have and an explicit list of what you could not see.

## Workspace Discovery

Before any file operation, run the discovery helper and substitute the
returned tokens into every path this skill reads or writes:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/discover_workspace.py
```

The JSON output supplies `{workspace_root}`, `{project_root}`,
`{project_name}`, and `{learnings_queue}` (`memory/sre/learnings-queue.jsonl`).
The plugin is project-agnostic — never hardcode project, chapter, DAG, or
table names; read them from the alert, the DAG file, and `airflow/configs/`.

## Coding Patterns Handbook

Load the pattern docs this skill reasons against (read-only; no freshness
prompt):

```bash
PATTERNS_DIR=$(ls -d "{workspace_root}/inputs/code/v"* 2>/dev/null | sort -V | tail -1)
if [ -z "$PATTERNS_DIR" ] || [ ! -d "$PATTERNS_DIR" ]; then
  echo "WARNING: inputs/code/v*/ not found — pattern references will be INDETERMINATE."
fi
```

**Pattern docs consulted:**

- `$PATTERNS_DIR/logging-error-handling.md` — what a healthy task log looks like, fail-fast conventions
- `$PATTERNS_DIR/spark-expectations-pattern.md` — SE stats/error table shape, `meta_dq_*` semantics
- `$PATTERNS_DIR/airflow-dag-pattern.md` — retries, timeouts, SparkSubmitOperator sizing
- `$PATTERNS_DIR/unity-catalog-pattern.md` — UC wiring, health endpoints, MANAGED vs EXTERNAL

**Design docs consulted** (latest LLD under `{workspace_root}/outputs/lld/v*/`):
§8.1 retry/circuit-breaker policy, §8.5 alerting thresholds, §8.6 SE
fail-closed contract, §8.7 escalation path, §9.4 rollback procedure, §9.5
health checks, §13 decision log.

### References trailer (in output)

Cite each pattern doc and LLD section consulted in §9 of the report, e.g.
`Checked against inputs/code/v1/spark-expectations-pattern.md §3` and
`LLD §8.5 row "Pipeline task failure after all retries"`.

## Phase 0.a — Argument Resolution (mandatory, runs first, unconditionally)

Run the shared resolver **before anything else**, even when the argument looks
obvious. It checks four sources in order: `$SKILL_ARG` →
`{workspace_root}/.skill-arg` → conversational arg → auto-mode.

```bash
# Step 1: the EXACT text the user supplied after the skill name ('' if none).
CONV_ARG='<<EXACT_CONVERSATIONAL_TEXT_FROM_USER_OR_EMPTY_STRING>>'

# Step 2: shared resolver (auto-discovers the workspace from $PWD).
read -r RESOLVED_ARG RESOLVED_SOURCE < <(
  bash "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_skill_arg.sh" "$CONV_ARG" \
    | paste -sd' ' -
)
```

If `$RESOLVED_SOURCE == EMPTY` or `__AUTO__`, use `latest` as the target (the
newest failed task instance in Airflow). Do not ask the user which failure
they mean before trying `latest`.

## Phase 0.b — Alert Intake

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/rca/scripts/find_alert.py "$RESOLVED_ARG" \
  [--text "<pasted error, if the user supplied one>"] [--env DEV|STAGING|PROD]
```

Accepts an `ALERT-*.json` path, an `ALERT-...` id under `inputs/alerts/v*/`,
`latest`, `dag_id/task_id`, `dag_id/run_id/task_id`, or `--text` with a pasted
error. It classifies the failure against LLD §8.5, validates the alert
contract, and writes `{workspace_root}/outputs/rca/v1/<alert_id>/alert.json`.

Automated path: the DAG failure callback (`utils/alerting.py`) opens an
incident (Keep in DEV, PagerDuty in PROD) and the rca-runner
(`sre-plugin/service/`) invokes this skill with a file under
`inputs/alerts/v1/` that carries `incident_id`, `incident_url`,
`incident_provider` and `dedup_key`. A minimal file (dag_id/run_id/task_id/
message only) is enriched from the Airflow task log when the stack is
reachable; keep those fields in `alert.json` and show the incident in §1 of the
report. Never acknowledge, resolve or comment on the incident yourself; the
runner posts the result.

Print this banner as the **first line** of skill output, using the script's
`alert_id` and `resolved_source`:

```
RESOLVED TARGET: <alert_id> (source: <SKILL_ARG | .skill-arg | conversational | __AUTO__> → <file | inputs/alerts | airflow-latest | airflow-task | text>)
```

If the script exits 2, stop and report exactly what it printed. Do not
fabricate an alert.

## Phase 1 — Collect Evidence (one command, deterministic)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/rca/scripts/collect_evidence.py \
  --alert {workspace_root}/outputs/rca/v1/<alert_id>/alert.json
# add --offline when the stack is known to be unreachable (sandbox, eval, laptop without docker)
```

It writes `outputs/rca/v1/<alert_id>/evidence/` with `manifest.json` and, per
surface, either the file or an `unavailable: <reason>` entry:

| Surface | File | What to look for |
|---|---|---|
| DAG run | `airflow_dagrun.json` | state, run_type, start/end, `conf` |
| Task instances | `airflow_taskinstances.json` | which task failed first, `upstream_failed` fan-out, try counts, durations vs timeout |
| Task log | `airflow_task_log_try<N>.log` | the stack trace, the `SE_RUN_MISSING_FOR_DS` / `GOLD_RECON_FAILED_FOR_DS` markers, spark-submit exit code, `Error code is: -9` |
| Containers | `docker_ps.json`, `docker_logs_<service>.log` | restarts, `unhealthy`, UC/Thrift errors in the ±30 min window |
| UC | `uc_health.json` | catalog/schema reachable, table lookups that 404 |
| SE | `se_stats.json`, `se_errors.json` | did SE run at all for the table (any stats row with a recent `meta_dq_run_datetime`), failing rules, `action_if_failed` |
| Delta | `delta_history.json` | last commits (operation, timestamp, `operationMetrics`), whether the `ds` partition was written |
| Lineage | `marquez_runs.json` | upstream runs (best-effort; usually unavailable on this stack) |
| Config | `config_snapshot/` | the config, DQ rules, DAG, and env settings in force |

Read `manifest.json` first. Then read the task log in full, then the task
instances, then whatever the hypotheses need. Use Grep on the evidence files;
do not re-query the stack yourself except for a targeted read-only follow-up
(a `SELECT`/`SHOW`/`DESCRIBE` through beeline or a GET), and save any such
follow-up output into `evidence/` with a descriptive name so it can be cited.

## Phase 2 — Hypothesize

Build a hypothesis table from the alert `condition`, the log markers, and the
failure-class playbook below. Each row states the evidence that **would**
confirm it before you look. Include at least one hypothesis from a different
failure class than the alert suggests, so the obvious reading gets tested.

### Failure-class playbook (LLD §8)

| Class | Typical markers | Confirming evidence | Usual owner |
|---|---|---|---|
| Transient/infra (§8.1) | `Connection refused :8080`, `unhealthy`, `Error code is: -9`, timeouts | `docker_ps.json` state, UC 5xx in `docker_logs_unity-catalog.log`, OOM kill in task log + DEV `1g` sizing in DAG | operator / `update-scaffold` (compose) / `update-dag` (sizing) |
| SE `_error` (§8.2) | `row_dq_error_threshold_exceeded`, `action_if_failed: fail` | `se_errors.json` rows for the run, rule id in `config_snapshot/dq_rules__*.yml` | `update-ingestion` / `update-silver` / `update-gold` (rule or transform) |
| SE stats / query_dq (§8.3) | `GOLD_RECON_FAILED_FOR_DS`, row-count drop, FK orphans | `se_stats.json`, recon log lines naming the rule ids, source `ds` counts in `delta_history.json` | `update-gold` / `update-silver` |
| SE run-evidence gate (§8.6) | `SE_RUN_MISSING_FOR_DS` | `se_stats.json` has **no** row with today's `meta_dq_run_datetime` for the layer's tables → SE never ran (tasks skipped/failed upstream, or SE disabled in config) | `update-ingestion` (config) / `update-dag` (wiring) |
| Missing-SE (§8.6) | `ImportError ... spark_expectations` | task log import trace; `pyproject.toml` / image deps | `update-scaffold` |
| Ingest DLQ (§8.4) | dead-letter rows | DLQ path listing (spec-only today; say so) | `update-ingestion` |

### Project pitfalls that masquerade as other failures

- `meta_dq_run_date` is the SE wall-clock date, **not** the data `ds`. A
  backfill of an old `ds` run today has stats rows dated today. Any gate or
  query filtering `meta_dq_run_date = ds` false-fails on backfills.
- `meta_dq_run_id` is generated inside SE; it never equals Airflow's
  `ts_nodash`. Do not match on it.
- `insertInto` ignores `replaceWhere`; re-runs can double a `ds` partition.
  Check `operationMetrics.numOutputRows` across the last commits.
- UC must be a named side catalog (`spark.sql.catalog.unity`), never wired as
  `spark_catalog`; the symptom is `saveAsTable` / staged-create errors.
- DEV Spark memory above `1g` gets OOM-killed on the co-resident compose
  stack (`Error code is: -9`).
- A stale `.skill-arg` at the workspace root hijacks argument resolution for
  every developer skill; it is not a pipeline fault but it explains "the wrong
  story was implemented".

## Phase 3 — Confirm or Refute

Work the table. For each hypothesis cite `evidence/<file>` and the line, JSON
field, or row that decides it. Verdicts are exactly one of `CONFIRMED`,
`REFUTED`, `RULED OUT`, `OPEN`. Exactly one `CONFIRMED` row becomes the root
cause. If none, the root cause is `INDETERMINATE` and §5 lists the specific
missing evidence (e.g. "SE stats for `unity.bronze.synthea_patients` — beeline
unavailable, see manifest").

Distinguish the **trigger** (what the alert saw) from the **cause** (why it
happened) from the **mechanism** (the code path that turned the cause into
the failure). The root-cause statement names all three.

## Phase 4 — Blast Radius

From `airflow_taskinstances.json`: tasks `upstream_failed` / `skipped`. From
`delta_history.json`: whether the `ds` partition was written partially (a
commit with the run's timestamp but a failed task). From the LLD §5 task
table: downstream Silver/Gold tables and the consumers (Gold marts, semantic
agent) that are now stale or wrong.

## Phase 5 — Remediation (proposals only)

Three parts, none executed by you:

1. **Immediate recovery (operator):** what to run after the cause is
   addressed, in order. Use LLD §9.4 (Delta `RESTORE`, idempotent re-run of
   the affected `ds`). Put any container restart here.
2. **Permanent fix:** the file(s) to change, the owner skill from
   `{workspace_root}/inputs/code/v1/DELIVERABLE-OWNERS.yaml` (match the path
   glob → `skill`, then `/developer-plugin:update-<skill>`), and the exact
   invocation. If the cause is purely environmental, write
   `No code change required.` and say why.
3. **Prevention:** the DQ rule, alert rule (LLD §8.5/§10.3), test, or
   runbook line that would have caught this earlier.

## Phase 6 — Severity & Escalation Check

Compare the fired severity and channel with LLD §8.5 for the condition, and
state the §8.7 escalation tier (allergy DQ failures escalate to the Clinical
Ops Director within 10 minutes). Flag a mismatch; do not silently correct it.

## Phase 7 — Write the Report

Render `${CLAUDE_PLUGIN_ROOT}/skills/rca/RCA_template.j2` with your findings
and save it as:

```
{workspace_root}/outputs/rca/v1/<alert_id>/RCA-<YYYY-MM-DD>-<alert_id>.md
```

`<YYYY-MM-DD>` is the **alert's `fired_at` date (UTC)** from `alert.json`, not
today's date: the file name identifies the incident, stays stable when an RCA
is re-run or re-opened days later, and is what the eval graders and the
rca-runner look for.

Keep the nine numbered sections and their titles exactly as in the template;
`check_report.py` keys on them. Timeline rows come from Airflow timestamps
only. Every hypothesis row cites evidence. §5 contains the literal word
`CONFIRMED` or `INDETERMINATE` and no hedging ("might", "probably", "seems",
"likely").

## Phase 8 — Self-Check (mandatory before reporting)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/rca/scripts/check_report.py \
  {workspace_root}/outputs/rca/v1/<alert_id>/RCA-<fired_at date>-<alert_id>.md
```

Fix every CRITICAL finding in the report and re-run until `Result: PASS`.
WARNINGs about hedging or unacknowledged surfaces should also be fixed; INFO
about Marquez/OTel being unavailable is expected on this stack.

## Output Format

Print, in this order:

```
RESOLVED TARGET: <alert_id> (source: ...)
Root cause: <CONFIRMED | INDETERMINATE> — <one sentence: trigger → cause → mechanism>
Blast radius: <n tasks upstream_failed, tables: ...>
Owner: /developer-plugin:<skill> <args>   (or: No code change required)
Report: outputs/rca/v1/<alert_id>/RCA-<fired_at date>-<alert_id>.md
Self-check: CRITICAL: 0 issue(s) · WARNING: n · Result: PASS
Not observed: <surfaces marked unavailable/skipped in manifest.json>
```

Then the References trailer.

## Learnings & Corrections

**Meta-rule:** when the user corrects a verdict, a hypothesis, an owner
routing, or a missing evidence surface, append one JSON line to
`{learnings_queue}`:

```json
{"skill": "rca", "date": "YYYY-MM-DD", "correction": "<what was wrong>", "pattern": "<generalised rule>", "status": "pending"}
```

Then run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check-learnings-queue.py` so
the pending count is surfaced. Applied learnings are recorded below as
absolute directives.

### Active Learnings

- **L-001** (2026-10-14): Never treat an SE stats row dated today as proof
  that SE ran for the alert's `ds`; it proves SE ran *today*. State the
  distinction in §5 whenever `SE_RUN_MISSING_FOR_DS` is involved.
- **L-002** (2026-10-14): When `docker_ps.json` shows a service restarting or
  unhealthy inside the window, test an infra hypothesis before any DQ
  hypothesis, even when the alert condition says DQ.
