"""Smoke test: ``/developer-plugin:validate-ingestion`` runs cleanly.

Shells out to the validator script and asserts a green result for the
project tree. Skipped when the validator script is not on disk (e.g. an
exported subset of the repo).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = PROJECT_ROOT.parent
VALIDATOR = (
    WORKSPACE_ROOT
    / "developer-plugin"
    / "skills"
    / "validate-ingestion"
    / "scripts"
    / "validate_ingestion.py"
)


@pytest.mark.skipif(
    not VALIDATOR.exists(), reason="validate-ingestion script not present in this checkout"
)
def test_validate_ingestion_passes():
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), "--project-root", str(PROJECT_ROOT)],
        capture_output=True,
        text=True,
    )
    out = result.stdout + "\n" + result.stderr
    assert "Result: PASS" in out, f"validate-ingestion did not pass.\nrc={result.returncode}\n{out}"
