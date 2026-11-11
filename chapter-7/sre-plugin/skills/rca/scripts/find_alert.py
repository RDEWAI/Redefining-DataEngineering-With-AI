#!/usr/bin/env python3
"""Alert intake for the `rca` skill: normalise any trigger into one alert JSON.

Accepted targets (positional ``target``):

* a path to an ``ALERT-*.json`` file following the alert contract
* an alert id (``ALERT-...``) looked up under ``{workspace_root}/inputs/alerts/v*/``
* ``latest`` — newest failed task instance across all DAGs (Airflow REST, read-only)
* ``<dag_id>/<task_id>`` — newest failed run of that task
* ``<dag_id>/<run_id>/<task_id>`` — that exact task instance
* ``--text "<pasted error>"`` (target may be omitted) — bind the text to the most
  recent failed task instance whose log contains it

The alert is classified against the LLD §8.5 alert taxonomy (see
``rca_common.CONDITION_RULES``), validated, and written to
``{workspace_root}/outputs/rca/v1/<alert_id>/alert.json``. The script prints a
small JSON summary on stdout and exits 0; exit 2 on any intake failure (the
skill must then report that it cannot proceed, never guess).

Read-only: every Airflow call is a GET (plus the JWT mint).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rca_common import (  # noqa: E402
    AirflowClient,
    HttpError,
    classify,
    discover,
    ds_from_run_id,
    eprint,
    make_alert_id,
    utc_now_iso,
    validate_alert,
    write_json,
)

LOG_TAIL_FOR_CLASSIFY = 65536  # chars from the end of the log used for classification;
# Airflow JSON-line logs are verbose: on the live 2026-10-15 UC outage the last
# ConnectException sat 14 KB from the end, past a 4 KB window.


# --------------------------------------------------------------------------
# Builders
# --------------------------------------------------------------------------
def _alert_from_task_instance(
    client: AirflowClient, dag_id: str, ti: dict, env: str, text: str | None = None
) -> dict:
    run_id = ti.get("dag_run_id") or ti.get("run_id")
    task_id = ti["task_id"]
    try_number = int(ti.get("try_number") or 1)
    log_tail = ""
    try:
        log = client.task_log(dag_id, run_id, task_id, try_number)
        log_tail = log[-LOG_TAIL_FOR_CLASSIFY:]
    except HttpError as exc:
        eprint(f"warning: could not fetch log for {task_id} try {try_number}: {exc}")
    rule = classify(f"{text or ''}\n{log_tail}", task_id)
    message = text or _first_marker_line(log_tail) or f"{task_id} failed (state={ti.get('state')})"
    fired_at = ti.get("end_date") or ti.get("start_date") or utc_now_iso()
    return {
        "alert_id": make_alert_id(task_id, fired_at),
        "fired_at": fired_at,
        "env": env,
        "condition": rule.condition,
        "failure_class": rule.failure_class,
        "severity": rule.severity,
        "channel": rule.channel.replace("{env}", env.lower()),
        "response_time": rule.response_time,
        "source": "airflow",
        "dag_id": dag_id,
        "run_id": run_id,
        "task_id": task_id,
        "try_number": try_number,
        "ds": ds_from_run_id(run_id),
        "message": message.strip()[:2000],
    }


_MARKER_RE = re.compile(
    r"(SE_RUN_MISSING_FOR_DS=\S+.*|GOLD_RECON_FAILED_FOR_DS=\S+.*|.*Error code is: -9.*|"
    r".*ImportError.*|.*Connection refused.*|.*SparkExpectationsMiscException.*|.*Exception:.*|.*Error:.*)"  # noqa: E501
)


def _first_marker_line(log_tail: str) -> str | None:
    for line in reversed(log_tail.splitlines()):
        m = _MARKER_RE.match(line.strip())
        if m:
            return m.group(1)
    return None


def _failed_task_instances(
    client: AirflowClient, dag_id: str, run_limit: int = 5
) -> list[tuple[dict, dict]]:
    """Return (dag_run, task_instance) pairs for failed TIs, newest run first."""
    pairs: list[tuple[dict, dict]] = []
    for run in client.dag_runs(dag_id, state="failed", limit=run_limit):
        run_id = run.get("dag_run_id") or run.get("run_id")
        for ti in client.task_instances(dag_id, run_id):
            if ti.get("state") in ("failed", "upstream_failed"):
                ti.setdefault("dag_run_id", run_id)
                pairs.append((run, ti))
    # Prefer genuinely failed tasks over upstream_failed ones, newest first.
    pairs.sort(key=lambda p: (p[1].get("state") != "failed", -(_ts(p[1].get("end_date")))))
    return pairs


def _ts(value: str | None) -> float:
    if not value:
        return 0.0
    from datetime import datetime

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


# --------------------------------------------------------------------------
# Intake modes
# --------------------------------------------------------------------------
def from_file(path: Path, env: str, client: AirflowClient | None = None) -> dict:
    """Load an alert file; fill the contract from the Airflow log when the file is minimal.

    The DAG failure callback (utils/alerting.py) and the rca-runner write only
    dag_id/run_id/task_id/try_number/message. When ``condition`` is absent and
    Airflow is reachable, the real log tail is fetched so classification uses
    the LLD §8.5 marker rather than the (often generic) operator exception.
    """
    alert = json.loads(path.read_text(encoding="utf-8"))
    alert.setdefault("env", env)
    alert.setdefault("source", "manual")
    if not alert.get("ds"):
        alert["ds"] = ds_from_run_id(alert.get("run_id"))
    if not alert.get("condition") or not alert.get("severity"):
        log_tail = ""
        if (
            client is not None
            and alert.get("dag_id")
            and alert.get("run_id")
            and alert.get("task_id")
        ):
            try:
                log_tail = client.task_log(
                    alert["dag_id"],
                    alert["run_id"],
                    alert["task_id"],
                    int(alert.get("try_number") or 1),
                )[-20000:]
            except HttpError as exc:
                eprint(f"warning: could not fetch Airflow log to enrich {path.name}: {exc}")
        rule = classify(f"{alert.get('message', '')}\n{log_tail}", alert.get("task_id", ""))
        if log_tail and not alert.get("message"):
            alert["message"] = _first_marker_line(log_tail) or ""
        alert.setdefault("condition", rule.condition)
        alert.setdefault("severity", rule.severity)
        alert.setdefault("channel", rule.channel.replace("{env}", env.lower()))
        alert.setdefault("failure_class", rule.failure_class)
        alert.setdefault("response_time", rule.response_time)
    if not alert.get("alert_id"):
        alert["alert_id"] = make_alert_id(alert.get("task_id") or "manual", alert.get("fired_at"))
    alert.setdefault("fired_at", utc_now_iso())
    return alert


def from_alert_id(
    alert_id: str, workspace_root: Path, env: str, client: AirflowClient | None = None
) -> dict:
    matches = sorted(workspace_root.glob(f"inputs/alerts/v*/{alert_id}.json"))
    if not matches:
        raise SystemExit(f"error: no inputs/alerts/v*/{alert_id}.json under {workspace_root}")
    return from_file(matches[-1], env, client)


def latest(client: AirflowClient, env: str, dag_filter: str | None = None) -> dict:
    candidates: list[tuple[str, dict, dict]] = []
    dag_ids = [dag_filter] if dag_filter else [d["dag_id"] for d in client.dags()]
    for dag_id in dag_ids:
        for run, ti in _failed_task_instances(client, dag_id):
            candidates.append((dag_id, run, ti))
    if not candidates:
        raise SystemExit("error: no failed task instances found in Airflow (nothing to analyse)")
    candidates.sort(key=lambda c: (c[2].get("state") != "failed", -_ts(c[2].get("end_date"))))
    dag_id, _run, ti = candidates[0]
    return _alert_from_task_instance(client, dag_id, ti, env)


def dag_task(client: AirflowClient, spec: str, env: str) -> dict:
    parts = spec.split("/")
    if len(parts) == 3:
        dag_id, run_id, task_id = parts
        tis = [ti for ti in client.task_instances(dag_id, run_id) if ti["task_id"] == task_id]
        if not tis:
            raise SystemExit(f"error: task {task_id} not found in {dag_id}/{run_id}")
        tis[0].setdefault("dag_run_id", run_id)
        return _alert_from_task_instance(client, dag_id, tis[0], env)
    if len(parts) == 2:
        dag_id, task_id = parts
        for _run, ti in _failed_task_instances(client, dag_id, run_limit=10):
            if ti["task_id"] == task_id:
                return _alert_from_task_instance(client, dag_id, ti, env)
        raise SystemExit(
            f"error: no failed instance of {task_id} in the last 10 failed runs of {dag_id}"
        )
    raise SystemExit(
        f"error: expected <dag_id>/<task_id> or <dag_id>/<run_id>/<task_id>, got {spec!r}"
    )


def from_text(client: AirflowClient | None, text: str, env: str) -> dict:
    needle = text.strip().splitlines()[0][:200] if text.strip() else ""
    if client is not None:
        try:
            for dag in client.dags():
                for _run, ti in _failed_task_instances(client, dag["dag_id"]):
                    run_id = ti["dag_run_id"]
                    try:
                        log = client.task_log(
                            dag["dag_id"], run_id, ti["task_id"], int(ti.get("try_number") or 1)
                        )
                    except HttpError:
                        continue
                    if needle and needle in log:
                        return _alert_from_task_instance(client, dag["dag_id"], ti, env, text=text)
        except HttpError as exc:
            eprint(f"warning: Airflow not reachable, building a manual alert from text only: {exc}")
    rule = classify(text)
    return {
        "alert_id": make_alert_id("manual"),
        "fired_at": utc_now_iso(),
        "env": env,
        "condition": rule.condition,
        "failure_class": rule.failure_class,
        "severity": rule.severity,
        "channel": rule.channel.replace("{env}", env.lower()),
        "response_time": rule.response_time,
        "source": "manual",
        "message": text.strip()[:2000],
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="alert json path | ALERT-id | latest | dag_id/task_id | dag_id/run_id/task_id",
    )
    parser.add_argument(
        "--text", default=None, help="pasted error / stack trace to bind to a failed task"
    )
    parser.add_argument(
        "--env", default=None, help="DEV|STAGING|PROD (default: PATIENT360_ENV or DEV)"
    )
    parser.add_argument("--dag-id", default=None, help="restrict 'latest' to one DAG")
    parser.add_argument("--workspace-root", type=Path, default=None)
    parser.add_argument(
        "--out-root", type=Path, default=None, help="default {workspace_root}/outputs/rca/v1"
    )
    parser.add_argument(
        "--no-airflow", action="store_true", help="never contact Airflow (file/id/text only)"
    )
    args = parser.parse_args(argv)

    import os

    env = (args.env or os.environ.get("PATIENT360_ENV") or "DEV").upper()
    ws = discover(workspace_root=args.workspace_root)
    out_root = args.out_root or (ws.workspace_root / "outputs" / "rca" / "v1")

    target = args.target
    source_token = "conversational"
    client = None if args.no_airflow else AirflowClient()
    try:
        if args.text and not target:
            alert = from_text(client, args.text, env)
            source_token = "text"
        elif target is None:
            raise SystemExit(
                "error: give a target (alert json | ALERT-id | latest | dag_id/task_id) or --text"
            )
        elif target.lower() == "latest":
            if client is None:
                raise SystemExit("error: 'latest' needs Airflow access (remove --no-airflow)")
            alert = latest(client, env, args.dag_id)
            source_token = "airflow-latest"
        elif target.startswith("ALERT-") and not target.endswith(".json"):
            alert = from_alert_id(target, ws.workspace_root, env, client)
            source_token = "inputs/alerts"
        elif Path(target).is_file():
            alert = from_file(Path(target), env, client)
            source_token = "file"
        elif "/" in target and client is not None:
            alert = dag_task(client, target, env)
            source_token = "airflow-task"
        else:
            raise SystemExit(
                f"error: cannot resolve target {target!r} "
                "(not a file, alert id, 'latest' or dag/task)"
            )
        if args.text and target:
            alert["message"] = (
                f"{alert.get('message', '')}\n--- user supplied ---\n{args.text.strip()}"[:2000]
            )
    except HttpError as exc:
        eprint(f"error: Airflow unreachable or rejected the request: {exc}")
        return 2
    except SystemExit as exc:
        if exc.code and isinstance(exc.code, str):
            eprint(exc.code)
            return 2
        raise

    problems = validate_alert(alert)
    if problems:
        eprint("error: alert does not satisfy the contract:")
        for p in problems:
            eprint(f"  - {p}")
        return 2

    out_dir = out_root / alert["alert_id"]
    out_path = out_dir / "alert.json"
    write_json(out_path, alert)
    print(
        json.dumps(
            {
                "alert_id": alert["alert_id"],
                "alert_path": str(out_path),
                "resolved_source": source_token,
                "condition": alert["condition"],
                "severity": alert["severity"],
                "dag_id": alert.get("dag_id"),
                "task_id": alert.get("task_id"),
                "ds": alert.get("ds"),
                "incident_id": alert.get("incident_id"),
                "incident_url": alert.get("incident_url"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
