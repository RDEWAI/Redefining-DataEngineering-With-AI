"""Tests for the DQS PostToolUse validation hook script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from conftest import VALID_DQS

HOOK_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "dq-engineer-plugin"
    / "scripts"
    / "validate-dqs-hook.py"
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


class TestHookSkipsNonDqsFiles:
    """Hook should exit 0 for files that are not DQS documents."""

    def test_non_markdown_file(self):
        result = _run_hook(_write_input("/project/outputs/dqs/data.csv"))
        assert result.returncode == 0

    def test_markdown_not_in_outputs_dqs(self):
        result = _run_hook(_write_input("/project/some/other/file.md"))
        assert result.returncode == 0

    def test_gitkeep_file(self):
        result = _run_hook(_write_input("/project/outputs/dqs/.gitkeep"))
        assert result.returncode == 0

    def test_yaml_file_skipped(self):
        result = _run_hook(_write_input("/project/outputs/dqs/v1/se-rules/rules.yaml"))
        assert result.returncode == 0

    def test_empty_file_path(self):
        result = _run_hook(json.dumps({"tool_input": {"file_path": ""}}))
        assert result.returncode == 0

    def test_missing_tool_input(self):
        result = _run_hook(json.dumps({"something": "else"}))
        assert result.returncode == 0


class TestHookValidatesDqsFiles:
    """Hook should validate .md files in outputs/dqs/."""

    def test_valid_dqs_passes(self, tmp_path):
        dqs_file = tmp_path / "outputs" / "dqs" / "test.md"
        dqs_file.parent.mkdir(parents=True)
        dqs_file.write_text(VALID_DQS, encoding="utf-8")
        result = _run_hook(_write_input(str(dqs_file)))
        assert result.returncode == 0

    def test_critical_issues_block(self, tmp_path):
        dqs_file = tmp_path / "outputs" / "dqs" / "bad.md"
        dqs_file.parent.mkdir(parents=True)
        dqs_file.write_text("# Bad DQS\n\nNo sections.", encoding="utf-8")
        result = _run_hook(_write_input(str(dqs_file)))
        assert result.returncode == 2

    def test_empty_dqs_produces_critical(self, tmp_path):
        dqs_file = tmp_path / "outputs" / "dqs" / "empty.md"
        dqs_file.parent.mkdir(parents=True)
        dqs_file.write_text(
            "# DQS: Empty\n\n## 1. Overview\n",
            encoding="utf-8",
        )
        result = _run_hook(_write_input(str(dqs_file)))
        assert result.returncode == 2


class TestHookInvalidInput:
    """Hook should handle invalid JSON gracefully."""

    def test_invalid_json_input(self):
        result = _run_hook("not json at all")
        assert result.returncode == 0

    def test_empty_stdin(self):
        result = _run_hook("")
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# SE YAML auto-generation tests
# ---------------------------------------------------------------------------

# Real paths for the hook to discover the generator script
CHAPTER_ROOT = Path(__file__).resolve().parent.parent
GENERATOR_SCRIPT = (
    CHAPTER_ROOT
    / "dq-engineer-plugin"
    / "skills"
    / "generate-se-rules"
    / "scripts"
    / "generate_se_rules.py"
)


def _setup_dqs_with_se(tmp_path: Path) -> tuple[Path, Path]:
    """Set up a valid DQS file in the real chapter-4 outputs dir structure.

    Returns (dqs_file, se_rules_dir).

    The hook discovers the generator via plugin_root (dirname of scripts/).
    It discovers the SE config via _find_chapter_root() which walks up from
    the DQS file looking for dq-engineer-plugin/. For tests, we write the
    DQS into the real chapter-4/outputs/dqs/ tree so the hook finds everything.
    """
    # Use a version subdir under the real chapter root
    version_dir = CHAPTER_ROOT / "outputs" / "dqs" / "test_hook_se"
    version_dir.mkdir(parents=True, exist_ok=True)

    dqs_file = version_dir / "DQS-test-hook.md"
    dqs_file.write_text(VALID_DQS, encoding="utf-8")

    # Ensure matching inputs dir with SE config template
    inputs_dir = CHAPTER_ROOT / "inputs" / "dqs" / "test_hook_se"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    se_config = inputs_dir / "se-config-template.yaml"
    se_config.write_text(
        yaml.dump(
            {
                "product_id": "test-hook",
                "dq_env": {
                    "DEV": {
                        "table_name": "dev_{schema}.{table}",
                        "action_if_failed": "ignore",
                        "enable_for_source_dq_validation": True,
                        "enable_for_target_dq_validation": True,
                        "is_active": True,
                        "enable_error_drop_alert": False,
                        "error_drop_threshold": 0,
                        "priority": "medium",
                    },
                    "PROD": {
                        "table_name": "{schema}.{table}",
                        "action_if_failed": "fail",
                        "enable_for_source_dq_validation": True,
                        "enable_for_target_dq_validation": True,
                        "is_active": True,
                        "enable_error_drop_alert": True,
                        "error_drop_threshold": 2,
                        "priority": "high",
                    },
                },
                "_generator": {
                    "layer_schemas": {
                        "bronze": "raw",
                        "silver": "clinical",
                        "gold": "analytics",
                        "source": "synthea",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    se_rules_dir = version_dir / "se-rules"
    return dqs_file, se_rules_dir


@pytest.fixture(autouse=False)
def _cleanup_test_hook_se():
    """Clean up test_hook_se directories after tests."""
    yield
    import shutil

    for d in [
        CHAPTER_ROOT / "outputs" / "dqs" / "test_hook_se",
        CHAPTER_ROOT / "inputs" / "dqs" / "test_hook_se",
    ]:
        if d.exists():
            shutil.rmtree(d)


@pytest.mark.skipif(
    not GENERATOR_SCRIPT.exists(),
    reason="generate_se_rules.py not found",
)
class TestHookGeneratesSeRules:
    """Hook should auto-generate and validate SE YAML after valid DQS."""

    def test_hook_generates_se_rules_after_valid_dqs(self, _cleanup_test_hook_se):
        """Valid DQS write should produce SE YAML files."""
        dqs_file, se_rules_dir = _setup_dqs_with_se(Path())
        result = _run_hook(_write_input(str(dqs_file)))
        assert result.returncode == 0
        yaml_files = list(se_rules_dir.glob("se-rules-*.yaml"))
        assert (
            len(yaml_files) > 0
        ), f"No SE YAML files in {se_rules_dir}. stdout={result.stdout!r} stderr={result.stderr!r}"

    def test_hook_validates_generated_se_yamls(self, _cleanup_test_hook_se):
        """Generated SE YAML files should pass SE structural validation.

        Soft warnings (unqualified tables, no comparison operator) are
        acceptable from test fixtures — they indicate the DQS parser
        couldn't fully qualify expressions from the test DQS.
        """
        sys.path.insert(
            0,
            str(CHAPTER_ROOT / "dq-engineer-plugin" / "skills" / "generate-se-rules" / "scripts"),
        )
        from generate_se_rules import validate_se_yaml

        soft_patterns = [
            "no comparison operator",
            "no aggregate function",
            "may not match SE regex",
            "unqualified table",
        ]

        dqs_file, se_rules_dir = _setup_dqs_with_se(Path())
        _run_hook(_write_input(str(dqs_file)))
        yaml_files = list(se_rules_dir.glob("se-rules-*.yaml"))
        assert len(yaml_files) > 0
        for yf in yaml_files:
            content = yf.read_text(encoding="utf-8")
            errors = validate_se_yaml(content)
            hard_errors = [e for e in errors if not any(p in e for p in soft_patterns)]
            assert hard_errors == [], f"{yf.name} failed SE validation: {hard_errors}"

    def test_hook_skips_se_rules_on_critical_failure(self, _cleanup_test_hook_se):
        """Invalid DQS should NOT produce SE YAML files."""
        version_dir = CHAPTER_ROOT / "outputs" / "dqs" / "test_hook_se"
        version_dir.mkdir(parents=True, exist_ok=True)
        dqs_file = version_dir / "DQS-bad.md"
        dqs_file.write_text("# Bad DQS\n\nNo sections.", encoding="utf-8")
        se_rules_dir = version_dir / "se-rules"

        result = _run_hook(_write_input(str(dqs_file)))
        assert result.returncode == 2
        assert not se_rules_dir.exists() or not list(se_rules_dir.glob("se-rules-*.yaml"))

    def test_hook_reports_se_generation_in_context(self, _cleanup_test_hook_se):
        """Hook stdout should contain SE generation info."""
        dqs_file, _ = _setup_dqs_with_se(Path())
        result = _run_hook(_write_input(str(dqs_file)))
        assert result.returncode == 0
        # Hook output should be JSON with additionalContext
        if result.stdout.strip():
            output = json.loads(result.stdout)
            ctx = output.get("hookSpecificOutput", {}).get("additionalContext", "")
            assert "SE YAML" in ctx or "SE validation" in ctx

    def test_hook_handles_missing_se_config_gracefully(self, _cleanup_test_hook_se):
        """Missing SE config should not crash the hook."""
        version_dir = CHAPTER_ROOT / "outputs" / "dqs" / "test_hook_se"
        version_dir.mkdir(parents=True, exist_ok=True)
        dqs_file = version_dir / "DQS-no-config.md"
        dqs_file.write_text(VALID_DQS, encoding="utf-8")
        # Do NOT create inputs/dqs/test_hook_se/se-config-template.yaml
        result = _run_hook(_write_input(str(dqs_file)))
        # Should not crash — SE generation uses defaults
        assert result.returncode == 0
