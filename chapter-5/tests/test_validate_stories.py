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


class TestBootstrapRule:
    """STORIES-BOOTSTRAP-001 — backlog must contain ≥1 runtime-bootstrap story."""

    def test_missing_bootstrap_fires_critical(self, tmp_path):
        from conftest import VALID_BACKLOG, VALID_EPIC, VALID_STORY

        stories_dir = tmp_path / "stories"
        stories_dir.mkdir()
        (stories_dir / "BACKLOG-2026-04-26-test.md").write_text(VALID_BACKLOG, encoding="utf-8")
        epic_dir = stories_dir / "EPIC-01-test"
        epic_dir.mkdir()
        (epic_dir / "EPIC-01.md").write_text(VALID_EPIC, encoding="utf-8")
        # Build-only backlog — no runtime-bootstrap story
        (epic_dir / "STORY-01-001-build.md").write_text(VALID_STORY, encoding="utf-8")

        report = validate_stories_dir(stories_dir)
        msgs = [r.message for r in report.results if r.level == ValidationLevel.CRITICAL]
        assert any("runtime-bootstrap story" in m for m in msgs), msgs

    def test_present_bootstrap_does_not_fire(self, valid_stories_dir):
        report = validate_stories_dir(valid_stories_dir)
        msgs = [r.message for r in report.results if r.level == ValidationLevel.CRITICAL]
        assert not any("runtime-bootstrap story" in m for m in msgs)


class TestTestingSectionRule:
    """STORIES-TESTING-001 — every story needs a populated `## Testing` table."""

    def test_missing_testing_section_fires(self, tmp_path):
        from validate_stories import check_testing_section

        story = tmp_path / "STORY-01-001-no-testing.md"
        story.write_text(
            """# STORY-01-001: No testing

| Field | Value |
|-------|-------|
| **Status** | To Do |

## User Story
As a dev, I want X.

## Acceptance Criteria
- [ ] Foo [LLD §1]
""",
            encoding="utf-8",
        )
        results = check_testing_section(story)
        assert len(results) == 1
        assert results[0].level == ValidationLevel.CRITICAL
        assert "Testing" in results[0].message

    def test_populated_testing_passes(self, tmp_path):
        from validate_stories import check_testing_section

        story = tmp_path / "STORY-01-001-ok.md"
        story.write_text(
            """# STORY-01-001: ok

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | foo | pytest tests/foo.py |
""",
            encoding="utf-8",
        )
        results = check_testing_section(story)
        assert results == []


class TestUserTestSectionRule:
    """STORIES-USER-TEST-001 — build/integration-test/runtime-bootstrap need user-runnable steps."""

    def test_build_missing_user_test_is_critical(self, tmp_path):
        from validate_stories import check_user_test_section

        story = tmp_path / "STORY-01-001-build.md"
        story.write_text("# STORY-01-001\n\n## Acceptance Criteria\n- [ ] Foo\n", encoding="utf-8")
        results = check_user_test_section(story, "build")
        assert len(results) == 1
        assert results[0].level == ValidationLevel.CRITICAL

    def test_integration_test_missing_user_test_is_critical(self, tmp_path):
        from validate_stories import check_user_test_section

        story = tmp_path / "STORY-02-007-integ.md"
        story.write_text("# STORY-02-007\n\n## Acceptance Criteria\n- [ ] Foo\n", encoding="utf-8")
        results = check_user_test_section(story, "integration-test")
        assert len(results) == 1
        assert results[0].level == ValidationLevel.CRITICAL

    def test_runtime_bootstrap_missing_user_test_is_critical(self, tmp_path):
        from validate_stories import check_user_test_section

        story = tmp_path / "STORY-01-006-bootstrap.md"
        story.write_text("# STORY-01-006\n\n## Acceptance Criteria\n- [ ] Foo\n", encoding="utf-8")
        results = check_user_test_section(story, "runtime-bootstrap")
        assert len(results) == 1
        assert results[0].level == ValidationLevel.CRITICAL

    def test_observability_missing_user_test_is_warning(self, tmp_path):
        from validate_stories import check_user_test_section

        story = tmp_path / "STORY-09-001-obs.md"
        story.write_text("# STORY-09-001\n\n## Acceptance Criteria\n- [ ] Foo\n", encoding="utf-8")
        results = check_user_test_section(story, "observability")
        assert len(results) == 1
        assert results[0].level == ValidationLevel.WARNING

    def test_populated_steps_pass(self, tmp_path):
        from validate_stories import check_user_test_section

        story = tmp_path / "STORY-01-001-ok.md"
        story.write_text(
            """# STORY-01-001: ok

## How to Test (User)

### Steps

1. Run `make test`
2. Verify exit 0
""",
            encoding="utf-8",
        )
        results = check_user_test_section(story, "build")
        assert results == []


