#!/usr/bin/env python3
"""Validate Low-Level Design (LLD) against completeness and quality standards.

Checks all required sections, metadata, DAG specification, code architecture,
configuration schema, upstream artifact references, and traceability. Reports
issues as CRITICAL, WARNING, or INFO.

Usage:
    python validate_lld.py <path-to-lld.md>
    python validate_lld.py --all <directory>
    python validate_lld.py --format json <path-to-lld.md>

Exit Codes:
    0: All validations passed (may have INFO items)
    1: Critical issues found
    2: Warning issues found (no criticals)
    3: File not found or parse error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ValidationLevel(Enum):
    """Severity level for validation findings."""

    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class ValidationResult:
    """A single validation finding."""

    level: ValidationLevel
    section: str
    message: str
    suggestion: str


@dataclass
class ValidationReport:
    """Aggregate validation report for an LLD file."""

    file_path: str
    results: list[ValidationResult] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for r in self.results if r.level == ValidationLevel.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for r in self.results if r.level == ValidationLevel.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for r in self.results if r.level == ValidationLevel.INFO)

    @property
    def passed(self) -> bool:
        return self.critical_count == 0 and self.warning_count == 0


REQUIRED_SECTIONS = [
    "1. Design Overview",
    "2. Code Architecture",
    "3. File Formats & Storage Layout",
    "4. DAG Specification",
    "5. Task Implementation Details",
    "6. Performance & Optimization",
    "7. Configuration Schema",
    "8. Error Handling",
    "9. Deployment",
    "10. Monitoring",
    "11. Upstream Artifact References",
    "12. Traceability Matrix",
    "13. Decision Log",
    "14. Version History",
]


def parse_lld_sections(content: str) -> dict[str, str]:
    """Parse an LLD markdown file into a dict of section_heading -> section_content."""
    sections: dict[str, str] = {}
    current_heading = ""
    current_lines: list[str] = []

    for line in content.split("\n"):
        if line.startswith("## "):
            if current_heading:
                sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = line.lstrip("# ").strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_heading:
        sections[current_heading] = "\n".join(current_lines).strip()

    return sections


def _has_table_rows(content: str, min_rows: int = 1) -> bool:
    """Check if content has a markdown table with at least min_rows data rows."""
    lines = content.strip().split("\n")
    table_rows = [
        ln
        for ln in lines
        if ln.strip().startswith("|")
        and not ln.strip().startswith("| ---")
        and not ln.strip().startswith("|---")
        and not all(c in "|- " for c in ln.strip())
    ]
    # Subtract 1 for header row
    data_rows = max(0, len(table_rows) - 1)
    return data_rows >= min_rows


# --- CRITICAL checks ---


def check_required_sections(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that all 14 required top-level sections exist."""
    results: list[ValidationResult] = []
    for section in REQUIRED_SECTIONS:
        if section not in sections:
            results.append(
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    section=section,
                    message=f'Required section "{section}" is missing.',
                    suggestion=f'Add a "## {section}" section to the LLD.',
                )
            )
    return results


VALID_STATUSES = {"Draft", "Updated - Pending Review", "Approved"}


def check_metadata(content: str) -> list[ValidationResult]:
    """Check that version metadata fields are present and non-empty."""
    results: list[ValidationResult] = []
    required_fields = [
        "Version",
        "Created",
        "Author",
        "Status",
        "DRD Reference",
        "HLD Reference",
        "DMS Reference",
        "STM Reference",
        "DQS Reference",
    ]
    for field_name in required_fields:
        pattern = rf"\*\*{re.escape(field_name)}\*\*\s*\|\s*(.+)"
        match = re.search(pattern, content)
        if not match or not match.group(1).strip():
            results.append(
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    section="Metadata",
                    message=f'Metadata field "{field_name}" is missing or empty.',
                    suggestion=(
                        f'Add a "{field_name}" field to the metadata table at the top of the LLD.'
                    ),
                )
            )
    # Validate Status field value
    status_pattern = r"\*\*Status\*\*\s*\|\s*(.+)"
    status_match = re.search(status_pattern, content)
    if status_match:
        status_value = status_match.group(1).strip().rstrip("|").strip()
        if status_value not in VALID_STATUSES:
            results.append(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    section="Metadata",
                    message=f'Status field has unrecognized value: "{status_value}".',
                    suggestion=(
                        "Status must be one of: " + ", ".join(sorted(VALID_STATUSES)) + "."
                    ),
                )
            )
    return results


