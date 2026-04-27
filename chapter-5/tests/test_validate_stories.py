"""Tests for the stories validator script."""
# ruff: noqa: E501  # test fixtures embed long markdown literals verbatim

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


class TestBootstrapExecutorCoverageRule:
    """STORIES-BOOTSTRAP-COVERAGE-001 — bootstrap must verify executors build stories invoke."""

    BUILD_WITH_SPARK = """\
# STORY-02-001: Bronze ingestion runner

| Field | Value |
|-------|-------|
| **Story Type** | build |

## Acceptance Criteria
- [ ] `ingestion_runner.py` invoked via SparkSubmitOperator [LLD §2.3]
"""

    BUILD_WITHOUT_SPARK = """\
# STORY-02-001: Contract files

| Field | Value |
|-------|-------|
| **Story Type** | build |

## Acceptance Criteria
- [ ] One YAML contract per Bronze table [DMS §3]
"""

    BOOTSTRAP_WITHOUT_SPARK = """\
# STORY-01-006: Bootstrap

| Field | Value |
|-------|-------|
| **Story Type** | runtime-bootstrap |

## Acceptance Criteria
- [ ] `java -version` reports 17.x [LLD §6.1]
- [ ] `docker compose up` succeeds [LLD §1]
- [ ] UC catalog `unity` and schemas `bronze`/`silver`/`gold` created [LLD §1]
- [ ] `curl localhost:8080/api/2.1/unity-catalog/catalogs` returns 200 [LLD §1]
"""

    BOOTSTRAP_WITH_SPARK = """\
# STORY-01-006: Bootstrap

| Field | Value |
|-------|-------|
| **Story Type** | runtime-bootstrap |

## Acceptance Criteria
- [ ] `java -version` reports 17.x [LLD §6.1]
- [ ] `docker compose exec airflow-scheduler spark-submit --master spark://spark-master:7077 --version` exits 0 [LLD §6.1]
"""

    def _build_dir(self, tmp_path, build_body, bootstrap_body):
        from conftest import VALID_BACKLOG, VALID_EPIC

        stories_dir = tmp_path / "stories"
        stories_dir.mkdir()
        (stories_dir / "BACKLOG-2026-04-26-test.md").write_text(VALID_BACKLOG, encoding="utf-8")
        epic_dir = stories_dir / "EPIC-01-test"
        epic_dir.mkdir()
        (epic_dir / "EPIC-01.md").write_text(VALID_EPIC, encoding="utf-8")
        (epic_dir / "STORY-01-006-bootstrap.md").write_text(bootstrap_body, encoding="utf-8")
        (epic_dir / "STORY-02-001-build.md").write_text(build_body, encoding="utf-8")
        return stories_dir

    def test_spark_build_without_spark_bootstrap_fires_critical(self, tmp_path):
        stories_dir = self._build_dir(tmp_path, self.BUILD_WITH_SPARK, self.BOOTSTRAP_WITHOUT_SPARK)
        report = validate_stories_dir(stories_dir)
        msgs = [r.message for r in report.results if r.level == ValidationLevel.CRITICAL]
        assert any("spark-submit reachability" in m for m in msgs), msgs

    def test_spark_build_with_spark_bootstrap_does_not_fire(self, tmp_path):
        stories_dir = self._build_dir(tmp_path, self.BUILD_WITH_SPARK, self.BOOTSTRAP_WITH_SPARK)
        report = validate_stories_dir(stories_dir)
        msgs = [r.message for r in report.results if r.level == ValidationLevel.CRITICAL]
        assert not any("spark-submit reachability" in m for m in msgs), msgs

    def test_no_spark_build_does_not_require_spark_bootstrap(self, tmp_path):
        stories_dir = self._build_dir(
            tmp_path, self.BUILD_WITHOUT_SPARK, self.BOOTSTRAP_WITHOUT_SPARK
        )
        report = validate_stories_dir(stories_dir)
        msgs = [r.message for r in report.results if r.level == ValidationLevel.CRITICAL]
        assert not any("spark-submit reachability" in m for m in msgs), msgs

    def test_pyspark_import_in_build_triggers_rule(self, tmp_path):
        body = (
            "# STORY-02-001\n\n| Field | Value |\n|---|---|\n| **Story Type** | build |\n\n"
            "## Acceptance Criteria\n- [ ] Worker `import pyspark` succeeds [LLD §6.1]\n"
        )
        stories_dir = self._build_dir(tmp_path, body, self.BOOTSTRAP_WITHOUT_SPARK)
        report = validate_stories_dir(stories_dir)
        msgs = [r.message for r in report.results if r.level == ValidationLevel.CRITICAL]
        assert any("spark-submit reachability" in m for m in msgs), msgs


