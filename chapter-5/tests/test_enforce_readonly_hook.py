"""Tests for the PreToolUse read-only query enforcement hook script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK_SCRIPT = str(
    Path(__file__).resolve().parent.parent / "ba-plugin" / "scripts" / "enforce-readonly-queries.py"
)


def _run_hook(stdin_data: dict) -> subprocess.CompletedProcess:
    """Run the hook script with the given JSON input on stdin."""
    return subprocess.run(
        [sys.executable, HOOK_SCRIPT],
        input=json.dumps(stdin_data),
        capture_output=True,
        text=True,
        timeout=10,
    )


def _bash_input(command: str) -> dict:
    """Build a PreToolUse Bash hook input payload."""
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


class TestNonDbCommandsPassThrough:
    """Non-database Bash commands should be allowed without interference."""

    def test_ls_command(self):
        result = _run_hook(_bash_input("ls -la /some/path"))
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_make_command(self):
        result = _run_hook(_bash_input("make test"))
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_python_command(self):
        result = _run_hook(_bash_input("python -c 'print(1)'"))
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_git_command(self):
        result = _run_hook(_bash_input("git status"))
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_empty_command(self):
        result = _run_hook(_bash_input(""))
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestReadOnlyQueriesPass:
    """Valid read-only DuckDB commands with -readonly should pass."""

    def test_select_with_readonly(self):
        result = _run_hook(
            _bash_input(
                'duckdb data/duckdb/raw.db -readonly -c "SELECT COUNT(*) FROM synthea.patients;"'
            )
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_information_schema_with_readonly(self):
        result = _run_hook(
            _bash_input(
                "duckdb data/duckdb/raw.db -readonly -c "
                '"SELECT table_name FROM information_schema.tables;"'
            )
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_read_only_underscore_variant(self):
        result = _run_hook(_bash_input('duckdb data/duckdb/raw.db -read_only -c "SELECT 1;"'))
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestMissingReadonlyFlagBlocked:
    """DuckDB commands without -readonly flag should be blocked."""

    def test_duckdb_without_readonly(self):
        result = _run_hook(
            _bash_input('duckdb data/duckdb/raw.db -c "SELECT COUNT(*) FROM synthea.patients;"')
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "-readonly" in output["systemMessage"]


class TestWriteOperationsBlocked:
    """Database write operations should be blocked even with -readonly flag."""

    def test_insert_blocked(self):
        result = _run_hook(
            _bash_input(
                'duckdb data/duckdb/raw.db -readonly -c "INSERT INTO synthea.patients VALUES (1);"'
            )
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "INSERT" in output["systemMessage"]

    def test_update_blocked(self):
        result = _run_hook(
            _bash_input(
                "duckdb data/duckdb/raw.db -readonly -c \"UPDATE synthea.patients SET name='x';\""
            )
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "UPDATE" in output["systemMessage"]

    def test_delete_blocked(self):
        result = _run_hook(
            _bash_input('duckdb data/duckdb/raw.db -readonly -c "DELETE FROM synthea.patients;"')
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "DELETE" in output["systemMessage"]

    def test_drop_blocked(self):
        result = _run_hook(
            _bash_input('duckdb data/duckdb/raw.db -readonly -c "DROP TABLE synthea.patients;"')
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "DROP" in output["systemMessage"]

    def test_alter_blocked(self):
        result = _run_hook(
            _bash_input(
                "duckdb data/duckdb/raw.db -readonly"
                ' -c "ALTER TABLE synthea.patients'
                ' ADD COLUMN x INT;"'
            )
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "ALTER" in output["systemMessage"]

    def test_create_blocked(self):
        result = _run_hook(
            _bash_input('duckdb data/duckdb/raw.db -readonly -c "CREATE TABLE test (id INT);"')
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "CREATE" in output["systemMessage"]

    def test_truncate_blocked(self):
        result = _run_hook(
            _bash_input('duckdb data/duckdb/raw.db -readonly -c "TRUNCATE TABLE synthea.patients;"')
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "TRUNCATE" in output["systemMessage"]

    def test_case_insensitive_detection(self):
        result = _run_hook(
            _bash_input(
                'duckdb data/duckdb/raw.db -readonly -c "insert into synthea.patients values (1);"'
            )
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


class TestEdgeCases:
    """Edge cases and malformed input should be handled gracefully."""

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

    def test_missing_tool_input(self):
        result = _run_hook({"hook_event_name": "PreToolUse", "tool_name": "Bash"})
        assert result.returncode == 0

    def test_dot_db_in_path_triggers_inspection(self):
        """A command referencing a .db file should be inspected for writes."""
        result = _run_hook(_bash_input('sqlite3 other.db "INSERT INTO test VALUES (1);"'))
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
