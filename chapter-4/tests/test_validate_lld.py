"""Tests for the LLD validator script."""

from __future__ import annotations

import sys
from pathlib import Path

# Add the validator's parent directory to sys.path
VALIDATOR_DIR = (
    Path(__file__).resolve().parent.parent
    / "technical-lead-plugin"
    / "skills"
    / "validate-lld"
    / "scripts"
)
sys.path.insert(0, str(VALIDATOR_DIR))

from conftest import (  # noqa: E402
    EMPTY_SECTIONS_LLD,
    MINIMAL_INVALID_LLD,
    PLACEHOLDER_LLD,
    VALID_LLD,
)
from validate_lld import (  # noqa: E402
    ValidationLevel,
    ValidationReport,
    check_dag_definition_exists,
    check_dag_specification,
    check_design_overview,
    check_impl_sequence_exists,
    check_mermaid_export_exists,
    check_metadata,
    check_placeholders,
    check_required_sections,
    check_upstream_references,
    parse_lld_sections,
    validate_lld,
)


class TestParseLldSections:
    """Test LLD section parsing."""

    def test_parses_valid_lld(self):
        sections = parse_lld_sections(VALID_LLD)
        assert len(sections) > 0

    def test_parses_minimal_lld(self):
        sections = parse_lld_sections(MINIMAL_INVALID_LLD)
        assert len(sections) > 0

    def test_section_content_is_correct(self):
        sections = parse_lld_sections(VALID_LLD)
        assert "4. DAG Specification" in sections


class TestCheckRequiredSections:
    """All 14 LLD sections must be present."""

    def test_valid_lld_passes(self):
        sections = parse_lld_sections(VALID_LLD)
        results = check_required_sections(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) == 0

    def test_missing_sections_detected(self):
        sections = parse_lld_sections(MINIMAL_INVALID_LLD)
        results = check_required_sections(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) > 0

    def test_reports_specific_missing_sections(self):
        sections = parse_lld_sections(MINIMAL_INVALID_LLD)
        results = check_required_sections(sections)
        messages = " ".join(r.message for r in results)
        assert "DAG Specification" in messages


class TestCheckMetadata:
    """LLD must have complete metadata."""

    def test_valid_metadata_passes(self):
        results = check_metadata(VALID_LLD)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) == 0

    def test_missing_metadata_detected(self):
        results = check_metadata(MINIMAL_INVALID_LLD)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) > 0


class TestCheckDesignOverview:
    """Design Overview must exist with meaningful content."""

    def test_valid_design_overview_passes(self):
        sections = parse_lld_sections(VALID_LLD)
        results = check_design_overview(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) == 0

    def test_empty_design_overview_fails(self):
        sections = parse_lld_sections(EMPTY_SECTIONS_LLD)
        results = check_design_overview(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) > 0


class TestCheckDagSpecification:
    """DAG Specification must have a task table."""

    def test_valid_dag_passes(self):
        sections = parse_lld_sections(VALID_LLD)
        results = check_dag_specification(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) == 0

    def test_empty_dag_fails(self):
        sections = parse_lld_sections(EMPTY_SECTIONS_LLD)
        results = check_dag_specification(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) > 0


class TestCheckUpstreamReferences:
    """Upstream Artifact References must cite all 5 upstream docs."""

    def test_valid_upstream_passes(self):
        sections = parse_lld_sections(VALID_LLD)
        results = check_upstream_references(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) == 0

    def test_missing_upstream_fails(self):
        sections = parse_lld_sections(EMPTY_SECTIONS_LLD)
        results = check_upstream_references(sections)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) > 0


class TestCheckPlaceholders:
    """Placeholder text should be reported as INFO."""

    def test_no_placeholders_in_valid(self):
        results = check_placeholders(VALID_LLD)
        assert len(results) == 0

    def test_placeholders_detected(self):
        results = check_placeholders(PLACEHOLDER_LLD)
        assert len(results) > 0
        assert results[0].level == ValidationLevel.INFO


class TestValidateLld:
    """Integration tests for validate_lld function."""

    def test_valid_lld_passes(self, tmp_path):
        f = tmp_path / "valid.md"
        f.write_text(VALID_LLD, encoding="utf-8")
        report = validate_lld(f)
        assert report.critical_count == 0

    def test_invalid_lld_fails(self, tmp_path):
        f = tmp_path / "invalid.md"
        f.write_text(MINIMAL_INVALID_LLD, encoding="utf-8")
        report = validate_lld(f)
        assert report.critical_count > 0

    def test_missing_file_fails(self, tmp_path):
        f = tmp_path / "nonexistent.md"
        report = validate_lld(f)
        assert report.critical_count > 0


class TestCheckDagDefinitionExists:
    """Test DAG definition file existence check."""

    def test_dag_definition_absent(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text(VALID_LLD, encoding="utf-8")
        sections = parse_lld_sections(VALID_LLD)
        results = check_dag_definition_exists(sections, f)
        assert len(results) == 1
        assert results[0].level == ValidationLevel.INFO

    def test_dag_definition_present(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text(VALID_LLD, encoding="utf-8")
        dag_dir = tmp_path / "dag"
        dag_dir.mkdir()
        (dag_dir / "dag-definition.yaml").write_text("dag_id: test")
        sections = parse_lld_sections(VALID_LLD)
        results = check_dag_definition_exists(sections, f)
        assert len(results) == 0


class TestCheckMermaidExportExists:
    """Test Mermaid export file existence check."""

    def test_mermaid_absent(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text(VALID_LLD, encoding="utf-8")
        sections = parse_lld_sections(VALID_LLD)
        results = check_mermaid_export_exists(sections, f)
        assert len(results) == 1
        assert results[0].level == ValidationLevel.INFO

    def test_mermaid_present(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text(VALID_LLD, encoding="utf-8")
        dag_dir = tmp_path / "dag"
        dag_dir.mkdir()
        (dag_dir / "dag-pipeline.mmd").write_text("graph TD\n  A --> B")
        sections = parse_lld_sections(VALID_LLD)
        results = check_mermaid_export_exists(sections, f)
        assert len(results) == 0


class TestCheckImplSequenceExists:
    """Test implementation sequence file existence check."""

    def test_impl_sequence_absent(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text(VALID_LLD, encoding="utf-8")
        sections = parse_lld_sections(VALID_LLD)
        results = check_impl_sequence_exists(sections, f)
        assert len(results) == 1
        assert results[0].level == ValidationLevel.INFO

    def test_impl_sequence_present(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text(VALID_LLD, encoding="utf-8")
        (tmp_path / "impl-sequence.md").write_text("# Impl Sequence")
        sections = parse_lld_sections(VALID_LLD)
        results = check_impl_sequence_exists(sections, f)
        assert len(results) == 0


class TestValidationReport:
    """Validation report properties."""

    def test_passed_property(self):
        report = ValidationReport(file_path="test.md", results=[])
        assert report.passed is True

    def test_failed_with_critical(self, tmp_path):
        f = tmp_path / "invalid.md"
        f.write_text(MINIMAL_INVALID_LLD, encoding="utf-8")
        report = validate_lld(f)
        assert report.passed is False
