"""End-to-end behavioural harness — exercises real side effects.

Brings up the patient_360 docker-compose stack, runs the chosen skill's
script entry points against it, asserts the documented side effects
(e.g. for pr-process: after --destroy, the named volumes no longer
appear in `docker volume ls`).

Tagged `@pytest.mark.e2e` and excluded from `make eval` (`make test`)
default. Run via `make eval-e2e`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

CH6_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = CH6_ROOT / "patient_360" / "_infra" / "docker" / "docker-compose.yml"


@dataclass
class E2EResult:
    name: str
    ok: bool
    detail: str = ""


def have_docker() -> bool:
    return shutil.which("docker") is not None


def docker_volume_ls() -> set[str]:
    if not have_docker():
        return set()
    proc = subprocess.run(
        ["docker", "volume", "ls", "--format", "{{.Name}}"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    return {line.strip() for line in proc.stdout.splitlines() if line.strip()}


def compose_up() -> E2EResult:
    if not have_docker():
        return E2EResult("compose_up", False, "docker not installed")
    proc = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d", "--wait"],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    return E2EResult(
        "compose_up",
        proc.returncode == 0,
        proc.stderr.strip()[-500:] if proc.returncode else "",
    )


def run_teardown_destroy(driver: Path) -> tuple[E2EResult, dict]:
    # Inherit the parent env (PATH, HOME, DOCKER_HOST, etc.) and add our
    # override. Passing `env={...}` with a single key REPLACES the entire
    # environment, stripping PATH — the driver then can't find `docker`,
    # `python3`, or `date`, and exits 66 with a misleading "docker CLI
    # not installed" diagnostic on hosts where docker is in fact installed.
    env = {**os.environ, "PATIENT360_PROJECT_ROOT": str(CH6_ROOT / "patient_360")}
    proc = subprocess.run(
        [str(driver), "--destroy"],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    summary: dict = {}
    try:
        summary = json.loads(proc.stdout)
    except json.JSONDecodeError:
        pass
    return (
        E2EResult(
            "teardown_destroy",
            proc.returncode == 0 and bool(summary),
            (proc.stderr or proc.stdout).strip()[-500:],
        ),
        summary,
    )
