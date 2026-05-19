"""Tests for the stories PostToolUse validation hook script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conftest import VALID_BACKLOG, VALID_EPIC, VALID_RUNTIME_BOOTSTRAP_STORY, VALID_STORY

HOOK_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "scrum-master-plugin"
    / "scripts"
    / "validate-stories-hook.py"
)


def _run_hook(stdin_data: str) -> subprocess.CompletedProcess:
    """Run the hook script with the given stdin."""
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=stdin_data,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _write_input(file_path: str) -> str:
    """Create a PostToolUse JSON input for the hook."""
    return json.dumps({"tool_input": {"file_path": file_path}})


class TestHookSkipsNonStoriesFiles:
    """Hook should exit 0 for files that are not in outputs/stories/."""

    def test_non_markdown_file(self):
        result = _run_hook(_write_input("/project/outputs/stories/data.csv"))
        assert result.returncode == 0

    def test_markdown_not_in_outputs_stories(self):
        result = _run_hook(_write_input("/project/some/other/file.md"))
        assert result.returncode == 0

    def test_gitkeep_file(self):
        result = _run_hook(_write_input("/project/outputs/stories/.gitkeep"))
        assert result.returncode == 0

    def test_empty_file_path(self):
        result = _run_hook(json.dumps({"tool_input": {"file_path": ""}}))
        assert result.returncode == 0

    def test_missing_tool_input(self):
        result = _run_hook(json.dumps({"something": "else"}))
        assert result.returncode == 0

    def test_individual_story_file_skipped(self):
        """Hook only validates on BACKLOG-*.md writes, not individual story files."""
        result = _run_hook(_write_input("/project/outputs/stories/v1/EPIC-01/STORY-01-001.md"))
        assert result.returncode == 0


class TestHookValidatesBacklogFiles:
    """Hook should validate when a BACKLOG-*.md file is written."""

    def test_valid_backlog_passes(self, tmp_path):
        stories_dir = tmp_path / "outputs" / "stories" / "v1"
        stories_dir.mkdir(parents=True)

        # Create a valid directory structure
        (stories_dir / "BACKLOG-2026-03-23-test.md").write_text(VALID_BACKLOG, encoding="utf-8")
        epic_dir = stories_dir / "EPIC-01-test"
        epic_dir.mkdir()
        (epic_dir / "EPIC-01.md").write_text(VALID_EPIC, encoding="utf-8")
        (epic_dir / "STORY-01-001-test.md").write_text(VALID_STORY, encoding="utf-8")
        (epic_dir / "STORY-01-002-bootstrap.md").write_text(
            VALID_RUNTIME_BOOTSTRAP_STORY, encoding="utf-8"
        )

        result = _run_hook(_write_input(str(stories_dir / "BACKLOG-2026-03-23-test.md")))
        assert result.returncode == 0

    def test_critical_issues_block(self, tmp_path):
        stories_dir = tmp_path / "outputs" / "stories" / "v1"
        stories_dir.mkdir(parents=True)
        (stories_dir / "BACKLOG-bad.md").write_text(
            "# Bad Backlog\n\nNo sections.", encoding="utf-8"
        )
        result = _run_hook(_write_input(str(stories_dir / "BACKLOG-bad.md")))
        assert result.returncode == 2


class TestHookInvalidInput:
    """Hook should handle invalid JSON gracefully."""

    def test_invalid_json_input(self):
        result = _run_hook("not json at all")
        assert result.returncode == 0

    def test_empty_stdin(self):
        result = _run_hook("")
        assert result.returncode == 0
