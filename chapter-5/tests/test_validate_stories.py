"""Tests for the stories validator script."""

from __future__ import annotations

import sys
from pathlib import Path

# Add the validator's parent directory to sys.path
VALIDATOR_DIR = (
    Path(__file__).resolve().parent.parent
    / "scrum-master-plugin"
    / "skills"
    / "validate-stories"
    / "scripts"
)
sys.path.insert(0, str(VALIDATOR_DIR))

from conftest import (  # noqa: E402
    MINIMAL_INVALID_BACKLOG,
    PLACEHOLDER_BACKLOG,
    VALID_BACKLOG,
)
from validate_stories import (  # noqa: E402
    ValidationLevel,
    ValidationReport,
    check_backlog_metadata,
    check_backlog_sections,
    check_dependency_graph,
    check_placeholders,
    parse_sections,
    validate_single_backlog,
    validate_stories_dir,
)


class TestParseSections:
    """Test markdown section parsing."""

    def test_parses_valid_backlog(self):
        sections = parse_sections(VALID_BACKLOG)
        assert len(sections) > 0

    def test_parses_minimal_backlog(self):
        sections = parse_sections(MINIMAL_INVALID_BACKLOG)
        assert len(sections) > 0

    def test_section_content_is_correct(self):
        sections = parse_sections(VALID_BACKLOG)
        assert "2. Epic Overview" in sections


class TestCheckBacklogSections:
    """All 7 backlog sections must be present."""

    def test_valid_backlog_passes(self):
        results = check_backlog_sections(VALID_BACKLOG)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) == 0

    def test_missing_sections_detected(self):
        results = check_backlog_sections(MINIMAL_INVALID_BACKLOG)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) > 0

    def test_reports_specific_missing_sections(self):
        results = check_backlog_sections(MINIMAL_INVALID_BACKLOG)
        messages = " ".join(r.message for r in results)
        assert "Dependency Graph" in messages


class TestCheckMetadata:
    """Backlog must have complete metadata."""

    def test_valid_metadata_passes(self):
        results = check_backlog_metadata(VALID_BACKLOG)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) == 0

    def test_missing_metadata_detected(self):
        results = check_backlog_metadata(MINIMAL_INVALID_BACKLOG)
        criticals = [r for r in results if r.level == ValidationLevel.CRITICAL]
        assert len(criticals) > 0


class TestCheckDependencyGraph:
    """Backlog should have a Mermaid dependency diagram."""

    def test_valid_diagram_passes(self):
        results = check_dependency_graph(VALID_BACKLOG)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) == 0

    def test_missing_diagram_detected(self):
        results = check_dependency_graph(MINIMAL_INVALID_BACKLOG)
        warnings = [r for r in results if r.level == ValidationLevel.WARNING]
        assert len(warnings) > 0


class TestCheckPlaceholders:
    """Detect placeholder text."""

    def test_no_placeholders_passes(self):
        results = check_placeholders(VALID_BACKLOG, "Backlog")
        infos = [r for r in results if r.level == ValidationLevel.INFO]
        assert len(infos) == 0

    def test_placeholders_detected(self):
        results = check_placeholders(PLACEHOLDER_BACKLOG, "Backlog")
        infos = [r for r in results if r.level == ValidationLevel.INFO]
        assert len(infos) > 0


class TestValidateSingleBacklog:
    """Integration tests for single backlog file validation."""

    def test_valid_backlog_passes(self, valid_backlog_file):
        report = validate_single_backlog(valid_backlog_file)
        assert report.critical_count == 0

    def test_invalid_backlog_has_criticals(self, invalid_backlog_file):
        report = validate_single_backlog(invalid_backlog_file)
        assert report.critical_count > 0

    def test_nonexistent_file_returns_critical(self, tmp_path):
        missing = tmp_path / "does-not-exist.md"
        report = validate_single_backlog(missing)
        assert report.critical_count > 0


class TestValidateStoriesDir:
    """Integration tests for full directory validation."""

    def test_valid_dir_passes(self, valid_stories_dir):
        report = validate_stories_dir(valid_stories_dir)
        assert report.critical_count == 0

    def test_empty_dir_has_criticals(self, tmp_path):
        empty_dir = tmp_path / "empty-stories"
        empty_dir.mkdir()
        report = validate_stories_dir(empty_dir)
        assert report.critical_count > 0

    def test_nonexistent_dir_returns_critical(self, tmp_path):
        missing = tmp_path / "does-not-exist"
        report = validate_stories_dir(missing)
        assert report.critical_count > 0


class TestValidationReport:
    """Test the ValidationReport dataclass."""

    def test_empty_report_passes(self):
        report = ValidationReport(file_path="test", results=[])
        assert report.passed

    def test_report_with_critical_fails(self):
        from validate_stories import ValidationResult

        report = ValidationReport(
            file_path="test",
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