class TestAcContradictionRule:
    """STORIES-AC-CONTRADICTION-001 — grep vs grep_absent on same file/pattern, same LLD §, no Depends-On."""

    def _bootstrap_story(self, dependencies: str = "STORY-01-006") -> str:
        return f"""# STORY-02-001: bootstrap soft-import

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02 |
| **Story Type** | build |
| **Dependencies** | {dependencies} |
| **Status** | To Do |

## Acceptance Criteria
- [ ] Runner soft-imports `se_runner` and logs `WARNING: se_runner not available` [LLD §8.6]

## Verification

```yaml
AC1:
  - grep: {{file: "src/p/bronze/runner.py", pattern: "WARNING: se_runner not available"}}
```
"""

    def _fail_closed_story(self, dependencies: str = "None") -> str:
        return f"""# STORY-02-004: fail-closed se_runner

| Field | Value |
|-------|-------|
| **Epic** | EPIC-02 |
| **Story Type** | build |
| **Dependencies** | {dependencies} |
| **Status** | To Do |

## Acceptance Criteria
- [ ] No soft-import; fail-closed if se_runner missing [LLD §8.6]

## Verification

```yaml
AC1:
  - grep_absent: {{file: "src/p/bronze/runner.py", pattern: "WARNING: se_runner not available"}}
```
"""

    _RUNTIME_BOOTSTRAP_STUB = """# STORY-01-006: runtime bootstrap

| Field | Value |
|-------|-------|
| **Story Type** | runtime-bootstrap |
| **Dependencies** | None |
| **Status** | To Do |

## Acceptance Criteria
- [ ] `make dev-up` succeeds [LLD §1]
"""

    def _build_dir(self, tmp_path, *, fail_closed_deps: str) -> Path:
        from conftest import VALID_BACKLOG, VALID_EPIC

        stories_dir = tmp_path / "stories"
        stories_dir.mkdir()
        (stories_dir / "BACKLOG-2026-04-26-test.md").write_text(VALID_BACKLOG, encoding="utf-8")
        epic_dir = stories_dir / "EPIC-02-bronze-ingestion"
        epic_dir.mkdir()
        (epic_dir / "EPIC-02.md").write_text(VALID_EPIC, encoding="utf-8")
        # Runtime-bootstrap stub satisfies BOOTSTRAP-001 without any grep
        # that could collide with STORY-02-004's grep_absent.
        (epic_dir / "STORY-01-006-runtime-bootstrap.md").write_text(
            self._RUNTIME_BOOTSTRAP_STUB, encoding="utf-8"
        )
        (epic_dir / "STORY-02-001-bootstrap-runner.md").write_text(
            self._bootstrap_story(), encoding="utf-8"
        )
        (epic_dir / "STORY-02-004-fail-closed.md").write_text(
            self._fail_closed_story(dependencies=fail_closed_deps), encoding="utf-8"
        )
        return stories_dir

    def test_grep_vs_grep_absent_same_section_no_depends_fires_critical(self, tmp_path):
        # fail-closed story has Dependencies = "None" — no edge to bootstrap.
        stories_dir = self._build_dir(tmp_path, fail_closed_deps="None")
        report = validate_stories_dir(stories_dir)
        msgs = [r.message for r in report.results if r.level == ValidationLevel.CRITICAL]
        assert any("AC contradiction" in m for m in msgs), msgs

    def test_grep_vs_grep_absent_with_depends_on_passes(self, tmp_path):
        stories_dir = self._build_dir(tmp_path, fail_closed_deps="STORY-02-001")
        report = validate_stories_dir(stories_dir)
        msgs = [r.message for r in report.results if r.level == ValidationLevel.CRITICAL]
        assert not any("AC contradiction" in m for m in msgs), msgs

    def test_different_lld_sections_does_not_fire(self, tmp_path):
        from conftest import VALID_BACKLOG, VALID_EPIC

        bootstrap = """# STORY-02-001
| Field | Value |
|---|---|
| **Story Type** | build |
| **Dependencies** | None |
| **Status** | To Do |
## Acceptance Criteria
- [ ] grep WARNING [LLD §8.6]
## Verification
```yaml
AC1:
  - grep: {file: "src/p/bronze/runner.py", pattern: "WARNING: se_runner not available"}
```
"""
        # fail-closed cites a DIFFERENT LLD section (§5.4 instead of §8.6)
        fail_closed = """# STORY-02-004
| Field | Value |
|---|---|
| **Story Type** | build |
| **Dependencies** | None |
| **Status** | To Do |
## Acceptance Criteria
- [ ] grep_absent WARNING [LLD §5.4]
## Verification
```yaml
AC1:
  - grep_absent: {file: "src/p/bronze/runner.py", pattern: "WARNING: se_runner not available"}
```
"""
        stories_dir = tmp_path / "stories"
        stories_dir.mkdir()
        (stories_dir / "BACKLOG-2026-04-26-test.md").write_text(VALID_BACKLOG, encoding="utf-8")
        epic_dir = stories_dir / "EPIC-02-test"
        epic_dir.mkdir()
        (epic_dir / "EPIC-02.md").write_text(VALID_EPIC, encoding="utf-8")
        (epic_dir / "STORY-01-006-bootstrap.md").write_text(bootstrap, encoding="utf-8")
        (epic_dir / "STORY-02-001-build.md").write_text(bootstrap, encoding="utf-8")
        (epic_dir / "STORY-02-004-fail-closed.md").write_text(fail_closed, encoding="utf-8")
        report = validate_stories_dir(stories_dir)
        msgs = [r.message for r in report.results if r.level == ValidationLevel.CRITICAL]
        assert not any("AC contradiction" in m for m in msgs), msgs

    def test_different_target_files_does_not_fire(self, tmp_path):
        """Same pattern, but on different files — not a contradiction."""
        from conftest import VALID_BACKLOG, VALID_EPIC

        bootstrap = """# STORY-02-001
| Field | Value |
|---|---|
| **Story Type** | build |
| **Dependencies** | None |
| **Status** | To Do |
## Acceptance Criteria
- [ ] grep [LLD §8.6]
## Verification
```yaml
AC1:
  - grep: {file: "src/p/bronze/runner.py", pattern: "WARNING"}
```
"""
        fail_closed = """# STORY-02-004
| Field | Value |
|---|---|
| **Story Type** | build |
| **Dependencies** | None |
| **Status** | To Do |
## Acceptance Criteria
- [ ] grep_absent [LLD §8.6]
## Verification
```yaml
AC1:
  - grep_absent: {file: "src/p/silver/transform.py", pattern: "WARNING"}
```
"""
        stories_dir = tmp_path / "stories"
        stories_dir.mkdir()
        (stories_dir / "BACKLOG-2026-04-26-test.md").write_text(VALID_BACKLOG, encoding="utf-8")
        epic_dir = stories_dir / "EPIC-02-test"
        epic_dir.mkdir()
        (epic_dir / "EPIC-02.md").write_text(VALID_EPIC, encoding="utf-8")
        (epic_dir / "STORY-01-006-bootstrap.md").write_text(bootstrap, encoding="utf-8")
        (epic_dir / "STORY-02-001-build.md").write_text(bootstrap, encoding="utf-8")
        (epic_dir / "STORY-02-004-fail-closed.md").write_text(fail_closed, encoding="utf-8")
        report = validate_stories_dir(stories_dir)
        msgs = [r.message for r in report.results if r.level == ValidationLevel.CRITICAL]
        assert not any("AC contradiction" in m for m in msgs), msgs

    def test_pattern_substring_only_does_not_false_positive(self, tmp_path):
        """grep 'WARNING' vs grep_absent 'WARNING: se_runner not available' — different patterns."""
        from conftest import VALID_BACKLOG, VALID_EPIC

        bootstrap = """# STORY-02-001
| Field | Value |
|---|---|
| **Story Type** | build |
| **Dependencies** | None |
| **Status** | To Do |
## Acceptance Criteria
- [ ] grep [LLD §8.6]
## Verification
```yaml
AC1:
  - grep: {file: "src/p/bronze/runner.py", pattern: "WARNING"}
```
"""
        fail_closed = """# STORY-02-004
| Field | Value |
|---|---|
| **Story Type** | build |
| **Dependencies** | None |
| **Status** | To Do |
## Acceptance Criteria
- [ ] grep_absent [LLD §8.6]
## Verification
```yaml
AC1:
  - grep_absent: {file: "src/p/bronze/runner.py", pattern: "WARNING: se_runner not available"}
```
"""
        stories_dir = tmp_path / "stories"
        stories_dir.mkdir()
        (stories_dir / "BACKLOG-2026-04-26-test.md").write_text(VALID_BACKLOG, encoding="utf-8")
        epic_dir = stories_dir / "EPIC-02-test"
        epic_dir.mkdir()
        (epic_dir / "EPIC-02.md").write_text(VALID_EPIC, encoding="utf-8")
        (epic_dir / "STORY-01-006-bootstrap.md").write_text(bootstrap, encoding="utf-8")
        (epic_dir / "STORY-02-001-build.md").write_text(bootstrap, encoding="utf-8")
        (epic_dir / "STORY-02-004-fail-closed.md").write_text(fail_closed, encoding="utf-8")
        report = validate_stories_dir(stories_dir)
        msgs = [r.message for r in report.results if r.level == ValidationLevel.CRITICAL]
        assert not any("AC contradiction" in m for m in msgs), msgs


