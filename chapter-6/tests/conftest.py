"""Shared fixtures for chapter-6 plugin tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

CH6_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = CH6_ROOT / "developer-plugin"
PR_PROCESS_DIR = PLUGIN_ROOT / "skills" / "pr-process"


@pytest.fixture
def chapter6_root() -> Path:
    return CH6_ROOT


@pytest.fixture
def plugin_root() -> Path:
    return PLUGIN_ROOT


@pytest.fixture
def pr_process_dir() -> Path:
    return PR_PROCESS_DIR


@pytest.fixture
def teardown_driver() -> Path:
    return PR_PROCESS_DIR / "scripts" / "teardown_drivers" / "local_docker.sh"


@pytest.fixture
def readiness_script() -> Path:
    return PR_PROCESS_DIR / "scripts" / "check_pr_readiness.py"


@pytest.fixture
def fake_project(tmp_path: Path) -> Path:
    """A throwaway 'project_root' with a docker-compose.yml + Makefile.

    Initialised as a git repo with one commit on `main` and a feature branch
    one commit ahead. No remote. Tests that need `origin/main` mock the
    subprocess interaction instead — the goal here is just to exercise the
    aggregator with a real git tree.
    """
    project = tmp_path / "project_360"
    (project / "_infra" / "docker").mkdir(parents=True)
    (project / "_infra" / "docker" / "docker-compose.yml").write_text(
        "services: {fake: {image: alpine}}\n", encoding="utf-8"
    )
    (project / "Makefile").write_text("lint:\n\t@true\ntest:\n\t@true\n", encoding="utf-8")

    # Strip any GIT_* env vars leaking in from a parent invocation (e.g.
    # when pytest runs inside a pre-push hook). They redirect git to the
    # surrounding repo instead of our fresh tmp_path/project_360 repo.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_AUTHOR_NAME"] = "test"
    env["GIT_AUTHOR_EMAIL"] = "test@example.com"
    env["GIT_COMMITTER_NAME"] = "test"
    env["GIT_COMMITTER_EMAIL"] = "test@example.com"

    def _git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=project, env=env, check=True)

    _git("init", "-q", "-b", "main")
    _git("config", "user.email", "test@example.com")
    _git("config", "user.name", "test")
    _git("add", ".")
    _git("commit", "-q", "-m", "initial")
    _git("checkout", "-q", "-b", "feature/STORY-99-001")
    (project / "src.py").write_text("x = 1\n", encoding="utf-8")
    _git("add", "src.py")
    _git("commit", "-q", "-m", "feature commit")
    return project


@pytest.fixture
def fake_workspace(tmp_path: Path, fake_project: Path) -> Path:
    """A throwaway 'workspace_root' that holds a story file + memory dir."""
    ws = fake_project.parent
    stories = ws / "outputs" / "stories" / "EPIC-99-fake"
    stories.mkdir(parents=True)
    (stories / "STORY-99-001-fake.md").write_text(
        "# Fake Story\n\nStatus: Approved\n\n## Verification\n- AC1\n",
        encoding="utf-8",
    )
    (ws / "memory" / "developer").mkdir(parents=True)
    return ws


@pytest.fixture
def python_exe() -> str:
    return sys.executable
