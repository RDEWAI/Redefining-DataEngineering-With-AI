#!/usr/bin/env python3
"""Validate Data Quality Specification (DQS) against completeness and quality.

Checks all required sections, metadata, field-level rules, referential
integrity, statistical tests, reconciliation rules, alert framework,
traceability, and upstream references. Reports issues as CRITICAL, WARNING,
or INFO.

Usage:
    python validate_dqs.py <path-to-dqs.md>
    python validate_dqs.py --all <directory>
    python validate_dqs.py --format json <path-to-dqs.md>

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
    """Aggregate validation report for a DQS file."""

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
    "1. Overview",
    "2. Field-Level Validation Rules",
    "3. Referential Integrity Rules",
    "4. Statistical Distribution Tests",
    "5. Reconciliation Rules",
    "6. Freshness & SLA Monitoring",
    "7. Alert & Escalation Framework",
    "8. Traceability Matrix",
    "9. Version History",
]


def parse_dqs_sections(content: str) -> dict[str, str]:
    """Parse DQS markdown into dict of heading -> content."""
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
    """Check if content has markdown table data rows (pipe-separated)."""
    lines = content.split("\n")
    data_rows = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            # Skip separator rows (|---|---|)
            inner = stripped.strip("|").strip()
            if not re.match(r"^[\s\-:|]+$", inner):
                data_rows += 1
    # Subtract header rows (first data row is usually the header)
    return data_rows > min_rows


# --- CRITICAL checks ---


def check_required_sections(
    sections: dict[str, str],
) -> list[ValidationResult]:
    """Check that all 9 required top-level sections exist."""
    results: list[ValidationResult] = []
    for section in REQUIRED_SECTIONS:
        if section not in sections:
            results.append(
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    section=section,
                    message=f'Required section "{section}" is missing.',
                    suggestion=f'Add a "## {section}" section to the DQS.',
                )
            )
    return results


def check_metadata(content: str) -> list[ValidationResult]:
    """Check that metadata fields are present and non-empty."""
    results: list[ValidationResult] = []
    required_fields = ["Version", "Created", "Author", "Status"]
    # At least one upstream reference required
    upstream_fields = ["STM Reference", "DMS Reference"]

    for field_name in required_fields:
        pattern = rf"\*\*{field_name}\*\*\s*\|\s*(.+)"
        match = re.search(pattern, content)
        if not match or not match.group(1).strip():
            results.append(
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    section="Metadata",
                    message=(f'Metadata field "{field_name}" is missing or empty.'),
                    suggestion=(f'Add "{field_name}" to the metadata table.'),
                )
            )

    has_upstream = False
    for field_name in upstream_fields:
        pattern = rf"\*\*{field_name}\*\*\s*\|\s*(.+)"
        match = re.search(pattern, content)
        if match and match.group(1).strip():
            has_upstream = True
            break

    if not has_upstream:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="Metadata",
                message="No upstream artifact reference found.",
                suggestion=("Add STM Reference or DMS Reference to metadata."),
            )
        )

    return results


def check_field_level_rules(
    sections: dict[str, str],
) -> list[ValidationResult]:
    """Check that field-level rules section has rule tables."""
    results: list[ValidationResult] = []
    content = sections.get("2. Field-Level Validation Rules", "")

    if not content:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="2. Field-Level Validation Rules",
                message="Field-Level Validation Rules section is empty.",
                suggestion="Add rule tables with DQ-FLD rules.",
            )
        )
        return results

    has_rules = bool(re.search(r"DQ-\w+-\d{3}", content))
    has_table = _has_table_rows(content)

    if not has_rules or not has_table:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="2. Field-Level Validation Rules",
                message="No valid rule table with DQ- rule IDs found.",
                suggestion=("Add markdown table rows with DQ-FLD-nnn rule IDs."),
            )
        )

    return results


def check_referential_integrity(
    sections: dict[str, str],
) -> list[ValidationResult]:
    """Check that referential integrity section has FK checks."""
    results: list[ValidationResult] = []
    content = sections.get("3. Referential Integrity Rules", "")

    if not content or not _has_table_rows(content):
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="3. Referential Integrity Rules",
                message="No referential integrity rules found.",
                suggestion="Add at least one FK check rule.",
            )
        )

    return results


def check_severity_definitions(
    sections: dict[str, str],
) -> list[ValidationResult]:
    """Check that Overview defines CRITICAL/WARNING/INFO severities."""
    results: list[ValidationResult] = []
    content = sections.get("1. Overview", "")
    content_upper = content.upper()

    for sev in ["CRITICAL", "WARNING", "INFO"]:
        if sev not in content_upper:
            results.append(
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    section="1. Overview",
                    message=f'Severity "{sev}" not defined in Overview.',
                    suggestion=(
                        "Add a severity definitions table with CRITICAL, WARNING, and INFO levels."
                    ),
                )
            )

    return results


def check_rule_id_format(content: str) -> list[ValidationResult]:
    """Check that rule IDs follow DQ-xxx-nnn pattern."""
    results: list[ValidationResult] = []
    rule_ids = re.findall(r"DQ-[A-Z]{2,4}-\d{3}", content)

    if len(rule_ids) < 3:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="Rules",
                message=(f"Only {len(rule_ids)} rule IDs found (need at least 3)."),
                suggestion=("Add rules with IDs like DQ-FLD-001, DQ-REF-001, etc."),
            )
        )

    return results


# --- WARNING checks ---


def check_multi_layer_coverage(
    sections: dict[str, str],
) -> list[ValidationResult]:
    """Check rules cover bronze, silver, AND gold layers."""
    results: list[ValidationResult] = []
    content = sections.get("2. Field-Level Validation Rules", "")
    lower = content.lower()

    missing = []
    for layer in ["bronze", "silver", "gold"]:
        if layer not in lower:
            missing.append(layer)

    if missing:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="2. Field-Level Validation Rules",
                message=(f"Missing rules for layer(s): {', '.join(missing)}."),
                suggestion=("Add validation rules for all three layers (bronze, silver, gold)."),
            )
        )

    return results


def check_reconciliation_rules(
    sections: dict[str, str],
) -> list[ValidationResult]:
    """Check that reconciliation section has at least one rule."""
    results: list[ValidationResult] = []
    content = sections.get("5. Reconciliation Rules", "")

    if not content or not _has_table_rows(content):
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="5. Reconciliation Rules",
                message="No reconciliation rules found.",
                suggestion=("Add source-to-target comparison rules."),
            )
        )

    return results


def check_alert_thresholds(
    sections: dict[str, str],
) -> list[ValidationResult]:
    """Check alert & escalation framework has severity routing."""
    results: list[ValidationResult] = []
    content = sections.get("7. Alert & Escalation Framework", "")
    lower = content.lower()

    has_routing = any(kw in lower for kw in ["severity", "threshold", "escalation", "routing"])

    if not has_routing:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="7. Alert & Escalation Framework",
                message="No severity routing or alert thresholds found.",
                suggestion=(
                    "Add a severity routing table with response times and notification channels."
                ),
            )
        )

    return results


def check_freshness_monitoring(
    sections: dict[str, str],
) -> list[ValidationResult]:
    """Check freshness & SLA section has monitoring entries."""
    results: list[ValidationResult] = []
    content = sections.get("6. Freshness & SLA Monitoring", "")

    if not content or not _has_table_rows(content):
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="6. Freshness & SLA Monitoring",
                message="No freshness monitoring entries found.",
                suggestion="Add per-consumer SLA checks with latency targets.",
            )
        )

    return results


def check_stm_traceability(content: str) -> list[ValidationResult]:
    """Check that STM is referenced at least twice."""
    results: list[ValidationResult] = []
    count = len(re.findall(r"\bSTM\b", content))

    if count < 2:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="Traceability",
                message=f"STM referenced only {count} time(s) (need ≥2).",
                suggestion="Add STM references to rule descriptions.",
            )
        )

    return results


def check_dms_traceability(content: str) -> list[ValidationResult]:
    """Check that DMS is referenced at least twice."""
    results: list[ValidationResult] = []
    count = len(re.findall(r"\bDMS\b", content))

    if count < 2:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="Traceability",
                message=f"DMS referenced only {count} time(s) (need ≥2).",
                suggestion="Add DMS references to rule descriptions.",
            )
        )

    return results


def check_traceability_matrix(
    sections: dict[str, str],
) -> list[ValidationResult]:
    """Check traceability matrix has data rows."""
    results: list[ValidationResult] = []
    content = sections.get("8. Traceability Matrix", "")

    if not content or not _has_table_rows(content):
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="8. Traceability Matrix",
                message="Traceability matrix has no data rows.",
                suggestion=("Add rows mapping DQS rules to DRD requirements."),
            )
        )

    return results


def check_statistical_tests(
    sections: dict[str, str],
) -> list[ValidationResult]:
    """Check statistical distribution tests have baselines/thresholds."""
    results: list[ValidationResult] = []
    content = sections.get("4. Statistical Distribution Tests", "")
    lower = content.lower()

    has_data = bool(re.search(r"\d+", content)) and (
        "baseline" in lower or "threshold" in lower or "%" in content or "±" in content
    )

    if not has_data:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="4. Statistical Distribution Tests",
                message="No baseline or threshold values found.",
                suggestion=("Add statistical baselines with numeric thresholds."),
            )
        )

    return results


# --- INFO checks ---


def check_placeholders(content: str) -> list[ValidationResult]:
    """Flag TBD/TODO/PLACEHOLDER text."""
    results: list[ValidationResult] = []
    patterns = [
        r"\[TBD\]",
        r"\[TODO\]",
        r"\[PLACEHOLDER\]",
        r"\[TO BE DETERMINED\]",
    ]

    count = 0
    for pat in patterns:
        count += len(re.findall(pat, content, re.IGNORECASE))

    if count > 0:
        results.append(
            ValidationResult(
                level=ValidationLevel.INFO,
                section="General",
                message=f"Found {count} placeholder(s) (TBD/TODO).",
                suggestion="Replace placeholders with actual content.",
            )
        )

    return results


def check_drd_traceability(content: str) -> list[ValidationResult]:
    """Check that DRD is referenced for business context."""
    results: list[ValidationResult] = []
    count = len(re.findall(r"\bDRD\b", content))

    if count < 1:
        results.append(
            ValidationResult(
                level=ValidationLevel.INFO,
                section="Traceability",
                message="No DRD references found.",
                suggestion="Add DRD references for business context.",
            )
        )

    return results


def check_escalation_contacts(
    sections: dict[str, str],
) -> list[ValidationResult]:
    """Check alert framework mentions contacts or channels."""
    results: list[ValidationResult] = []
    content = sections.get("7. Alert & Escalation Framework", "")
    lower = content.lower()

    has_contacts = any(kw in lower for kw in ["email", "slack", "pagerduty", "contact", "channel"])

    if not has_contacts:
        results.append(
            ValidationResult(
                level=ValidationLevel.INFO,
                section="7. Alert & Escalation Framework",
                message="No notification channels or contacts specified.",
                suggestion=("Add notification channels (Slack, PagerDuty, email)."),
            )
        )

    return results


# --- Main validation ---


def validate_dqs(file_path: Path) -> ValidationReport:
    """Run all validation checks on a DQS file."""
    report = ValidationReport(file_path=str(file_path))

    try:
        content = file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        report.results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="File",
                message=f"File not found: {file_path}",
                suggestion="Check the file path.",
            )
        )
        return report
    except (OSError, UnicodeDecodeError) as exc:
        report.results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="File",
                message=f"Cannot read file: {exc}",
                suggestion="Check file encoding (expected UTF-8).",
            )
        )
        return report

    sections = parse_dqs_sections(content)

    # CRITICAL checks
    report.results.extend(check_required_sections(sections))
    report.results.extend(check_metadata(content))
    report.results.extend(check_field_level_rules(sections))
    report.results.extend(check_referential_integrity(sections))
    report.results.extend(check_severity_definitions(sections))
    report.results.extend(check_rule_id_format(content))

    # WARNING checks
    report.results.extend(check_multi_layer_coverage(sections))
    report.results.extend(check_reconciliation_rules(sections))
    report.results.extend(check_alert_thresholds(sections))
    report.results.extend(check_freshness_monitoring(sections))
    report.results.extend(check_stm_traceability(content))
    report.results.extend(check_dms_traceability(content))
    report.results.extend(check_traceability_matrix(sections))
    report.results.extend(check_statistical_tests(sections))

    # INFO checks
    report.results.extend(check_placeholders(content))
    report.results.extend(check_drd_traceability(content))
    report.results.extend(check_escalation_contacts(sections))

    return report


def print_report(report: ValidationReport) -> None:
    """Print formatted validation report."""
    filename = Path(report.file_path).name
    print(f"\n{'=' * 60}")
    print(f"DQS Validation Report: {filename}")
    print(f"{'=' * 60}")

    for level in [
        ValidationLevel.CRITICAL,
        ValidationLevel.WARNING,
        ValidationLevel.INFO,
    ]:
        items = [r for r in report.results if r.level == level]
        if not items:
            continue
        print(f"\n  {level.value} ({len(items)})")
        print(f"  {'-' * 40}")
        for r in items:
            print(f"  [{r.level.value}] Section: {r.section}")
            print(f"           {r.message}")
            print(f"           Fix: {r.suggestion}")

    print()
    if report.critical_count > 0:
        print(
            f"FAILED: {report.critical_count} critical,"
            f" {report.warning_count} warning,"
            f" {report.info_count} info"
        )
    elif report.warning_count > 0:
        print(f"PASSED WITH WARNINGS: {report.warning_count} warning, {report.info_count} info")
    else:
        print(f"PASSED: {report.info_count} info item(s)")


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
    parser = argparse.ArgumentParser(description="Validate DQS markdown files")
    parser.add_argument("path", help="DQS file or directory")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all .md files in directory",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )

    args = parser.parse_args()
    path = Path(args.path)

    if args.all:
        if not path.is_dir():
            print(f"Error: {path} is not a directory", file=sys.stderr)
            return 3
        files = sorted(path.rglob("*.md"))
        if not files:
            print(f"No .md files found in {path}", file=sys.stderr)
            return 3
    else:
        if not path.exists():
            print(f"Error: {path} not found", file=sys.stderr)
            return 3
        files = [path]

    worst = 0
    for f in files:
        report = validate_dqs(f)
        if args.format == "json":
            print(report_to_json(report))
        else:
            print_report(report)

        if report.critical_count > 0:
            worst = max(worst, 1)
        elif report.warning_count > 0:
            worst = max(worst, 2)

    return worst


if __name__ == "__main__":
    sys.exit(main())
