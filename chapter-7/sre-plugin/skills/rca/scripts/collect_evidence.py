#!/usr/bin/env python3
"""Deterministic, read-only evidence collector for the `rca` skill.

Given an alert JSON (written by ``find_alert.py``) it pulls every evidence
surface the stack offers into ``<alert dir>/evidence/`` and writes a
``manifest.json`` that records, per surface, whether it was collected or why
it was unavailable. Surfaces are independent: one failing never aborts the
others, so the RCA can state precisely what it could and could not see.

Surfaces
--------
airflow_dagrun.json           the DAG run (state, timestamps, run_type)
airflow_taskinstances.json    every task instance in the run (state/try/duration)
airflow_task_log_try<N>.log   failed task log (try N and N-1); Spark driver output is inside it
docker_ps.json                `docker compose ps` for the stack
docker_logs_<service>.log     tails for airflow, unity-catalog, spark-thrift-server, marquez
uc_health.json                UC catalogs/schemas + table lookups for the task's tables
se_stats.json / se_errors.json  SE `<table>_stats` / `<table>_error` via beeline (no ds filter)
delta_history.json            DESCRIBE HISTORY + SHOW PARTITIONS for target tables (beeline)
marquez_runs.json             OpenLineage jobs/runs (best-effort; usually unavailable today)
config_snapshot/              airflow/configs, dq_rules, the DAG file, _infra/cd/config/<ENV>.yaml

``--offline`` skips network and docker calls (sandboxes, evals) and only
snapshots config. Nothing here mutates anything: GET requests, `docker compose
ps/logs/exec ... beeline -e "SELECT|SHOW|DESCRIBE ..."`, and file copies.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rca_common import (  # noqa: E402
    AirflowClient,
    HttpError,
    discover,
    eprint,
    http_get_json,
    marquez_api,
    run_cmd,
    uc_uri,
    utc_now_iso,
    write_json,
)

DOCKER_SERVICES = ("airflow", "unity-catalog", "spark-thrift-server", "marquez")
DOCKER_TAIL = 500
TASK_LOG_MAX_BYTES = 2 * 1024 * 1024
BEELINE_TIMEOUT = 120
LAYER_SCHEMAS = {"bronze": "bronze", "silver": "silver", "gold": "gold"}


class Manifest:
    def __init__(self, alert: dict, offline: bool):
        self.data: dict[str, Any] = {
            "alert_id": alert["alert_id"],
            "collected_at": utc_now_iso(),
            "offline": offline,
            "tables": [],
            "surfaces": {},
        }

    def ok(self, name: str, file: str, **extra: Any) -> None:
        self.data["surfaces"][name] = {"status": "ok", "file": file, **extra}

    def unavailable(self, name: str, reason: str) -> None:
        self.data["surfaces"][name] = {"status": "unavailable", "reason": reason[:500]}

    def skipped(self, name: str, reason: str) -> None:
        self.data["surfaces"][name] = {"status": "skipped", "reason": reason}


def guarded(manifest: Manifest, name: str) -> Callable[[Callable[[], None]], None]:
    """Run a collector; any exception becomes an `unavailable` manifest entry."""

    def _run(fn: Callable[[], None]) -> None:
        try:
            fn()
        except HttpError as exc:
            manifest.unavailable(name, f"http: {exc}")
        except Exception as exc:  # noqa: BLE001 — evidence collection must never abort
            manifest.unavailable(name, f"{type(exc).__name__}: {exc}")

    return _run


# --------------------------------------------------------------------------
# Task -> table resolution (read from the project at runtime, no hardcoding)
# --------------------------------------------------------------------------
def bronze_tables(project_root: Path) -> dict[str, str]:
    """Map config stem -> fully qualified output table from airflow/configs/*.yml."""
    out: dict[str, str] = {}
    for yml in sorted((project_root / "airflow" / "configs").glob("*.yml")):
        if yml.stem.startswith("_"):
            continue
        text = yml.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^output_table:\s*['\"]?([\w.]+)", text, re.MULTILINE)
        out[yml.stem] = m.group(1) if m else f"unity.bronze.{yml.stem}"
    return out


def layer_tables_from_source(project_root: Path, project_name: str, layer: str) -> set[str]:
    """Scan src/<project>/<layer>/**/*.py for `unity.<layer>.<table>` literals."""
    found: set[str] = set()
    pattern = re.compile(rf"unity\.{layer}\.(\w+)")
    for py in (project_root / "src" / project_name / layer).rglob("*.py"):
        for m in pattern.finditer(py.read_text(encoding="utf-8", errors="replace")):
            if not m.group(1).endswith(("_stats", "_error", "_detailed")):
                found.add(f"unity.{layer}.{m.group(1)}")
    return found


def resolve_tables(task_id: str | None, project_root: Path, project_name: str) -> list[str]:
    if not task_id:
        return []
    task = task_id.split(".")[-1]  # strip TaskGroup prefix
    bronze = bronze_tables(project_root)
    if task.startswith("ingest_"):
        stem = task[len("ingest_") :]
        return [bronze.get(stem, f"unity.bronze.{stem}")]
    m = re.fullmatch(r"transform_(\w+)_silver", task)
    if m:
        key = m.group(1)
        silver = sorted(
            t for t in layer_tables_from_source(project_root, project_name, "silver") if key in t
        )
        src = [bronze[key]] if key in bronze else []
        return (silver or [f"unity.silver.{key}"]) + src
    m = re.fullmatch(r"build_(\w+)_gold", task)
    if m:
        key = m.group(1)
        gold = sorted(
            t for t in layer_tables_from_source(project_root, project_name, "gold") if key in t
        )
        return gold or [f"unity.gold.{key}"]
    m = re.fullmatch(r"reconciliation_(\w+)", task)
    if m:
        layer = m.group(1)
        if layer == "bronze":
            return sorted(bronze.values())
        return sorted(layer_tables_from_source(project_root, project_name, layer))
    return []


# --------------------------------------------------------------------------
# Collectors
# --------------------------------------------------------------------------
def collect_airflow(alert: dict, out: Path, manifest: Manifest) -> None:
    dag_id, run_id, task_id = alert.get("dag_id"), alert.get("run_id"), alert.get("task_id")
    if not (dag_id and run_id):
        manifest.skipped("airflow_dagrun", "alert carries no dag_id/run_id")
        manifest.skipped("airflow_taskinstances", "alert carries no dag_id/run_id")
        manifest.skipped("airflow_task_log", "alert carries no dag_id/run_id")
        return
    client = AirflowClient()

    def _dagrun() -> None:
        write_json(out / "airflow_dagrun.json", client.dag_run(dag_id, run_id))
        manifest.ok("airflow_dagrun", "airflow_dagrun.json")

    def _tis() -> None:
        tis = client.task_instances(dag_id, run_id)
        slim = [
            {
                k: ti.get(k)
                for k in (
                    "task_id",
                    "state",
                    "try_number",
                    "start_date",
                    "end_date",
                    "duration",
                    "operator",
                    "max_tries",
                    "queued_when",
                )
            }
            for ti in tis
        ]
        write_json(
            out / "airflow_taskinstances.json",
            {"dag_id": dag_id, "run_id": run_id, "task_instances": slim},
        )
        counts: dict[str, int] = {}
        for ti in slim:
            counts[ti["state"] or "none"] = counts.get(ti["state"] or "none", 0) + 1
        manifest.ok("airflow_taskinstances", "airflow_taskinstances.json", state_counts=counts)

    def _logs() -> None:
        if not task_id:
            manifest.skipped("airflow_task_log", "alert carries no task_id")
            return
        try_number = int(alert.get("try_number") or 1)
        files: list[str] = []
        for n in sorted({try_number, max(1, try_number - 1)}, reverse=True):
            try:
                log = client.task_log(dag_id, run_id, task_id, n)
            except HttpError as exc:
                if n == try_number:
                    raise
                eprint(f"note: try {n} log unavailable: {exc}")
                continue
            if len(log.encode()) > TASK_LOG_MAX_BYTES:
                log = "[truncated: head omitted]\n" + log[-TASK_LOG_MAX_BYTES:]
            name = f"airflow_task_log_try{n}.log"
            (out / name).write_text(log, encoding="utf-8")
            files.append(name)
        manifest.ok("airflow_task_log", files[0], files=files, try_number=try_number)

    guarded(manifest, "airflow_dagrun")(_dagrun)
    guarded(manifest, "airflow_taskinstances")(_tis)
    guarded(manifest, "airflow_task_log")(_logs)


def _compose_argv(project_root: Path) -> list[str]:
    return [
        "docker",
        "compose",
        "-f",
        str(project_root / "_infra" / "docker" / "docker-compose.yml"),
    ]


def collect_docker(
    alert: dict, project_root: Path, out: Path, manifest: Manifest, window_minutes: int
) -> None:
    compose = _compose_argv(project_root)

    def _ps() -> None:
        rc, so, se = run_cmd(compose + ["ps", "--all", "--format", "json"], timeout=30)
        if rc != 0:
            raise RuntimeError(se.strip() or f"docker compose ps exit {rc}")
        rows = []
        for line in so.splitlines():
            line = line.strip()
            if line.startswith("{"):
                rows.append(json.loads(line))
            elif line.startswith("["):
                rows.extend(json.loads(line))
        write_json(out / "docker_ps.json", rows)
        manifest.ok(
            "docker_ps", "docker_ps.json", services={r.get("Service"): r.get("State") for r in rows}
        )

    guarded(manifest, "docker_ps")(_ps)

    since, until = _window(alert.get("fired_at"), window_minutes)
    for service in DOCKER_SERVICES:

        def _logs(service: str = service) -> None:
            argv = compose + ["logs", "--no-color", "--tail", str(DOCKER_TAIL)]
            if since:
                argv += ["--since", since, "--until", until]
            argv.append(service)
            rc, so, se = run_cmd(argv, timeout=60)
            if rc != 0 and since:  # retry without the time window (older compose)
                rc, so, se = run_cmd(
                    compose + ["logs", "--no-color", "--tail", str(DOCKER_TAIL), service],
                    timeout=60,
                )
            if rc != 0:
                raise RuntimeError(se.strip() or f"docker compose logs {service} exit {rc}")
            name = f"docker_logs_{service}.log"
            (out / name).write_text(so, encoding="utf-8")
            manifest.ok(f"docker_logs_{service}", name, lines=len(so.splitlines()))

        guarded(manifest, f"docker_logs_{service}")(_logs)


def _window(fired_at: str | None, minutes: int) -> tuple[str | None, str | None]:
    if not fired_at:
        return None, None
    try:
        t = datetime.fromisoformat(fired_at.replace("Z", "+00:00"))
    except ValueError:
        return None, None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (t - timedelta(minutes=minutes)).isoformat(), (
        t + timedelta(minutes=minutes)
    ).isoformat()


def collect_uc(tables: list[str], out: Path, manifest: Manifest) -> None:
    def _uc() -> None:
        base = f"{uc_uri()}/api/2.1/unity-catalog"
        data: dict[str, Any] = {"catalogs": http_get_json(f"{base}/catalogs")}
        data["schemas"] = http_get_json(f"{base}/schemas?catalog_name=unity")
        data["tables"] = {}
        for fqn in tables:
            try:
                data["tables"][fqn] = http_get_json(f"{base}/tables/{fqn}")
            except HttpError as exc:
                data["tables"][fqn] = {"error": f"HTTP {exc.status}", "body": exc.body[:300]}
        write_json(out / "uc_health.json", data)
        missing = [t for t, v in data["tables"].items() if "error" in v]
        manifest.ok(
            "uc_health", "uc_health.json", tables_checked=len(tables), tables_missing=missing
        )

    guarded(manifest, "uc_health")(_uc)


def beeline(project_root: Path, sql: str) -> str:
    """Run one read-only statement through the Thrift server's beeline and return csv text."""
    if not re.match(r"^\s*(select|show|describe|desc)\b", sql, re.IGNORECASE):
        raise ValueError(f"refusing non-read statement: {sql[:80]}")
    argv = _compose_argv(project_root) + [
        "exec",
        "-T",
        "spark-thrift-server",
        "/opt/spark/bin/beeline",
        "-u",
        "jdbc:hive2://localhost:10000",
        "--silent=true",
        "--outputformat=csv2",
        "-e",
        sql,
    ]
    rc, so, se = run_cmd(argv, timeout=BEELINE_TIMEOUT)
    if rc != 0:
        raise RuntimeError((se or so).strip()[-500:] or f"beeline exit {rc}")
    return so


