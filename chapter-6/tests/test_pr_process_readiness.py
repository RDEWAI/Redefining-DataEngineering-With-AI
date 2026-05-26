"""Tests for check_pr_readiness.py — the Phase 1 aggregator of pr-process."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def _run_aggregator(
    python_exe: str,
    readiness_script: Path,
    *,
    story: str,
    workspace_root: Path,
    project_root: Path,
    branch: str,
    emit: str = "json",
) -> subprocess.CompletedProcess:
    # Strip GIT_* leaks from a parent invocation (e.g. pre-push hook)
    # so the aggregator's `git status` resolves the fake project, not
    # the surrounding repo.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(
        [
            python_exe,
            str(readiness_script),
            "--story",
            story,
            "--workspace-root",
            str(workspace_root),
            "--project-root",
            str(project_root),
            "--branch",
            branch,
            "--emit",
            emit,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
        env=env,
    )


class TestReadinessAggregator:
    def test_clean_workspace_fails_only_because_origin_is_missing(
        self,
        python_exe: str,
        readiness_script: Path,
        fake_workspace: Path,
        fake_project: Path,
    ) -> None:
        """No remote → branch_state gate emits a WARN, not a hard FAIL.

        We assert the script exits with a code we recognise (0/1/2) and the
        JSON includes the expected gate names. We do not assert PASS — the
        story is Approved but `make test` only runs `@true`, and there are
        no ACs, so verify_acs may emit WARN. The point of this test is the
        wiring, not the verdict.
        """
        result = _run_aggregator(
            python_exe,
            readiness_script,
            story="STORY-99-001",
            workspace_root=fake_workspace,
            project_root=fake_project,
            branch="feature/STORY-99-001",
        )
        assert result.returncode in (0, 1, 2), result.stderr
        payload = json.loads(result.stdout)
        gate_names = [g["name"] for g in payload["gates"]]
        assert gate_names == [
            "git_tree_clean",
            "branch_state",
            "story_approved",
            "make_lint",
            "make_test",
            "verify_acs",
            "validate_stories",
        ]

    def test_unapproved_story_fails(
        self,
        python_exe: str,
        readiness_script: Path,
        fake_workspace: Path,
        fake_project: Path,
    ) -> None:
        story_file = (
            fake_workspace / "outputs" / "stories" / "EPIC-99-fake" / "STORY-99-001-fake.md"
        )
        story_file.write_text(
            "# Fake Story\n\nStatus: Draft\n\n## Verification\n- AC1\n",
            encoding="utf-8",
        )

        result = _run_aggregator(
            python_exe,
            readiness_script,
            story="STORY-99-001",
            workspace_root=fake_workspace,
            project_root=fake_project,
            branch="feature/STORY-99-001",
        )
        payload = json.loads(result.stdout)
        story_gate = next(g for g in payload["gates"] if g["name"] == "story_approved")
        assert story_gate["status"] == "FAIL"
        assert "Draft" in story_gate["detail"]
        assert payload["result"] == "FAIL"
        assert result.returncode == 1

    def test_dirty_tree_fails(
        self,
        python_exe: str,
        readiness_script: Path,
        fake_workspace: Path,
        fake_project: Path,
    ) -> None:
        # Introduce an uncommitted change.
        (fake_project / "src.py").write_text("x = 2\n", encoding="utf-8")
        result = _run_aggregator(
            python_exe,
            readiness_script,
            story="STORY-99-001",
            workspace_root=fake_workspace,
            project_root=fake_project,
            branch="feature/STORY-99-001",
        )
        payload = json.loads(result.stdout)
        git_gate = next(g for g in payload["gates"] if g["name"] == "git_tree_clean")
        assert git_gate["status"] == "FAIL"
        assert "src.py" in git_gate["detail"]

    def test_main_branch_blocked(
        self,
        python_exe: str,
        readiness_script: Path,
        fake_workspace: Path,
        fake_project: Path,
    ) -> None:
        result = _run_aggregator(
            python_exe,
            readiness_script,
            story="STORY-99-001",
            workspace_root=fake_workspace,
            project_root=fake_project,
            branch="main",
        )
        payload = json.loads(result.stdout)
        branch_gate = next(g for g in payload["gates"] if g["name"] == "branch_state")
        assert branch_gate["status"] == "FAIL"
        assert "main" in branch_gate["detail"]

    def test_labels_emit_includes_required_sandbox_teardown(
        self,
        python_exe: str,
        readiness_script: Path,
        fake_workspace: Path,
        fake_project: Path,
    ) -> None:
        result = _run_aggregator(
            python_exe,
            readiness_script,
            story="STORY-99-001",
            workspace_root=fake_workspace,
            project_root=fake_project,
            branch="feature/STORY-99-001",
            emit="labels",
        )
        assert "requires-sandbox-teardown" in result.stdout

    def test_teardown_plan_reflects_local_docker_when_compose_exists(
        self,
        python_exe: str,
        readiness_script: Path,
        fake_workspace: Path,
        fake_project: Path,
    ) -> None:
        result = _run_aggregator(
            python_exe,
            readiness_script,
            story="STORY-99-001",
            workspace_root=fake_workspace,
            project_root=fake_project,
            branch="feature/STORY-99-001",
        )
        payload = json.loads(result.stdout)
        assert payload["teardown_driver"] == "local-docker"
        assert any(r["kind"] == "compose-project" for r in payload["teardown_plan"])


class TestReadinessReportSchema:
    """Snapshot-shape tests for the JSON the PR-body template consumes."""

    def test_report_has_all_top_level_keys(
        self,
        python_exe: str,
        readiness_script: Path,
        fake_workspace: Path,
        fake_project: Path,
    ) -> None:
        result = _run_aggregator(
            python_exe,
            readiness_script,
            story="STORY-99-001",
            workspace_root=fake_workspace,
            project_root=fake_project,
            branch="feature/STORY-99-001",
        )
        payload = json.loads(result.stdout)
        for key in (
            "story",
            "branch",
            "workspace_root",
            "project_root",
            "timestamp",
            "gates",
            "acs",
            "files_by_layer",
            "validators",
            "teardown_driver",
            "teardown_plan",
            "labels",
            "result",
        ):
            assert key in payload, f"missing key: {key}"

    def test_validators_summary_one_row_per_gate(
        self,
        python_exe: str,
        readiness_script: Path,
        fake_workspace: Path,
        fake_project: Path,
    ) -> None:
        result = _run_aggregator(
            python_exe,
            readiness_script,
            story="STORY-99-001",
            workspace_root=fake_workspace,
            project_root=fake_project,
            branch="feature/STORY-99-001",
        )
        payload = json.loads(result.stdout)
        assert len(payload["validators"]) == len(payload["gates"])
