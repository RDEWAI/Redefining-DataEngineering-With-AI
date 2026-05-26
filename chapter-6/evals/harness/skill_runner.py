"""Invoke a skill's scripted side (the parts that don't require an LLM).

The harness exercises script entry points (e.g. check_pr_readiness.py,
local_docker.sh) against a controlled workspace, capturing every file
written so the golden-diff harness can compare against committed
expectations.

The harness does NOT spawn a real Claude session — that's what
trigger_eval.py covers for selection accuracy, and e2e_sandbox.py covers
for behavioural side-effects. skill_runner.py is the deterministic, no-
LLM tier that runs on every PR.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

CH6_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = CH6_ROOT / "developer-plugin"


@dataclass
class RunResult:
    skill: str
    returncode: int
    stdout: str
    stderr: str
    artifacts: dict[str, str] = field(default_factory=dict)


def seed_workspace(fixture: Path, dest: Path) -> Path:
    """Copy a fixture workspace into dest and return dest.

    Fixtures are the smallest plausible workspaces — just enough story
    files, planning artifacts, and patient_360 skeleton for the skill
    under test. The harness operates on the copy; tests can mutate freely.
    """
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(fixture, dest)
    return dest


def collect_artifacts(workspace: Path, patterns: list[str]) -> dict[str, str]:
    """Read every file under workspace matching any glob and return its text.

    Keys are workspace-relative POSIX paths. Used to feed golden_diff.
    """
    out: dict[str, str] = {}
    for pat in patterns:
        for path in workspace.rglob(pat):
            if path.is_file():
                rel = path.relative_to(workspace).as_posix()
                try:
                    out[rel] = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    out[rel] = "<binary>"
    return out


def run_script(
    script: Path,
    args: list[str],
    workspace: Path,
    *,
    env_extra: dict[str, str] | None = None,
    timeout: int = 60,
) -> RunResult:
    """Run a skill's executable entry point with workspace as CWD."""
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(PLUGIN_ROOT)
    env["PATIENT360_PROJECT_ROOT"] = str(workspace)
    if env_extra:
        env.update(env_extra)

    proc = subprocess.run(
        [sys.executable if script.suffix == ".py" else str(script)]
        + ([str(script)] if script.suffix == ".py" else [])
        + args,
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    return RunResult(
        skill=script.stem,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
