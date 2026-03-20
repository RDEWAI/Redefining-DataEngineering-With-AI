"""Tests for generate_se_rules.py — DQS to Spark-Expectations YAML converter."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

# Make the script importable
sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parent.parent
        / "dq-engineer-plugin"
        / "skills"
        / "generate-se-rules"
        / "scripts"
    ),
)

from conftest import VALID_DQS
from generate_se_rules import (
    DqsRule,
    _normalize_table_name,
    _validate_agg_dq_expression,
    _validate_query_dq_expression,
    _validate_row_dq_expression,
    generate_se_yaml_for_table,
    group_rules_by_table,
    load_se_config,
    parse_dqs,
    table_name_to_filename,
    validate_se_yaml,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_dqs_path(tmp_path: Path) -> Path:
    """Write VALID_DQS to a temp file and return the path."""
    f = tmp_path / "DQS-2026-03-17-patient-360.md"
    f.write_text(VALID_DQS, encoding="utf-8")
    return f


@pytest.fixture
def minimal_dqs_path(tmp_path: Path) -> Path:
    """Write a minimal DQS with just enough to parse."""
    content = """\
# Data Quality Specification: Minimal

| Field | Value |
|-------|-------|
| **Version** | 1.0 |

## 2. Field-Level Validation Rules

### Bronze Layer

