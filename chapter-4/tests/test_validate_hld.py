"""Tests for the HLD validator script."""

from __future__ import annotations

import sys
from pathlib import Path

# Add the validator's parent directory to sys.path
VALIDATOR_DIR = (
    Path(__file__).resolve().parent.parent
    / "architect-plugin"
    / "skills"
    / "validate-hld"
    / "scripts"
)
sys.path.insert(0, str(VALIDATOR_DIR))

from conftest import (  # noqa: E402
    EMPTY_SECTIONS_HLD,
    MINIMAL_INVALID_HLD,
    PLACEHOLDER_HLD,
    VALID_HLD,
)
from validate_hld import (  # noqa: E402
    ValidationLevel,
    ValidationReport,
    check_capacity_projections,
    check_cdc_strategy,
    check_cost_estimates,
    check_decision_documentation,
    check_diagrams,
    check_drd_traceability,
    check_layer_specs,
    check_metadata,
    check_pattern_justification,
    check_placeholders,
    check_required_sections,
    check_security_compliance,
    check_technology_table,
    parse_hld_sections,
    validate_hld,
)


class TestParseHldSections:
    """Test HLD section parsing."""

    def test_parses_valid_hld(self):
        sections = parse_hld_sections(VALID_HLD)
        assert len(sections) > 0

    def test_parses_minimal_hld(self):
        sections = parse_hld_sections(MINIMAL_INVALID_HLD)
        assert len(sections) > 0

    def test_section_content_is_correct(self):
        sections = parse_hld_sections(VALID_HLD)
        assert "1. Design Overview" in sections


class TestCheckRequiredSections:
    """All 8 HLD sections must be present."""

    def test_valid_hld_passes(self):
        sections = parse_hld_sections(VALID_HLD)
        results = check_required_sections(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) == 0

    def test_missing_sections_detected(self):
        sections = parse_hld_sections(MINIMAL_INVALID_HLD)
        results = check_required_sections(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) > 0

    def test_reports_specific_missing_sections(self):
        sections = parse_hld_sections(MINIMAL_INVALID_HLD)
        results = check_required_sections(sections)
        messages = " ".join(r.message for r in results)
        assert "Layer Specifications" in messages


class TestCheckMetadata:
    """HLD must have complete metadata."""

    def test_valid_metadata_passes(self):
        results = check_metadata(VALID_HLD)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) == 0

    def test_missing_metadata_detected(self):
        results = check_metadata(MINIMAL_INVALID_HLD)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) > 0


class TestCheckLayerSpecs:
    """Layer specifications must be non-empty."""

    def test_valid_layers_pass(self):
        sections = parse_hld_sections(VALID_HLD)
        results = check_layer_specs(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) == 0

    def test_empty_layers_detected(self):
        sections = parse_hld_sections(EMPTY_SECTIONS_HLD)
        results = check_layer_specs(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) > 0


class TestCheckTechnologyTable:
    """Technology stack must have a table with entries."""

    def test_valid_tech_table_passes(self):
        sections = parse_hld_sections(VALID_HLD)
        results = check_technology_table(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) == 0

    def test_missing_tech_table_detected(self):
        sections = parse_hld_sections(MINIMAL_INVALID_HLD)
        results = check_technology_table(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) > 0


class TestCheckDrdTraceability:
    """Design decisions must cite DRD requirements."""

    def test_valid_traceability_passes(self):
        results = check_drd_traceability(VALID_HLD)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) == 0

    def test_missing_traceability_detected(self):
        results = check_drd_traceability("# HLD\n\nNo references here.")
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) > 0


class TestCheckCdcStrategy:
    """CDC section must mention detection methods."""

    def test_valid_cdc_passes(self):
        sections = parse_hld_sections(VALID_HLD)
        results = check_cdc_strategy(sections)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) == 0

    def test_missing_cdc_detected(self):
        sections = parse_hld_sections(EMPTY_SECTIONS_HLD)
        results = check_cdc_strategy(sections)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) > 0


class TestCheckCapacityProjections:
    """Capacity section must have numeric projections."""

    def test_valid_capacity_passes(self):
        sections = parse_hld_sections(VALID_HLD)
        results = check_capacity_projections(sections)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) == 0


class TestCheckSecurityCompliance:
    """Security section must reference compliance/regulatory controls."""

    def test_valid_security_passes(self):
        sections = parse_hld_sections(VALID_HLD)
        results = check_security_compliance(sections)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) == 0


class TestCheckPatternJustification:
    """Design overview must justify the pattern choice."""

    def test_valid_justification_passes(self):
        sections = parse_hld_sections(VALID_HLD)
        results = check_pattern_justification(sections)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) == 0


class TestCheckDecisionDocumentation:
    """HLD must contain decision documentation."""

    def test_valid_decisions_pass(self):
        results = check_decision_documentation(VALID_HLD)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) == 0


class TestCheckPlaceholders:
    """Detect placeholder text."""

    def test_no_placeholders_passes(self):
        results = check_placeholders(VALID_HLD)
        infos = [r for r in results if r.level == ValidationLevel.INFO]
        assert len(infos) == 0

    def test_placeholders_detected(self):
        results = check_placeholders(PLACEHOLDER_HLD)
        infos = [r for r in results if r.level == ValidationLevel.INFO]
        assert len(infos) > 0


class TestCheckDiagrams:
    """Check for Mermaid diagrams."""

    def test_diagrams_present(self):
        results = check_diagrams(VALID_HLD)
        infos = [r for r in results if r.level == ValidationLevel.INFO]
        assert len(infos) == 0

    def test_missing_diagrams_flagged(self):
        results = check_diagrams(MINIMAL_INVALID_HLD)
        infos = [r for r in results if r.level == ValidationLevel.INFO]
        assert len(infos) > 0


class TestCheckCostEstimates:
    """Capacity section should mention costs."""

    def test_costs_present(self):
        sections = parse_hld_sections(VALID_HLD)
        results = check_cost_estimates(sections)
        infos = [r for r in results if r.level == ValidationLevel.INFO]
        assert len(infos) == 0


class TestValidateHld:
    """Integration tests for the full validator."""

    def test_valid_hld_passes(self, valid_hld_file):
        report = validate_hld(valid_hld_file)
        assert report.passed

    def test_invalid_hld_has_criticals(self, invalid_hld_file):
        report = validate_hld(invalid_hld_file)
        assert report.critical_count > 0

    def test_nonexistent_file_returns_critical(self, tmp_path):
        missing = tmp_path / "does-not-exist.md"
        report = validate_hld(missing)
        assert report.critical_count > 0

    def test_empty_sections_hld_has_criticals(self, empty_hld_sections_file):
        report = validate_hld(empty_hld_sections_file)
        assert report.critical_count > 0

    def test_placeholder_hld_has_info(self, placeholder_hld_file):
        report = validate_hld(placeholder_hld_file)
        assert report.info_count > 0


class TestValidationReport:
    """Test the ValidationReport dataclass."""

    def test_empty_report_passes(self):
        report = ValidationReport(file_path="test.md", results=[])
        assert report.passed

    def test_report_with_critical_fails(self):
        from validate_hld import ValidationResult

        report = ValidationReport(
            file_path="test.md",
            results=[
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    section="Test",
                    message="Missing section",
                    suggestion="Add it",
                )
            ],
        )
        assert not report.passed
