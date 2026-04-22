"""Config compliance and factory tests for all 13 Bronze tables (STORY-02-009).

Pure YAML + factory parse tests — no Spark cluster required.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIGS_DIR = PROJECT_ROOT / "airflow" / "configs"
DQ_RULES_DIR = PROJECT_ROOT / "dq_rules"
CONTRACTS_DIR = PROJECT_ROOT / "contracts"

EXPECTED_TABLES = {
    "patients", "encounters", "conditions", "medications", "observations",
    "allergies", "immunizations", "procedures", "claims", "careplans",
    "organizations", "providers", "payers",
}

CRITICAL_EMPTY_FAIL = {"patients", "encounters", "allergies", "organizations", "providers", "payers"}

REQUIRED_KEYS = {
    "table", "source", "schema_ref", "output_path",
    "empty_input_behavior", "dq_rules_table", "se_action_if_failed",
    "quarantine_path",
}


def _all_configs() -> list[Path]:
    return sorted(CONFIGS_DIR.glob("*.yml"))


@pytest.mark.parametrize("config_path", _all_configs(), ids=lambda p: p.stem)
def test_config_has_required_keys(config_path: Path) -> None:
    data = yaml.safe_load(config_path.read_text())
    missing = REQUIRED_KEYS - set(data.keys())
    assert not missing, f"{config_path.name} missing keys: {missing}"


@pytest.mark.parametrize("config_path", _all_configs(), ids=lambda p: p.stem)
def test_table_key_matches_filename(config_path: Path) -> None:
    data = yaml.safe_load(config_path.read_text())
    assert data["table"] == config_path.stem


@pytest.mark.parametrize("config_path", _all_configs(), ids=lambda p: p.stem)
def test_source_table_is_fully_qualified(config_path: Path) -> None:
    data = yaml.safe_load(config_path.read_text())
    table = data["table"]
    assert data["source"]["table"] == f"synthea.{table}", (
        f"{config_path.name}: source.table must be 'synthea.{table}'"
    )


@pytest.mark.parametrize("config_path", _all_configs(), ids=lambda p: p.stem)
def test_metadata_columns_declared(config_path: Path) -> None:
    data = yaml.safe_load(config_path.read_text())
    cols = set(data.get("metadata_columns", []))
    assert {"ds", "_ingested_at", "_source_batch_id"}.issubset(cols), (
        f"{config_path.name}: missing metadata columns"
    )


@pytest.mark.parametrize("config_path", _all_configs(), ids=lambda p: p.stem)
def test_referenced_contract_exists(config_path: Path) -> None:
    data = yaml.safe_load(config_path.read_text())
    contract = PROJECT_ROOT / data["schema_ref"]
    assert contract.exists(), f"Contract missing: {data['schema_ref']}"


@pytest.mark.parametrize("config_path", _all_configs(), ids=lambda p: p.stem)
def test_referenced_dq_rules_exists(config_path: Path) -> None:
    data = yaml.safe_load(config_path.read_text())
    rules = DQ_RULES_DIR / f"{data['dq_rules_table']}.yml"
    assert rules.exists(), f"DQ rules missing: dq_rules/{data['dq_rules_table']}.yml"


@pytest.mark.parametrize("config_path", _all_configs(), ids=lambda p: p.stem)
def test_dq_rules_has_at_least_one_rule(config_path: Path) -> None:
    data = yaml.safe_load(config_path.read_text())
    rules_path = DQ_RULES_DIR / f"{data['dq_rules_table']}.yml"
    if not rules_path.exists():
        pytest.skip("dq_rules file missing — covered by test_referenced_dq_rules_exists")
    rules_data = yaml.safe_load(rules_path.read_text())
    assert rules_data.get("rules"), f"{rules_path.name}: no rules defined"


@pytest.mark.parametrize("config_path", _all_configs(), ids=lambda p: p.stem)
def test_critical_tables_use_fail_behavior(config_path: Path) -> None:
    data = yaml.safe_load(config_path.read_text())
    table = data["table"]
    if table in CRITICAL_EMPTY_FAIL:
        assert data["empty_input_behavior"] == "fail", (
            f"{table}: critical table must have empty_input_behavior=fail"
        )
        assert data["se_action_if_failed"] == "fail", (
            f"{table}: critical table must have se_action_if_failed=fail"
        )
    else:
        assert data["empty_input_behavior"] == "write_empty"
        assert data["se_action_if_failed"] == "drop"


@pytest.mark.parametrize("config_path", _all_configs(), ids=lambda p: p.stem)
def test_output_path_is_table_root_no_ds_suffix(config_path: Path) -> None:
    data = yaml.safe_load(config_path.read_text())
    assert "ds=" not in data["output_path"], (
        f"{config_path.name}: output_path must be Delta table root, not include ds= partition"
    )


@pytest.mark.parametrize("config_path", _all_configs(), ids=lambda p: p.stem)
def test_quarantine_path_pattern(config_path: Path) -> None:
    data = yaml.safe_load(config_path.read_text())
    qp = data["quarantine_path"]
    assert "{env}" in qp and data["table"] in qp, (
        f"{config_path.name}: quarantine_path must contain {{env}} and table name"
    )


def test_thirteen_tables_present() -> None:
    found = {p.stem for p in _all_configs()}
    assert found == EXPECTED_TABLES, (
        f"Table mismatch. Extra: {found - EXPECTED_TABLES}, Missing: {EXPECTED_TABLES - found}"
    )


@pytest.mark.parametrize("config_path", _all_configs(), ids=lambda p: p.stem)
def test_se_rules_have_three_envs(config_path: Path) -> None:
    data = yaml.safe_load(config_path.read_text())
    rules_path = DQ_RULES_DIR / f"{data['dq_rules_table']}.yml"
    if not rules_path.exists():
        pytest.skip("dq_rules file missing")
    rules_data = yaml.safe_load(rules_path.read_text())
    dq_env = rules_data.get("dq_env", {})
    assert {"DEV", "QA", "PROD"}.issubset(set(dq_env.keys())), (
        f"{rules_path.name}: dq_env must declare DEV, QA, PROD profiles"
    )
