"""Tests for the DMS validator script."""

from __future__ import annotations

import sys
from pathlib import Path

# Add the validator's parent directory to sys.path
VALIDATOR_DIR = (
    Path(__file__).resolve().parent.parent
    / "data-modeler-plugin"
    / "skills"
    / "validate-dms"
    / "scripts"
)
sys.path.insert(0, str(VALIDATOR_DIR))

from conftest import (  # noqa: E402
    EMPTY_SECTIONS_DMS,
    MINIMAL_INVALID_DMS,
    PLACEHOLDER_DMS,
    VALID_DMS,
)
from validate_dms import (  # noqa: E402
    ValidationLevel,
    ValidationReport,
    check_bronze_schemas,
    check_diagrams,
    check_gold_schemas,
    check_hld_traceability,
    check_holistic_er_diagram,
    check_metadata,
    check_naming_conventions,
    check_no_null_handling_in_silver,
    check_no_transform_in_silver,
    check_placeholders,
    check_required_sections,
    check_scd_documentation,
    check_silver_schemas,
    check_traceability_matrix,
    parse_dms_sections,
    validate_dms,
)


class TestParseDmsSections:
    """Test DMS section parsing."""

    def test_parses_valid_dms(self):
        sections = parse_dms_sections(VALID_DMS)
        assert len(sections) > 0

    def test_parses_minimal_dms(self):
        sections = parse_dms_sections(MINIMAL_INVALID_DMS)
        assert len(sections) > 0

    def test_section_content_is_correct(self):
        sections = parse_dms_sections(VALID_DMS)
        assert "1. Design Overview" in sections


class TestCheckRequiredSections:
    """All 9 DMS sections must be present."""

    def test_valid_dms_passes(self):
        sections = parse_dms_sections(VALID_DMS)
        results = check_required_sections(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) == 0

    def test_missing_sections_detected(self):
        sections = parse_dms_sections(MINIMAL_INVALID_DMS)
        results = check_required_sections(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) > 0

    def test_reports_specific_missing_sections(self):
        sections = parse_dms_sections(MINIMAL_INVALID_DMS)
        results = check_required_sections(sections)
        messages = " ".join(r.message for r in results)
        assert "Silver Layer Schemas" in messages or "Gold Layer" in messages


class TestCheckMetadata:
    """DMS must have complete metadata."""

    def test_valid_metadata_passes(self):
        results = check_metadata(VALID_DMS)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) == 0

    def test_missing_metadata_detected(self):
        results = check_metadata(MINIMAL_INVALID_DMS)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) > 0


class TestCheckBronzeSchemas:
    """Bronze schemas must have YAML blocks with table and columns."""

    def test_valid_bronze_passes(self):
        sections = parse_dms_sections(VALID_DMS)
        results = check_bronze_schemas(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) == 0

    def test_empty_bronze_detected(self):
        sections = parse_dms_sections(EMPTY_SECTIONS_DMS)
        results = check_bronze_schemas(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) > 0


class TestCheckSilverSchemas:
    """Silver schemas must have YAML blocks with primary_key."""

    def test_valid_silver_passes(self):
        sections = parse_dms_sections(VALID_DMS)
        results = check_silver_schemas(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) == 0

    def test_empty_silver_detected(self):
        sections = parse_dms_sections(EMPTY_SECTIONS_DMS)
        results = check_silver_schemas(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) > 0


class TestCheckGoldSchemas:
    """Gold schemas must have YAML blocks with grain."""

    def test_valid_gold_passes(self):
        sections = parse_dms_sections(VALID_DMS)
        results = check_gold_schemas(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) == 0

    def test_empty_gold_detected(self):
        sections = parse_dms_sections(EMPTY_SECTIONS_DMS)
        results = check_gold_schemas(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) > 0


class TestCheckHldTraceability:
    """Schema decisions must cite HLD sections."""

    def test_valid_traceability_passes(self):
        results = check_hld_traceability(VALID_DMS)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) == 0

    def test_missing_traceability_detected(self):
        results = check_hld_traceability("# DMS\n\nNo references here.")
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) > 0


class TestCheckScdDocumentation:
    """SCD section must mention SCD types."""

    def test_valid_scd_passes(self):
        sections = parse_dms_sections(VALID_DMS)
        results = check_scd_documentation(sections)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) == 0

    def test_missing_scd_detected(self):
        sections = parse_dms_sections(EMPTY_SECTIONS_DMS)
        results = check_scd_documentation(sections)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) > 0