| Rule ID | Table | Column | Check Type | Expression | Severity | Action |
|---------|-------|--------|------------|------------|----------|--------|
| DQ-FLD-001 | bronze.patients | id | NOT NULL | id IS NOT NULL | CRITICAL | Reject |
| DQ-FLD-002 | bronze.encounters | id | NOT NULL | id IS NOT NULL | CRITICAL | Reject |
"""
    f = tmp_path / "DQS-minimal.md"
    f.write_text(content, encoding="utf-8")
    return f


@pytest.fixture
def se_config_path(tmp_path: Path) -> Path:
    """Write a minimal SE config template."""
    config = {
        "product_id": "test-product",
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
            "QA": {
                "table_name": "qa_{schema}.{table}",
                "action_if_failed": "ignore",
                "enable_for_source_dq_validation": True,
                "enable_for_target_dq_validation": True,
                "is_active": True,
                "enable_error_drop_alert": True,
                "error_drop_threshold": 5,
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
    }
    f = tmp_path / "se-config.yaml"
    f.write_text(yaml.dump(config), encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# DqsRule unit tests
# ---------------------------------------------------------------------------


class TestDqsRuleRuleType:
    """DqsRule.rule_type maps correctly based on rule ID prefix."""

    def test_fld_maps_to_row_dq(self):
        rule = DqsRule(
            rule_id="DQ-FLD-001",
            table="bronze.patients",
            column="id",
            check_type="NOT NULL",
            expression="id IS NOT NULL",
            severity="CRITICAL",
            action="Reject",
        )
        assert rule.rule_type == "row_dq"

    def test_sta_maps_to_agg_dq(self):
        rule = DqsRule(
            rule_id="DQ-STA-001",
            table="bronze.patients",
            column="",
            check_type="STATISTICAL",
            expression="COUNT(*) > 0",
            severity="WARNING",
            action="",
        )
        assert rule.rule_type == "agg_dq"

    def test_ref_maps_to_query_dq(self):
        rule = DqsRule(
            rule_id="DQ-REF-001",
            table="clinical.encounters",
            column="",
            check_type="REFERENTIAL_INTEGRITY",
            expression="SELECT COUNT(*) FROM ...",
            severity="CRITICAL",
            action="Reject",
        )
        assert rule.rule_type == "query_dq"

    def test_rec_maps_to_query_dq(self):
        rule = DqsRule(
            rule_id="DQ-REC-001",
            table="analytics.dim_patient",
            column="",
            check_type="RECONCILIATION",
            expression="SELECT ABS(...)",
            severity="CRITICAL",
            action="",
        )
        assert rule.rule_type == "query_dq"

    def test_frs_maps_to_agg_dq(self):
        rule = DqsRule(
            rule_id="DQ-FRS-001",
            table="analytics.dim_patient",
            column="",
            check_type="FRESHNESS",
            expression="MAX(_updated_at) > ...",
            severity="WARNING",
            action="",
        )
        assert rule.rule_type == "agg_dq"


class TestDqsRuleActionIfFailed:
    """DqsRule.action_if_failed maps severity to SE action."""

    def test_critical_maps_to_fail(self):
        rule = DqsRule(
            rule_id="DQ-FLD-001",
            table="t",
            column="c",
            check_type="NOT NULL",
            expression="c IS NOT NULL",
            severity="CRITICAL",
            action="Reject",
        )
        assert rule.action_if_failed == "fail"

    def test_warning_maps_to_ignore(self):
        rule = DqsRule(
            rule_id="DQ-FLD-002",
            table="t",
            column="c",
            check_type="RANGE",
            expression="c > 0",
            severity="WARNING",
            action="Log",
        )
        assert rule.action_if_failed == "ignore"

    def test_info_maps_to_ignore(self):
        rule = DqsRule(
            rule_id="DQ-FLD-003",
            table="t",
            column="c",
            check_type="FORMAT",
            expression="c ~ '^[A-Z]'",
            severity="INFO",
            action="",
        )
        assert rule.action_if_failed == "ignore"


class TestDqsRuleTag:
    """DqsRule.tag maps rule ID prefix to category tag."""

    def test_fld_tag(self):
        rule = DqsRule(
            rule_id="DQ-FLD-001",
            table="t",
            column="c",
            check_type="X",
            expression="x",
            severity="CRITICAL",
            action="",
        )
        assert rule.tag == "field_validation"

    def test_ref_tag(self):
        rule = DqsRule(
            rule_id="DQ-REF-001",
            table="t",
            column="",
            check_type="X",
            expression="x",
            severity="CRITICAL",
            action="",
        )
        assert rule.tag == "referential_integrity"

    def test_sta_tag(self):
        rule = DqsRule(
            rule_id="DQ-STA-001",
            table="t",
            column="",
            check_type="X",
            expression="x",
            severity="WARNING",
            action="",
        )
        assert rule.tag == "statistical_distribution"

    def test_rec_tag(self):
        rule = DqsRule(
            rule_id="DQ-REC-001",
            table="t",
            column="",
            check_type="X",
            expression="x",
            severity="CRITICAL",
            action="",
        )
        assert rule.tag == "reconciliation"


class TestDqsRuleErrorDropThreshold:
    """DqsRule.error_drop_threshold extracts from expression or uses default."""

    def test_percentage_in_expression(self):
        rule = DqsRule(
            rule_id="DQ-STA-001",
            table="t",
            column="",
            check_type="STATISTICAL",
            expression="COUNT(*) within ±20% of 50000",
            severity="WARNING",
            action="",
        )
        assert rule.error_drop_threshold() == 20
        assert isinstance(rule.error_drop_threshold(), int)

    def test_default_when_no_percentage(self):
        rule = DqsRule(
            rule_id="DQ-FLD-001",
            table="t",
            column="c",
            check_type="NOT NULL",
            expression="c IS NOT NULL",
            severity="CRITICAL",
            action="",
        )
        assert rule.error_drop_threshold() == 0
        assert isinstance(rule.error_drop_threshold(), int)

    def test_custom_default(self):
        rule = DqsRule(
            rule_id="DQ-FLD-001",
            table="t",
            column="c",
            check_type="NOT NULL",
            expression="c IS NOT NULL",
            severity="CRITICAL",
            action="",
        )
        assert rule.error_drop_threshold(5) == 5


# ---------------------------------------------------------------------------
# parse_dqs tests
# ---------------------------------------------------------------------------


class TestParseDqs:
    """parse_dqs extracts rules from DQS markdown."""

    def test_parses_valid_dqs(self, valid_dqs_path: Path):
        rules = parse_dqs(valid_dqs_path)
        assert len(rules) > 0

    def test_finds_field_level_rules(self, valid_dqs_path: Path):
        rules = parse_dqs(valid_dqs_path)
        fld_rules = [r for r in rules if r.rule_id.startswith("DQ-FLD")]
        assert len(fld_rules) > 0

    def test_finds_referential_integrity_rules(self, valid_dqs_path: Path):
        rules = parse_dqs(valid_dqs_path)
        ref_rules = [r for r in rules if r.rule_id.startswith("DQ-REF")]
        assert len(ref_rules) > 0

    def test_finds_statistical_rules(self, valid_dqs_path: Path):
        rules = parse_dqs(valid_dqs_path)
        sta_rules = [r for r in rules if r.rule_id.startswith("DQ-STA")]
        assert len(sta_rules) > 0

    def test_finds_reconciliation_rules(self, valid_dqs_path: Path):
        rules = parse_dqs(valid_dqs_path)
        rec_rules = [r for r in rules if r.rule_id.startswith("DQ-REC")]
        assert len(rec_rules) > 0

    def test_rules_have_table_names(self, valid_dqs_path: Path):
        rules = parse_dqs(valid_dqs_path)
        for rule in rules:
            assert rule.table, f"Rule {rule.rule_id} has no table name"

    def test_rules_have_expressions(self, valid_dqs_path: Path):
        rules = parse_dqs(valid_dqs_path)
        for rule in rules:
            assert rule.expression, f"Rule {rule.rule_id} has no expression"

    def test_parses_minimal_dqs(self, minimal_dqs_path: Path):
        rules = parse_dqs(minimal_dqs_path)
        assert len(rules) == 2
        assert all(r.rule_id.startswith("DQ-FLD") for r in rules)

    def test_layer_assigned_to_field_rules(self, valid_dqs_path: Path):
        rules = parse_dqs(valid_dqs_path)
        fld_rules = [r for r in rules if r.rule_id.startswith("DQ-FLD")]
        layers = {r.layer for r in fld_rules if r.layer}
        assert "bronze" in layers or "silver" in layers or "gold" in layers


# ---------------------------------------------------------------------------
# group_rules_by_table tests
# ---------------------------------------------------------------------------


class TestGroupRulesByTable:
    """group_rules_by_table groups rules under their table key."""

    def test_groups_correctly(self):
        rules = [
            DqsRule("DQ-FLD-001", "dim_patient", "c", "NOT NULL", "x IS NOT NULL", "CRITICAL", ""),
            DqsRule("DQ-FLD-002", "dim_patient", "d", "NOT NULL", "d IS NOT NULL", "WARNING", ""),
            DqsRule(
                "DQ-FLD-003",
                "fact_encounter",
                "e",
                "NOT NULL",
                "e IS NOT NULL",
                "CRITICAL",
                "",
            ),
        ]
        grouped = group_rules_by_table(rules)
        assert "analytics.dim_patient" in grouped
        assert "analytics.fact_encounter" in grouped
        assert len(grouped["analytics.dim_patient"]) == 2
        assert len(grouped["analytics.fact_encounter"]) == 1

    def test_valid_dqs_groups_multiple_tables(self, valid_dqs_path: Path):
        rules = parse_dqs(valid_dqs_path)
        grouped = group_rules_by_table(rules)
        assert len(grouped) > 1

    def test_empty_rules_returns_empty(self):
        grouped = group_rules_by_table([])
        assert grouped == {}


# ---------------------------------------------------------------------------
# load_se_config tests
# ---------------------------------------------------------------------------


class TestLoadSeConfig:
    """load_se_config loads config from file or returns defaults."""

    def test_loads_from_file(self, se_config_path: Path):
        config = load_se_config(se_config_path)
        assert config["product_id"] == "test-product"
        assert "dq_env" in config

    def test_returns_defaults_for_none(self):
        config = load_se_config(None)
        assert "product_id" in config
        assert "dq_env" in config

    def test_defaults_have_three_environments(self):
        config = load_se_config(None)
        dq_env = config["dq_env"]
        assert "DEV" in dq_env
        assert "QA" in dq_env
        assert "PROD" in dq_env

    def test_returns_defaults_for_missing_file(self, tmp_path: Path):
        config = load_se_config(tmp_path / "nonexistent.yaml")
        assert "product_id" in config


# ---------------------------------------------------------------------------
# generate_se_yaml_for_table tests
# ---------------------------------------------------------------------------


class TestGenerateSeYamlForTable:
    """generate_se_yaml_for_table produces valid SE YAML."""

    def _make_rules(self) -> list[DqsRule]:
        return [
            DqsRule(
                rule_id="DQ-FLD-001",
                table="bronze.patients",
                column="id",
                check_type="NOT NULL",
                expression="id IS NOT NULL",
                severity="CRITICAL",
                action="Reject",
                description="Patient ID must not be null",
            ),
            DqsRule(
                rule_id="DQ-STA-001",
                table="bronze.patients",
                column="",
                check_type="STATISTICAL",
                expression="COUNT(*) BETWEEN 800 AND 1200",
                severity="WARNING",
                action="",
                description="Row count within baseline ±20%",
            ),
        ]

    def test_returns_valid_yaml(self):
        rules = self._make_rules()
        config = load_se_config(None)
        yaml_content = generate_se_yaml_for_table("bronze.patients", rules, config, "test-dqs.md")
        parsed = yaml.safe_load(yaml_content)
        assert parsed is not None

    def test_yaml_has_product_id(self):
        config = {"product_id": "my-pipeline", "dq_env": {}}
        yaml_content = generate_se_yaml_for_table(
            "bronze.patients", self._make_rules(), config, "test.md"
        )
        parsed = yaml.safe_load(yaml_content)
        assert parsed["product_id"] == "my-pipeline"

    def test_yaml_has_dq_env(self):
        config = load_se_config(None)
        yaml_content = generate_se_yaml_for_table(
            "bronze.patients", self._make_rules(), config, "test.md"
        )
        parsed = yaml.safe_load(yaml_content)
        assert "dq_env" in parsed

    def test_yaml_has_rules_list(self):
        config = load_se_config(None)
        yaml_content = generate_se_yaml_for_table(
            "bronze.patients", self._make_rules(), config, "test.md"
        )
        parsed = yaml.safe_load(yaml_content)
        assert "rules" in parsed
        assert len(parsed["rules"]) == 2

    def test_rule_has_17_required_columns(self):
        config = load_se_config(None)
        yaml_content = generate_se_yaml_for_table(
            "bronze.patients", self._make_rules(), config, "test.md"
        )
        parsed = yaml.safe_load(yaml_content)
        rule = parsed["rules"][0]
        required_columns = [
            "rule",
            "rule_type",
            "column_name",
            "expectation",
            "action_if_failed",
            "tag",
            "description",
            "enable_for_source_dq_validation",
            "enable_for_target_dq_validation",
            "is_active",
            "enable_error_drop_alert",
            "error_drop_threshold",
            "query_dq_delimiter",
            "enable_querydq_custom_output",
            "priority",
        ]
        for col in required_columns:
            assert col in rule, f"Missing required SE column: {col}"

    def test_critical_rule_action_is_fail(self):
        config = load_se_config(None)
        rules = [
            DqsRule(
                rule_id="DQ-FLD-001",
                table="t",
                column="c",
                check_type="NOT NULL",
                expression="c IS NOT NULL",
                severity="CRITICAL",
                action="Reject",
            )
        ]
        yaml_content = generate_se_yaml_for_table("t", rules, config, "x.md")
        parsed = yaml.safe_load(yaml_content)
        assert parsed["rules"][0]["action_if_failed"] == "fail"

    def test_warning_rule_action_is_ignore(self):
        config = load_se_config(None)
        rules = [
            DqsRule(
                rule_id="DQ-FLD-002",
                table="t",
                column="c",
                check_type="RANGE",
                expression="c > 0",
                severity="WARNING",
                action="Log",
            )
        ]
        yaml_content = generate_se_yaml_for_table("t", rules, config, "x.md")
        parsed = yaml.safe_load(yaml_content)
        assert parsed["rules"][0]["action_if_failed"] == "ignore"

    def test_row_dq_has_column_name(self):
        config = load_se_config(None)
        rules = [
            DqsRule(
                rule_id="DQ-FLD-001",
                table="t",
                column="patient_id",
                check_type="NOT NULL",
                expression="patient_id IS NOT NULL",
                severity="CRITICAL",
                action="Reject",
            )
        ]
        yaml_content = generate_se_yaml_for_table("t", rules, config, "x.md")
        parsed = yaml.safe_load(yaml_content)
        assert parsed["rules"][0]["column_name"] == "patient_id"

    def test_agg_dq_has_empty_column_name(self):
        config = load_se_config(None)
        rules = [
            DqsRule(
                rule_id="DQ-STA-001",
                table="t",
                column="",
                check_type="STATISTICAL",
                expression="COUNT(*) > 0",
                severity="WARNING",
                action="",
            )
        ]
        yaml_content = generate_se_yaml_for_table("t", rules, config, "x.md")
        parsed = yaml.safe_load(yaml_content)
        assert parsed["rules"][0]["rule_type"] == "agg_dq"
        assert parsed["rules"][0]["column_name"] == ""

    def test_query_dq_enables_custom_output(self):
        config = load_se_config(None)
        rules = [
            DqsRule(
                rule_id="DQ-REC-001",
                table="t",
                column="",
                check_type="RECONCILIATION",
                expression="SELECT ABS(s.cnt - t.cnt)",
                severity="CRITICAL",
                action="",
            )
        ]
        yaml_content = generate_se_yaml_for_table("t", rules, config, "x.md")
        parsed = yaml.safe_load(yaml_content)
        assert parsed["rules"][0]["rule_type"] == "query_dq"
        assert parsed["rules"][0]["enable_querydq_custom_output"] is True


# ---------------------------------------------------------------------------
# _normalize_table_name tests
# ---------------------------------------------------------------------------


class TestNormalizeTableName:
    """_normalize_table_name strips parenthetical qualifiers from DQS cells."""

    def test_plain_table(self):
        assert _normalize_table_name("analytics.dim_patient") == "analytics.dim_patient"

    def test_strips_where_qualifier(self):
        assert (
            _normalize_table_name("analytics.dim_patient (WHERE is_current = TRUE)")
            == "analytics.dim_patient"
        )

    def test_strips_count_distinct_qualifier(self):
        assert (
            _normalize_table_name("clinical.patients (COUNT DISTINCT patient_id)")
            == "clinical.patients"
        )

    def test_strips_sum_qualifier(self):
        assert (
            _normalize_table_name("analytics.fact_encounter (SUM base_encounter_cost)")
            == "analytics.fact_encounter"
        )

    def test_strips_backticks(self):
        assert _normalize_table_name("`bronze.patients`") == "bronze.patients"

    def test_strips_whitespace(self):
        assert _normalize_table_name("  analytics.dim_patient  ") == "analytics.dim_patient"

    def test_combined_backtick_and_qualifier(self):
        assert (
            _normalize_table_name("`analytics.dim_patient` (is_current)") == "analytics.dim_patient"
        )


# ---------------------------------------------------------------------------
# table_name_to_filename tests
# ---------------------------------------------------------------------------


class TestTableNameToFilename:
    """table_name_to_filename converts table names to YAML filenames."""

    def test_strips_schema_prefix(self):
        assert table_name_to_filename("analytics.dim_patient") == "se-rules-dim-patient.yaml"

    def test_replaces_underscores_with_hyphens(self):
        assert table_name_to_filename("analytics.fact_encounter") == "se-rules-fact-encounter.yaml"

    def test_no_schema_prefix(self):
        assert table_name_to_filename("patients") == "se-rules-patients.yaml"

    def test_bronze_table(self):
        assert table_name_to_filename("raw.patients") == "se-rules-patients.yaml"


# ---------------------------------------------------------------------------
# End-to-end integration tests
# ---------------------------------------------------------------------------


class TestGenerateSeRulesIntegration:
    """End-to-end tests: parse DQS → group → generate YAML."""

    def test_valid_dqs_produces_multiple_yaml_files(self, valid_dqs_path: Path, tmp_path: Path):
        """Parsing VALID_DQS should yield rules for multiple tables."""
        rules = parse_dqs(valid_dqs_path)
        grouped = group_rules_by_table(rules)
        assert len(grouped) >= 2

    def test_all_generated_yamls_are_valid(self, valid_dqs_path: Path, tmp_path: Path):
        """All generated YAML files must parse without error."""
        rules = parse_dqs(valid_dqs_path)
        grouped = group_rules_by_table(rules)
        config = load_se_config(None)

        for table_name, table_rules in grouped.items():
            yaml_content = generate_se_yaml_for_table(
                table_name, table_rules, config, valid_dqs_path.name
            )
            parsed = yaml.safe_load(yaml_content)
            assert parsed is not None, f"Invalid YAML for table {table_name}"
            assert "rules" in parsed, f"No rules for table {table_name}"
            assert len(parsed["rules"]) > 0

    def test_all_rules_have_required_se_columns(self, valid_dqs_path: Path):
        """Every generated rule entry must have all 15 SE per-rule fields."""
        required = {
            "rule",
            "rule_type",
            "column_name",
            "expectation",
            "action_if_failed",
            "tag",
            "description",
            "enable_for_source_dq_validation",
            "enable_for_target_dq_validation",
            "is_active",
            "enable_error_drop_alert",
            "error_drop_threshold",
            "query_dq_delimiter",
            "enable_querydq_custom_output",
            "priority",
        }
        rules = parse_dqs(valid_dqs_path)
        grouped = group_rules_by_table(rules)
        config = load_se_config(None)

        for table_name, table_rules in grouped.items():
            yaml_content = generate_se_yaml_for_table(
                table_name, table_rules, config, valid_dqs_path.name
            )
            parsed = yaml.safe_load(yaml_content)
            for rule_entry in parsed["rules"]:
                missing = required - set(rule_entry.keys())
                assert (
                    not missing
                ), f"Table {table_name}, rule {rule_entry.get('rule')}: missing columns {missing}"

    def test_cli_generates_files(self, valid_dqs_path: Path, tmp_path: Path):
        """CLI invocation writes YAML files to the output directory."""
        import subprocess

        script = (
            Path(__file__).resolve().parent.parent
            / "dq-engineer-plugin"
            / "skills"
            / "generate-se-rules"
            / "scripts"
            / "generate_se_rules.py"
        )
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                str(valid_dqs_path),
                "-o",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"CLI failed:\n{result.stderr}"
        yaml_files = list(tmp_path.glob("se-rules-*.yaml"))
        assert len(yaml_files) > 0, "No YAML files generated by CLI"

    def test_cli_dry_run_writes_nothing(self, valid_dqs_path: Path, tmp_path: Path):
        """CLI --dry-run prints to stdout without writing files."""
        import subprocess

        script = (
            Path(__file__).resolve().parent.parent
            / "dq-engineer-plugin"
            / "skills"
            / "generate-se-rules"
            / "scripts"
            / "generate_se_rules.py"
        )
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                str(valid_dqs_path),
                "--dry-run",
                "-o",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        yaml_files = list(tmp_path.glob("se-rules-*.yaml"))
        assert len(yaml_files) == 0, "Dry run should not write files"
        assert "---" in result.stdout or "product_id" in result.stdout

    def test_missing_dqs_file_exits_nonzero(self, tmp_path: Path):
        """CLI exits with non-zero when DQS file does not exist."""
        import subprocess

        script = (
            Path(__file__).resolve().parent.parent
            / "dq-engineer-plugin"
            / "skills"
            / "generate-se-rules"
            / "scripts"
            / "generate_se_rules.py"
        )
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                str(tmp_path / "nonexistent.md"),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0

    def test_no_non_se_fields_in_generated_rules(self, valid_dqs_path: Path):
        """Generated rules must not contain product_id, table_name, or expectation_source."""
        rules = parse_dqs(valid_dqs_path)
        grouped = group_rules_by_table(rules)
        config = load_se_config(None)
        forbidden = {"product_id", "table_name", "expectation_source", "enable_error_drop_analysis"}

        for tbl, tbl_rules in grouped.items():
            yaml_content = generate_se_yaml_for_table(tbl, tbl_rules, config, "x.md")
            parsed = yaml.safe_load(yaml_content)
            for rule_entry in parsed["rules"]:
                found = forbidden & set(rule_entry.keys())
                assert not found, f"Table {tbl}: rule has non-SE fields {found}"

    def test_dq_env_has_table_name_not_schema_prefix(self, valid_dqs_path: Path):
        """dq_env entries must use table_name, not schema_prefix."""
        rules = parse_dqs(valid_dqs_path)
        grouped = group_rules_by_table(rules)
        config = load_se_config(None)

        for tbl, tbl_rules in list(grouped.items())[:1]:
            yaml_content = generate_se_yaml_for_table(tbl, tbl_rules, config, "x.md")
            parsed = yaml.safe_load(yaml_content)
            for env, settings in parsed["dq_env"].items():
                assert "table_name" in settings, f"dq_env.{env} missing table_name"
                assert "schema_prefix" not in settings, f"dq_env.{env} has schema_prefix"

    def test_dq_env_uses_enable_error_drop_alert(self, valid_dqs_path: Path):
        """dq_env must use enable_error_drop_alert, not enable_error_drop_analysis."""
        rules = parse_dqs(valid_dqs_path)
        grouped = group_rules_by_table(rules)
        config = load_se_config(None)

        for tbl, tbl_rules in list(grouped.items())[:1]:
            yaml_content = generate_se_yaml_for_table(tbl, tbl_rules, config, "x.md")
            parsed = yaml.safe_load(yaml_content)
            for env, settings in parsed["dq_env"].items():
                assert "enable_error_drop_alert" in settings
                assert "enable_error_drop_analysis" not in settings


# ---------------------------------------------------------------------------
# SE Validation tests (validate_se_yaml port of SE's flatten_rules_list)
# ---------------------------------------------------------------------------


class TestValidateSeYaml:
    """Tests for validate_se_yaml — pure-Python port of SE validation."""

    def _valid_yaml(self) -> str:
        return yaml.dump(
            {
                "product_id": "test",
                "dq_env": {
                    "DEV": {
                        "table_name": "dev_raw.patients",
                        "action_if_failed": "ignore",
                        "enable_for_source_dq_validation": True,
                        "enable_for_target_dq_validation": True,
                        "is_active": True,
                        "enable_error_drop_alert": False,
                        "error_drop_threshold": 0,
                        "priority": "medium",
                    },
                },
                "rules": [
                    {
                        "rule": "DQ-FLD-001",
                        "rule_type": "row_dq",
                        "column_name": "id",
                        "expectation": "id IS NOT NULL",
                        "action_if_failed": "fail",
                        "tag": "completeness",
                        "description": "ID not null",
                        "priority": "high",
                    },
                ],
            }
        )

    def test_valid_yaml_passes(self):
        errors = validate_se_yaml(self._valid_yaml())
        assert errors == []

    def test_missing_product_id(self):
        rules = [{"rule": "r", "expectation": "x", "rule_type": "row_dq"}]
        content = yaml.dump({"dq_env": {}, "rules": rules})
        errors = validate_se_yaml(content)
        assert any("product_id" in e for e in errors)

    def test_missing_table_name_in_dq_env(self):
        content = yaml.dump(
            {
                "product_id": "test",
                "dq_env": {"DEV": {"action_if_failed": "ignore"}},
                "rules": [{"rule": "r", "rule_type": "row_dq", "expectation": "x"}],
            }
        )
        errors = validate_se_yaml(content)
        assert any("table_name" in e for e in errors)

    def test_empty_rules_list(self):
        content = yaml.dump({"product_id": "test", "rules": []})
        errors = validate_se_yaml(content)
        assert any("rules" in e for e in errors)

    def test_missing_required_rule_fields(self):
        content = yaml.dump(
            {
                "product_id": "test",
                "rules": [{"rule_type": "row_dq"}],
            }
        )
        errors = validate_se_yaml(content)
        assert any("missing required" in e for e in errors)

    def test_invalid_rule_type(self):
        content = yaml.dump(
            {
                "product_id": "test",
                "rules": [{"rule": "r", "expectation": "x", "rule_type": "bad_type"}],
            }
        )
        errors = validate_se_yaml(content)
        assert any("invalid rule_type" in e for e in errors)

    def test_drop_invalid_for_agg_dq(self):
        content = yaml.dump(
            {
                "product_id": "test",
                "rules": [
                    {
                        "rule": "r",
                        "expectation": "COUNT(*) > 0",
                        "rule_type": "agg_dq",
                        "action_if_failed": "drop",
                    }
                ],
            }
        )
        errors = validate_se_yaml(content)
        assert any("drop" in e and "agg_dq" in e for e in errors)

    def test_drop_invalid_for_query_dq(self):
        content = yaml.dump(
            {
                "product_id": "test",
                "rules": [
                    {
                        "rule": "r",
                        "expectation": "SELECT 1",
                        "rule_type": "query_dq",
                        "action_if_failed": "drop",
                    }
                ],
            }
        )
        errors = validate_se_yaml(content)
        assert any("drop" in e and "query_dq" in e for e in errors)

    def test_drop_valid_for_row_dq(self):
        content = yaml.dump(
            {
                "product_id": "test",
                "rules": [
                    {
                        "rule": "r",
                        "expectation": "x IS NOT NULL",
                        "rule_type": "row_dq",
                        "action_if_failed": "drop",
                    }
                ],
            }
        )
        errors = validate_se_yaml(content)
        assert not any("drop" in e and "row_dq" in e for e in errors)

    def test_integer_type_casting(self):
        content = yaml.dump(
            {
                "product_id": "test",
                "rules": [
                    {
                        "rule": "r",
                        "expectation": "x",
                        "rule_type": "row_dq",
                        "error_drop_threshold": "not_a_number",
                    }
                ],
            }
        )
        errors = validate_se_yaml(content)
        assert any("integer" in e for e in errors)

    def test_end_to_end_generated_yaml_passes(self, valid_dqs_path: Path):
        """YAML generated from a valid DQS must pass SE structural validation.

        Soft warnings (e.g., 'no comparison operator' for placeholder
        expressions) are acceptable — they indicate the DQS parser couldn't
        extract a real SQL expression. Hard errors (wrong rule_type, SELECT
        in row_dq, etc.) must not occur.
        """
        rules = parse_dqs(valid_dqs_path)
        grouped = group_rules_by_table(rules)
        config = load_se_config(None)

        # These are soft warnings, not hard errors
        soft_patterns = [
            "no comparison operator",
            "no aggregate function",
            "may not match SE regex",
            "unqualified table",
        ]

        for tbl, tbl_rules in grouped.items():
            yaml_content = generate_se_yaml_for_table(tbl, tbl_rules, config, "x.md")
            errors = validate_se_yaml(yaml_content)
            hard_errors = [e for e in errors if not any(pat in e for pat in soft_patterns)]
            assert hard_errors == [], f"Table {tbl} failed SE validation: {hard_errors}"

    def test_row_dq_rejects_select_in_expectation(self):
        """row_dq expectation must not contain SELECT."""
        content = yaml.dump(
            {
                "product_id": "test",
                "rules": [
                    {
                        "rule": "r1",
                        "rule_type": "row_dq",
                        "expectation": "SELECT COUNT(*) FROM t",
                    }
                ],
            }
        )
        errors = validate_se_yaml(content)
        assert any("row_dq" in e and "SELECT" in e for e in errors)

    def test_agg_dq_warns_on_non_regex_expectation(self):
        """agg_dq with expression that won't match SE regex."""
        content = yaml.dump(
            {
                "product_id": "test",
                "rules": [
                    {
                        "rule": "r1",
                        "rule_type": "agg_dq",
                        "expectation": "patient_id IS NOT NULL",
                    }
                ],
            }
        )
        errors = validate_se_yaml(content)
        assert any("regex" in e for e in errors)

    def test_query_dq_warns_on_select_prefix(self):
        """query_dq should not start with SELECT (SE wraps it)."""
        content = yaml.dump(
            {
                "product_id": "test",
                "rules": [
                    {
                        "rule": "r1",
                        "rule_type": "query_dq",
                        "expectation": "SELECT COUNT(*) FROM t",
                    }
                ],
            }
        )
        errors = validate_se_yaml(content)
        assert any("query_dq" in e and "SELECT" in e for e in errors)

    def test_valid_row_dq_expectation_passes(self):
        """Valid row_dq boolean expressions should not trigger errors."""
        content = yaml.dump(
            {
                "product_id": "test",
                "rules": [
                    {
                        "rule": "r1",
                        "rule_type": "row_dq",
                        "expectation": "patient_id IS NOT NULL",
                    }
                ],
            }
        )
        errors = validate_se_yaml(content)
        assert not any("row_dq" in e and "SELECT" in e for e in errors)

    def test_valid_agg_dq_expectation_passes(self):
        """Valid agg_dq expressions matching SE regex should pass."""
        for exp in [
            "count(*) > 0",
            "sum(sales) > 10000",
            "count(*) > 40000 and count(*) < 60000",
        ]:
            content = yaml.dump(
                {
                    "product_id": "test",
                    "rules": [
                        {
                            "rule": "r1",
                            "rule_type": "agg_dq",
                            "expectation": exp,
                        }
                    ],
                }
            )
            errors = validate_se_yaml(content)
            assert not any("regex" in e for e in errors), f"False positive for: {exp}"


