#!/usr/bin/env python3
"""Validate Data Model Specification (DMS) against completeness and quality standards.

Checks all required sections, YAML schema block validity, SCD documentation,
naming conventions, HLD traceability, and traceability matrix. Reports issues
as CRITICAL, WARNING, or INFO.

Usage:
    python validate_dms.py <path-to-dms.md>
    python validate_dms.py --all <directory>
    python validate_dms.py --format json <path-to-dms.md>

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
    """Aggregate validation report for a DMS file."""

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
    "2. Bronze Layer Schemas",
    "3. Silver Layer Schemas",
    "4. Gold Layer Schemas",
    "5. Naming Conventions",
    "6. SCD Strategy",
    "7. Physical Design Notes",
    "8. Traceability Matrix",
    "9. Version History",
]


def parse_dms_sections(content: str) -> dict[str, str]:
    """Parse a DMS markdown file into a dict of section_heading -> section_content."""
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


def _extract_yaml_blocks(content: str) -> list[str]:
    """Extract all YAML fenced code blocks from content."""
    blocks = re.findall(r"```yaml\s*\n(.*?)```", content, re.DOTALL)
    return blocks


def _yaml_has_key(yaml_text: str, key: str) -> bool:
    """Check if a YAML block contains a top-level key."""
    return bool(re.search(rf"^{key}:", yaml_text, re.MULTILINE))


def _yaml_has_columns(yaml_text: str) -> bool:
    """Check if a YAML block has a columns list with entries."""
    return bool(re.search(r"^columns:\s*\n\s+-\s+(?:name:|{name:)", yaml_text, re.MULTILINE))


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
                    suggestion=f'Add a "## {section}" section to the DMS.',
                )
            )
    return results


def check_metadata(content: str) -> list[ValidationResult]:
    """Check that version metadata fields are present and non-empty."""
    results: list[ValidationResult] = []
    required_fields = ["Version", "Created", "Author", "Status", "HLD Reference"]
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
                        f'Add a "{field_name}" field to the metadata table at the top of the DMS.'
                    ),
                )
            )
    return results


def check_bronze_schemas(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that Bronze Layer Schemas has ≥1 YAML block with table and columns."""
    results: list[ValidationResult] = []
    bronze_content = sections.get("2. Bronze Layer Schemas", "")

    if not bronze_content:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="2. Bronze Layer Schemas",
                message="Bronze Layer Schemas section is empty.",
                suggestion="Add at least one table with a YAML schema block.",
            )
        )
        return results

    yaml_blocks = _extract_yaml_blocks(bronze_content)
    valid_blocks = [b for b in yaml_blocks if _yaml_has_key(b, "table") and _yaml_has_columns(b)]

    if not valid_blocks:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="2. Bronze Layer Schemas",
                message="No valid YAML schema blocks found (need table: and columns:).",
                suggestion=("Add a ```yaml block with table:, layer: bronze, and columns: list."),
            )
        )
    return results


def check_silver_schemas(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that Silver Layer Schemas has ≥1 YAML block with primary_key."""
    results: list[ValidationResult] = []
    silver_content = sections.get("3. Silver Layer Schemas", "")

    if not silver_content:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="3. Silver Layer Schemas",
                message="Silver Layer Schemas section is empty.",
                suggestion="Add at least one table with a YAML schema block.",
            )
        )
        return results

    yaml_blocks = _extract_yaml_blocks(silver_content)
    pk_blocks = [b for b in yaml_blocks if _yaml_has_key(b, "primary_key")]

    if not pk_blocks:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="3. Silver Layer Schemas",
                message="No YAML schema block with primary_key: found.",
                suggestion=("Add primary_key: to at least one silver layer YAML schema block."),
            )
        )
    return results


def check_gold_schemas(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that Gold Layer Schemas has ≥1 YAML block with grain."""
    results: list[ValidationResult] = []
    gold_content = sections.get("4. Gold Layer Schemas", "")

    if not gold_content:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="4. Gold Layer Schemas",
                message="Gold Layer Schemas section is empty.",
                suggestion="Add at least one table with a YAML schema block.",
            )
        )
        return results

    yaml_blocks = _extract_yaml_blocks(gold_content)
    grain_blocks = [b for b in yaml_blocks if _yaml_has_key(b, "grain")]

    if not grain_blocks:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="4. Gold Layer Schemas",
                message="No YAML schema block with grain: found.",
                suggestion=(
                    "Add grain: to at least one gold layer YAML schema block"
                    " (e.g., grain: one row per patient encounter)."
                ),
            )
        )
    return results


