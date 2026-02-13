"""Tests for the DRD validator script."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add the validator script to the path
sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parent.parent
        / "ba-plugin"
        / "skills"
        / "validate-drd"
        / "scripts"
    ),
)

from validate_drd import (
    ValidationLevel,
    ValidationReport,
    check_approval,
    check_business_rules,
    check_consumers,
    check_critical_fields,
    check_edge_cases,
    check_freshness,
    check_no_empty_sections,
    check_open_questions,
    check_placeholders,
    check_regulatory_compliance,
    check_required_sections,
    check_sla_defined,
    check_source_systems,
    check_tolerances,
    check_version_metadata,
    parse_drd_sections,
    validate_drd,
)

from conftest import (
    EMPTY_SECTIONS_DRD,
    MINIMAL_INVALID_DRD,
    PLACEHOLDER_DRD,
    VALID_DRD,
)


class TestParseDrdSections:
    """Tests for parsing DRD markdown into section dict."""

    def test_parses_valid_drd(self) -> None:
        sections = parse_drd_sections(VALID_DRD)
        assert "Executive Summary" in sections
        assert "1. Business Context" in sections
        assert "2. Source Discovery" in sections
        assert "7. Regulatory and Compliance" in sections
        assert "8. Version History" in sections

    def test_parses_minimal_drd(self) -> None:
        sections = parse_drd_sections(MINIMAL_INVALID_DRD)
        assert "Executive Summary" in sections
        assert "1. Business Context" in sections
        assert len(sections) == 2

    def test_section_content_is_correct(self) -> None:
        sections = parse_drd_sections(VALID_DRD)
        assert "unified patient search" in sections["Executive Summary"]


class TestCheckRequiredSections:
    """Tests for required section validation."""

    def test_valid_drd_passes(self) -> None:
        sections = parse_drd_sections(VALID_DRD)
        results = check_required_sections(sections)
        assert len(results) == 0

    def test_missing_sections_detected(self) -> None:
        sections = parse_drd_sections(MINIMAL_INVALID_DRD)
        results = check_required_sections(sections)
        assert len(results) > 0
        assert all(r.level == ValidationLevel.CRITICAL for r in results)

    def test_reports_specific_missing_sections(self) -> None:
        sections = parse_drd_sections(MINIMAL_INVALID_DRD)
        results = check_required_sections(sections)
        missing_names = [r.section for r in results]
        assert "2. Source Discovery" in missing_names
        assert "4. Consumer Requirements" in missing_names
        assert "5. Business Rules" in missing_names


class TestCheckVersionMetadata:
    """Tests for version metadata validation."""

    def test_valid_metadata_passes(self) -> None:
        results = check_version_metadata(VALID_DRD)
        assert len(results) == 0

    def test_missing_metadata_detected(self) -> None:
        content = "# DRD: Test\n\nNo metadata here.\n"
        results = check_version_metadata(content)
        assert len(results) == 4  # Version, Created, Author, Status
        assert all(r.level == ValidationLevel.CRITICAL for r in results)


class TestCheckSourceSystems:
    """Tests for source system validation."""

    def test_valid_source_systems_pass(self) -> None:
        sections = parse_drd_sections(VALID_DRD)
        results = check_source_systems(sections)
        assert len(results) == 0

    def test_empty_source_systems_detected(self) -> None:
        sections = parse_drd_sections(EMPTY_SECTIONS_DRD)
        results = check_source_systems(sections)
        assert len(results) > 0
        assert results[0].level == ValidationLevel.CRITICAL


class TestCheckConsumers:
    """Tests for consumer validation."""

    def test_valid_consumers_pass(self) -> None:
        sections = parse_drd_sections(VALID_DRD)
        results = check_consumers(sections)
        assert len(results) == 0

    def test_missing_consumers_detected(self) -> None:
        sections = parse_drd_sections(EMPTY_SECTIONS_DRD)
        results = check_consumers(sections)
        assert len(results) > 0
        assert results[0].level == ValidationLevel.CRITICAL


class TestCheckNoEmptySections:
    """Tests for empty section detection."""

    def test_populated_sections_pass(self) -> None:
        sections = parse_drd_sections(VALID_DRD)
        results = check_no_empty_sections(sections)
        assert len(results) == 0

    def test_empty_sections_detected(self) -> None:
        sections = parse_drd_sections(EMPTY_SECTIONS_DRD)
        results = check_no_empty_sections(sections)
        assert len(results) > 0
        assert all(r.level == ValidationLevel.CRITICAL for r in results)


class TestCheckSLADefined:
    """Tests for SLA validation."""

    def test_valid_sla_passes(self) -> None:
        sections = parse_drd_sections(VALID_DRD)
        results = check_sla_defined(sections)
        assert len(results) == 0

    def test_missing_sla_detected(self) -> None:
        sections = parse_drd_sections(EMPTY_SECTIONS_DRD)
        results = check_sla_defined(sections)
        assert len(results) > 0
        assert results[0].level == ValidationLevel.WARNING


class TestCheckCriticalFields:
    """Tests for critical fields validation."""

    def test_valid_critical_fields_pass(self) -> None:
        sections = parse_drd_sections(VALID_DRD)
        results = check_critical_fields(sections)
        assert len(results) == 0

    def test_missing_critical_fields_detected(self) -> None:
        sections = parse_drd_sections(EMPTY_SECTIONS_DRD)
        results = check_critical_fields(sections)
        assert len(results) > 0
        assert results[0].level == ValidationLevel.WARNING


class TestCheckBusinessRules:
    """Tests for business rules validation."""

    def test_valid_business_rules_pass(self) -> None:
        sections = parse_drd_sections(VALID_DRD)
        results = check_business_rules(sections)
        assert len(results) == 0

    def test_missing_business_rules_detected(self) -> None:
        sections = parse_drd_sections(EMPTY_SECTIONS_DRD)
        results = check_business_rules(sections)
        assert len(results) > 0
        assert results[0].level == ValidationLevel.WARNING


class TestCheckFreshness:
    """Tests for freshness requirements validation."""

    def test_valid_freshness_passes(self) -> None:
        sections = parse_drd_sections(VALID_DRD)
        results = check_freshness(sections)
        assert len(results) == 0


class TestCheckOpenQuestions:
    """Tests for open questions validation."""

    def test_valid_open_questions_pass(self) -> None:
        sections = parse_drd_sections(VALID_DRD)
        results = check_open_questions(sections)
        assert len(results) == 0

    def test_missing_open_questions_detected(self) -> None:
        sections = parse_drd_sections(MINIMAL_INVALID_DRD)
        results = check_open_questions(sections)
        assert len(results) > 0
        assert results[0].level == ValidationLevel.WARNING


class TestCheckTolerances:
    """Tests for tolerance threshold validation."""

    def test_valid_tolerances_pass(self) -> None:
        sections = parse_drd_sections(VALID_DRD)
        results = check_tolerances(sections)
        assert len(results) == 0


class TestCheckRegulatoryCompliance:
    """Tests for regulatory compliance validation."""

    def test_valid_regulatory_passes(self) -> None:
        sections = parse_drd_sections(VALID_DRD)
        results = check_regulatory_compliance(sections)
        assert len(results) == 0

    def test_missing_regulatory_detected(self) -> None:
        sections = parse_drd_sections(EMPTY_SECTIONS_DRD)
        results = check_regulatory_compliance(sections)
        assert len(results) > 0
        assert results[0].level == ValidationLevel.WARNING


class TestCheckPlaceholders:
    """Tests for placeholder text detection."""

    def test_no_placeholders_passes(self) -> None:
        results = check_placeholders(VALID_DRD)
        assert len(results) == 0

    def test_placeholders_detected(self) -> None:
        results = check_placeholders(PLACEHOLDER_DRD)
        assert len(results) > 0
        assert results[0].level == ValidationLevel.INFO
        assert "placeholder" in results[0].message.lower()


class TestCheckApproval:
    """Tests for approval section validation."""

    def test_empty_approval_flagged(self) -> None:
        sections = parse_drd_sections(EMPTY_SECTIONS_DRD)
        results = check_approval(sections)
        # Missing section 8 entirely
        assert len(results) > 0
        assert results[0].level == ValidationLevel.INFO


class TestCheckEdgeCases:
    """Tests for edge case documentation validation."""

    def test_valid_edge_cases_pass(self) -> None:
        sections = parse_drd_sections(VALID_DRD)
        results = check_edge_cases(sections)
        assert len(results) == 0

    def test_missing_edge_cases_detected(self) -> None:
        sections = parse_drd_sections(EMPTY_SECTIONS_DRD)
        results = check_edge_cases(sections)
        assert len(results) > 0
        assert results[0].level == ValidationLevel.INFO


class TestValidateDrd:
    """Integration tests for the full validation pipeline."""

    def test_valid_drd_passes(self, valid_drd_file: Path) -> None:
        report = validate_drd(valid_drd_file)
        assert report.critical_count == 0

    def test_invalid_drd_has_criticals(self, invalid_drd_file: Path) -> None:
        report = validate_drd(invalid_drd_file)
        assert report.critical_count > 0
        assert not report.passed

    def test_nonexistent_file_returns_critical(self, tmp_path: Path) -> None:
        report = validate_drd(tmp_path / "does-not-exist.md")
        assert report.critical_count == 1
        assert "not found" in report.results[0].message.lower()

    def test_empty_sections_drd_has_criticals(self, empty_sections_file: Path) -> None:
        report = validate_drd(empty_sections_file)
        assert report.critical_count > 0

    def test_placeholder_drd_has_info(self, placeholder_drd_file: Path) -> None:
        report = validate_drd(placeholder_drd_file)
        info_results = [r for r in report.results if r.level == ValidationLevel.INFO]
        assert len(info_results) > 0


class TestValidationReport:
    """Tests for the ValidationReport dataclass."""

    def test_empty_report_passes(self) -> None:
        report = ValidationReport(file_path="test.md")
        assert report.passed
        assert report.critical_count == 0
        assert report.warning_count == 0
        assert report.info_count == 0

    def test_report_with_critical_fails(self) -> None:
        from validate_drd import ValidationResult

        report = ValidationReport(
            file_path="test.md",
            results=[
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    section="Test",
                    message="Test failure",
                    suggestion="Fix it",
                )
            ],
        )
        assert not report.passed
        assert report.critical_count == 1
