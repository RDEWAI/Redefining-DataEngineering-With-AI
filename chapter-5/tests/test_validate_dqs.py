"""Tests for the DQS validator script."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make validator importable
sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parent.parent
        / "dq-engineer-plugin"
        / "skills"
        / "validate-dqs"
        / "scripts"
    ),
)

from conftest import (
    EMPTY_SECTIONS_DQS,
    MINIMAL_INVALID_DQS,
    PLACEHOLDER_DQS,
    VALID_DQS,
)
from validate_dqs import (
    ValidationLevel,
    ValidationReport,
    check_alert_thresholds,
    check_field_level_rules,
    check_metadata,
    check_multi_layer_coverage,
    check_placeholders,
    check_reconciliation_rules,
    check_referential_integrity,
    check_required_sections,
    check_rule_id_format,
    check_severity_definitions,
    parse_dqs_sections,
    validate_dqs,
)


class TestParseDqsSections:
    def test_parses_valid_dqs(self):
        sections = parse_dqs_sections(VALID_DQS)
        assert len(sections) >= 9

    def test_parses_minimal_dqs(self):
        sections = parse_dqs_sections(MINIMAL_INVALID_DQS)
        assert "1. Overview" in sections

    def test_section_content_is_correct(self):
        sections = parse_dqs_sections(VALID_DQS)
        assert "2. Field-Level Validation Rules" in sections


class TestCheckRequiredSections:
    def test_valid_dqs_passes(self):
        sections = parse_dqs_sections(VALID_DQS)
        results = check_required_sections(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) == 0

    def test_missing_sections_detected(self):
        sections = parse_dqs_sections(MINIMAL_INVALID_DQS)
        results = check_required_sections(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) > 0

    def test_reports_specific_missing_sections(self):
        sections = parse_dqs_sections(MINIMAL_INVALID_DQS)
        results = check_required_sections(sections)
        messages = " ".join(r.message for r in results)
        assert "Reconciliation" in messages


class TestCheckMetadata:
    def test_valid_metadata_passes(self):
        results = check_metadata(VALID_DQS)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) == 0

    def test_missing_metadata_detected(self):
        results = check_metadata(MINIMAL_INVALID_DQS)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) > 0


class TestCheckFieldLevelRules:
    def test_valid_rules_pass(self):
        sections = parse_dqs_sections(VALID_DQS)
        results = check_field_level_rules(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) == 0

    def test_empty_section_fails(self):
        sections = parse_dqs_sections(EMPTY_SECTIONS_DQS)
        results = check_field_level_rules(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) > 0


class TestCheckReferentialIntegrity:
    def test_valid_passes(self):
        sections = parse_dqs_sections(VALID_DQS)
        results = check_referential_integrity(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) == 0

    def test_empty_fails(self):
        sections = parse_dqs_sections(EMPTY_SECTIONS_DQS)
        results = check_referential_integrity(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) > 0


class TestCheckSeverityDefinitions:
    def test_valid_passes(self):
        sections = parse_dqs_sections(VALID_DQS)
        results = check_severity_definitions(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) == 0

    def test_missing_severity_detected(self):
        sections = parse_dqs_sections(EMPTY_SECTIONS_DQS)
        results = check_severity_definitions(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) > 0


class TestCheckRuleIdFormat:
    def test_valid_has_enough_ids(self):
        results = check_rule_id_format(VALID_DQS)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) == 0

    def test_minimal_lacks_ids(self):
        results = check_rule_id_format(MINIMAL_INVALID_DQS)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) > 0


class TestCheckMultiLayerCoverage:
    def test_valid_covers_all_layers(self):
        sections = parse_dqs_sections(VALID_DQS)
        results = check_multi_layer_coverage(sections)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) == 0

    def test_gold_only_warned(self):
        sections = {"2. Field-Level Validation Rules": "gold dim_patient"}
        results = check_multi_layer_coverage(sections)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) > 0
        assert "bronze" in warnings[0].message.lower()


class TestCheckReconciliationRules:
    def test_valid_passes(self):
        sections = parse_dqs_sections(VALID_DQS)
        results = check_reconciliation_rules(sections)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) == 0

    def test_empty_warned(self):
        sections = parse_dqs_sections(EMPTY_SECTIONS_DQS)
        results = check_reconciliation_rules(sections)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) > 0


class TestCheckAlertThresholds:
    def test_valid_passes(self):
        sections = parse_dqs_sections(VALID_DQS)
        results = check_alert_thresholds(sections)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) == 0

    def test_empty_warned(self):
        sections = parse_dqs_sections(EMPTY_SECTIONS_DQS)
        results = check_alert_thresholds(sections)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) > 0


class TestCheckPlaceholders:
    def test_valid_has_none(self):
        results = check_placeholders(VALID_DQS)
        info = [r for r in results if r.level == ValidationLevel.INFO]
        assert len(info) == 0

    def test_placeholder_dqs_flagged(self):
        results = check_placeholders(PLACEHOLDER_DQS)
        info = [r for r in results if r.level == ValidationLevel.INFO]
        assert len(info) > 0


class TestValidateDqsIntegration:
    def test_valid_dqs_passes(self, valid_dqs_file):
        report = validate_dqs(valid_dqs_file)
        assert report.passed is True

    def test_invalid_dqs_has_criticals(self, invalid_dqs_file):
        report = validate_dqs(invalid_dqs_file)
        assert report.critical_count > 0

    def test_nonexistent_file_returns_critical(self, tmp_path):
        report = validate_dqs(tmp_path / "nonexistent.md")
        assert report.critical_count > 0

    def test_empty_sections_has_criticals(self, empty_dqs_sections_file):
        report = validate_dqs(empty_dqs_sections_file)
        assert report.critical_count > 0

    def test_placeholder_dqs_has_info(self, placeholder_dqs_file):
        report = validate_dqs(placeholder_dqs_file)
        assert report.info_count > 0


class TestValidationReport:
    def test_empty_report_passes(self):
        report = ValidationReport(file_path="test.md")
        assert report.passed is True

    def test_report_with_critical_fails(self):
        report = ValidationReport(file_path="test.md")
        report.results.append(
            pytest.importorskip("validate_dqs").ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="Test",
                message="Test",
                suggestion="Test",
            )
        )
        assert report.passed is False
