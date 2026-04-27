"""Per-table empty-input override (LLD §5.1, Decision 11).

Critical Bronze tables must declare ``empty_input_behavior: fail``;
all others default to ``write_empty``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CRITICAL = {"patients", "encounters", "allergies", "organizations", "providers", "payers"}

CONFIGS_DIR = Path(__file__).resolve().parents[2] / "airflow" / "configs"


def _all_configs():
    return sorted(CONFIGS_DIR.glob("*.yml"))


def test_configs_dir_has_thirteen_files():
    assert (
        len(_all_configs()) == 13
    ), f"expected 13 configs in {CONFIGS_DIR}, got {len(_all_configs())}"


@pytest.mark.parametrize("path", _all_configs(), ids=lambda p: p.stem)
def test_critical_tables_use_fail_behavior(path):
    cfg = yaml.safe_load(path.read_text())
    expected = "fail" if path.stem in CRITICAL else "write_empty"
    assert (
        cfg["empty_input_behavior"] == expected
    ), f"{path.name}: expected empty_input_behavior={expected!r}"


def test_six_critical_tables_total():
    fail_count = sum(
        1 for p in _all_configs() if yaml.safe_load(p.read_text())["empty_input_behavior"] == "fail"
    )
    assert fail_count == 6