def check_yaml_syntax(content: str) -> list[ValidationResult]:
    """Check that YAML blocks have basic structural validity."""
    results: list[ValidationResult] = []
    yaml_blocks = _extract_yaml_blocks(content)

    for i, block in enumerate(yaml_blocks):
        lines = block.strip().split("\n")
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("-"):
                if ":" not in stripped and not stripped.startswith(" "):
                    results.append(
                        ValidationResult(
                            level=ValidationLevel.CRITICAL,
                            section=f"YAML Block {i + 1}",
                            message=(
                                f"Line {line_num} in YAML block {i + 1} may be invalid:"
                                f" '{stripped[:50]}'"
                            ),
                            suggestion="Ensure all YAML entries use 'key: value' format.",
                        )
                    )
                    break
    return results


# --- WARNING checks ---


def check_hld_traceability(content: str) -> list[ValidationResult]:
    """Check that 'HLD' appears at least 3 times (traceability citations)."""
    results: list[ValidationResult] = []
    hld_count = len(re.findall(r"\bHLD\b", content))
    if hld_count < 3:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="General",
                message=(
                    f"HLD is cited only {hld_count} time(s);"
                    " at least 3 citations required for traceability."
                ),
                suggestion=(
                    "Add [HLD §X.Y] citations throughout the DMS to trace"
                    " each schema decision back to the HLD layer specification."
                ),
            )
        )
    return results


def check_scd_documentation(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that SCD Strategy section mentions SCD types."""
    results: list[ValidationResult] = []
    scd_content = sections.get("6. SCD Strategy", "")

    if not scd_content:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="6. SCD Strategy",
                message="SCD Strategy section is empty.",
                suggestion=(
                    "Document the SCD type for each dimension attribute:"
                    " Type 1 (overwrite), Type 2 (versioned), or Type 3 (previous+current)."
                ),
            )
        )
        return results

    has_scd = bool(
        re.search(
            r"\b(scd|type\s*1|type\s*2|type\s*3|slowly\s*changing)\b",
            scd_content,
            re.IGNORECASE,
        )
    )
    if not has_scd:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="6. SCD Strategy",
                message="SCD Strategy section does not mention recognized SCD types.",
                suggestion=(
                    "Specify SCD type per dimension attribute:"
                    " Type 1, Type 2, or Type 3 with rationale."
                ),
            )
        )
    return results


def check_naming_conventions(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that naming conventions section has prefix rules."""
    results: list[ValidationResult] = []
    naming_content = sections.get("5. Naming Conventions", "")

    if not naming_content:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="5. Naming Conventions",
                message="Naming Conventions section is empty.",
                suggestion=(
                    "Document table naming prefixes (dim_, fact_),"
                    " column naming (snake_case), and schema organization."
                ),
            )
        )
        return results

    has_prefixes = bool(
        re.search(r"\b(dim_|fact_|snake_case|prefix)\b", naming_content, re.IGNORECASE)
    )
    if not has_prefixes:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="5. Naming Conventions",
                message="Naming Conventions does not mention standard prefixes.",
                suggestion=(
                    "Add prefix conventions: dim_ for dimensions,"
                    " fact_ for facts, snake_case for all columns."
                ),
            )
        )
    return results


