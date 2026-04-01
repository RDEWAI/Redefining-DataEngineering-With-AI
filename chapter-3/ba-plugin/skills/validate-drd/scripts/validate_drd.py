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
                    suggestion=(
                        f'Add a "{field_name}" field to the metadata table'
                        " at the top of the DRD."
                    ),
                )
            )
    # Validate Status field value
    status_pattern = r"\*\*Status\*\*\s*\|\s*(.+)"
    status_match = re.search(status_pattern, content)
    if status_match:
        status_value = status_match.group(1).strip().rstrip("|").strip()
        allowed_statuses = {"Draft", "Updated - Pending Review", "Approved"}
        if status_value not in allowed_statuses:
            results.append(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    section="Metadata",
                    message=f'Status field has unrecognized value: "{status_value}".',
                    suggestion=f"Status must be one of: {', '.join(sorted(allowed_statuses))}.",
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
                suggestion=(
                    "Add at least one source system with its type," " owner, and access method."
                ),
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
                suggestion=(
                    "Add at least one data consumer with department,"
                    " use case, and access pattern."
                ),
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
                    suggestion="Populate this section with the relevant requirements and details.",
                )
            )
    return results


# --- WARNING checks ---


def check_sla_defined(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that SLAs are defined with numeric targets in section 4.3."""
    results: list[ValidationResult] = []
    sub = _find_subsection(
        sections,
        "4. Consumer Requirements",
        "4.3 Service Level Agreements",
        "4.3 Service Level",
    )
    if sub is None or not _section_has_table_rows(sub or ""):
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="4.3 Service Level Agreements",
                message="No SLAs are defined.",
                suggestion=(
                    "Define at least one SLA with target,"
                    " measurement method, and escalation path."
                ),
            )
        )
    elif sub:
        # Check that SLA table rows contain numeric targets (e.g., "99.9%", "2 seconds", "< 5s")
        has_numeric = bool(
            re.search(r"\d+\.?\d*\s*(%|seconds?|s\b|ms\b|minutes?|hours?)", sub, re.IGNORECASE)
        )
        if not has_numeric:
            results.append(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    section="4.3 Service Level Agreements",
                    message="SLA section has no numeric targets.",
                    suggestion=(
                        "Add specific numeric targets (e.g.,"
                        " '99.9% availability', 'under 2 seconds response time')."
                    ),
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
                suggestion=(
                    "Identify fields that are essential" " for the system to function correctly."
                ),
            )
        )
    return results


def check_business_rules(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that at least one calculation or derivation is documented in section 5.2."""
    results: list[ValidationResult] = []
    sub = _find_subsection(
        sections,
        "5. Business Rules",
        "5.2 Calculations and Derivations",
        "5.2 Calculations",
    )
    if sub is None or not sub.strip() or len(sub.strip()) < 20:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="5.2 Calculations and Derivations",
                message="No calculations or derivations are documented.",
                suggestion=(
                    "Document at least one derived field"
                    " with its formula, inputs, and business purpose."
                ),
            )
        )
    return results