def _csv_rows(text: str) -> list[dict[str, str]]:
    import csv
    import io

    lines = [
        ln
        for ln in text.splitlines()
        if ln.strip() and not ln.startswith(("WARN", "log4j", "SLF4J"))
    ]
    if not lines:
        return []
    return list(csv.DictReader(io.StringIO("\n".join(lines))))


def _beeline_status(
    manifest: Manifest, surface: str, file: str, data: dict[str, Any], **extra: Any
) -> None:
    """Record a beeline-backed surface honestly.

    A query that failed on every table (Thrift session refused, UC down) is
    ``unavailable`` with the reason, not ``ok`` with an empty file: the self-check
    and the hypotheses table treat ``ok`` as "this evidence was read". A partial
    failure stays ``ok`` and lists ``tables_failed``.
    """
    failed = {t: v["error"] for t, v in data.items() if isinstance(v, dict) and "error" in v}
    if data and len(failed) == len(data):
        reason = next(iter(failed.values()))
        manifest.unavailable(surface, f"beeline failed for all {len(data)} table(s): {reason}")
        manifest.data["surfaces"][surface]["file"] = file
        return
    manifest.ok(surface, file, tables=len(data), tables_failed=sorted(failed), **extra)


def collect_se(tables: list[str], project_root: Path, out: Path, manifest: Manifest) -> None:
    def _stats() -> None:
        data: dict[str, Any] = {}
        for fqn in tables:
            try:
                # Never filter by ds: meta_dq_run_date is SE wall-clock, not the data partition.
                data[fqn] = _csv_rows(
                    beeline(
                        project_root,
                        f"SELECT * FROM {fqn}_stats ORDER BY meta_dq_run_datetime DESC LIMIT 5",
                    )
                )
            except Exception as exc:  # noqa: BLE001
                data[fqn] = {"error": str(exc)[-300:]}
        write_json(out / "se_stats.json", data)
        _beeline_status(
            manifest,
            "se_stats",
            "se_stats.json",
            data,
            tables_with_rows=[t for t, v in data.items() if isinstance(v, list) and v],
        )

    def _errors() -> None:
        data: dict[str, Any] = {}
        for fqn in tables:
            try:
                data[fqn] = _csv_rows(
                    beeline(
                        project_root,
                        f"SELECT meta_dq_run_id, meta_dq_run_datetime, dq_rules, action_if_failed, "
                        f"count(*) AS n "
                        f"FROM {fqn}_error GROUP BY 1,2,3,4 ORDER BY 2 DESC LIMIT 20",
                    )
                )
            except Exception as exc:  # noqa: BLE001
                data[fqn] = {"error": str(exc)[-300:]}
        write_json(out / "se_errors.json", data)
        _beeline_status(manifest, "se_errors", "se_errors.json", data)

    if not tables:
        manifest.skipped("se_stats", "no tables resolved for this task")
        manifest.skipped("se_errors", "no tables resolved for this task")
        return
    guarded(manifest, "se_stats")(_stats)
    guarded(manifest, "se_errors")(_errors)


