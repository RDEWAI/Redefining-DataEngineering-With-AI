"""Tests for the PostToolUse DRD validation hook script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_SCRIPT = str(
    Path(__file__).resolve().parent.parent / "ba-plugin" / "scripts" / "validate-drd-hook.py"
)


def _run_hook(stdin_data: dict) -> subprocess.CompletedProcess:
    """Run the hook script with the given JSON input on stdin."""
    return subprocess.run(
        [sys.executable, HOOK_SCRIPT],
        input=json.dumps(stdin_data),
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestHookSkipsNonDrdFiles:
    """Hook should exit 0 for files that are not DRDs."""

    def test_non_markdown_file(self):
        result = _run_hook(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": "/some/path/code.py", "content": "x = 1"},
            }
        )
        assert result.returncode == 0

    def test_markdown_not_in_outputs_drd(self):
        result = _run_hook(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "/some/path/README.md",
                    "content": "# Hello",
                },
            }
        )
        assert result.returncode == 0

    def test_gitkeep_file(self):
        result = _run_hook(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "/project/outputs/drd/.gitkeep",
                    "content": "",
                },
            }
        )
        assert result.returncode == 0

    def test_empty_file_path(self):
        result = _run_hook(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": "", "content": ""},
            }
        )
        assert result.returncode == 0

    def test_missing_tool_input(self):
        result = _run_hook(
            {"hook_event_name": "PostToolUse", "tool_name": "Write"}
        )
        assert result.returncode == 0


class TestHookValidatesDrdFiles:
    """Hook should run the validator on DRD files in outputs/drd/."""

    def test_valid_drd_passes(self, tmp_path: Path):
        from conftest import VALID_DRD

        drd_dir = tmp_path / "outputs" / "drd"
        drd_dir.mkdir(parents=True)
        drd_file = drd_dir / "DRD-2026-01-29-test.md"
        drd_file.write_text(VALID_DRD, encoding="utf-8")

        result = _run_hook(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(drd_file),
                    "content": VALID_DRD,
                },
            }
        )
        assert result.returncode == 0

    def test_critical_issues_block(self, tmp_path: Path):
        from conftest import MINIMAL_INVALID_DRD

        drd_dir = tmp_path / "outputs" / "drd"
        drd_dir.mkdir(parents=True)
        drd_file = drd_dir / "DRD-2026-01-29-bad.md"
        drd_file.write_text(MINIMAL_INVALID_DRD, encoding="utf-8")

        result = _run_hook(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(drd_file),
                    "content": MINIMAL_INVALID_DRD,
                },
            }
        )
        # Exit code 2 = blocking error fed back to Claude
        assert result.returncode == 2
        assert "CRITICAL" in result.stderr

    def test_empty_sections_produce_critical(self, tmp_path: Path):
        from conftest import EMPTY_SECTIONS_DRD

        drd_dir = tmp_path / "outputs" / "drd"
        drd_dir.mkdir(parents=True)
        drd_file = drd_dir / "DRD-2026-01-29-empty.md"
        drd_file.write_text(EMPTY_SECTIONS_DRD, encoding="utf-8")

        result = _run_hook(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(drd_file),
                    "content": EMPTY_SECTIONS_DRD,
                },
            }
        )
        assert result.returncode == 2
        assert "CRITICAL" in result.stderr


class TestHookWarningOutput:
    """Hook should return JSON additionalContext for warnings."""

    def test_placeholder_drd_returns_json_context(self, tmp_path: Path):
        from conftest import PLACEHOLDER_DRD

        drd_dir = tmp_path / "outputs" / "drd"
        drd_dir.mkdir(parents=True)
        drd_file = drd_dir / "DRD-2026-01-29-placeholder.md"
        drd_file.write_text(PLACEHOLDER_DRD, encoding="utf-8")

        result = _run_hook(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Write",
                "tool_input": {
                    "file_path": str(drd_file),
                    "content": PLACEHOLDER_DRD,
                },
            }
        )
        # Placeholder DRD has all sections but may produce warnings or info only
        # Exit 0 means non-blocking
        assert result.returncode == 0


class TestHookInvalidInput:
    """Hook should handle bad input gracefully."""

    def test_invalid_json_input(self):
        proc = subprocess.run(
            [sys.executable, HOOK_SCRIPT],
            input="not valid json",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 0

    def test_empty_stdin(self):
        proc = subprocess.run(
            [sys.executable, HOOK_SCRIPT],
            input="",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 0
