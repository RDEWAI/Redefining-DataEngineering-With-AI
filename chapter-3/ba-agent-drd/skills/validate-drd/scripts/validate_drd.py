#!/usr/bin/env python3
"""Validate Data Requirements Document (DRD) against completeness and quality standards.

Checks all required sections, metadata, source systems, consumers, SLAs,
and business rules. Reports issues as CRITICAL, WARNING, or INFO.

Usage:
    python validate_drd.py <path-to-drd.md>
    python validate_drd.py --all <directory>
    python validate_drd.py --format json <path-to-drd.md>

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
    """Aggregate validation report for a DRD file."""

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
    "Executive Summary",
    "1. Business Context",
    "2. Source Discovery",
    "3. Data Quality Expectations",
    "4. Consumer Requirements",
    "5. Business Rules",
    "6. Assumptions and Open Questions",
    "7. Regulatory and Compliance",
    "8. Version History",
]

CONTENT_SECTIONS = [
    "2. Source Discovery",
    "3. Data Quality Expectations",
    "4. Consumer Requirements",
    "5. Business Rules",
    "7. Regulatory and Compliance",
]


def parse_drd_sections(content: str) -> dict[str, str]:
    """Parse a DRD markdown file into a dict of section_heading -> section_content."""
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


def _section_has_table_rows(content: str) -> bool:
    """Check if section content contains at least one markdown table data row."""
    lines = content.strip().split("\n")
    table_rows = [
        ln
        for ln in lines
        if ln.strip().startswith("|")
        and not ln.strip().startswith("| ---")
        and not ln.strip().startswith("|---")
        and not all(c in "|- " for c in ln.strip())
    ]
    # Exclude header row (first table row) — need at least 2 pipe-rows
    return len(table_rows) >= 2


def _section_has_content_beyond_headings(content: str) -> bool:
    """Check if section has meaningful content beyond sub-headings and whitespace."""
    lines = content.strip().split("\n")
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
            return True
    return False


def _subsection_content(sections: dict[str, str], parent: str, sub: str) -> str | None:
    """Extract subsection content from within a parent section."""
    parent_content = sections.get(parent, "")
    if not parent_content:
        return None
    # Split the parent section on ### headings and find the matching subsection
    parts = re.split(r"(?m)^###\s+", parent_content)
    for part in parts:
        # Each part starts with the heading text (after ### was stripped)
        if part.startswith(sub) or sub in part.split("\n")[0]:
            # Return everything after the heading line
            lines = part.split("\n", 1)
            if len(lines) > 1:
                return lines[1].strip()
            return ""
    return None


def _find_subsection(sections: dict[str, str], parent: str, *names: str) -> str | None:
    """Try multiple subsection names under a parent, returning the first match."""
    for name in names:
        sub = _subsection_content(sections, parent, name)
        if sub is not None:
            return sub
    return None


# --- CRITICAL checks ---


def check_required_sections(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that all 9 required top-level sections exist."""
    results: list[ValidationResult] = []
    for section in REQUIRED_SECTIONS:
        if section not in sections:
            results.append(
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    section=section,
                    message=f'Required section "{section}" is missing.',
                    suggestion=f'Add a "## {section}" section to the DRD.',
                )
            )
    return results


def check_version_metadata(content: str) -> list[ValidationResult]:
    """Check that version metadata fields are present and non-empty."""
    results: list[ValidationResult] = []
    required_fields = ["Version", "Created", "Author", "Status"]
    for field_name in required_fields:
        pattern = rf"\*\*{field_name}\*\*\s*\|\s*(.+)"
        match = re.search(pattern, content)
        if not match or not match.group(1).strip():
            results.append(
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    section="Metadata",
                    message=f'Metadata field "{field_name}" is missing or empty.',
                    suggestion=f'Add a "{field_name}" field to the metadata table at the top of the DRD.',
                )
            )
    return results


