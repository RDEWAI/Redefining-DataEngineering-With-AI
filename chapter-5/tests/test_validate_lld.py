"""Tests for the LLD validator script."""
# ruff: noqa: E501  # test fixtures embed long markdown literals verbatim

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
    check_bronze_uc_wiring,
    check_catalog_config,
    check_dag_definition_exists,
    check_dag_specification,
    check_design_overview,
    check_impl_sequence_exists,
    check_local_executor_mode,
    check_mermaid_export_exists,
    check_metadata,
    check_performance_subsections,
    check_placeholders,
    check_required_sections,
    check_se_version_floor,
    check_uc_decision_log,
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


# --- Chapter-5 specific rule tests --------------------------------------------


class TestCheckLocalExecutorMode:
    """LLD-EXECUTOR-MODE-001 — §6 must declare `local_executor_mode` (CRITICAL)."""

    def test_valid_lld_passes(self):
        sections = parse_lld_sections(VALID_LLD)
        results = check_local_executor_mode(sections)
        assert results == []

    def test_missing_yaml_fails(self):
        sections = {
            "6. Performance & Optimization": (
                "Spark cluster: 4 executors. Target file size 128MB."
            ),
        }
        results = check_local_executor_mode(sections)
        assert len(results) == 1
        assert results[0].level == ValidationLevel.CRITICAL
        assert "local_executor_mode" in results[0].message

    def test_invalid_value_rejected(self):
        sections = {
            "6. Performance & Optimization": (
                "### 6.1\n\n```yaml\nlocal_executor_mode: kubernetes-magic\n```"
            ),
        }
        results = check_local_executor_mode(sections)
        assert len(results) == 1
        assert results[0].level == ValidationLevel.CRITICAL
        assert "kubernetes-magic" in results[0].message

    def test_each_valid_mode_accepted(self):
        for mode in ("in-airflow-local[*]", "sidecar-spark", "external-cluster"):
            sections = {
                "6. Performance & Optimization": (
                    f"### 6.1\n\n```yaml\nlocal_executor_mode: {mode}\n```"
                ),
            }
            assert check_local_executor_mode(sections) == [], f"mode={mode}"

    def test_yaml_value_outside_fenced_block_rejected(self):
        """Bare `local_executor_mode: foo` outside a code fence does NOT count."""
        sections = {
            "6. Performance & Optimization": (
                "Some prose. local_executor_mode: in-airflow-local[*]"
            ),
        }
        results = check_local_executor_mode(sections)
        assert len(results) == 1
        assert results[0].level == ValidationLevel.CRITICAL


class TestCheckPerformanceSubsections:
    """LLD-PERFORMANCE-SUBSECTIONS — §6 should be split into §6.1–§6.5 (WARNING)."""

    def test_valid_lld_has_all_subsections(self):
        sections = parse_lld_sections(VALID_LLD)
        results = check_performance_subsections(sections)
        assert results == []

    def test_missing_subsections_warns(self):
        sections = {
            "6. Performance & Optimization": "Just a paragraph, no subsections.",
        }
        results = check_performance_subsections(sections)
        assert len(results) == 1
        assert results[0].level == ValidationLevel.WARNING
        for num in ("6.1", "6.2", "6.3", "6.4", "6.5"):
            assert num in results[0].message


class TestCheckBronzeUcWiring:
    """LLD-UC-WIRING-001 — Bronze must use UC saveAsTable, not path-based Delta (CRITICAL)."""

    def test_valid_lld_passes(self):
        sections = parse_lld_sections(VALID_LLD)
        results = check_bronze_uc_wiring(sections)
        # VALID_LLD doesn't reference path-based bronze — no fire.
        assert results == []

    def test_path_based_bronze_in_section_2_fires(self):
        sections = {
            "2. Code Architecture": (
                "**Bronze Ingestion Runner**\n"
                "- Output: Delta table written to `warehouse/{env}/bronze/<table>/ds={ds}/`."
            ),
        }
        results = check_bronze_uc_wiring(sections)
        assert len(results) == 1
        assert results[0].level == ValidationLevel.CRITICAL
        assert "Decision 15" in results[0].message

    def test_uc_saveastable_present_passes(self):
        sections = {
            "2. Code Architecture": (
                "**Bronze Ingestion Runner**\n"
                '- Output: Delta table written via `saveAsTable("unity.bronze.<table>")`\n'
                "  with `UCSingleCatalog` Spark session, instead of "
                "`warehouse/{env}/bronze/<table>/`."
            ),
        }
        results = check_bronze_uc_wiring(sections)
        assert results == []

    def test_path_based_bronze_in_section_5_fires(self):
        sections = {
            "5. Task Implementation Details": (
                "| ingest_patients | Bronze | "
                "Output: `warehouse/{env}/bronze/synthea_patients/ds={ds}/` |"
            ),
        }
        results = check_bronze_uc_wiring(sections)
        assert len(results) == 1
        assert results[0].level == ValidationLevel.CRITICAL