def check_design_overview(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that Design Overview exists and has meaningful content (>=2 sentences)."""
    results: list[ValidationResult] = []
    content = sections.get("1. Design Overview", "")

    if not content or not content.strip():
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="1. Design Overview",
                message="Design Overview section is missing or empty.",
                suggestion=(
                    "Add a 3-5 sentence overview covering the implementation approach,"
                    " key technology choices, and pipeline architecture."
                ),
            )
        )
        return results

    sentences = re.findall(r"[.!?](?:\s|$)", content)
    if len(sentences) < 2:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="1. Design Overview",
                message=(
                    f"Design Overview has only {len(sentences)} sentence(s);"
                    " at least 2 required."
                ),
                suggestion=(
                    "Expand the Design Overview to at least 3-5 sentences"
                    " covering implementation approach, DAG strategy, and key decisions."
                ),
            )
        )
    return results


def check_dag_specification(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that DAG Specification has a task table with >=3 data rows."""
    results: list[ValidationResult] = []
    section_key = "4. DAG Specification"
    content = sections.get(section_key, "")

    if not content:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section=section_key,
                message="DAG Specification section is empty.",
                suggestion=(
                    "Add task inventory table, dependency graph (Mermaid),"
                    " scheduling details, and critical path analysis."
                ),
            )
        )
        return results

    if not _has_table_rows(content, 3):
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section=section_key,
                message=("DAG Specification has fewer than 3 task rows;" " at least 3 required."),
                suggestion=(
                    "Add rows for all pipeline tasks: ingestion, transformation,"
                    " denormalization, and DQ validation tasks."
                ),
            )
        )
    return results


def check_task_implementation(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that Task Implementation Details section has per-task specs."""
    results: list[ValidationResult] = []
    section_key = "5. Task Implementation Details"
    content = sections.get(section_key, "")

    if not content:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section=section_key,
                message="Task Implementation Details section is empty.",
                suggestion=(
                    "Add per-task implementation details with input/output paths,"
                    " transformation references (DMS/STM), and DQ checks (DQS)."
                ),
            )
        )
        return results

    if not _has_table_rows(content, 3):
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section=section_key,
                message="Task Implementation section needs a table with at least 3 task rows.",
                suggestion=(
                    "Add a table with columns: Task | Input | Output | Transform Ref | DQ Check."
                ),
            )
        )
    return results


def check_configuration_schema(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that Configuration Schema has a parameter table."""
    results: list[ValidationResult] = []
    section_key = "7. Configuration Schema"
    content = sections.get(section_key, "")

    if not content:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section=section_key,
                message="Configuration Schema section is empty.",
                suggestion=(
                    "Add a parameter inventory table with columns:"
                    " Parameter | Type | Default | Description | Per-Environment."
                ),
            )
        )
        return results

    if not _has_table_rows(content, 3):
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section=section_key,
                message="Configuration Schema has fewer than 3 parameter rows.",
                suggestion=(
                    "Add rows for key parameters: scheduling, compute resources,"
                    " storage paths, retry settings, and alerting channels."
                ),
            )
        )
    return results


def check_upstream_references(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that Upstream Artifact References cites all 5 upstream docs."""
    results: list[ValidationResult] = []
    section_key = "11. Upstream Artifact References"
    content = sections.get(section_key, "")

    if not content:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section=section_key,
                message="Upstream Artifact References section is empty.",
                suggestion=(
                    "Add a cross-reference table mapping topics to upstream"
                    " artifacts (DRD, HLD, DMS, STM, DQS) with section numbers."
                ),
            )
        )
        return results

    required_refs = ["DRD", "HLD", "DMS", "STM", "DQS"]
    for ref in required_refs:
        if ref not in content:
            results.append(
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    section=section_key,
                    message=f"{ref} is not referenced in Upstream Artifact References.",
                    suggestion=f"Add a row referencing the {ref} with specific section numbers.",
                )
            )
    return results


# --- WARNING checks ---


def check_upstream_traceability(content: str) -> list[ValidationResult]:
    """Check that upstream artifacts are cited at least 5 times throughout the LLD."""
    results: list[ValidationResult] = []
    ref_count = len(re.findall(r"\b(DRD|HLD|DMS|STM|DQS)\s*§", content))
    if ref_count < 5:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="General",
                message=(
                    f"Upstream artifacts cited with section refs only {ref_count} time(s);"
                    " at least 5 citations required for traceability."
                ),
                suggestion=(
                    "Add [HLD §X.Y], [DMS §X.Y], [STM Tab:name], [DQS §X.Y],"
                    " or [DRD §X.Y] citations throughout the LLD."
                ),
            )
        )
    return results


def check_error_handling(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that Error Handling mentions retry, dead letter, and alerting."""
    results: list[ValidationResult] = []
    section_key = "8. Error Handling"
    content = sections.get(section_key, "")

    if not content:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section=section_key,
                message="Error Handling section is empty.",
                suggestion=(
                    "Add retry policies, dead letter queue strategy," " and alerting thresholds."
                ),
            )
        )
        return results

    has_retry = bool(re.search(r"\bretry\b", content, re.IGNORECASE))
    has_dlq = bool(re.search(r"\b(dead.letter|quarantine|DLQ)\b", content, re.IGNORECASE))
    has_alert = bool(re.search(r"\balert\b", content, re.IGNORECASE))

    missing = []
    if not has_retry:
        missing.append("retry policies")
    if not has_dlq:
        missing.append("dead letter/quarantine")
    if not has_alert:
        missing.append("alerting")

    if missing:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section=section_key,
                message=f"Error Handling is missing: {', '.join(missing)}.",
                suggestion="Add retry policies, dead letter queue handling, and alerting setup.",
            )
        )
    return results


