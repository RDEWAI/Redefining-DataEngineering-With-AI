#!/usr/bin/env python3
"""Validate Sprint Backlog (Epics & Stories) against completeness and quality standards.

Checks the backlog index, epic files, and story files for required sections,
upstream traceability, dependency consistency, and sprint allocation. Reports
issues as CRITICAL, WARNING, or INFO.

Usage:
    python validate_stories.py <path-to-backlog.md>
    python validate_stories.py --all <stories-directory>
    python validate_stories.py --format json <path-to-backlog.md>

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
    """Aggregate validation report for a stories directory."""

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


BACKLOG_REQUIRED_SECTIONS = [
    "1. Executive Summary",
    "2. Epic Overview",
    "3. Dependency Graph",
    "4. Sprint Plan",
    "5. Traceability Matrix",
    "6. Risks & Assumptions",
    "7. Version History",
]

EPIC_REQUIRED_SECTIONS = ["Objective", "Stories"]

STORY_REQUIRED_SECTIONS = ["User Story", "Acceptance Criteria"]


def parse_sections(content: str) -> dict[str, str]:
    """Parse a markdown file into a dict of section_heading -> section_content."""
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


def find_backlog_file(directory: Path) -> Path | None:
    """Find the BACKLOG-*.md file in the directory."""
    backlog_files = sorted(directory.glob("BACKLOG-*.md"))
    return backlog_files[-1] if backlog_files else None


def find_epic_dirs(directory: Path) -> list[Path]:
    """Find all EPIC-NN-* directories."""
    return sorted([d for d in directory.iterdir() if d.is_dir() and d.name.startswith("EPIC-")])


def find_epic_file(epic_dir: Path) -> Path | None:
    """Find the EPIC-NN.md file in an epic directory."""
    epic_files = sorted(epic_dir.glob("EPIC-*.md"))
    return epic_files[0] if epic_files else None


def find_story_files(epic_dir: Path) -> list[Path]:
    """Find all STORY-*.md files in an epic directory."""
    return sorted(epic_dir.glob("STORY-*.md"))


# --- CRITICAL checks ---


def check_backlog_exists(directory: Path) -> list[ValidationResult]:
    """Check that a BACKLOG-*.md file exists."""
    results: list[ValidationResult] = []
    backlog = find_backlog_file(directory)
    if not backlog:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="Backlog",
                message="No BACKLOG-*.md file found in the stories directory.",
                suggestion="Create a BACKLOG-{YYYY-MM-DD}-{name}.md index file.",
            )
        )
    return results


def check_backlog_sections(content: str) -> list[ValidationResult]:
    """Check that all 7 required backlog sections exist."""
    results: list[ValidationResult] = []
    sections = parse_sections(content)
    for section in BACKLOG_REQUIRED_SECTIONS:
        if section not in sections:
            results.append(
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    section=section,
                    message=f'Required backlog section "{section}" is missing.',
                    suggestion=f'Add a "## {section}" section to the backlog.',
                )
            )
    return results


VALID_STATUSES = {"Draft", "Updated - Pending Review", "Approved"}


def check_backlog_metadata(content: str) -> list[ValidationResult]:
    """Check that version metadata fields are present and non-empty."""
    results: list[ValidationResult] = []
    required_fields = ["Version", "Created", "Author", "Status", "LLD Reference"]
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
                        f'Add a "{field_name}" field to the metadata table '
                        f"at the top of the backlog."
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


def check_epic_dirs_exist(directory: Path) -> list[ValidationResult]:
    """Check that at least one EPIC directory exists."""
    results: list[ValidationResult] = []
    epic_dirs = find_epic_dirs(directory)
    if not epic_dirs:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="Epics",
                message="No EPIC-* directories found.",
                suggestion="Create at least one EPIC-NN-{slug}/ directory with an EPIC-NN.md file.",
            )
        )
    return results


def check_epic_has_file(epic_dir: Path) -> list[ValidationResult]:
    """Check that an epic directory has an EPIC-NN.md file."""
    results: list[ValidationResult] = []
    epic_file = find_epic_file(epic_dir)
    if not epic_file:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section=epic_dir.name,
                message=f"No EPIC-*.md file found in {epic_dir.name}/.",
                suggestion=f"Create an EPIC-NN.md file in {epic_dir.name}/.",
            )
        )
    return results


def check_epic_sections(epic_file: Path) -> list[ValidationResult]:
    """Check that an epic file has required sections."""
    results: list[ValidationResult] = []
    content = epic_file.read_text(encoding="utf-8")
    sections = parse_sections(content)
    for section in EPIC_REQUIRED_SECTIONS:
        if section not in sections:
            results.append(
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    section=f"{epic_file.parent.name}/{epic_file.name}",
                    message=f'Required epic section "{section}" is missing.',
                    suggestion=f'Add a "## {section}" section to {epic_file.name}.',
                )
            )
    return results


def check_stories_exist(epic_dir: Path) -> list[ValidationResult]:
    """Check that an epic has at least one story file."""
    results: list[ValidationResult] = []
    stories = find_story_files(epic_dir)
    if not stories:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section=epic_dir.name,
                message=f"No STORY-*.md files found in {epic_dir.name}/.",
                suggestion=(
                    f"Create at least one STORY-NN-NNN-{{slug}}.md file " f"in {epic_dir.name}/."
                ),
            )
        )
    return results


def check_story_sections(story_file: Path) -> list[ValidationResult]:
    """Check that a story file has required sections."""
    results: list[ValidationResult] = []
    content = story_file.read_text(encoding="utf-8")
    sections = parse_sections(content)
    for section in STORY_REQUIRED_SECTIONS:
        if section not in sections:
            results.append(
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    section=f"{story_file.parent.name}/{story_file.name}",
                    message=f'Required story section "{section}" is missing.',
                    suggestion=f'Add a "## {section}" section to {story_file.name}.',
                )
            )
    return results


# --- WARNING checks ---


def check_upstream_traceability(story_file: Path) -> list[ValidationResult]:
    """Check that a story references upstream artifacts."""
    results: list[ValidationResult] = []
    content = story_file.read_text(encoding="utf-8")
    has_upstream = bool(re.search(r"\[(LLD|DMS|DQS|STM|HLD|DRD)\s*§", content))
    if not has_upstream:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section=f"{story_file.parent.name}/{story_file.name}",
                message="Story does not reference any upstream artifacts.",
                suggestion=(
                    "Add [LLD §X.Y], [DMS §X.Y], or [DQS §X.Y] references "
                    "to acceptance criteria and technical notes."
                ),
            )
        )
    return results


def check_dependency_consistency(
    story_file: Path, all_story_ids: set[str]
) -> list[ValidationResult]:
    """Check that referenced dependency STORY IDs actually exist."""
    results: list[ValidationResult] = []
    content = story_file.read_text(encoding="utf-8")

    # Find dependency references like STORY-01-002, STORY-03-001
    dep_match = re.search(r"\*\*Dependencies\*\*\s*\|\s*(.+)", content)
    if not dep_match:
        return results

    dep_text = dep_match.group(1).strip()
    if dep_text.lower() in ("none", "—", "-", "n/a", ""):
        return results

    referenced_ids = re.findall(r"STORY-\d{2}-\d{3}", dep_text)
    for story_id in referenced_ids:
        if story_id not in all_story_ids:
            results.append(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    section=f"{story_file.parent.name}/{story_file.name}",
                    message=f"Dependency {story_id} does not exist.",
                    suggestion=(
                        f"Verify that {story_id} is a valid story ID "
                        f"or remove the dependency reference."
                    ),
                )
            )
    return results


def check_sprint_allocation(story_file: Path) -> list[ValidationResult]:
    """Check that a story has a sprint allocation."""
    results: list[ValidationResult] = []
    content = story_file.read_text(encoding="utf-8")
    sprint_match = re.search(r"\*\*Sprint\*\*\s*\|\s*(.+)", content)
    if not sprint_match or not sprint_match.group(1).strip():
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section=f"{story_file.parent.name}/{story_file.name}",
                message="Story has no sprint allocation.",
                suggestion="Assign a sprint number to this story.",
            )
        )
    return results


def check_story_points(story_file: Path) -> list[ValidationResult]:
    """Check that a story has story point estimates."""
    results: list[ValidationResult] = []
    content = story_file.read_text(encoding="utf-8")
    points_match = re.search(r"\*\*Story Points\*\*\s*\|\s*(.+)", content)
    if not points_match or not points_match.group(1).strip():
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section=f"{story_file.parent.name}/{story_file.name}",
                message="Story has no story point estimate.",
                suggestion="Add a story point estimate to this story.",
            )
        )
    return results


def check_dependency_graph(backlog_content: str) -> list[ValidationResult]:
    """Check that the backlog has a Mermaid dependency diagram."""
    results: list[ValidationResult] = []
    has_mermaid = bool(re.search(r"```mermaid", backlog_content))
    if not has_mermaid:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="3. Dependency Graph",
                message="No Mermaid dependency diagram found in backlog.",
                suggestion="Add a Mermaid diagram showing epic and story dependencies.",
            )
        )
    return results


# --- INFO checks ---


def check_placeholders(content: str, context: str) -> list[ValidationResult]:
    """Warn about remaining placeholder text."""
    results: list[ValidationResult] = []
    placeholders = re.findall(r"\[(TBD|TODO|TO BE DETERMINED)[^\]]*\]", content, re.IGNORECASE)
    if placeholders:
        results.append(
            ValidationResult(
                level=ValidationLevel.INFO,
                section=context,
                message=f"Found {len(placeholders)} placeholder(s) that need to be resolved.",
                suggestion="Replace placeholder text with actual content.",
            )
        )
    return results


def check_estimation_support(story_file: Path) -> list[ValidationResult]:
    """Check if story has estimation support table."""
    results: list[ValidationResult] = []
    content = story_file.read_text(encoding="utf-8")
    sections = parse_sections(content)
    if "Estimation Support" not in sections:
        results.append(
            ValidationResult(
                level=ValidationLevel.INFO,
                section=f"{story_file.parent.name}/{story_file.name}",
                message="Story has no Estimation Support section.",
                suggestion=(
                    "Add an Estimation Support table mapping to DMS tables, "
                    "STM sheets, DQS rules, and LLD tasks."
                ),
            )
        )
    return results


# --- Main validation ---


def _extract_story_id(story_file: Path) -> str | None:
    """Extract STORY-NN-NNN from a story filename."""
    match = re.match(r"(STORY-\d{2}-\d{3})", story_file.name)
    return match.group(1) if match else None


def validate_stories_dir(directory: Path) -> ValidationReport:
    """Run all validation checks on a stories directory."""
    report = ValidationReport(file_path=str(directory))

    if not directory.is_dir():
        report.results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="Directory",
                message=f"Not a directory: {directory}",
                suggestion="Provide a valid stories output directory.",
            )
        )
        return report

    # Check backlog file exists
    report.results.extend(check_backlog_exists(directory))

    backlog_file = find_backlog_file(directory)
    if backlog_file:
        backlog_content = backlog_file.read_text(encoding="utf-8")
        report.results.extend(check_backlog_sections(backlog_content))
        report.results.extend(check_backlog_metadata(backlog_content))
        report.results.extend(check_dependency_graph(backlog_content))
        report.results.extend(check_placeholders(backlog_content, "Backlog"))

    # Check epic directories
    report.results.extend(check_epic_dirs_exist(directory))

    epic_dirs = find_epic_dirs(directory)

    # Collect all story IDs for dependency checking
    all_story_ids: set[str] = set()
    all_story_files: list[Path] = []
    for epic_dir in epic_dirs:
        story_files = find_story_files(epic_dir)
        all_story_files.extend(story_files)
        for sf in story_files:
            sid = _extract_story_id(sf)
            if sid:
                all_story_ids.add(sid)

    # Check each epic
    for epic_dir in epic_dirs:
        report.results.extend(check_epic_has_file(epic_dir))
        epic_file = find_epic_file(epic_dir)
        if epic_file:
            report.results.extend(check_epic_sections(epic_file))
            epic_content = epic_file.read_text(encoding="utf-8")
            report.results.extend(check_placeholders(epic_content, epic_dir.name))

        report.results.extend(check_stories_exist(epic_dir))
        story_files = find_story_files(epic_dir)
        for story_file in story_files:
            report.results.extend(check_story_sections(story_file))
            report.results.extend(check_upstream_traceability(story_file))
            report.results.extend(check_dependency_consistency(story_file, all_story_ids))
            report.results.extend(check_sprint_allocation(story_file))
            report.results.extend(check_story_points(story_file))
            report.results.extend(check_estimation_support(story_file))
            story_content = story_file.read_text(encoding="utf-8")
            report.results.extend(
                check_placeholders(
                    story_content,
                    f"{story_file.parent.name}/{story_file.name}",
                )
            )

    return report


def validate_single_backlog(file_path: Path) -> ValidationReport:
    """Validate a single backlog file (without epic/story directory checks)."""
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

    report.results.extend(check_backlog_sections(content))
    report.results.extend(check_backlog_metadata(content))
    report.results.extend(check_dependency_graph(content))
    report.results.extend(check_placeholders(content, "Backlog"))

    return report


def print_report(report: ValidationReport) -> None:
    """Print a formatted validation report to stdout."""
    print(f"\n{'=' * 70}")
    print(f"Stories Validation Report: {report.file_path}")
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
        description="Validate Sprint Backlog (Epics & Stories)",
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Path to backlog file or stories directory (with --all)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all files in the given stories directory",
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
        report = validate_stories_dir(args.path)
    else:
        if not args.path.is_file():
            print(f"Error: {args.path} is not a file.", file=sys.stderr)
            return 3
        report = validate_single_backlog(args.path)

    if args.format == "json":
        print(report_to_json(report))
    else:
        print_report(report)

    if report.critical_count > 0:
        return 1
    elif report.warning_count > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
