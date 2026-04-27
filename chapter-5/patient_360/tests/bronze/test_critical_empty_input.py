"""Verify the 6 LLD §5.1 critical tables use ``empty_input_behavior: fail``."""

from __future__ import annotations

from pathlib import Path

import yaml

CONFIGS_DIR = Path(__file__).resolve().parents[2] / "airflow" / "configs"

CRITICAL = {"patients", "encounters", "allergies", "organizations", "providers", "payers"}


def test_six_critical_tables_use_fail():
    failing = {
        p.stem
        for p in sorted(CONFIGS_DIR.glob("*.yml"))
        if yaml.safe_load(p.read_text())["empty_input_behavior"] == "fail"
    }
    assert failing == CRITICAL, (
        f"critical-table set diverged from LLD §5.1.\n"
        f"  expected: {sorted(CRITICAL)}\n  got:      {sorted(failing)}"
    )
