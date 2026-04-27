"""Per-table Bronze ingestion config schema test (STORY-02-003).

Asserts the 13 YAML configs in ``airflow/configs/*.yml`` are well-formed:
required keys present, table-name matches filename stem, the referenced
contract + DQ-rules files exist, target follows ``unity.bronze.synthea_*``
per Decision 15, and tables flagged ``fail`` in LLD §5.1 use the right
behaviour.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIGS_DIR = PROJECT_ROOT / "airflow" / "configs"
CONTRACTS_DIR = PROJECT_ROOT / "contracts"
DQ_RULES_DIR = PROJECT_ROOT / "dq_rules"

REQUIRED_KEYS = [
    "table",
    "target",
    "source",
    "schema_ref",
    "empty_input_behavior",
    "dq_rules_table",
    "se_action_if_failed",
    "metadata_columns",
    "quarantine_path",
    "timeout_minutes",
    "retries",
    "retry_delay_seconds",
]

VALID_EMPTY_INPUT = {"fail", "write_empty"}
VALID_SE_ACTIONS = {"fail", "drop", "ignore"}

CRITICAL_TABLES = {"patients", "encounters", "allergies", "organizations", "providers", "payers"}


def _configs():
    return sorted(CONFIGS_DIR.glob("*.yml"))


def test_thirteen_configs_present():
    assert len(_configs()) == 13


@pytest.mark.parametrize("path", _configs(), ids=lambda p: p.stem)
def test_required_keys(path):
    cfg = yaml.safe_load(path.read_text())
    missing = [k for k in REQUIRED_KEYS if k not in cfg]
    assert not missing, f"{path.name} missing keys: {missing}"


@pytest.mark.parametrize("path", _configs(), ids=lambda p: p.stem)
def test_table_matches_filename(path):
    cfg = yaml.safe_load(path.read_text())
    # Filename stem == bare table name; UC target carries the synthea_ prefix.
    assert cfg["table"] == path.stem
    assert cfg["target"] == f"unity.bronze.synthea_{path.stem}"


@pytest.mark.parametrize("path", _configs(), ids=lambda p: p.stem)
def test_target_uc_format(path):
    cfg = yaml.safe_load(path.read_text())
    assert cfg["target"].startswith(
        "unity.bronze.synthea_"
    ), f"{path.name} target must start with unity.bronze.synthea_"


@pytest.mark.parametrize("path", _configs(), ids=lambda p: p.stem)
def test_contract_referenced_exists(path):
    cfg = yaml.safe_load(path.read_text())
    contract = PROJECT_ROOT / cfg["schema_ref"]
    assert contract.exists(), f"contract missing: {contract}"


@pytest.mark.parametrize("path", _configs(), ids=lambda p: p.stem)
def test_dq_rules_referenced_exists(path):
    cfg = yaml.safe_load(path.read_text())
    rules = DQ_RULES_DIR / f"{cfg['dq_rules_table']}.yml"
    assert rules.exists(), f"dq_rules missing: {rules}"


@pytest.mark.parametrize("path", _configs(), ids=lambda p: p.stem)
def test_critical_table_empty_input_fail(path):
    cfg = yaml.safe_load(path.read_text())
    expected = "fail" if path.stem in CRITICAL_TABLES else "write_empty"
    assert cfg["empty_input_behavior"] == expected


@pytest.mark.parametrize("path", _configs(), ids=lambda p: p.stem)
def test_se_action_valid(path):
    cfg = yaml.safe_load(path.read_text())
    assert cfg["se_action_if_failed"] in VALID_SE_ACTIONS


@pytest.mark.parametrize("path", _configs(), ids=lambda p: p.stem)
def test_dq_env_present_in_se_rules(path):
    """The DQ rule file referenced must declare every dq_env value
    (DEV / QA / PROD) used at runtime."""
    cfg = yaml.safe_load(path.read_text())
    rules_path = DQ_RULES_DIR / f"{cfg['dq_rules_table']}.yml"
    rules = yaml.safe_load(rules_path.read_text())
    if rules.get("dq_env"):
        envs = set(rules["dq_env"].keys())
        assert envs >= {
            "DEV",
            "QA",
            "PROD",
        }, f"{rules_path.name} dq_env missing one of DEV/QA/PROD: {envs}"
