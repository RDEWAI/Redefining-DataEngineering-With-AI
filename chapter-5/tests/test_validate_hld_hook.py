"""Tests for the HLD PostToolUse validation hook script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conftest import VALID_HLD

HOOK_SCRIPT = (
    Path(__file__).resolve().parent.parent / "architect-plugin" / "scripts" / "validate-hld-hook.py"
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


class TestHookSkipsNonHldFiles:
    """Hook should exit 0 for files that are not HLDs."""

    def test_non_markdown_file(self):
        result = _run_hook(_write_input("/project/outputs/hld/data.csv"))
        assert result.returncode == 0

    def test_markdown_not_in_outputs_hld(self):
        result = _run_hook(_write_input("/project/some/other/file.md"))
        assert result.returncode == 0

    def test_gitkeep_file(self):
        result = _run_hook(_write_input("/project/outputs/hld/.gitkeep"))
        assert result.returncode == 0

    def test_empty_file_path(self):
        result = _run_hook(json.dumps({"tool_input": {"file_path": ""}}))
        assert result.returncode == 0

    def test_missing_tool_input(self):
        result = _run_hook(json.dumps({"something": "else"}))
        assert result.returncode == 0


class TestHookValidatesHldFiles:
    """Hook should validate files in outputs/hld/."""

    def test_valid_hld_passes(self, tmp_path):
        hld_file = tmp_path / "outputs" / "hld" / "test.md"
        hld_file.parent.mkdir(parents=True)
        hld_file.write_text(VALID_HLD, encoding="utf-8")
        result = _run_hook(_write_input(str(hld_file)))
        assert result.returncode == 0

    def test_critical_issues_block(self, tmp_path):
        hld_file = tmp_path / "outputs" / "hld" / "bad.md"
        hld_file.parent.mkdir(parents=True)
        hld_file.write_text("# Bad HLD\n\nNo sections.", encoding="utf-8")
        result = _run_hook(_write_input(str(hld_file)))
        assert result.returncode == 2

    def test_empty_hld_produces_critical(self, tmp_path):
        hld_file = tmp_path / "outputs" / "hld" / "empty.md"
        hld_file.parent.mkdir(parents=True)
        hld_file.write_text(
            "# HLD: Empty\n\n## 1. Design Overview\n",
            encoding="utf-8",
        )
        result = _run_hook(_write_input(str(hld_file)))
        assert result.returncode == 2


class TestHookInvalidInput:
    """Hook should handle invalid JSON gracefully."""

    def test_invalid_json_input(self):
        result = _run_hook("not json at all")
        assert result.returncode == 0

    def test_empty_stdin(self):
        result = _run_hook("")
        assert result.returncode == 0
