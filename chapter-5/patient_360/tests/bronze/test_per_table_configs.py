"""Sweep checks over the 13 per-table ingestion configs in airflow/configs/.

These tests run without Spark — they validate the YAML contract shape,
critical-table policy, and cross-file references only.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIGS_DIR = REPO_ROOT / "airflow" / "configs"
CONTRACTS_DIR = REPO_ROOT / "contracts"
DQ_RULES_DIR = REPO_ROOT / "dq_rules"

EXPECTED_TABLES = {
    "patients", "encounters", "conditions", "medications", "observations",
    "allergies", "immunizations", "procedures", "claims", "careplans",
    "organizations", "providers", "payers",
}

CRITICAL_EMPTY_FAIL = {"patients", "encounters", "allergies", "organizations", "providers", "payers"}

REQUIRED_KEYS = ("table", "source", "schema_ref", "output_path",
                 "empty_input_behavior", "dq_rules_table")


def _iter_configs():
    return [p for p in sorted(CONFIGS_DIR.glob("*.yml")) if p.stem != "table_name"]


@pytest.mark.parametrize("config_path", _iter_configs(), ids=lambda p: p.stem)
def test_config_has_required_keys(config_path: Path) -> None:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{config_path} top-level must be a mapping"
    missing = [k for k in REQUIRED_KEYS if k not in data]
    assert not missing, f"{config_path} missing keys: {missing}"


@pytest.mark.parametrize("config_path", _iter_configs(), ids=lambda p: p.stem)
def test_table_key_matches_filename(config_path: Path) -> None:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert data["table"].lower() == config_path.stem.lower()


@pytest.mark.parametrize("config_path", _iter_configs(), ids=lambda p: p.stem)
def test_referenced_contract_exists(config_path: Path) -> None:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    contract = REPO_ROOT / data["schema_ref"]
    assert contract.exists(), f"{config_path}: contract {contract} missing"


@pytest.mark.parametrize("config_path", _iter_configs(), ids=lambda p: p.stem)
def test_referenced_dq_rules_exists(config_path: Path) -> None:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    dq_file = DQ_RULES_DIR / f"{data['dq_rules_table']}.yml"
    assert dq_file.exists(), f"{config_path}: {dq_file} missing"


@pytest.mark.parametrize("config_path", _iter_configs(), ids=lambda p: p.stem)
def test_critical_tables_use_fail_behavior(config_path: Path) -> None:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if data["table"] in CRITICAL_EMPTY_FAIL:
        assert data["empty_input_behavior"] == "fail", (
            f"{config_path}: critical table must have empty_input_behavior=fail"
        )


def test_thirteen_tables_present() -> None:
    actual = {p.stem for p in _iter_configs()}
    assert actual == EXPECTED_TABLES, f"drift vs LLD §5.1: {actual ^ EXPECTED_TABLES}"


@pytest.mark.parametrize("table", sorted(EXPECTED_TABLES))
def test_se_rules_have_three_envs(table: str) -> None:
    dq_file = DQ_RULES_DIR / f"{table}.yml"
    data = yaml.safe_load(dq_file.read_text(encoding="utf-8"))
    assert "dq_env" in data, f"{dq_file}: expected SE-format dq_env block"
    for env in ("DEV", "QA", "PROD"):
        assert env in data["dq_env"], f"{dq_file}: missing dq_env.{env}"