def collect_delta(tables: list[str], project_root: Path, out: Path, manifest: Manifest) -> None:
    def _delta() -> None:
        data: dict[str, Any] = {}
        for fqn in tables:
            entry: dict[str, Any] = {}
            try:
                entry["history"] = _csv_rows(
                    beeline(project_root, f"DESCRIBE HISTORY {fqn} LIMIT 10")
                )
            except Exception as exc:  # noqa: BLE001
                entry["history_error"] = str(exc)[-300:]
            try:
                entry["partitions"] = _csv_rows(beeline(project_root, f"SHOW PARTITIONS {fqn}"))[
                    -20:
                ]
            except Exception as exc:  # noqa: BLE001
                entry["partitions_note"] = "unpartitioned or unavailable: " + str(exc)[-200:]
            data[fqn] = entry
        write_json(out / "delta_history.json", data)
        _beeline_status(
            manifest,
            "delta_history",
            "delta_history.json",
            {
                t: ({"error": e["history_error"]} if "history_error" in e else e)
                for t, e in data.items()
            },
        )

    if not tables:
        manifest.skipped("delta_history", "no tables resolved for this task")
        return
    guarded(manifest, "delta_history")(_delta)


def collect_marquez(out: Path, manifest: Manifest) -> None:
    def _mq() -> None:
        import os

        ns = os.environ.get("MARQUEZ_NAMESPACE", "patient_360")
        jobs = http_get_json(f"{marquez_api()}/namespaces/{ns}/jobs").get("jobs", [])
        if not jobs:
            manifest.unavailable(
                "marquez_runs",
                f"no jobs in Marquez namespace {ns} (OpenLineage transport not configured)",
            )
            return
        runs = {}
        for job in jobs[:20]:
            name = job.get("name")
            try:
                runs[name] = http_get_json(
                    f"{marquez_api()}/namespaces/{ns}/jobs/{name}/runs?limit=3"
                ).get("runs", [])
            except HttpError as exc:
                runs[name] = {"error": str(exc)}
        write_json(
            out / "marquez_runs.json",
            {"namespace": ns, "jobs": [j.get("name") for j in jobs], "runs": runs},
        )
        manifest.ok("marquez_runs", "marquez_runs.json", jobs=len(jobs))

    guarded(manifest, "marquez_runs")(_mq)


