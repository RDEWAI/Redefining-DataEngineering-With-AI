#!/usr/bin/env python3
"""Validate High-Level Design (HLD) against completeness and quality standards.

Checks all required sections, metadata, layer specifications, technology table,
CDC strategy, capacity planning, security, and DRD traceability. Reports issues
as CRITICAL, WARNING, or INFO.

Usage:
    python validate_hld.py <path-to-hld.md>
    python validate_hld.py --all <directory>
    python validate_hld.py --format json <path-to-hld.md>

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
    """Aggregate validation report for an HLD file."""

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
    "2. Layer Specifications",
    "3. Technology Stack",
    "4. Integration Points",
    "5. Capacity Planning",
    "6. Security Architecture",
    "7. Disaster Recovery",
    "8. CDC Strategy",
]


def parse_hld_sections(content: str) -> dict[str, str]:
    """Parse an HLD markdown file into a dict of section_heading -> section_content."""
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
    # Exclude header row — need at least 2 pipe-rows
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
    parts = re.split(r"(?m)^###\s+", parent_content)
    for part in parts:
        if part.startswith(sub) or sub in part.split("\n")[0]:
            lines = part.split("\n", 1)
            if len(lines) > 1:
                return lines[1].strip()
            return ""
    return None


# --- CRITICAL checks ---


def check_required_sections(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that all 8 required top-level sections exist."""
    results: list[ValidationResult] = []
    for section in REQUIRED_SECTIONS:
        if section not in sections:
            results.append(
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    section=section,
                    message=f'Required section "{section}" is missing.',
                    suggestion=f'Add a "## {section}" section to the HLD.',
                )
            )
    return results


def check_metadata(content: str) -> list[ValidationResult]:
    """Check that version metadata fields are present and non-empty."""
    results: list[ValidationResult] = []
    required_fields = ["Version", "Created", "Author", "Status", "DRD Reference"]
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
                        f'Add a "{field_name}" field to the metadata table at the top of the HLD.'
                    ),
                )
            )
    return results


def check_layer_specs(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that Bronze, Silver, and Gold layer subsections are non-empty."""
    results: list[ValidationResult] = []
    layer_section = "2. Layer Specifications"

    layer_checks = [
        ("Bronze", ["2.1 Bronze", "Bronze Layer", "2.1"]),
        ("Silver", ["2.2 Silver", "Silver Layer", "2.2"]),
        ("Gold", ["2.3 Gold", "Gold Layer", "2.3"]),
    ]

    parent_content = sections.get(layer_section, "")

    for layer_name, search_terms in layer_checks:
        found = False
        for term in search_terms:
            sub = _subsection_content(sections, layer_section, term)
            if sub is not None and sub.strip():
                found = True
                break
        # Also check if the layer name appears in the parent section
        if not found and layer_name.lower() in parent_content.lower():
            found = True

        if not found:
            results.append(
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    section=f"2. Layer Specifications — {layer_name}",
                    message=f"{layer_name} layer specification is missing or empty.",
                    suggestion=(
                        f"Add a subsection defining the {layer_name} layer:"
                        " purpose, write strategy, and table inventory."
                    ),
                )
            )

    return results


def check_technology_table(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that the technology stack section has a table with >= 3 rows."""
    results: list[ValidationResult] = []
    tech_content = sections.get("3. Technology Stack", "")

    if not tech_content:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="3. Technology Stack",
                message="Technology stack section is empty.",
                suggestion=(
                    "Add a table listing all tools with tool, version,"
                    " role, license, and JAR coordinate columns."
                ),
            )
        )
        return results

    lines = tech_content.strip().split("\n")
    table_rows = [
        ln
        for ln in lines
        if ln.strip().startswith("|")
        and not ln.strip().startswith("| ---")
        and not ln.strip().startswith("|---")
        and not all(c in "|- " for c in ln.strip())
    ]
    # Need header + at least 3 data rows = 4 total pipe-rows
    if len(table_rows) < 4:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="3. Technology Stack",
                message=(
                    f"Technology table has only {len(table_rows) - 1} data rows;"
                    " at least 3 required."
                ),
                suggestion=(
                    "Add rows for all tools: processing engine, table format,"
                    " metastore, lineage, and data quality tools."
                ),
            )
        )
    return results


# --- WARNING checks ---


def check_drd_traceability(content: str) -> list[ValidationResult]:
    """Check that 'DRD' appears at least 3 times (traceability citations)."""
    results: list[ValidationResult] = []
    drd_count = len(re.findall(r"\bDRD\b", content))
    if drd_count < 3:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="General",
                message=(
                    f"DRD is cited only {drd_count} time(s);"
                    " at least 3 citations required for traceability."
                ),
                suggestion=(
                    "Add [DRD §X.Y] citations throughout the HLD to trace"
                    " each design decision back to its source requirement."
                ),
            )
        )
    return results


def check_cdc_strategy(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that CDC section mentions snapshot, timestamp, or CDC method."""
    results: list[ValidationResult] = []
    cdc_content = sections.get("8. CDC Strategy", "")

    if not cdc_content:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="8. CDC Strategy",
                message="CDC Strategy section is empty.",
                suggestion=(
                    "Document the change detection method for each source table:"
                    " Full Snapshot, Timestamp Watermark, or Log-Based CDC."
                ),
            )
        )
        return results

    has_cdc_method = bool(
        re.search(
            r"\b(snapshot|timestamp|cdc|log.based|watermark|debezium)\b",
            cdc_content,
            re.IGNORECASE,
        )
    )
    if not has_cdc_method:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="8. CDC Strategy",
                message="CDC Strategy section does not specify a recognized CDC method.",
                suggestion=(
                    "Specify the CDC method per source table:"
                    " Full Snapshot, Timestamp Watermark, or Log-Based CDC."
                ),
            )
        )
    return results


def check_capacity_projections(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that capacity section contains numeric values."""
    results: list[ValidationResult] = []
    capacity_content = sections.get("5. Capacity Planning", "")

    if not capacity_content:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="5. Capacity Planning",
                message="Capacity Planning section is empty.",
                suggestion=(
                    "Add current row counts, growth projections, and compute"
                    " sizing with specific numeric values."
                ),
            )
        )
        return results

    has_numeric = bool(re.search(r"\d[\d,]*\s*(rows?|GB|MB|TB|M\b)", capacity_content))
    if not has_numeric:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="5. Capacity Planning",
                message="Capacity Planning section has no numeric volume values.",
                suggestion=(
                    "Add specific numbers: row counts, storage estimates"
                    " (GB/MB), and growth projections."
                ),
            )
        )
    return results