def check_deployment_environments(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that Deployment mentions DEV and PROD environments."""
    results: list[ValidationResult] = []
    section_key = "9. Deployment"
    content = sections.get(section_key, "")

    if not content:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section=section_key,
                message="Deployment section is empty.",
                suggestion=(
                    "Add environment definitions (DEV, STAGING, PROD),"
                    " promotion strategy, and rollback procedures."
                ),
            )
        )
        return results

    has_dev = bool(re.search(r"\bDEV\b", content))
    has_prod = bool(re.search(r"\bPROD\b", content))

    if not has_dev or not has_prod:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section=section_key,
                message="Deployment does not mention both DEV and PROD environments.",
                suggestion=(
                    "Add environment-specific deployment details" " for DEV, STAGING, and PROD."
                ),
            )
        )
    return results


def check_monitoring_metrics(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that Monitoring has specific metric names or a metrics table."""
    results: list[ValidationResult] = []
    section_key = "10. Monitoring"
    content = sections.get(section_key, "")

    if not content:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section=section_key,
                message="Monitoring section is empty.",
                suggestion="Add metrics to collect, dashboard specs, and alerting rules.",
            )
        )
        return results

    has_metrics = _has_table_rows(content, 1) or bool(
        re.search(r"\b(metric|latency|throughput|duration|SLA)\b", content, re.IGNORECASE)
    )
    if not has_metrics:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section=section_key,
                message="Monitoring section has no specific metrics or metrics table.",
                suggestion=(
                    "Add a metrics table with: metric name, type, collection method,"
                    " and alerting threshold."
                ),
            )
        )
    return results


def check_mermaid_diagram(content: str) -> list[ValidationResult]:
    """Check that at least 1 Mermaid diagram is present (for DAG visualization)."""
    results: list[ValidationResult] = []
    mermaid_count = len(re.findall(r"```mermaid", content))
    if mermaid_count == 0:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="4. DAG Specification",
                message="No Mermaid diagrams found for DAG visualization.",
                suggestion=(
                    "Add a Mermaid flowchart or graph diagram showing"
                    " task dependencies and critical path."
                ),
            )
        )
    return results


def check_decision_documentation(content: str) -> list[ValidationResult]:
    """Check that Decision Log uses Options Considered / Rationale format."""
    results: list[ValidationResult] = []

    has_options = bool(re.search(r"Options Considered", content, re.IGNORECASE))
    has_rationale = bool(re.search(r"\bRationale\b", content))

    if not has_options or not has_rationale:
        missing = []
        if not has_options:
            missing.append('"Options Considered"')
        if not has_rationale:
            missing.append('"Rationale"')
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="13. Decision Log",
                message=f"Decision documentation is incomplete — missing: {', '.join(missing)}.",
                suggestion=(
                    "Use the standard decision format: Options Considered,"
                    " Selected, Rationale, Trade-off for each major decision."
                ),
            )
        )
    return results


