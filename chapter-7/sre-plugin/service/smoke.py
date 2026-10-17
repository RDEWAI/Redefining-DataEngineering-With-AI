#!/usr/bin/env python3
"""Smoke test for rca-runner: dry-run server + one generic alert -> a journaled run.

No claude, no stack.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
WS = HERE.parents[1]
PORT = int(os.environ.get("RCA_SMOKE_PORT", "18090"))
with tempfile.TemporaryDirectory() as tmp:
    env = {**os.environ, "RCA_WEBHOOK_TOKEN": "smoke"}
    # Isolated alerts dir + journal so the smoke never touches inputs/alerts or outputs/rca.
    proc = subprocess.Popen(
        [
            sys.executable,
            str(HERE / "rca_runner.py"),
            "--workspace-root",
            str(WS),
            "--dry-run",
            "--port",
            str(PORT),
            "--alerts-dir",
            f"{tmp}/alerts",
            "--journal",
            f"{tmp}/runs.jsonl",
        ],
        env=env,
    )
    try:
        for _ in range(30):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/healthz", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        body = json.dumps(
            {
                "dag_id": "patient360_hourly_v1",
                "task_id": "reconciliation_bronze",
                "run_id": "manual__smoke",
                "message": "SE_RUN_MISSING_FOR_DS=2026-10-15 (smoke)",
            }
        ).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/webhook/generic",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "X-RCA-Token": "smoke"},
        )
        print("submit:", urllib.request.urlopen(req, timeout=5).read().decode().strip())
        dup = json.loads(urllib.request.urlopen(req, timeout=5).read())
        assert dup["status"] == "duplicate", dup
        for _ in range(30):
            runs = json.loads(
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/runs", timeout=5).read()
            )["runs"]
            if runs:
                break
            time.sleep(0.2)
        assert runs and runs[-1]["status"] == "ok", runs
        alert = json.loads(Path(tmp, "alerts", runs[-1]["alert_id"] + ".json").read_text())
        assert (
            alert["dedup_key"] == "patient360_hourly_v1/manual__smoke"
            and alert["source"] == "airflow"
        )
        print("smoke OK:", runs[-1]["alert_id"], "|", runs[-1]["parsed"]["root_cause"])
    finally:
        proc.terminate()
        proc.wait(timeout=5)