class TestSeCoverageRule:
    """STORIES-SE-COVERAGE-001 — bootstrap must verify SE runs end-to-end."""

    BUILD_USING_SE = """\
# STORY-02-001: SE-using build

| Field | Value |
|-------|-------|
| **Story Type** | build |

## Acceptance Criteria
- [ ] Runner uses `WrappedDataFrameWriter().with_expectations(...)` per LLD §8.6
"""

    BUILD_NO_SE = """\
# STORY-02-001: contract-only build

| Field | Value |
|-------|-------|
| **Story Type** | build |

## Acceptance Criteria
- [ ] One YAML contract per Bronze table [DMS §3]
"""

    BOOTSTRAP_IMPORT_ONLY = """\
# STORY-01-006: Bootstrap

| Field | Value |
|-------|-------|
| **Story Type** | runtime-bootstrap |

## Acceptance Criteria
- [ ] `python -c "from spark_expectations.core.expectations import SparkExpectations"` exits 0 [LLD §6.1]
"""

    BOOTSTRAP_END_TO_END = """\
# STORY-01-006: Bootstrap

| Field | Value |
|-------|-------|
| **Story Type** | runtime-bootstrap |

## Acceptance Criteria
- [ ] `python -c "from spark_expectations.core.expectations import SparkExpectations"` exits 0 [LLD §6.1]
- [ ] SE end-to-end smoke: pytest -m integration runs `with_expectations(...)` and `bronze_se_stats` has >=1 row [LLD §8.6]
"""

    def _build_dir(self, tmp_path, build_body, bootstrap_body):
        from conftest import VALID_BACKLOG, VALID_EPIC

        stories_dir = tmp_path / "stories"
        stories_dir.mkdir()
        (stories_dir / "BACKLOG-2026-04-26-test.md").write_text(VALID_BACKLOG, encoding="utf-8")
        epic_dir = stories_dir / "EPIC-01-test"
        epic_dir.mkdir()
        (epic_dir / "EPIC-01.md").write_text(VALID_EPIC, encoding="utf-8")
        (epic_dir / "STORY-01-006-bootstrap.md").write_text(bootstrap_body, encoding="utf-8")
        (epic_dir / "STORY-02-001-build.md").write_text(build_body, encoding="utf-8")
        return stories_dir

    def test_se_using_build_with_import_only_bootstrap_fires_critical(self, tmp_path):
        stories_dir = self._build_dir(tmp_path, self.BUILD_USING_SE, self.BOOTSTRAP_IMPORT_ONLY)
        report = validate_stories_dir(stories_dir)
        msgs = [r.message for r in report.results if r.level == ValidationLevel.CRITICAL]
        assert any("SE actually runs end-to-end" in m for m in msgs), msgs

    def test_se_using_build_with_end_to_end_bootstrap_passes(self, tmp_path):
        stories_dir = self._build_dir(tmp_path, self.BUILD_USING_SE, self.BOOTSTRAP_END_TO_END)
        report = validate_stories_dir(stories_dir)
        msgs = [r.message for r in report.results if r.level == ValidationLevel.CRITICAL]
        assert not any("SE actually runs end-to-end" in m for m in msgs), msgs

    def test_no_se_build_does_not_require_se_bootstrap(self, tmp_path):
        stories_dir = self._build_dir(tmp_path, self.BUILD_NO_SE, self.BOOTSTRAP_IMPORT_ONLY)
        report = validate_stories_dir(stories_dir)
        msgs = [r.message for r in report.results if r.level == ValidationLevel.CRITICAL]
        assert not any("SE actually runs end-to-end" in m for m in msgs), msgs

    def test_se_runner_reference_triggers_rule(self, tmp_path):
        body = (
            "# STORY-02-001\n\n| Field | Value |\n|---|---|\n| **Story Type** | build |\n\n"
            "## Acceptance Criteria\n- [ ] Calls `se_runner.run_dq(df, ...)` for inline DQ [LLD §2.3]\n"
        )
        stories_dir = self._build_dir(tmp_path, body, self.BOOTSTRAP_IMPORT_ONLY)
        report = validate_stories_dir(stories_dir)
        msgs = [r.message for r in report.results if r.level == ValidationLevel.CRITICAL]
        assert any("SE actually runs end-to-end" in m for m in msgs), msgs