def check_traceability_matrix(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that traceability matrix has at least one entry."""
    results: list[ValidationResult] = []
    matrix_content = sections.get("8. Traceability Matrix", "")

    if not matrix_content:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="8. Traceability Matrix",
                message="Traceability Matrix section is empty.",
                suggestion=(
                    "Add a table mapping gold tables back through silver"
                    " and bronze source tables with key design decisions."
                ),
            )
        )
        return results

    lines = matrix_content.strip().split("\n")
    table_rows = [
        ln
        for ln in lines
        if ln.strip().startswith("|")
        and not ln.strip().startswith("| ---")
        and not ln.strip().startswith("|---")
        and not all(c in "|- " for c in ln.strip())
    ]
    if len(table_rows) < 2:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="8. Traceability Matrix",
                message="Traceability Matrix has no data rows.",
                suggestion=(
                    "Add at least one row mapping a gold table through"
                    " silver → bronze source tables."
                ),
            )
        )
    return results


def check_silver_lineage(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that silver YAML blocks have source: fields."""
    results: list[ValidationResult] = []
    silver_content = sections.get("3. Silver Layer Schemas", "")
    if not silver_content:
        return results

    yaml_blocks = _extract_yaml_blocks(silver_content)
    blocks_with_source = [b for b in yaml_blocks if "source:" in b]

    if yaml_blocks and not blocks_with_source:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="3. Silver Layer Schemas",
                message="Silver YAML blocks do not have source: fields for lineage.",
                suggestion=(
                    "Add source: field to each column in silver YAML blocks"
                    " (e.g., source: bronze.patients.BIRTHDATE)."
                ),
            )
        )
    return results