def check_security_compliance(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that security section mentions compliance, regulatory, or encryption controls."""
    results: list[ValidationResult] = []
    security_content = sections.get("6. Security Architecture", "")

    if not security_content:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="6. Security Architecture",
                message="Security Architecture section is empty.",
                suggestion=(
                    "Document compliance controls, encryption strategy,"
                    " access model, and sensitive data handling rules."
                ),
            )
        )
        return results

    has_compliance = bool(
        re.search(
            r"\b(compliance|regulatory|encryption|access.control"
            r"|sensitive|restricted|classification)\b",
            security_content,
            re.IGNORECASE,
        )
    )
    if not has_compliance:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="6. Security Architecture",
                message=(
                    "Security Architecture section does not mention"
                    " compliance, regulatory, or encryption controls."
                ),
                suggestion=(
                    "Add compliance control table, sensitive data handling"
                    " rules, and encryption requirements."
                ),
            )
        )
    return results


def check_pattern_justification(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that Design Overview section contains pattern justification."""
    results: list[ValidationResult] = []
    overview_content = sections.get("1. Design Overview", "")

    if not overview_content:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="1. Design Overview",
                message="Design Overview section is empty.",
                suggestion=(
                    "Add architecture pattern selection with justification,"
                    " options considered, and trade-off analysis."
                ),
            )
        )
        return results

    has_justification = bool(
        re.search(
            r"\b(because|rationale|justification|selected|chosen|trade.off)\b",
            overview_content,
            re.IGNORECASE,
        )
    )
    if not has_justification:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="1. Design Overview",
                message=(
                    "Design Overview does not contain pattern justification"
                    " (rationale/because/trade-off)."
                ),
                suggestion=(
                    "Add explicit justification for the selected architecture"
                    " pattern including trade-off analysis."
                ),
            )
        )
    return results


def check_decision_documentation(content: str) -> list[ValidationResult]:
    """Check that decision log uses Options Considered / Selected / Rationale format."""
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
                section="Decision Log",
                message=(f"Decision documentation is incomplete — missing: {', '.join(missing)}."),
                suggestion=(
                    "Use the standard decision format: Options Considered,"
                    " Selected, Rationale, Trade-off for each major decision."
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
                    "Replace placeholder text with actual design decisions"
                    " or add to Open Questions with an owner and due date."
                ),
            )
        )
    return results


def check_diagrams(content: str) -> list[ValidationResult]:
    """Check if architecture diagram (mermaid block) is present."""
    results: list[ValidationResult] = []
    has_mermaid = bool(re.search(r"```mermaid", content))
    if not has_mermaid:
        results.append(
            ValidationResult(
                level=ValidationLevel.INFO,
                section="1. Design Overview",
                message="No Mermaid architecture diagram found.",
                suggestion=(
                    "Add a ```mermaid flowchart showing the data flow from"
                    " sources through Bronze/Silver/Gold to consumers."
                ),
            )
        )
    return results


def check_cost_estimates(sections: dict[str, str]) -> list[ValidationResult]:
    """Check if capacity section includes cost or budget information."""
    results: list[ValidationResult] = []
    capacity_content = sections.get("5. Capacity Planning", "")

    has_cost = bool(
        re.search(r"\b(cost|\$|budget|estimate|monthly)\b", capacity_content, re.IGNORECASE)
    )
    if not has_cost:
        results.append(
            ValidationResult(
                level=ValidationLevel.INFO,
                section="5. Capacity Planning",
                message="No cost estimates found in Capacity Planning section.",
                suggestion=(
                    "Add a cost estimate table with monthly estimates"
                    " for compute, storage, and tooling."
                ),
            )
        )
    return results


# --- Main validation ---


def validate_hld(file_path: Path) -> ValidationReport:
    """Run all validation checks on an HLD file."""
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

    sections = parse_hld_sections(content)

    # CRITICAL checks
    report.results.extend(check_required_sections(sections))
    report.results.extend(check_metadata(content))
    report.results.extend(check_layer_specs(sections))
    report.results.extend(check_technology_table(sections))

    # WARNING checks
    report.results.extend(check_drd_traceability(content))
    report.results.extend(check_cdc_strategy(sections))
    report.results.extend(check_capacity_projections(sections))
    report.results.extend(check_security_compliance(sections))
    report.results.extend(check_pattern_justification(sections))
    report.results.extend(check_decision_documentation(content))

    # INFO checks
    report.results.extend(check_placeholders(content))
    report.results.extend(check_diagrams(content))
    report.results.extend(check_cost_estimates(sections))

    return report


def print_report(report: ValidationReport) -> None:
    """Print a formatted validation report to stdout."""
    print(f"\n{'=' * 70}")
    print(f"HLD Validation Report: {report.file_path}")
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
        description="Validate High-Level Design (HLD)",
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Path to HLD file or directory (with --all)",
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
        report = validate_hld(file_path)

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