def check_freshness(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that freshness requirements are defined in section 4.4."""
    results: list[ValidationResult] = []
    sub = _find_subsection(
        sections,
        "4. Consumer Requirements",
        "4.4 Data Freshness",
        "4.4 Data Freshness Requirements",
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
    sub = _subsection_content(sections, "3. Data Quality Expectations", "3.4 Tolerance Thresholds")
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
    """Check that regulatory subsections 7.1-7.5 are documented."""
    results: list[ValidationResult] = []

    regulatory_subsections = [
        (
            "7.1 Applicable Regulations",
            "No applicable regulations are documented.",
            "Identify regulations that apply (e.g., HIPAA, GDPR)"
            " with scope and impact on data design.",
        ),
        (
            "7.2 Data Classification",
            "No data classification levels are documented.",
            "Classify data elements by sensitivity level (e.g., PHI, PII, Internal, Public).",
        ),
        (
            "7.3 Retention",
            "No data retention periods are documented.",
            "Document retention periods with legal basis for each data category.",
        ),
        (
            "7.4 Access Controls",
            "No access controls are documented.",
            "Map role-based access controls per consumer group.",
        ),
        (
            "7.5 Audit",
            "No audit requirements are documented.",
            "Specify audit logging requirements (access events, modifications, breach detection).",
        ),
    ]

    for sub_name, message, suggestion in regulatory_subsections:
        sub = _find_subsection(
            sections,
            "7. Regulatory and Compliance",
            sub_name,
            sub_name.split(" ", 1)[-1],
        )
        if sub is None or not sub.strip() or len(sub.strip()) < 10:
            results.append(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    section=sub_name,
                    message=message,
                    suggestion=suggestion,
                )
            )

    return results


def check_vague_language(content: str) -> list[ValidationResult]:
    """Check for vague language anti-patterns that should be made specific."""
    results: list[ValidationResult] = []

    vague_patterns = [
        (
            r"\breal[\s-]?time\b",
            "real-time",
            "Specify exact latency: sub-second, minute-level, hourly, or daily batch.",
        ),
        (
            r"\bfast\s+response\b",
            "fast response",
            "Specify the acceptable 90th percentile response time (e.g., under 2 seconds).",
        ),
        (
            r"\ball\s+(?:the\s+)?data\b",
            "all the data",
            "Specify which tables, fields, or data domains are needed.",
        ),
        (
            r"\bcomprehensive\s+view\b",
            "comprehensive view",
            "List the specific data domains included (e.g., demographics, encounters, conditions).",
        ),
        (
            r"\bup[\s-]?to[\s-]?date\b",
            "up-to-date",
            "Specify maximum acceptable data staleness per consumer.",
        ),
        (
            r"\ball\s+users\b",
            "all users",
            "Name the specific user groups, departments, and headcount per group.",
        ),
        (
            r"\bstandard\s+compliance\b",
            "standard compliance",
            "Which specific regulations? HIPAA? GDPR? State laws?",
        ),
    ]

    found_patterns: list[str] = []
    for pattern, label, _ in vague_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            found_patterns.append(label)

    if found_patterns:
        suggestions = []
        for pattern, label, suggestion in vague_patterns:
            if label in found_patterns:
                suggestions.append(f'"{label}": {suggestion}')

        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="General",
                message=(
                    "Found vague language that should be made specific: "
                    f"{', '.join(found_patterns)}."
                ),
                suggestion=" | ".join(suggestions),
            )
        )

    return results


# --- INFO checks ---


def check_placeholders(content: str) -> list[ValidationResult]:
    """Warn about remaining placeholder text and check for owner/due date."""
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
                suggestion=(
                    "Replace placeholder text with actual requirements"
                    " or mark as open questions."
                ),
            )
        )

    # Check that [TO BE DETERMINED] placeholders include owner and due date
    tbd_without_details = re.findall(
        r"\[TO BE DETERMINED(?!\s*-\s*requires input from\s+\S+.*?due\s+\d{4})[^\]]*\]",
        content,
        re.IGNORECASE,
    )
    if tbd_without_details:
        results.append(
            ValidationResult(
                level=ValidationLevel.INFO,
                section="General",
                message=(
                    f"Found {len(tbd_without_details)} [TO BE DETERMINED]"
                    " placeholder(s) missing owner or due date."
                ),
                suggestion=(
                    "Use format: [TO BE DETERMINED - requires input"
                    " from {Name}, due {YYYY-MM-DD}]."
                ),
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
        sections,
        "5. Business Rules",
        "5.4 Edge Cases",
        "5.4 Edge Cases and Exceptions",
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
    report.results.extend(check_vague_language(content))

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

    print(
        f"  Summary: {report.critical_count} critical,"
        f" {report.warning_count} warnings, {report.info_count} info"
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