def check_source_systems(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that at least one source system is documented in section 2.1."""
    results: list[ValidationResult] = []
    sub = _subsection_content(sections, "2. Source Discovery", "2.1 Source Systems")
    if sub is None or not sub.strip():
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="2.1 Source Systems",
                message="No source systems are documented.",
                suggestion="Add at least one source system with its type, owner, and access method.",
            )
        )
    elif "####" not in sub and not _section_has_table_rows(sub):
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="2.1 Source Systems",
                message="Source systems section has no system entries.",
                suggestion="Document each source system with a #### heading or table row.",
            )
        )
    return results


def check_consumers(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that at least one data consumer is documented in section 4.1."""
    results: list[ValidationResult] = []
    sub = _subsection_content(sections, "4. Consumer Requirements", "4.1 Data Consumers")
    if sub is None or not sub.strip():
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="4.1 Data Consumers",
                message="No data consumers are documented.",
                suggestion="Add at least one data consumer with department, use case, and access pattern.",
            )
        )
    elif not _section_has_table_rows(sub):
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="4.1 Data Consumers",
                message="Data consumers section has no consumer entries.",
                suggestion="Add consumer rows to the table in section 4.1.",
            )
        )
    return results


def check_no_empty_sections(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that content sections (2-5) have meaningful content."""
    results: list[ValidationResult] = []
    for section in CONTENT_SECTIONS:
        content = sections.get(section, "")
        if not _section_has_content_beyond_headings(content):
            results.append(
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    section=section,
                    message=f'Section "{section}" is empty or contains only headings.',
                    suggestion=f"Populate this section with the relevant requirements and details.",
                )
            )
    return results


# --- WARNING checks ---


def check_sla_defined(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that at least one SLA is defined in section 4.3."""
    results: list[ValidationResult] = []
    sub = _find_subsection(
        sections, "4. Consumer Requirements",
        "4.3 Service Level Agreements", "4.3 Service Level",
    )
    if sub is None or not _section_has_table_rows(sub or ""):
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="4.3 Service Level Agreements",
                message="No SLAs are defined.",
                suggestion="Define at least one SLA with target, measurement method, and escalation path.",
            )
        )
    return results


def check_critical_fields(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that at least one critical field is identified in section 3.1."""
    results: list[ValidationResult] = []
    sub = _subsection_content(sections, "3. Data Quality Expectations", "3.1 Critical Fields")
    if sub is None or not _section_has_table_rows(sub or ""):
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="3.1 Critical Fields",
                message="No critical fields are identified.",
                suggestion="Identify fields that are essential for the system to function correctly.",
            )
        )
    return results


def check_business_rules(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that at least one calculation or derivation is documented in section 5.2."""
    results: list[ValidationResult] = []
    sub = _find_subsection(
        sections, "5. Business Rules",
        "5.2 Calculations and Derivations", "5.2 Calculations",
    )
    if sub is None or not sub.strip() or len(sub.strip()) < 20:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="5.2 Calculations and Derivations",
                message="No calculations or derivations are documented.",
                suggestion="Document at least one derived field with its formula, inputs, and business purpose.",
            )
        )
    return results


def check_freshness(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that freshness requirements are defined in section 4.4."""
    results: list[ValidationResult] = []
    sub = _find_subsection(
        sections, "4. Consumer Requirements",
        "4.4 Data Freshness", "4.4 Data Freshness Requirements",
    )
    if sub is None or not _section_has_table_rows(sub or ""):
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="4.4 Data Freshness Requirements",
                message="No data freshness requirements are defined.",
                suggestion="Specify maximum acceptable latency and refresh cadence per consumer.",
            )
        )
    return results


def check_open_questions(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that open questions section exists (even if empty)."""
    results: list[ValidationResult] = []
    section_content = sections.get("6. Assumptions and Open Questions", "")
    if "6.2" not in section_content and "Open Questions" not in section_content:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="6.2 Open Questions",
                message="Open questions subsection is missing.",
                suggestion="Add a 6.2 Open Questions subsection to track unresolved items.",
            )
        )
    return results


