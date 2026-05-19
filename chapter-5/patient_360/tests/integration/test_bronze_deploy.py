"""Bronze deploy-validation smoke — STORY-02-009 AC1..AC3.

Exercises the local CD scripts under ``_infra/cd/`` end-to-end against
the docker-compose stack:

* ``test_liquibase_apply``     — AC1: ``_infra/cd/liquibase-apply.sh`` applies
  the project-wide Liquibase ``master-changelog.xml`` locally and exits 0.
* ``test_airflow_sync_no_errors`` — AC2: ``_infra/cd/airflow-sync.sh``
  re-syncs the DAG bag and reports no import errors.
* ``test_dag_retrigger``       — AC3: re-triggering the Bronze DAG via
  the Airflow REST API yields a successful run.

The shared ``stack`` and ``_require_stack`` fixtures (see
``tests/integration/conftest.py``) skip the suite honestly when the
local stack is not answering HTTP.
"""

from __future__ import annotations

import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import pytest
import requests

pytestmark = pytest.mark.integration


# Project root = the patient_360 project (parent of `tests/`). The CD
# scripts live under `_infra/cd/` relative to this root.
_PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
_CD_DIR: Path = _PROJECT_ROOT / "_infra" / "cd"


# ----------------------------------------------------------------- helpers


def _run_cd_script(name: str, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    """Run a ``_infra/cd/`` shell script from the project root.

    The script body sources its own COMPOSE / COMPOSE_FILE env vars with
    safe defaults, so the test does not need to set them. We capture
    stdout+stderr for assertion messages on failure.
    """
    script = _CD_DIR / name
    assert script.exists(), f"Expected CD script missing: {script}"
    return subprocess.run(
        ["bash", str(script)],
        cwd=str(_PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _trigger_dag(stack, dag_id: str) -> str:
    run_id = f"deploy-{uuid.uuid4().hex[:8]}"
    resp = requests.post(
        f"{stack.airflow_api}/dags/{dag_id}/dagRuns",
        json={"dag_run_id": run_id},
        auth=stack.airflow_auth(),
        timeout=10,
    )
    if resp.status_code not in (200, 201):
        pytest.fail(
            f"Airflow refused to trigger {dag_id} (HTTP {resp.status_code}): {resp.text}"
        )
    return run_id


def _poll_run(
    stack, dag_id: str, run_id: str, deadline_sec: int = 1800
) -> dict[str, Any]:
    started = time.monotonic()
    while time.monotonic() - started < deadline_sec:
        resp = requests.get(
            f"{stack.airflow_api}/dags/{dag_id}/dagRuns/{run_id}",
            auth=stack.airflow_auth(),
            timeout=10,
        )
        resp.raise_for_status()
        payload = resp.json()
        state = payload.get("state")
        if state in ("success", "failed"):
            return payload
        time.sleep(10)
    pytest.fail(
        f"DAG run {dag_id}/{run_id} did not complete within {deadline_sec}s"
    )


# ----------------------------------------------------------------- tests


def test_liquibase_apply() -> None:
    """AC1 — Liquibase update succeeds locally against the master changelog.

    The script is idempotent: Liquibase tracks applied changesets in
    DATABASECHANGELOG so re-running is a no-op once the 13 Bronze
    changesets have been registered.
    """
    result = _run_cd_script("liquibase-apply.sh")
    if result.returncode != 0:
        pytest.fail(
            "liquibase-apply.sh failed "
            f"(exit {result.returncode})\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    assert "liquibase-apply] OK" in result.stdout, (
        f"liquibase-apply.sh did not emit the success sentinel.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_airflow_sync_no_errors() -> None:
    """AC2 — DAG re-sync exits 0 and `dags list-import-errors` is empty."""
    result = _run_cd_script("airflow-sync.sh")
    if result.returncode != 0:
        pytest.fail(
            "airflow-sync.sh failed "
            f"(exit {result.returncode})\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    assert "airflow-sync] OK" in result.stdout, (
        f"airflow-sync.sh did not emit the success sentinel.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_dag_retrigger(stack) -> None:
    """AC3 — Re-triggered Bronze DAG run completes successfully."""
    dag_id = stack.dag_id_for("bronze")
    run_id = _trigger_dag(stack, dag_id)
    payload = _poll_run(stack, dag_id, run_id)
    assert payload.get("state") == "success", (
        f"DAG re-trigger {dag_id}/{run_id} ended in state "
        f"{payload.get('state')!r}: {payload}"
    )
