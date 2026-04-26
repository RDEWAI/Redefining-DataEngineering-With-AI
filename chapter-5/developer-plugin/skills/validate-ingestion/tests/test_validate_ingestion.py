"""Regression tests for validate_ingestion.py."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "validate_ingestion.py"

spec = importlib.util.spec_from_file_location("validate_ingestion", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules["validate_ingestion"] = module
spec.loader.exec_module(module)


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_check_contract_config_real_shape(tmp_path):
    """Real contracts have top-level ``schema: <string>`` + sibling ``columns: [...]``."""
    project_root = tmp_path
    (project_root / "ddl" / "liquibase" / "changelogs").mkdir(parents=True)
    (project_root / "dq_rules").mkdir()
    (project_root / "ddl" / "liquibase" / "changelogs" / "patients.xml").write_text("<x/>")
    (project_root / "dq_rules" / "patients.yml").write_text("rules: []")

    contract_path = project_root / "contracts" / "patients.yml"
    _write_yaml(contract_path, {
        "table": "patients",
        "layer": "bronze",
        "schema": "synthea",
        "ddl_path": "ddl/liquibase/changelogs/patients.xml",
        "dq_path": "dq_rules/patients.yml",
        "columns": [
            {"name": "id", "type": "VARCHAR"},
            {"name": "ds", "type": "DATE"},
        ],
    })

    findings = module.Findings()
    module.check_contract_config(contract_path, project_root, findings)

    assert findings.critical == []
    assert any("ds" in w for w in findings.warning)


def test_check_contract_config_legacy_nested_shape(tmp_path):
    """Older contracts may nest ``schema.columns`` — still handled."""
    project_root = tmp_path
    (project_root / "ddl" / "liquibase" / "changelogs").mkdir(parents=True)
    (project_root / "dq_rules").mkdir()
    (project_root / "ddl" / "liquibase" / "changelogs" / "x.xml").write_text("<x/>")
    (project_root / "dq_rules" / "x.yml").write_text("rules: []")

    contract_path = project_root / "contracts" / "x.yml"
    _write_yaml(contract_path, {
        "table": "x",
        "ddl_path": "ddl/liquibase/changelogs/x.xml",
        "dq_path": "dq_rules/x.yml",
        "schema": {"columns": [{"name": "_ingested_at"}]},
    })

    findings = module.Findings()
    module.check_contract_config(contract_path, project_root, findings)

    assert findings.critical == []
    assert any("_ingested_at" in w for w in findings.warning)


def test_derive_fail_on_empty_skips_underscore_and_template(tmp_path):
    configs = tmp_path / "airflow" / "configs"
    configs.mkdir(parents=True)
    _write_yaml(
        configs / "patients.yml",
        {"table": "patients", "empty_input_behavior": "fail"},
    )
    _write_yaml(
        configs / "_template.yml",
        {"table": "_template", "empty_input_behavior": "fail"},
    )
    _write_yaml(
        configs / "table_name.yml",
        {"table": "table_name", "empty_input_behavior": "fail"},
    )

    assert module.derive_fail_on_empty_tables(configs) == {"patients"}