class TestCheckNamingConventions:
    """Naming conventions must mention prefixes."""

    def test_valid_naming_passes(self):
        sections = parse_dms_sections(VALID_DMS)
        results = check_naming_conventions(sections)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) == 0


class TestCheckTraceabilityMatrix:
    """Traceability matrix must have entries."""

    def test_valid_matrix_passes(self):
        sections = parse_dms_sections(VALID_DMS)
        results = check_traceability_matrix(sections)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) == 0


class TestCheckPlaceholders:
    """Detect placeholder text."""

    def test_no_placeholders_passes(self):
        results = check_placeholders(VALID_DMS)
        infos = [r for r in results if r.level == ValidationLevel.INFO]
        assert len(infos) == 0

    def test_placeholders_detected(self):
        results = check_placeholders(PLACEHOLDER_DMS)
        infos = [r for r in results if r.level == ValidationLevel.INFO]
        assert len(infos) > 0


class TestCheckDiagrams:
    """Check for Mermaid diagrams."""

    def test_diagrams_present(self):
        results = check_diagrams(VALID_DMS)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) == 0

    def test_missing_diagrams_flagged(self):
        results = check_diagrams(MINIMAL_INVALID_DMS)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) > 0


class TestCheckHolisticErDiagram:
    """Design Overview should include a holistic erDiagram spanning all layers."""

    def test_valid_dms_has_holistic_diagram(self):
        sections = parse_dms_sections(VALID_DMS)
        results = check_holistic_er_diagram(sections)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) == 0

    def test_missing_holistic_diagram_flagged(self):
        # Design Overview has text content but no erDiagram
        sections = {
            "1. Design Overview": (
                "### 1.1 Modeling Approach\n\nMedallion architecture.\n\n"
                "### 1.2 Layer Summary\n\n| Layer | Purpose |\n"
            )
        }
        results = check_holistic_er_diagram(sections)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) > 0


class TestValidateDms:
    """Integration tests for the full validator."""

    def test_valid_dms_passes(self, valid_dms_file):
        report = validate_dms(valid_dms_file)
        assert report.passed

    def test_invalid_dms_has_criticals(self, invalid_dms_file):
        report = validate_dms(invalid_dms_file)
        assert report.critical_count > 0

    def test_nonexistent_file_returns_critical(self, tmp_path):
        missing = tmp_path / "does-not-exist.md"
        report = validate_dms(missing)
        assert report.critical_count > 0

    def test_empty_sections_dms_has_criticals(self, empty_dms_sections_file):
        report = validate_dms(empty_dms_sections_file)
        assert report.critical_count > 0

    def test_placeholder_dms_has_info(self, placeholder_dms_file):
        report = validate_dms(placeholder_dms_file)
        assert report.info_count > 0


class TestValidationReport:
    """Test the ValidationReport dataclass."""

    def test_empty_report_passes(self):
        report = ValidationReport(file_path="test.md", results=[])
        assert report.passed

    def test_report_with_critical_fails(self):
        from validate_dms import ValidationResult

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


class TestCheckNoTransformInSilver:
    """Silver YAML blocks should not contain transform: expressions."""

    def test_valid_dms_has_no_transforms(self):
        sections = parse_dms_sections(VALID_DMS)
        results = check_no_transform_in_silver(sections)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) == 0

    def test_transform_in_silver_detected(self):
        dms_with_transform = VALID_DMS.replace(
            "    source: bronze.patients.BIRTHDATE",
            "    source: bronze.patients.BIRTHDATE\n" '    transform: "CAST(BIRTHDATE AS DATE)"',
        )
        sections = parse_dms_sections(dms_with_transform)
        results = check_no_transform_in_silver(sections)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) > 0


class TestCheckNoNullHandlingInSilver:
    """Silver YAML blocks should not contain null_handling: directives."""

    def test_valid_dms_has_no_null_handling(self):
        sections = parse_dms_sections(VALID_DMS)
        results = check_no_null_handling_in_silver(sections)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) == 0

    def test_null_handling_in_silver_detected(self):
        dms_with_nh = VALID_DMS.replace(
            "    source: bronze.patients.BIRTHDATE",
            "    source: bronze.patients.BIRTHDATE\n" '    null_handling: "pass through null"',
        )
        sections = parse_dms_sections(dms_with_nh)
        results = check_no_null_handling_in_silver(sections)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) > 0