# ---------------------------------------------------------------------------
# sqlparse-powered expression validation tests
# ---------------------------------------------------------------------------


class TestValidateRowDqExpression:
    """Tests for _validate_row_dq_expression (sqlparse-powered)."""

    def test_simple_not_null_passes(self):
        errors = _validate_row_dq_expression("patient_id IS NOT NULL")
        assert errors == []

    def test_comparison_passes(self):
        errors = _validate_row_dq_expression("age > 0")
        assert errors == []

    def test_in_clause_passes(self):
        errors = _validate_row_dq_expression("lower(trim(gender)) in ('male','female')")
        assert errors == []

    def test_between_passes(self):
        errors = _validate_row_dq_expression("age BETWEEN 0 AND 150")
        assert errors == []

    def test_like_passes(self):
        errors = _validate_row_dq_expression("email LIKE '%@%.%'")
        assert errors == []

    def test_rejects_select(self):
        errors = _validate_row_dq_expression("SELECT COUNT(*) FROM t")
        assert any("SELECT" in e for e in errors)

    def test_rejects_case_when(self):
        errors = _validate_row_dq_expression("CASE WHEN x > 0 THEN 1 ELSE 0 END")
        assert any("CASE" in e for e in errors)

    def test_rejects_subquery(self):
        errors = _validate_row_dq_expression("(SELECT 1 FROM t WHERE t.id = x.id) = 1")
        assert any("SELECT" in e for e in errors)

    def test_unbalanced_parens(self):
        errors = _validate_row_dq_expression("col > 0 AND (col2 < 10")
        assert any("unbalanced" in e for e in errors)

    def test_warns_no_comparison(self):
        errors = _validate_row_dq_expression("FORMAT check")
        assert any("comparison" in e for e in errors)