def check_gold_foreign_keys(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that gold YAML blocks have foreign_keys for fact tables."""
    results: list[ValidationResult] = []
    gold_content = sections.get("4. Gold Layer Schemas", "")
    if not gold_content:
        return results

    yaml_blocks = _extract_yaml_blocks(gold_content)
    fact_blocks = [b for b in yaml_blocks if "fact" in b.lower() or "grain:" in b]
    fk_blocks = [b for b in fact_blocks if "foreign_keys:" in b]

    if fact_blocks and not fk_blocks:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="4. Gold Layer Schemas",
                message="Gold fact table YAML blocks do not have foreign_keys: section.",
                suggestion=(
                    "Add foreign_keys: to fact table YAML blocks"
                    " referencing dimension surrogate keys."
                ),
            )
        )
    return results


def check_physical_design(sections: dict[str, str]) -> list[ValidationResult]:
    """Check that physical design notes are present."""
    results: list[ValidationResult] = []
    physical_content = sections.get("7. Physical Design Notes", "")

    if not physical_content:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="7. Physical Design Notes",
                message="Physical Design Notes section is empty.",
                suggestion=(
                    "Document partition strategy and clustering keys."
                    " Compression and storage format belong in the LLD."
                ),
            )
        )
    return results


def check_no_transform_in_silver(sections: dict[str, str]) -> list[ValidationResult]:
    """Warn if silver YAML blocks contain transform: expressions (belong in STM)."""
    results: list[ValidationResult] = []
    silver_content = sections.get("3. Silver Layer Schemas", "")
    if not silver_content:
        return results

    yaml_blocks = _extract_yaml_blocks(silver_content)
    blocks_with_transform = [
        b for b in yaml_blocks if re.search(r"^\s+transform:", b, re.MULTILINE)
    ]

    if blocks_with_transform:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="3. Silver Layer Schemas",
                message=(
                    f"Found transform: in {len(blocks_with_transform)} silver YAML"
                    " block(s). Column-level transforms belong in the"
                    " Source-to-Target Mapping document."
                ),
                suggestion=(
                    "Remove transform: fields from silver YAML blocks."
                    " The DMS defines what (columns, types, keys),"
                    " not how (transform expressions)."
                ),
            )
        )
    return results


def check_no_null_handling_in_silver(
    sections: dict[str, str],
) -> list[ValidationResult]:
    """Warn if silver YAML blocks contain null_handling: (belongs in DQS)."""
    results: list[ValidationResult] = []
    silver_content = sections.get("3. Silver Layer Schemas", "")
    if not silver_content:
        return results

    yaml_blocks = _extract_yaml_blocks(silver_content)
    blocks_with_nh = [b for b in yaml_blocks if re.search(r"^\s+null_handling:", b, re.MULTILINE)]

    if blocks_with_nh:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="3. Silver Layer Schemas",
                message=(
                    f"Found null_handling: in {len(blocks_with_nh)} silver YAML"
                    " block(s). Null handling rules belong in the"
                    " Data Quality Specification."
                ),
                suggestion=(
                    "Remove null_handling: fields from silver YAML blocks."
                    " Use nullable: true/false to define the schema contract;"
                    " handling rules go in the DQS."
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
                    "Replace placeholder text with actual schema decisions"
                    " or add to Open Questions with an owner and due date."
                ),
            )
        )
    return results


def check_diagrams(content: str) -> list[ValidationResult]:
    """Check if Mermaid diagrams are present."""
    results: list[ValidationResult] = []
    has_mermaid = bool(re.search(r"```mermaid", content))
    if not has_mermaid:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="General",
                message="No Mermaid diagrams found.",
                suggestion=(
                    "Add a layer architecture flowchart (§1) and a"
                    " gold star schema erDiagram (§4)."
                ),
            )
        )
    return results


def check_holistic_er_diagram(sections: dict[str, str]) -> list[ValidationResult]:
    """Check if Design Overview contains a holistic erDiagram spanning all layers."""
    results: list[ValidationResult] = []
    overview_content = sections.get("1. Design Overview", "")
    if not overview_content:
        return results

    has_er = bool(re.search(r"```mermaid\s*\n\s*erDiagram", overview_content))
    if not has_er:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="1. Design Overview",
                message=("No holistic erDiagram found in Design Overview section."),
                suggestion=(
                    "Add a ```mermaid erDiagram in §1 showing Bronze, Silver,"
                    " and Gold tables with columns, PKs, FKs, and relationships"
                    " across all layers."
                ),
            )
        )
    return results


def check_all_layers_have_yaml(sections: dict[str, str]) -> list[ValidationResult]:
    """Check if all three layers have YAML schema blocks."""
    results: list[ValidationResult] = []
    layers = [
        ("2. Bronze Layer Schemas", "Bronze"),
        ("3. Silver Layer Schemas", "Silver"),
        ("4. Gold Layer Schemas", "Gold"),
    ]

    for section_key, layer_name in layers:
        content = sections.get(section_key, "")
        if content and not _extract_yaml_blocks(content):
            results.append(
                ValidationResult(
                    level=ValidationLevel.INFO,
                    section=section_key,
                    message=f"{layer_name} layer section has no YAML schema blocks.",
                    suggestion=(f"Add ```yaml schema blocks for {layer_name} layer tables."),
                )
            )
    return results


def check_business_rules(sections: dict[str, str]) -> list[ValidationResult]:
    """Check if silver columns reference business rules."""
    results: list[ValidationResult] = []
    silver_content = sections.get("3. Silver Layer Schemas", "")
    if not silver_content:
        return results

    has_br_ref = bool(re.search(r"business_rule:", silver_content))
    if not has_br_ref:
        results.append(
            ValidationResult(
                level=ValidationLevel.INFO,
                section="3. Silver Layer Schemas",
                message="No business_rule: references found in silver YAML blocks.",
                suggestion=(
                    "Add business_rule: field to silver columns that implement"
                    " DRD business rules (e.g., business_rule: BR-001)."
                ),
            )
        )
    return results


# --- Main validation ---


def validate_dms(file_path: Path) -> ValidationReport:
    """Run all validation checks on a DMS file."""
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

    sections = parse_dms_sections(content)

    # CRITICAL checks
    report.results.extend(check_required_sections(sections))
    report.results.extend(check_metadata(content))
    report.results.extend(check_bronze_schemas(sections))
    report.results.extend(check_silver_schemas(sections))
    report.results.extend(check_gold_schemas(sections))
    report.results.extend(check_yaml_syntax(content))

    # WARNING checks
    report.results.extend(check_hld_traceability(content))
    report.results.extend(check_scd_documentation(sections))
    report.results.extend(check_naming_conventions(sections))
    report.results.extend(check_traceability_matrix(sections))
    report.results.extend(check_silver_lineage(sections))
    report.results.extend(check_gold_foreign_keys(sections))
    report.results.extend(check_physical_design(sections))
    report.results.extend(check_no_transform_in_silver(sections))
    report.results.extend(check_no_null_handling_in_silver(sections))
    report.results.extend(check_diagrams(content))
    report.results.extend(check_holistic_er_diagram(sections))

    # INFO checks
    report.results.extend(check_placeholders(content))
    report.results.extend(check_all_layers_have_yaml(sections))
    report.results.extend(check_business_rules(sections))

    return report


def print_report(report: ValidationReport) -> None:
    """Print a formatted validation report to stdout."""
    print(f"\n{'=' * 70}")
    print(f"DMS Validation Report: {report.file_path}")
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
        description="Validate Data Model Specification (DMS)",
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Path to DMS file or directory (with --all)",
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
        report = validate_dms(file_path)

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