def collect_config(
    alert: dict, tables: list[str], ws_root: Path, project_root: Path, out: Path, manifest: Manifest
) -> None:
    snap = out / "config_snapshot"
    snap.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    stems = {t.split(".")[-1] for t in tables}
    for t in list(stems):
        # bronze configs are keyed by the synthea stem; silver/gold rules by the fq stem
        for part in t.split("_"):
            if len(part) > 3:
                stems.add(part)
    for cfg in (project_root / "airflow" / "configs").glob("*.yml"):
        if cfg.stem in stems:
            shutil.copy2(cfg, snap / f"configs__{cfg.name}")
            copied.append(f"configs__{cfg.name}")
    for rule in (project_root / "dq_rules").glob("*.yml"):
        if any(s in rule.stem for s in stems):
            shutil.copy2(rule, snap / f"dq_rules__{rule.name}")
            copied.append(f"dq_rules__{rule.name}")
    dag_id = alert.get("dag_id")
    for dag in (project_root / "airflow" / "dags").glob("*.py"):
        if dag.name == "__init__.py":
            continue
        if not dag_id or dag_id in dag.read_text(encoding="utf-8", errors="replace"):
            shutil.copy2(dag, snap / f"dag__{dag.name}")
            copied.append(f"dag__{dag.name}")
    env_cfg = project_root / "_infra" / "cd" / "config" / f"{alert.get('env', 'DEV').upper()}.yaml"
    if env_cfg.is_file():
        shutil.copy2(env_cfg, snap / f"env__{env_cfg.name}")
        copied.append(f"env__{env_cfg.name}")
    manifest.ok("config_snapshot", "config_snapshot/", files=copied)