class TestIntegrationSeEvidenceRule:
    """STORIES-INTEGRATION-SE-001 — integration-test stories on layer epics must assert SE artifacts."""

    LAYER_EPIC_LLD51 = """\
# EPIC-02: Bronze Ingestion

| Field | Value |
|-------|-------|
| **LLD Section** | §5.1 Bronze Tasks |

## Objective

Ingest 13 Synthea tables.

## Stories

| ID |
|---|
| STORY-02-007 |
"""

    INTEGRATION_NO_SE_EVIDENCE = """\
# STORY-02-007: Bronze integration test

| Field | Value |
|-------|-------|
| **Story Type** | integration-test |
| **Dependencies** | STORY-02-006 |

## Acceptance Criteria
- [ ] Airflow DAG `bronze_ingestion_v1` triggered against Unity Catalog OSS local [LLD §4.2]
- [ ] All 13 Bronze tables registered in `unity.bronze` [LLD §5.1]

## Verification

```yaml
AC1:
  - pytest: {node: "tests/integration/test_bronze_uc.py::test_dag_triggers", marker: "integration"}
```
"""

    INTEGRATION_WITH_SE_EVIDENCE = """\
# STORY-02-007: Bronze integration test

| Field | Value |
|-------|-------|
| **Story Type** | integration-test |
| **Dependencies** | STORY-02-006 |

## Acceptance Criteria
- [ ] Airflow DAG `bronze_ingestion_v1` triggered against Unity Catalog OSS local [LLD §4.2]
- [ ] All 13 Bronze tables registered in `unity.bronze` [LLD §5.1]
- [ ] `bronze_se_stats` has >=1 row whose `meta_dq_run_id` matches the run [LLD §8.3]

## Verification

```yaml
AC1:
  - pytest: {node: "tests/integration/test_bronze_uc.py::test_dag_triggers", marker: "integration"}
AC2:
  - pytest: {node: "tests/integration/test_bronze_uc.py::test_se_stats_populated", marker: "integration"}
```
"""

    BUILD_PERF = """\
# STORY-02-006: Bronze perf

| Field | Value |
|-------|-------|
| **Story Type** | performance-optimization |

## Acceptance Criteria
- [ ] Shuffle partitions tuned [LLD §6.5]
"""

    def _build_layer_epic(self, tmp_path, integration_body):
        from conftest import VALID_BACKLOG

        stories_dir = tmp_path / "stories"
        stories_dir.mkdir()
        (stories_dir / "BACKLOG-2026-04-26-test.md").write_text(VALID_BACKLOG, encoding="utf-8")
        # EPIC-01 satisfies BOOTSTRAP-001
        epic1 = stories_dir / "EPIC-01-foundation"
        epic1.mkdir()
        (epic1 / "EPIC-01.md").write_text(
            "# EPIC-01\n## Objective\nFoo\n## Stories\n| ID |\n|---|\n",
            encoding="utf-8",
        )
        (epic1 / "STORY-01-006-bootstrap.md").write_text(
            "# STORY-01-006\n| Field | Value |\n|---|---|\n| **Story Type** | runtime-bootstrap |\n\n## Acceptance Criteria\n- [ ] foo\n",
            encoding="utf-8",
        )
        # Layer epic with the integration-test under test
        epic2 = stories_dir / "EPIC-02-bronze"
        epic2.mkdir()
        (epic2 / "EPIC-02.md").write_text(self.LAYER_EPIC_LLD51, encoding="utf-8")
        (epic2 / "STORY-02-006-perf.md").write_text(self.BUILD_PERF, encoding="utf-8")
        (epic2 / "STORY-02-007-integration.md").write_text(integration_body, encoding="utf-8")
        return stories_dir

    def test_integration_without_se_evidence_fires_critical(self, tmp_path):
        stories_dir = self._build_layer_epic(tmp_path, self.INTEGRATION_NO_SE_EVIDENCE)
        report = validate_stories_dir(stories_dir)
        msgs = [r.message for r in report.results if r.level == ValidationLevel.CRITICAL]
        assert any("no AC asserting SE runtime artifacts" in m for m in msgs), msgs

    def test_integration_with_se_evidence_passes(self, tmp_path):
        stories_dir = self._build_layer_epic(tmp_path, self.INTEGRATION_WITH_SE_EVIDENCE)
        report = validate_stories_dir(stories_dir)
        msgs = [r.message for r in report.results if r.level == ValidationLevel.CRITICAL]
        assert not any("no AC asserting SE runtime artifacts" in m for m in msgs), msgs

    def test_pytest_verifier_alone_discharges_rule(self, tmp_path):
        body = """\
# STORY-02-007: Bronze integration test

| Field | Value |
|-------|-------|
| **Story Type** | integration-test |
| **Dependencies** | STORY-02-006 |

## Acceptance Criteria
- [ ] Airflow DAG triggered against Unity Catalog OSS local [LLD §4.2]

## Verification

```yaml
AC1:
  - pytest: {node: "tests/integration/test_bronze_uc.py::test_se_stats_populated", marker: "integration"}
```
"""
        stories_dir = self._build_layer_epic(tmp_path, body)
        report = validate_stories_dir(stories_dir)
        msgs = [r.message for r in report.results if r.level == ValidationLevel.CRITICAL]
        assert not any("no AC asserting SE runtime artifacts" in m for m in msgs), msgs

    def test_non_layer_epic_skipped(self, tmp_path):
        from conftest import VALID_BACKLOG

        stories_dir = tmp_path / "stories"
        stories_dir.mkdir()
        (stories_dir / "BACKLOG-2026-04-26-test.md").write_text(VALID_BACKLOG, encoding="utf-8")
        epic1 = stories_dir / "EPIC-01-foundation"
        epic1.mkdir()
        (epic1 / "EPIC-01.md").write_text(
            "# EPIC-01\n## Objective\nFoo\n## Stories\n| ID |\n|---|\n",
            encoding="utf-8",
        )
        (epic1 / "STORY-01-006-bootstrap.md").write_text(
            "# STORY-01-006\n| Field | Value |\n|---|---|\n| **Story Type** | runtime-bootstrap |\n\n## Acceptance Criteria\n- [ ] foo\n",
            encoding="utf-8",
        )
        epic_release = stories_dir / "EPIC-09-release"
        epic_release.mkdir()
        (epic_release / "EPIC-09.md").write_text(
            "# EPIC-09: Release\n\n| Field | Value |\n|---|---|\n| **Epic Scope** | crosscut |\n\n## Objective\nProd promote.\n## Stories\n| ID |\n|---|\n",
            encoding="utf-8",
        )
        (epic_release / "STORY-09-001-release.md").write_text(
            self.INTEGRATION_NO_SE_EVIDENCE, encoding="utf-8"
        )
        report = validate_stories_dir(stories_dir)
        msgs = [r.message for r in report.results if r.level == ValidationLevel.CRITICAL]
        assert not any("no AC asserting SE runtime artifacts" in m for m in msgs), msgs
