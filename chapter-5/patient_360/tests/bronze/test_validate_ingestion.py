"""Integration tests: validate-ingestion skill script against the current project.

Shells out to the validator to assert CRITICAL: 0 (STORY-02-010).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
VALIDATOR = (
    PROJECT_ROOT.parent
    / "developer-plugin/skills/ingestion/validate-ingestion/scripts/validate_ingestion.py"
)
LLD = next(
    iter(
        sorted(
            (PROJECT_ROOT.parent / "inputs/lld/v1").glob("LLD-*.md"),
            reverse=True,
        )
    ),
    None,
)


def test_validator_passes_on_current_project() -> None:
    if not VALIDATOR.exists():
        pytest.skip("validate_ingestion.py not found")
    result = subprocess.run(
        [sys.executable, str(VALIDATOR),
         "--project-root", str(PROJECT_ROOT),
         "--lld", str(LLD)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"Validator exited {result.returncode}:\n{result.stdout}\n{result.stderr}"
    )
    assert "Result: PASS" in result.stdout
    assert "CRITICAL: 0" in result.stdout


def test_validator_flags_missing_runtime_dep(tmp_path: Path) -> None:
    if not VALIDATOR.exists():
        pytest.skip("validate_ingestion.py not found")

    fake = tmp_path / "fake_project"
    (fake / "src/patient_360/bronze").mkdir(parents=True)
    (fake / "airflow/configs").mkdir(parents=True)
    (fake / "dq_rules").mkdir(parents=True)
    (fake / "tests/bronze").mkdir(parents=True)

    (fake / "pyproject.toml").write_text(
        '[project]\nname = "fake"\n[project.dependencies]\ndeps = ["pyyaml>=6.0"]\n'
    )

    result = subprocess.run(
        [sys.executable, str(VALIDATOR),
         "--project-root", str(fake),
         "--lld", str(LLD)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "pyspark" in result.stdout.lower() or "delta" in result.stdout.lower()