def _read_prior_manifest(out: Path) -> dict[str, Any]:
    p = out / "manifest.json"
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    surfaces = dict(data.get("surfaces") or {})
    surfaces["collected_at"] = data.get("collected_at")
    return surfaces


def _existing_file_for(surface: str, out: Path) -> str | None:
    """Return the on-disk evidence file for a surface name, if present."""
    if surface == "airflow_task_log":
        logs = sorted(out.glob("airflow_task_log_try*.log"), reverse=True)
        return logs[0].name if logs else None
    candidate = out / f"{surface}.json"
    if candidate.is_file():
        return candidate.name
    candidate = out / f"{surface}.log"
    return candidate.name if candidate.is_file() else None


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--alert", type=Path, required=True, help="path to alert.json")
    parser.add_argument(
        "--out", type=Path, default=None, help="evidence dir (default: <alert dir>/evidence)"
    )
    parser.add_argument(
        "--offline", action="store_true", help="no network/docker; config snapshot only"
    )
    parser.add_argument(
        "--window-minutes", type=int, default=30, help="docker log window around fired_at"
    )
    parser.add_argument("--workspace-root", type=Path, default=None)
    args = parser.parse_args(argv)

    alert = json.loads(args.alert.read_text(encoding="utf-8"))
    ws = discover(workspace_root=args.workspace_root)
    if ws.project_root is None:
        eprint("error: workspace has no project (needs patient_360-style project with src/)")
        return 2
    out = args.out or (args.alert.parent / "evidence")
    out.mkdir(parents=True, exist_ok=True)
    manifest = Manifest(alert, args.offline)

    tables = resolve_tables(alert.get("task_id"), ws.project_root, ws.project_name)
    manifest.data["tables"] = tables

    collect_config(alert, tables, ws.workspace_root, ws.project_root, out, manifest)
    if args.offline:
        # Offline: never contact the stack. Evidence files that are already on
        # disk (a pre-collected bundle, a previous online run) are kept and
        # reported as `ok` with a `pre_collected` marker; everything else is
        # `skipped`. The existing manifest's entries for those files are reused
        # so statuses are not downgraded.
        prior = _read_prior_manifest(out)
        for name in (
            "airflow_dagrun",
            "airflow_taskinstances",
            "airflow_task_log",
            "docker_ps",
            *[f"docker_logs_{s}" for s in DOCKER_SERVICES],
            "uc_health",
            "se_stats",
            "se_errors",
            "delta_history",
            "marquez_runs",
        ):
            if name in manifest.data["surfaces"]:
                continue
            existing = _existing_file_for(name, out)
            if existing is not None:
                entry = dict(prior.get(name) or {"status": "ok"})
                entry.update({"status": "ok", "file": existing, "pre_collected": True})
                manifest.data["surfaces"][name] = entry
            elif prior.get(name, {}).get("status") == "unavailable":
                manifest.data["surfaces"][name] = dict(prior[name], pre_collected=True)
            else:
                manifest.skipped(name, "offline mode")
        if prior.get("collected_at"):
            manifest.data["pre_collected_at"] = prior["collected_at"]
    else:
        collect_airflow(alert, out, manifest)
        collect_docker(alert, ws.project_root, out, manifest, args.window_minutes)
        collect_uc(tables, out, manifest)
        collect_se(tables, ws.project_root, out, manifest)
        collect_delta(tables, ws.project_root, out, manifest)
        collect_marquez(out, manifest)

    write_json(out / "manifest.json", manifest.data)
    summary = {name: s["status"] for name, s in manifest.data["surfaces"].items()}
    print(json.dumps({"evidence_dir": str(out), "tables": tables, "surfaces": summary}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
