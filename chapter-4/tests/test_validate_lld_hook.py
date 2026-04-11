"""Tests for the LLD PostToolUse validation hook script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conftest import VALID_LLD

HOOK_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "technical-lead-plugin"
    / "scripts"
    / "validate-lld-hook.py"
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


class TestHookSkipsNonLldFiles:
    """Hook should exit 0 for files that are not LLDs."""

    def test_non_markdown_file(self):
        result = _run_hook(_write_input("/project/outputs/lld/data.csv"))
        assert result.returncode == 0

    def test_markdown_not_in_outputs_lld(self):
        result = _run_hook(_write_input("/project/some/other/file.md"))
        assert result.returncode == 0

    def test_gitkeep_file(self):
        result = _run_hook(_write_input("/project/outputs/lld/.gitkeep"))
        assert result.returncode == 0

    def test_config_file_skipped(self):
        result = _run_hook(_write_input("/project/outputs/lld/v1/config/config-template.yaml"))
        assert result.returncode == 0

    def test_dag_yaml_skipped(self):
        result = _run_hook(_write_input("/project/outputs/lld/v1/dag/dag-definition.yaml"))
        assert result.returncode == 0

    def test_mermaid_file_skipped(self):
        result = _run_hook(_write_input("/project/outputs/lld/v1/dag/dag-pipeline.mmd"))
        assert result.returncode == 0

    def test_impl_sequence_skipped(self):
        result = _run_hook(_write_input("/project/outputs/lld/v1/impl-sequence.md"))
        assert result.returncode == 0

    def test_empty_file_path(self):
        result = _run_hook(json.dumps({"tool_input": {"file_path": ""}}))
        assert result.returncode == 0

    def test_missing_tool_input(self):
        result = _run_hook(json.dumps({"something": "else"}))
        assert result.returncode == 0


class TestHookValidatesLldFiles:
    """Hook should validate files in outputs/lld/."""

    def test_valid_lld_passes(self, tmp_path):
        lld_file = tmp_path / "outputs" / "lld" / "test.md"
        lld_file.parent.mkdir(parents=True)
        lld_file.write_text(VALID_LLD, encoding="utf-8")
        result = _run_hook(_write_input(str(lld_file)))
        assert result.returncode == 0

    def test_critical_issues_block(self, tmp_path):
        lld_file = tmp_path / "outputs" / "lld" / "bad.md"
        lld_file.parent.mkdir(parents=True)
        lld_file.write_text("# Bad LLD\n\nNo sections.", encoding="utf-8")
        result = _run_hook(_write_input(str(lld_file)))
        assert result.returncode == 2

    def test_empty_lld_produces_critical(self, tmp_path):
        lld_file = tmp_path / "outputs" / "lld" / "empty.md"
        lld_file.parent.mkdir(parents=True)
        lld_file.write_text(
            "# LLD: Empty\n\n## 1. Design Overview\n",
            encoding="utf-8",
        )
        result = _run_hook(_write_input(str(lld_file)))
        assert result.returncode == 2


class TestHookInvalidInput:
    """Hook should handle invalid JSON gracefully."""

    def test_invalid_json_input(self):
        result = _run_hook("not json at all")
        assert result.returncode == 0

    def test_empty_stdin(self):
        result = _run_hook("")
        assert result.returncode == 0