class TestValidateAggDqExpression:
    """Tests for _validate_agg_dq_expression (sqlparse-powered)."""

    def test_count_star_passes(self):
        errors = _validate_agg_dq_expression("count(*) > 0")
        assert errors == []

    def test_sum_passes(self):
        errors = _validate_agg_dq_expression("sum(sales) > 10000")
        assert errors == []

    def test_range_passes(self):
        errors = _validate_agg_dq_expression("count(*) > 40000 and count(*) < 60000")
        assert errors == []

    def test_rejects_select(self):
        errors = _validate_agg_dq_expression("SELECT COUNT(*) FROM t")
        assert any("SELECT" in e for e in errors)

    def test_warns_no_aggregate(self):
        errors = _validate_agg_dq_expression("x > 0")
        assert any("aggregate" in e for e in errors)

    def test_warns_non_regex_match(self):
        errors = _validate_agg_dq_expression("patient_id IS NOT NULL")
        assert any("regex" in e for e in errors)


class TestValidateQueryDqExpression:
    """Tests for _validate_query_dq_expression (sqlparse-powered)."""

    def test_case_when_passes(self):
        exp = (
            "CASE WHEN ABS(s.cnt - t.cnt) * 100.0 / NULLIF(s.cnt, 0) <= 0.1 "
            "THEN 1 ELSE 0 END "
            "FROM (SELECT COUNT(*) AS cnt FROM clinical.encounters) s, "
            "(SELECT COUNT(*) AS cnt FROM analytics.fact_encounter) t"
        )
        errors = _validate_query_dq_expression(exp)
        assert errors == []

    def test_rejects_select_prefix(self):
        errors = _validate_query_dq_expression("SELECT COUNT(*) FROM t")
        assert any("SELECT" in e for e in errors)

    def test_flags_unqualified_tables(self):
        exp = (
            "CASE WHEN (SELECT COUNT(*) FROM billing_claims c "
            "LEFT JOIN clinical_patients p ON c.patient_id = p.patient_id "
            "WHERE p.patient_id IS NULL) = 0 THEN 1 ELSE 0 END"
        )
        errors = _validate_query_dq_expression(exp)
        assert any("unqualified" in e for e in errors)

    def test_qualified_tables_pass(self):
        exp = (
            "CASE WHEN (SELECT COUNT(*) FROM clinical.billing_claims c "
            "LEFT JOIN clinical.clinical_patients p "
            "ON c.patient_id = p.patient_id "
            "WHERE p.patient_id IS NULL) = 0 THEN 1 ELSE 0 END"
        )
        errors = _validate_query_dq_expression(exp)
        assert not any("unqualified" in e for e in errors)

    def test_unbalanced_parens(self):
        errors = _validate_query_dq_expression("CASE WHEN (SELECT COUNT(*) FROM clinical.t")
        assert any("unbalanced" in e for e in errors)
