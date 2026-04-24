"""Tests for the DMS PostToolUse validation hook script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conftest import VALID_DMS

HOOK_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "data-modeler-plugin"
    / "scripts"
    / "validate-dms-hook.py"
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


class TestHookSkipsNonDmsFiles:
    """Hook should exit 0 for files that are not DMS documents."""

    def test_non_markdown_file(self):
        result = _run_hook(_write_input("/project/outputs/dms/data.csv"))
        assert result.returncode == 0

    def test_markdown_not_in_outputs_dms(self):
        result = _run_hook(_write_input("/project/some/other/file.md"))
        assert result.returncode == 0

    def test_gitkeep_file(self):
        result = _run_hook(_write_input("/project/outputs/dms/.gitkeep"))
        assert result.returncode == 0

    def test_empty_file_path(self):
        result = _run_hook(json.dumps({"tool_input": {"file_path": ""}}))
        assert result.returncode == 0

    def test_missing_tool_input(self):
        result = _run_hook(json.dumps({"something": "else"}))
        assert result.returncode == 0


class TestHookValidatesDmsFiles:
    """Hook should validate files in outputs/dms/."""

    def test_valid_dms_passes(self, tmp_path):
        dms_file = tmp_path / "outputs" / "dms" / "test.md"
        dms_file.parent.mkdir(parents=True)
        dms_file.write_text(VALID_DMS, encoding="utf-8")
        result = _run_hook(_write_input(str(dms_file)))
        assert result.returncode == 0

    def test_critical_issues_block(self, tmp_path):
        dms_file = tmp_path / "outputs" / "dms" / "bad.md"
        dms_file.parent.mkdir(parents=True)
        dms_file.write_text("# Bad DMS\n\nNo sections.", encoding="utf-8")
        result = _run_hook(_write_input(str(dms_file)))
        assert result.returncode == 2

    def test_empty_dms_produces_critical(self, tmp_path):
        dms_file = tmp_path / "outputs" / "dms" / "empty.md"
        dms_file.parent.mkdir(parents=True)
        dms_file.write_text(
            "# DMS: Empty\n\n## 1. Design Overview\n",
            encoding="utf-8",
        )
        result = _run_hook(_write_input(str(dms_file)))
        assert result.returncode == 2


class TestHookInvalidInput:
    """Hook should handle invalid JSON gracefully."""

    def test_invalid_json_input(self):
        result = _run_hook("not json at all")
        assert result.returncode == 0

    def test_empty_stdin(self):
        result = _run_hook("")
        assert result.returncode == 0