def check_performance_numerics(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that Performance section has numeric values."""
    results: list[ValidationResult] = []
    section_key = "6. Performance & Optimization"
    content = sections.get(section_key, "")

    if not content:
        return results

    has_numeric = bool(
        re.search(
            r"\d[\d,]*\s*(MB|GB|TB|ms|seconds?|minutes?|partitions?|cores?|executors?)\b",
            content,
            re.IGNORECASE,
        )
    )
    if not has_numeric:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section=section_key,
                message="Performance section has no numeric values (MB, GB, seconds, partitions).",
                suggestion=(
                    "Add specific numbers: memory allocations, partition counts,"
                    " target durations, and parallelism settings."
                ),
            )
        )
    return results


# --- INFO checks ---


def check_placeholders(content: str) -> list[ValidationResult]:
    """Warn about remaining placeholder text."""
    results: list[ValidationResult] = []
    placeholders = re.findall(r"\[(TBD|TODO|TO BE DETERMINED)[^\]]*\]", content, re.IGNORECASE)
    if placeholders:
        results.append(
            ValidationResult(
                level=ValidationLevel.INFO,
                section="General",
                message=f"Found {len(placeholders)} placeholder(s) that need to be resolved.",
                suggestion=(
                    "Replace placeholder text with actual implementation decisions"
                    " or add to Decision Log with an owner and due date."
                ),
            )
        )
    return results


def check_rollback(sections: dict[str, str]) -> list[ValidationResult]:
    """Check if Deployment section mentions rollback."""
    results: list[ValidationResult] = []
    content = sections.get("9. Deployment", "")
    if content and not re.search(r"\brollback\b", content, re.IGNORECASE):
        results.append(
            ValidationResult(
                level=ValidationLevel.INFO,
                section="9. Deployment",
                message="Deployment section does not mention rollback procedures.",
                suggestion=(
                    "Add rollback strategy including detection," " revert, and notification steps."
                ),
            )
        )
    return results


def check_critical_path(sections: dict[str, str]) -> list[ValidationResult]:
    """Check if DAG section mentions critical path."""
    results: list[ValidationResult] = []
    content = sections.get("4. DAG Specification", "")
    if content and not re.search(r"critical.path", content, re.IGNORECASE):
        results.append(
            ValidationResult(
                level=ValidationLevel.INFO,
                section="4. DAG Specification",
                message="DAG Specification does not mention critical path.",
                suggestion="Add critical path analysis showing the longest dependency chain.",
            )
        )
    return results


def check_config_template_exists(
    sections: dict[str, str], file_path: Path
) -> list[ValidationResult]:
    """Check if config-template.yaml exists alongside the LLD."""
    results: list[ValidationResult] = []
    config_path = file_path.parent / "config" / "config-template.yaml"
    if not config_path.exists():
        results.append(
            ValidationResult(
                level=ValidationLevel.INFO,
                section="7. Configuration Schema",
                message="No config-template.yaml found alongside the LLD.",
                suggestion=(
                    "Run generate-config-template to create the environment-specific"
                    " config YAML from Section 7."
                ),
            )
        )
    return results


def check_dag_definition_exists(
    sections: dict[str, str], file_path: Path
) -> list[ValidationResult]:
    """Check if dag-definition.yaml exists alongside the LLD."""
    results: list[ValidationResult] = []
    dag_path = file_path.parent / "dag" / "dag-definition.yaml"
    if not dag_path.exists():
        results.append(
            ValidationResult(
                level=ValidationLevel.INFO,
                section="4. DAG Specification",
                message="No dag-definition.yaml found alongside the LLD.",
                suggestion=(
                    "Run generate-dag-definition to create the DAG YAML" " from Section 4."
                ),
            )
        )
    return results


def check_mermaid_export_exists(
    sections: dict[str, str], file_path: Path
) -> list[ValidationResult]:
    """Check if dag-pipeline.mmd exists alongside the LLD."""
    results: list[ValidationResult] = []
    mmd_path = file_path.parent / "dag" / "dag-pipeline.mmd"
    if not mmd_path.exists():
        results.append(
            ValidationResult(
                level=ValidationLevel.INFO,
                section="4. DAG Specification",
                message="No dag-pipeline.mmd found alongside the LLD.",
                suggestion=(
                    "Run generate-dag-definition to export the Mermaid" " diagram from Section 4.3."
                ),
            )
        )
    return results


def check_impl_sequence_exists(sections: dict[str, str], file_path: Path) -> list[ValidationResult]:
    """Check if impl-sequence.md exists alongside the LLD."""
    results: list[ValidationResult] = []
    impl_path = file_path.parent / "impl-sequence.md"
    if not impl_path.exists():
        results.append(
            ValidationResult(
                level=ValidationLevel.INFO,
                section="General",
                message="No impl-sequence.md found alongside the LLD.",
                suggestion=(
                    "Run generate-impl-sequence to create the build"
                    " sequence document from Sections 2, 4, 9, 12."
                ),
            )
        )
    return results


# --- Main validation ---


def validate_lld(file_path: Path) -> ValidationReport:
    """Run all validation checks on an LLD file."""
    report = ValidationReport(file_path=str(file_path))

    try:
        content = file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        report.results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="File",
                message=f"File not found: {file_path}",
                suggestion="Verify the file path is correct.",
            )
        )
        return report
    except Exception as e:
        report.results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="File",
                message=f"Error reading file: {e}",
                suggestion="Check file permissions and encoding.",
            )
        )
        return report

    sections = parse_lld_sections(content)

    # CRITICAL checks
    report.results.extend(check_required_sections(sections))
    report.results.extend(check_metadata(content))
    report.results.extend(check_design_overview(sections))
    report.results.extend(check_dag_specification(sections))
    report.results.extend(check_task_implementation(sections))
    report.results.extend(check_configuration_schema(sections))
    report.results.extend(check_upstream_references(sections))

    # WARNING checks
    report.results.extend(check_upstream_traceability(content))
    report.results.extend(check_error_handling(sections))
    report.results.extend(check_deployment_environments(sections))
    report.results.extend(check_monitoring_metrics(sections))
    report.results.extend(check_mermaid_diagram(content))
    report.results.extend(check_decision_documentation(content))
    report.results.extend(check_performance_numerics(sections))

    # INFO checks
    report.results.extend(check_placeholders(content))
    report.results.extend(check_rollback(sections))
    report.results.extend(check_critical_path(sections))
    report.results.extend(check_config_template_exists(sections, file_path))
    report.results.extend(check_dag_definition_exists(sections, file_path))
    report.results.extend(check_mermaid_export_exists(sections, file_path))
    report.results.extend(check_impl_sequence_exists(sections, file_path))

    return report


def print_report(report: ValidationReport) -> None:
    """Print a formatted validation report to stdout."""
    print(f"\n{'=' * 70}")
    print(f"LLD Validation Report: {report.file_path}")
    print(f"{'=' * 70}\n")

    if not report.results:
        print("  All checks passed. No issues found.\n")
        return

    level_icons = {
        ValidationLevel.CRITICAL: "[CRITICAL]",
        ValidationLevel.WARNING: "[WARNING] ",
        ValidationLevel.INFO: "[INFO]    ",
    }

    for level in [ValidationLevel.CRITICAL, ValidationLevel.WARNING, ValidationLevel.INFO]:
        level_results = [r for r in report.results if r.level == level]
        if level_results:
            print(f"  {level.value} ({len(level_results)})")
            print(f"  {'-' * 40}")
            for result in level_results:
                print(f"  {level_icons[level]} Section: {result.section}")
                print(f"               {result.message}")
                print(f"               Fix: {result.suggestion}")
                print()

    print(
        f"  Summary: {report.critical_count} critical,"
        f" {report.warning_count} warnings,"
        f" {report.info_count} info"
    )
    if report.passed:
        print("  Result: PASSED")
    elif report.critical_count > 0:
        print("  Result: FAILED (critical issues)")
    else:
        print("  Result: PASSED WITH WARNINGS")
    print()


def report_to_json(report: ValidationReport) -> str:
    """Convert report to JSON string."""
    return json.dumps(
        {
            "file": report.file_path,
            "passed": report.passed,
            "critical_count": report.critical_count,
            "warning_count": report.warning_count,
            "info_count": report.info_count,
            "results": [
                {
                    "level": r.level.value,
                    "section": r.section,
                    "message": r.message,
                    "suggestion": r.suggestion,
                }
                for r in report.results
            ],
        },
        indent=2,
    )


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate Low-Level Design (LLD)",
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Path to LLD file or directory (with --all)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all .md files in the given directory",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )

    args = parser.parse_args()

    if args.all:
        if not args.path.is_dir():
            print(f"Error: {args.path} is not a directory.", file=sys.stderr)
            return 3
        files = sorted(args.path.glob("*.md"))
        if not files:
            print(f"No .md files found in {args.path}", file=sys.stderr)
            return 3
    else:
        if not args.path.is_file():
            print(f"Error: {args.path} is not a file.", file=sys.stderr)
            return 3
        files = [args.path]

    worst_exit = 0
    for file_path in files:
        report = validate_lld(file_path)

        if args.format == "json":
            print(report_to_json(report))
        else:
            print_report(report)

        if report.critical_count > 0:
            worst_exit = max(worst_exit, 1)
        elif report.warning_count > 0:
            worst_exit = max(worst_exit, 2)

    return worst_exit


if __name__ == "__main__":
    sys.exit(main())
