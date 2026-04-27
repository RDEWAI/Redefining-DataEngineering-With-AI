"""Shared pytest fixtures for patient_360 tests."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure ``src/`` is importable when pytest is invoked from a parent
# working directory (e.g. the chapter-5 root by verify_acs.py).
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def project_name() -> str:
    return "patient_360"
