"""Tests for the check-learnings-queue PostToolUse hook script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Test against the architect-plugin version (all 6 are identical except paths)
HOOK_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "architect-plugin"
    / "scripts"
    / "check-learnings-queue.py"
)


def _run_hook(stdin_data: str, env_override: dict | None = None) -> subprocess.CompletedProcess:
    """Run the hook script with the given stdin."""
    import os

    env = os.environ.copy()
    if env_override:
        env.update(env_override)
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=stdin_data,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def _write_input(file_path: str) -> str:
    """Create a PostToolUse JSON input for the hook."""
    return json.dumps({"tool_input": {"file_path": file_path}})


class TestHookSkipsNonArtifactFiles:
    """Hook should exit 0 silently for files outside the output directory."""

    def test_non_artifact_file(self):
        result = _run_hook(_write_input("/project/some/other/file.md"))
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_non_markdown_file(self):
        result = _run_hook(_write_input("/project/outputs/hld/data.csv"))
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_empty_file_path(self):
        result = _run_hook(json.dumps({"tool_input": {"file_path": ""}}))
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_missing_tool_input(self):
        result = _run_hook(json.dumps({"something": "else"}))
        assert result.returncode == 0


class TestHookWithEmptyQueue:
    """Hook should exit 0 with no output when queue is empty."""

    def test_empty_queue_file(self, tmp_path):
        # Create empty queue file
        memory_dir = tmp_path / "memory" / "hld"
        memory_dir.mkdir(parents=True)
        queue_file = memory_dir / "learnings-queue.jsonl"
        queue_file.write_text("", encoding="utf-8")

        # Create an artifact file path that matches
        hld_file = tmp_path / "outputs" / "hld" / "v1" / "test.md"
        hld_file.parent.mkdir(parents=True)
        hld_file.write_text("# Test HLD", encoding="utf-8")

        result = _run_hook(
            _write_input(str(hld_file)),
            env_override={"CHAPTER5_ROOT": str(tmp_path)},
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_missing_queue_file(self, tmp_path):
        hld_file = tmp_path / "outputs" / "hld" / "v1" / "test.md"
        hld_file.parent.mkdir(parents=True)
        hld_file.write_text("# Test HLD", encoding="utf-8")

        result = _run_hook(
            _write_input(str(hld_file)),
            env_override={"CHAPTER5_ROOT": str(tmp_path)},
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestHookWithPendingEntries:
    """Hook should emit additionalContext when pending entries exist."""

    def test_pending_entries_emit_reminder(self, tmp_path):
        memory_dir = tmp_path / "memory" / "hld"
        memory_dir.mkdir(parents=True)
        queue_file = memory_dir / "learnings-queue.jsonl"
        line1 = (
            '{"skill": "create-hld", "date": "2026-03-23",'
            ' "correction": "test", "pattern": "test",'
            ' "status": "pending"}\n'
        )
        line2 = (
            '{"skill": "create-hld", "date": "2026-03-23",'
            ' "correction": "test2", "pattern": "test2",'
            ' "status": "pending"}\n'
        )
        queue_file.write_text(
            line1 + line2,
            encoding="utf-8",
        )

        hld_file = tmp_path / "outputs" / "hld" / "v1" / "test.md"
        hld_file.parent.mkdir(parents=True)
        hld_file.write_text("# Test HLD", encoding="utf-8")

        result = _run_hook(
            _write_input(str(hld_file)),
            env_override={"CHAPTER5_ROOT": str(tmp_path)},
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert "additionalContext" in output.get("hookSpecificOutput", {})
        assert "2" in output["hookSpecificOutput"]["additionalContext"]
        assert "pending" in output["hookSpecificOutput"]["additionalContext"].lower()

    def test_all_applied_no_reminder(self, tmp_path):
        memory_dir = tmp_path / "memory" / "hld"
        memory_dir.mkdir(parents=True)
        queue_file = memory_dir / "learnings-queue.jsonl"
        applied_line = (
            '{"skill": "create-hld", "date": "2026-03-23",'
            ' "correction": "test", "pattern": "test",'
            ' "status": "applied"}\n'
        )
        queue_file.write_text(
            applied_line,
            encoding="utf-8",
        )

        hld_file = tmp_path / "outputs" / "hld" / "v1" / "test.md"
        hld_file.parent.mkdir(parents=True)
        hld_file.write_text("# Test HLD", encoding="utf-8")

        result = _run_hook(
            _write_input(str(hld_file)),
            env_override={"CHAPTER5_ROOT": str(tmp_path)},
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_mixed_statuses_counts_only_pending(self, tmp_path):
        memory_dir = tmp_path / "memory" / "hld"
        memory_dir.mkdir(parents=True)
        queue_file = memory_dir / "learnings-queue.jsonl"
        queue_file.write_text(
            '{"skill": "create-hld", "status": "applied"}\n'
            '{"skill": "create-hld", "status": "pending"}\n'
            '{"skill": "update-hld", "status": "rejected"}\n',
            encoding="utf-8",
        )

        hld_file = tmp_path / "outputs" / "hld" / "v1" / "test.md"
        hld_file.parent.mkdir(parents=True)
        hld_file.write_text("# Test HLD", encoding="utf-8")

        result = _run_hook(
            _write_input(str(hld_file)),
            env_override={"CHAPTER5_ROOT": str(tmp_path)},
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert "1" in output["hookSpecificOutput"]["additionalContext"]


class TestHookInvalidInput:
    """Hook should handle invalid input gracefully."""

    def test_invalid_json_input(self):
        result = _run_hook("not json at all")
        assert result.returncode == 0

    def test_empty_stdin(self):
        result = _run_hook("")
        assert result.returncode == 0