class TestCheckCatalogConfig:
    """LLD-CATALOG-CONFIG — §7 should declare UC catalog parameters (WARNING)."""

    def test_valid_lld_has_catalog_block(self):
        sections = parse_lld_sections(VALID_LLD)
        results = check_catalog_config(sections)
        assert results == []

    def test_missing_catalog_keys_warns(self):
        sections = {
            "7. Configuration Schema": (
                "| Parameter | Type | Default |\n"
                "|---|---|---|\n"
                "| schedule_cron | string | 0 2 * * * |"
            ),
        }
        results = check_catalog_config(sections)
        assert len(results) == 1
        assert results[0].level == ValidationLevel.WARNING
        for key in ("catalog_uc_uri", "catalog_bronze_catalog_name", "catalog_bronze_schema"):
            assert key in results[0].message

    def test_dotted_form_also_accepted(self):
        sections = {
            "7. Configuration Schema": (
                "| Parameter | Type | Default |\n"
                "|---|---|---|\n"
                "| catalog.uc_uri | string | http://unity-catalog:8080 |\n"
                "| catalog.bronze_catalog_name | string | unity |\n"
                "| catalog.bronze_schema | string | bronze |"
            ),
        }
        results = check_catalog_config(sections)
        assert results == []


class TestCheckSeVersionFloor:
    """LLD-SE-VERSION-001 — spark-expectations must not be pinned below 2.10 (CRITICAL)."""

    def test_valid_lld_passes(self):
        results = check_se_version_floor(VALID_LLD)
        assert results == []

    def test_pin_below_2_10_fails(self):
        body = "Reference: `spark-expectations==2.6.0` per Nike repo."
        results = check_se_version_floor(body)
        assert len(results) == 1
        assert results[0].level == ValidationLevel.CRITICAL
        assert "2.10" in results[0].message

    def test_pin_at_2_10_passes(self):
        body = "Pinned to `spark-expectations>=2.10.0` for the YAML loader."
        results = check_se_version_floor(body)
        assert results == []

    def test_pin_above_2_10_passes(self):
        body = "Pinned to `spark-expectations==2.11.3` for the YAML loader."
        results = check_se_version_floor(body)
        assert results == []

    def test_underscore_form_also_caught(self):
        body = "spark_expectations==2.6.0"
        results = check_se_version_floor(body)
        assert len(results) == 1


class TestCheckUcDecisionLog:
    """LLD-DECISION-15 — UC-wired Bronze should be recorded in §13 (INFO)."""

    def test_no_uc_reference_no_fire(self):
        sections = {
            "2. Code Architecture": "Bronze writes path-based Delta.",
            "5. Task Implementation Details": "",
            "13. Decision Log": "Decision: Storage Format. Selected Delta.",
        }
        assert check_uc_decision_log(sections) == []

    def test_uc_referenced_no_decision_fires(self):
        sections = {
            "2. Code Architecture": (
                "Bronze runner uses `UCSingleCatalog` + " '`saveAsTable("unity.bronze.<table>")`.'
            ),
            "5. Task Implementation Details": "",
            "13. Decision Log": "Decision: Storage Format. Selected Delta.",
        }
        results = check_uc_decision_log(sections)
        assert len(results) == 1
        assert results[0].level == ValidationLevel.INFO
        assert "Decision 15" in results[0].message

    def test_uc_referenced_decision_recorded_passes(self):
        sections = {
            "2. Code Architecture": ("Bronze runner uses `UCSingleCatalog` + saveAsTable."),
            "5. Task Implementation Details": "",
            "13. Decision Log": (
                "### Decision 15: Bronze UC wiring\n"
                "Selected: UCSingleCatalog + saveAsTable.\n"
                "Rationale: spokane invisible-tables gap."
            ),
        }
        assert check_uc_decision_log(sections) == []
