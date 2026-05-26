"""Tests for the local-docker teardown driver.

Tests cover --check and --dry-run only (no docker daemon required). The
--destroy mode is exercised by the end-to-end eval (make eval-e2e).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def _run_driver(
    teardown_driver: Path,
    project_root: Path,
    mode: str,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PATIENT360_PROJECT_ROOT"] = str(project_root)
    return subprocess.run(
        [str(teardown_driver), mode],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=15,
    )


class TestDriverCheckMode:
    def test_emits_valid_json_with_required_keys(
        self,
        teardown_driver: Path,
        fake_project: Path,
    ) -> None:
        result = _run_driver(teardown_driver, fake_project, "--check")
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        for key in ("driver", "started_at", "project_root", "destroyed", "skipped"):
            assert key in payload

    def test_driver_name_is_local_docker(
        self,
        teardown_driver: Path,
        fake_project: Path,
    ) -> None:
        result = _run_driver(teardown_driver, fake_project, "--check")
        payload = json.loads(result.stdout)
        assert payload["driver"] == "local-docker"

    def test_plan_includes_compose_project_and_known_volumes(
        self,
        teardown_driver: Path,
        fake_project: Path,
    ) -> None:
        result = _run_driver(teardown_driver, fake_project, "--check")
        payload = json.loads(result.stdout)
        kinds = {(d["kind"], d["name"]) for d in payload["destroyed"]}
        # The driver's static plan uses the project basename + the named
        # volumes from the docker-compose-conventions.md contract.
        project_name = Path(payload["project_root"]).name
        assert ("compose-project", project_name) in kinds
        assert ("volume", f"{project_name}_uc-data") in kinds
        assert ("volume", f"{project_name}_marquez-db") in kinds


class TestDriverDryRunMode:
    def test_emits_compose_down_with_remove_orphans(
        self,
        teardown_driver: Path,
        fake_project: Path,
    ) -> None:
        result = _run_driver(teardown_driver, fake_project, "--dry-run")
        assert result.returncode == 0, result.stderr
        # The most load-bearing line of the entire driver.
        assert "down -v --remove-orphans" in result.stdout
        # Scoped to the compose file; never unscoped.
        assert "docker-compose.yml" in result.stdout

    def test_volume_prune_is_label_scoped(
        self,
        teardown_driver: Path,
        fake_project: Path,
    ) -> None:
        result = _run_driver(teardown_driver, fake_project, "--dry-run")
        assert "docker volume prune -f --filter" in result.stdout
        assert "label=project=" in result.stdout
        # Critically: never an unfiltered prune.
        assert "docker volume prune -f\n" not in result.stdout
        assert "docker system prune" not in result.stdout


class TestDriverNoProjectRoot:
    def test_fails_with_json_error_envelope(
        self,
        teardown_driver: Path,
        tmp_path: Path,
    ) -> None:
        # No PATIENT360_PROJECT_ROOT, $PWD has no compose file → error.
        result = subprocess.run(
            [str(teardown_driver), "--check"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env={k: v for k, v in os.environ.items() if k != "PATIENT360_PROJECT_ROOT"},
            check=False,
            timeout=15,
        )
        assert result.returncode == 65
        # Error envelope on stderr is the documented contract.
        envelope = json.loads(result.stderr)
        assert envelope["driver"] == "local-docker"
        assert "error" in envelope


class TestDriverBadMode:
    def test_unknown_mode_exits_64(
        self,
        teardown_driver: Path,
        fake_project: Path,
    ) -> None:
        result = _run_driver(teardown_driver, fake_project, "--burn-everything")
        assert result.returncode == 64
        assert "unknown mode" in result.stderr or "unknown mode" in result.stdout

    def test_no_mode_exits_64(
        self,
        teardown_driver: Path,
        fake_project: Path,
    ) -> None:
        env = os.environ.copy()
        env["PATIENT360_PROJECT_ROOT"] = str(fake_project)
        result = subprocess.run(
            [str(teardown_driver)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=15,
        )
        assert result.returncode == 64
        assert "usage" in result.stderr.lower()