class TestDocumentationUpdatesRule:
    """STORIES-DOCS-001 — runtime-bootstrap/integration-test/release need ≥1 README update."""

    def test_runtime_bootstrap_no_docs_is_critical(self, tmp_path):
        from validate_stories import check_documentation_updates

        story = tmp_path / "STORY-01-006-bootstrap.md"
        story.write_text("# STORY-01-006\n\n## Acceptance Criteria\n- [ ] Foo\n", encoding="utf-8")
        results = check_documentation_updates(story, "runtime-bootstrap")
        assert len(results) == 1
        assert results[0].level == ValidationLevel.CRITICAL

    def test_integration_test_no_docs_is_critical(self, tmp_path):
        from validate_stories import check_documentation_updates

        story = tmp_path / "STORY-02-007-integ.md"
        story.write_text("# STORY-02-007\n\n## Acceptance Criteria\n- [ ] Foo\n", encoding="utf-8")
        results = check_documentation_updates(story, "integration-test")
        assert len(results) == 1
        assert results[0].level == ValidationLevel.CRITICAL

    def test_release_no_docs_is_critical(self, tmp_path):
        from validate_stories import check_documentation_updates

        story = tmp_path / "STORY-99-001-release.md"
        story.write_text("# STORY-99-001\n\n## Acceptance Criteria\n- [ ] Foo\n", encoding="utf-8")
        results = check_documentation_updates(story, "release")
        assert len(results) == 1
        assert results[0].level == ValidationLevel.CRITICAL

    def test_build_creating_runtime_files_no_docs_is_warning(self, tmp_path):
        from validate_stories import check_documentation_updates

        story = tmp_path / "STORY-02-001-build.md"
        story.write_text(
            """# STORY-02-001: build

## Verification

```yaml
AC1:
  - file_exists: "src/foo/runner.py"
```
""",
            encoding="utf-8",
        )
        results = check_documentation_updates(story, "build")
        assert len(results) == 1
        assert results[0].level == ValidationLevel.WARNING

    def test_build_no_runtime_files_no_docs_passes(self, tmp_path):
        from validate_stories import check_documentation_updates

        story = tmp_path / "STORY-02-001-build.md"
        story.write_text("# STORY-02-001: build\n\n", encoding="utf-8")
        results = check_documentation_updates(story, "build")
        assert results == []

    def test_populated_docs_passes(self, tmp_path):
        from validate_stories import check_documentation_updates

        story = tmp_path / "STORY-01-006-ok.md"
        story.write_text(
            """# STORY-01-006: ok

## Documentation Updates

- [ ] Update README § Bootstrap with `make dev-up`
""",
            encoding="utf-8",
        )
        results = check_documentation_updates(story, "runtime-bootstrap")
        assert results == []


class TestIntegrationAutomatedRule:
    """STORIES-INTEGRATION-AUTOMATED-001 — integration-test must have ≥1 non-manual verifier."""

    def test_all_manual_fires_critical(self, tmp_path):
        from validate_stories import check_integration_test_automated

        story = tmp_path / "STORY-02-007-manual-only.md"
        story.write_text(
            """# STORY-02-007: integ

## Verification

```yaml
AC1:
  - manual: "trigger DAG manually"
AC2:
  - manual: "check UC manually"
```
""",
            encoding="utf-8",
        )
        results = check_integration_test_automated(story, "integration-test")
        assert len(results) == 1
        assert results[0].level == ValidationLevel.CRITICAL

    def test_one_pytest_passes(self, tmp_path):
        from validate_stories import check_integration_test_automated

        story = tmp_path / "STORY-02-007-mixed.md"
        story.write_text(
            """# STORY-02-007: integ

## Verification

```yaml
AC1:
  - pytest: {node: "tests/integration/test_bronze_uc.py", marker: "integration"}
AC2:
  - manual: "Marquez UI lineage check"
```
""",
            encoding="utf-8",
        )
        results = check_integration_test_automated(story, "integration-test")
        assert results == []

    def test_non_integration_story_skipped(self, tmp_path):
        from validate_stories import check_integration_test_automated

        story = tmp_path / "STORY-02-001-build.md"
        story.write_text(
            """## Verification

```yaml
AC1:
  - manual: "fine for build"
```
""",
            encoding="utf-8",
        )
        results = check_integration_test_automated(story, "build")
        assert results == []

    def test_missing_verification_fires_critical_for_integration(self, tmp_path):
        from validate_stories import check_integration_test_automated

        story = tmp_path / "STORY-02-007-no-verif.md"
        story.write_text("# STORY-02-007\n\nNo verification block.", encoding="utf-8")
        results = check_integration_test_automated(story, "integration-test")
        assert len(results) == 1
        assert results[0].level == ValidationLevel.CRITICAL


class TestRuntimeBootstrapTypeAccepted:
    """`runtime-bootstrap` is a recognized story type — get_story_type returns it."""

    def test_runtime_bootstrap_type_recognized(self, tmp_path):
        from validate_stories import get_story_type

        story = tmp_path / "STORY-01-006-bootstrap.md"
        story.write_text(
            """# STORY-01-006: bootstrap

| Field | Value |
|-------|-------|
| **Story Type** | runtime-bootstrap |
""",
            encoding="utf-8",
        )
        assert get_story_type(story) == "runtime-bootstrap"