def check_tolerances(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that tolerance thresholds are defined in section 3.4."""
    results: list[ValidationResult] = []
    sub = _subsection_content(
        sections, "3. Data Quality Expectations", "3.4 Tolerance Thresholds"
    )
    if sub is None or not _section_has_table_rows(sub or ""):
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="3.4 Tolerance Thresholds",
                message="No tolerance thresholds are defined.",
                suggestion="Define acceptable thresholds for data quality metrics.",
            )
        )
    return results


def check_regulatory_compliance(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that at least one regulation is documented in section 7.1."""
    results: list[ValidationResult] = []
    sub = _subsection_content(
        sections, "7. Regulatory and Compliance", "7.1 Applicable Regulations"
    )
    if sub is None or not _section_has_table_rows(sub or ""):
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="7.1 Applicable Regulations",
                message="No applicable regulations are documented.",
                suggestion="Identify regulations that apply (e.g., HIPAA, GDPR) with scope and impact on data design.",
            )
        )
    return results


# --- INFO checks ---


def check_placeholders(content: str) -> list[ValidationResult]:
    """Warn about remaining placeholder text."""
    results: list[ValidationResult] = []
    placeholders = re.findall(
        r"\[(TO BE DETERMINED|NEEDS VERIFICATION|TBD)[^\]]*\]", content, re.IGNORECASE
    )
    if placeholders:
        results.append(
            ValidationResult(
                level=ValidationLevel.INFO,
                section="General",
                message=f"Found {len(placeholders)} placeholder(s) that need to be resolved.",
                suggestion="Replace placeholder text with actual requirements or mark as open questions.",
            )
        )
    return results


def check_approval(sections: dict[str, str]) -> list[ValidationResult]:
    """Suggest adding approvals if section 9 is empty or missing."""
    results: list[ValidationResult] = []
    approval_content = sections.get("9. Approval", "")
    if not approval_content or not _section_has_table_rows(approval_content):
        results.append(
            ValidationResult(
                level=ValidationLevel.INFO,
                section="9. Approval",
                message="Approval section is empty or has no signatories.",
                suggestion="Add stakeholder names and roles for sign-off when ready for review.",
            )
        )
    return results


def check_edge_cases(sections: dict[str, str]) -> list[ValidationResult]:
    """Suggest documenting edge cases if section 5.4 is empty."""
    results: list[ValidationResult] = []
    sub = _find_subsection(
        sections, "5. Business Rules",
        "5.4 Edge Cases", "5.4 Edge Cases and Exceptions",
    )
    if sub is None or not sub.strip() or len(sub.strip()) < 20:
        results.append(
            ValidationResult(
                level=ValidationLevel.INFO,
                section="5.4 Edge Cases and Exceptions",
                message="No edge cases are documented.",
                suggestion="Document known edge cases with expected behavior and rationale.",
            )
        )
    return results


# --- Main validation ---


def validate_drd(file_path: Path) -> ValidationReport:
    """Run all validation checks on a DRD file."""
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

    sections = parse_drd_sections(content)

    # CRITICAL checks
    report.results.extend(check_required_sections(sections))
    report.results.extend(check_version_metadata(content))
    report.results.extend(check_source_systems(sections))
    report.results.extend(check_consumers(sections))
    report.results.extend(check_no_empty_sections(sections))

    # WARNING checks
    report.results.extend(check_sla_defined(sections))
    report.results.extend(check_critical_fields(sections))
    report.results.extend(check_business_rules(sections))
    report.results.extend(check_freshness(sections))
    report.results.extend(check_open_questions(sections))
    report.results.extend(check_tolerances(sections))
    report.results.extend(check_regulatory_compliance(sections))

    # INFO checks
    report.results.extend(check_placeholders(content))
    report.results.extend(check_approval(sections))
    report.results.extend(check_edge_cases(sections))

    return report


def print_report(report: ValidationReport) -> None:
    """Print a formatted validation report to stdout."""
    print(f"\n{'=' * 70}")
    print(f"DRD Validation Report: {report.file_path}")
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

    print(f"  Summary: {report.critical_count} critical, {report.warning_count} warnings, {report.info_count} info")
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
        description="Validate Data Requirements Document (DRD)",
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Path to DRD file or directory (with --all)",
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
        report = validate_drd(file_path)

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
