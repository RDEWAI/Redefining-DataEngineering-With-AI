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

# Layer epic detection: LLD Section metadata cites §5.1, §5.2, or §5.3
LAYER_LLD_SECTION_PATTERN = re.compile(r"§\s*5\.[123]\b")

# Trailing (cross-layer) epic detection: LLD Section cites §9.x, or title/scope flags release/hardening  # noqa: E501
TRAILING_EPIC_TITLE_PATTERN = re.compile(
    r"\b(release|hardening|deployment|post[- ]launch)\b", re.IGNORECASE
)
TRAILING_LLD_SECTION_PATTERN = re.compile(r"§\s*9\.\d+")

# Story Type field in metadata table
STORY_TYPE_META_PATTERN = re.compile(r"\|\s*\*\*Story Type\*\*\s*\|\s*([^|]+?)\s*\|")

# Epic Scope field in metadata table
EPIC_SCOPE_META_PATTERN = re.compile(r"\|\s*\*\*Epic Scope\*\*\s*\|\s*([^|]+?)\s*\|")

# Integration-test AC wording: must mention BOTH an Airflow DAG AND Unity Catalog (or UC local / uc_oss)  # noqa: E501
DAG_WORDING_PATTERN = re.compile(r"airflow\s+dag|\btrigger\b.*\bdag\b|dag\s+trigger", re.IGNORECASE)
UC_WORDING_PATTERN = re.compile(
    r"unity\s+catalog|\buc\s+local\b|\buc_oss\b|\buc\s+oss\b", re.IGNORECASE
)

# Deploy N/A note in epic Objective (accept either the canonical phrasing or the word "N/A" near integration-test)  # noqa: E501
DEPLOY_NA_NOTE_PATTERN = re.compile(
    r"deploy\s*:\s*n/a.*integration[- ]test|layer\s+completes\s+at\s+integration[- ]test",
    re.IGNORECASE,
)

VALID_STORY_TYPES = {
    "build",
    "performance-optimization",
    "integration-test",
    "deploy-validation",
    "observability",
    "release",
    "hardening",
    "runtime-bootstrap",
}

LAYER_REQUIRED_STORY_TYPES = {"performance-optimization", "integration-test"}
TRAILING_FORBIDDEN_STORY_TYPES = {
    "performance-optimization",
    "integration-test",
    "deploy-validation",
}

# Story types whose ACs are expected to land changes a developer will run end-to-end.
# These types REQUIRE a populated ## How to Test (User) section so a human can verify.
USER_TEST_REQUIRED_TYPES = {"build", "integration-test", "runtime-bootstrap"}

# Story types whose closure intrinsically changes how the project runs.
# These types REQUIRE a ## Documentation Updates AC list (≥1 README update).
DOCS_UPDATE_REQUIRED_TYPES = {"runtime-bootstrap", "integration-test", "release"}


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


# --- Epic / Story classification helpers ---


def _read_metadata_field(content: str, field_name: str) -> str:
    """Extract a metadata table field value; return '' if missing."""
    pattern = rf"\|\s*\*\*{re.escape(field_name)}\*\*\s*\|\s*([^|]+?)\s*\|"
    match = re.search(pattern, content)
    return match.group(1).strip() if match else ""


def get_story_type(story_file: Path) -> str:
    """Return the Story Type metadata value, defaulting to 'build' when unspecified."""
    content = story_file.read_text(encoding="utf-8")
    match = STORY_TYPE_META_PATTERN.search(content)
    if not match:
        return "build"
    value = match.group(1).strip().lower()
    return value if value in VALID_STORY_TYPES else "build"


def get_epic_scope(epic_file: Path) -> str:
    """Return the Epic Scope metadata value (layer / foundation / crosscut), or '' if unset."""
    content = epic_file.read_text(encoding="utf-8")
    match = EPIC_SCOPE_META_PATTERN.search(content)
    return match.group(1).strip().lower() if match else ""


def is_layer_epic(epic_file: Path) -> bool:
    """Detect a medallion-layer epic via Epic Scope == layer OR LLD Section cites §5.1/§5.2/§5.3."""
    content = epic_file.read_text(encoding="utf-8")
    scope = _read_metadata_field(content, "Epic Scope").lower()
    if scope == "layer":
        return True
    if scope in {"foundation", "crosscut"}:
        return False
    lld_section = _read_metadata_field(content, "LLD Section")
    return bool(LAYER_LLD_SECTION_PATTERN.search(lld_section))


def is_trailing_epic(epic_file: Path) -> bool:
    """Detect a trailing/cross-cutting epic (release or hardening)."""
    content = epic_file.read_text(encoding="utf-8")
    scope = _read_metadata_field(content, "Epic Scope").lower()
    if scope == "crosscut":
        return True
    if scope == "layer":
        return False
    # Fall back to title / LLD section pattern
    title_match = re.search(r"^#\s*EPIC-\d+:\s*(.+)$", content, re.MULTILINE)
    title = title_match.group(1) if title_match else ""
    lld_section = _read_metadata_field(content, "LLD Section")
    return bool(
        TRAILING_EPIC_TITLE_PATTERN.search(title)
        or TRAILING_LLD_SECTION_PATTERN.search(lld_section)
    )


def _epic_number_from_dir(epic_dir: Path) -> int | None:
    """Extract the numeric epic number from EPIC-NN-slug/ directory name."""
    match = re.match(r"EPIC-(\d+)", epic_dir.name)
    return int(match.group(1)) if match else None


def _parse_dependency_story_ids(story_file: Path) -> list[str]:
    """Parse the Dependencies metadata field into a list of STORY-NN-NNN IDs."""
    content = story_file.read_text(encoding="utf-8")
    dep_match = re.search(r"\*\*Dependencies\*\*\s*\|\s*([^|]+)", content)
    if not dep_match:
        return []
    dep_text = dep_match.group(1).strip()
    if dep_text.lower() in ("none", "—", "-", "n/a", ""):
        return []
    return re.findall(r"STORY-\d{2}-\d{3}", dep_text)


def _get_section_content(content: str, section_name: str) -> str:
    """Return the content of a '## section_name' block, or '' if missing."""
    sections = parse_sections(content)
    return sections.get(section_name, "")


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
# Story-level lifecycle (distinct from artifact-level VALID_STATUSES above).
# `developer-plugin:complete-stories` rejects anything outside this set.
VALID_STORY_STATUSES = {"To Do", "In Progress", "Done"}


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
                    f"Create at least one STORY-NN-NNN-{{slug}}.md file in {epic_dir.name}/."
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


def check_story_status_value(story_file: Path) -> list[ValidationResult]:
    """Reject artifact-level statuses (Draft / Approved / etc.) on story files.

    Stories have their own lifecycle: To Do → In Progress → Done.
    `developer-plugin:complete-stories` halts on anything else, so a
    "Draft" status leaking from the backlog template is a CRITICAL gate
    failure — catch it here.
    """
    results: list[ValidationResult] = []
    section = f"{story_file.parent.name}/{story_file.name}"
    content = story_file.read_text(encoding="utf-8")
    m = re.search(r"\|\s*\*\*Status\*\*\s*\|\s*([^|\n]+?)\s*\|", content)
    if not m:
        return results
    value = m.group(1).strip()
    if value not in VALID_STORY_STATUSES:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section=section,
                message=f'Story Status="{value}" is not a valid story-lifecycle value.',
                suggestion=(
                    "Stories use {" + ", ".join(sorted(VALID_STORY_STATUSES)) + "}. "
                    "Set Status to 'To Do' for newly-generated stories. 'Draft' is an "
                    "artifact-level status (used on the BACKLOG metadata table) and is "
                    "rejected by developer-plugin:complete-stories."
                ),
            )
        )
    return results


def check_verification_block(story_file: Path) -> list[ValidationResult]:
    """Validate the ``## Verification`` YAML block (presence + parseability + shape).

    Three findings, in increasing severity:

    1. Block missing  → WARNING (heuristic fallback still works).
    2. Block present but YAML parse fails  → CRITICAL (the runner will crash;
       common cause: unescaped regex metacharacters like ``\\s`` inside
       double-quoted YAML strings — use single quotes or ``\\\\s``).
    3. Block parses but is not a mapping of ``ACn`` → list  → CRITICAL (the
       runner expects ``{"AC1": [...], "AC2": [...]}``).

    Authoritative schema lives in ``developer-plugin/scripts/verify_acs.py``.
    """
    import yaml

    results: list[ValidationResult] = []
    section = f"{story_file.parent.name}/{story_file.name}"
    content = story_file.read_text(encoding="utf-8")

    block_match = re.search(
        r"^##\s+Verification\s*\n(.*?)(?=^##\s|\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    if not block_match:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section=section,
                message="Story has no `## Verification` block; AC verdicts will be heuristic-only.",
                suggestion=(
                    "Add a `## Verification` YAML block mapping each AC to verifier "
                    "specs (file_exists / file_count / grep / grep_count / pytest / manual). "
                    "See developer-plugin/scripts/verify_acs.py module docstring for schema."
                ),
            )
        )
        return results

    body = block_match.group(1)
    fence = re.search(r"```ya?ml\s*\n(.*?)\n```", body, re.DOTALL)
    payload = fence.group(1) if fence else body

    try:
        data = yaml.safe_load(payload)
    except yaml.YAMLError as e:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section=section,
                message=f"`## Verification` YAML failed to parse: {e}",
                suggestion=(
                    "Common cause: regex metacharacters like `\\s`, `\\d`, `\\b` inside "
                    "double-quoted YAML strings are invalid escapes. Use single quotes "
                    "(`'foo:\\s*bar'`) or double-escape (`\"foo:\\\\s*bar\"`). "
                    "verify_acs.py will crash on a malformed block."
                ),
            )
        )
        return results

    if not isinstance(data, dict) or not data:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section=section,
                message="`## Verification` block parsed but is not a non-empty AC→specs mapping.",
                suggestion="Top-level keys must be `AC1`, `AC2`, ... each mapped to specs.",
            )
        )
        return results

    bad_keys = [k for k in data if not re.fullmatch(r"AC\d+", str(k))]
    if bad_keys:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section=section,
                message=f"`## Verification` keys must match `ACn`; bad keys: {bad_keys}",
                suggestion="Rename keys to AC1, AC2, ... matching AC checkbox order.",
            )
        )

    return results


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


# --- Layer-closure checks (CRITICAL / WARNING) ---


def check_layer_closure(
    epic_dir: Path,
    story_type_by_id: dict[str, str],
    story_file_by_id: dict[str, Path],
) -> list[ValidationResult]:
    """Enforce the per-layer closure sequence: perf → integration-test → (optional) deploy.

    Fires CRITICAL / WARNING findings when a medallion-layer epic (detected via
    Epic Scope == layer OR LLD Section §5.1/§5.2/§5.3) is missing required
    closure stories, the integration-test lacks the DAG + UC wording, or the
    dependency order is inverted. For trailing epics, emits a WARNING when
    layer-specific perf/integration-test stories have leaked in.
    """
    results: list[ValidationResult] = []
    epic_file = find_epic_file(epic_dir)
    if not epic_file:
        return results

    epic_num = _epic_number_from_dir(epic_dir)
    epic_content = epic_file.read_text(encoding="utf-8")

    # Collect this epic's stories and their types
    story_files = find_story_files(epic_dir)
    epic_story_ids = [sid for sid in (_extract_story_id(s) for s in story_files) if sid]
    epic_story_types = {sid: story_type_by_id.get(sid, "build") for sid in epic_story_ids}
    types_present = set(epic_story_types.values())

    if is_layer_epic(epic_file):
        # CLOSURE-001: must have a performance-optimization story
        if "performance-optimization" not in types_present:
            results.append(
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    section=epic_dir.name,
                    message=(
                        "Layer epic has no performance-optimization story. "
                        "Every medallion-layer epic (LLD §5.1/§5.2/§5.3) must close with "
                        "a performance-optimization story derived from LLD §6."
                    ),
                    suggestion=(
                        "Add a STORY-NN-NNN with `Story Type: performance-optimization` "
                        "citing LLD §6 (partitioning, shuffle, join strategy, or caching)."
                    ),
                )
            )

        # CLOSURE-002: must have an integration-test story
        if "integration-test" not in types_present:
            results.append(
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    section=epic_dir.name,
                    message=(
                        "Layer epic has no integration-test story. "
                        "Every layer epic must close with a local integration test "
                        "(trigger layer DAG on local Airflow against Unity Catalog OSS local)."
                    ),
                    suggestion=(
                        "Add a STORY-NN-NNN with `Story Type: integration-test` whose "
                        "AC includes both the Airflow DAG trigger and validation of data "
                        "in Unity Catalog local."
                    ),
                )
            )

        # CLOSURE-003: integration-test AC must mention both "Airflow DAG" and "Unity Catalog"
        integration_story_ids = [
            sid for sid, stype in epic_story_types.items() if stype == "integration-test"
        ]
        for sid in integration_story_ids:
            sfile = story_file_by_id.get(sid)
            if not sfile:
                continue
            sfile_content = sfile.read_text(encoding="utf-8")
            ac_content = _get_section_content(sfile_content, "Acceptance Criteria")
            dag_ok = bool(DAG_WORDING_PATTERN.search(ac_content))
            uc_ok = bool(UC_WORDING_PATTERN.search(ac_content))
            if not (dag_ok and uc_ok):
                missing = []
                if not dag_ok:
                    missing.append("Airflow DAG")
                if not uc_ok:
                    missing.append("Unity Catalog")
                results.append(
                    ValidationResult(
                        level=ValidationLevel.CRITICAL,
                        section=f"{epic_dir.name}/{sfile.name}",
                        message=(
                            "Integration-test AC missing required wording: "
                            f"{', '.join(missing)}. Local integration testing means "
                            "triggering the layer DAG on local Airflow against Unity "
                            "Catalog OSS local and validating data in UC local."
                        ),
                        suggestion=(
                            "Rewrite acceptance criteria to include both the Airflow "
                            "DAG id (from LLD §4.2) being triggered and the Unity "
                            "Catalog local assertions (row counts, schema, metadata "
                            "columns, reconciliation)."
                        ),
                    )
                )

        # CLOSURE-004: integration-test must depend on a performance-optimization story from same epic  # noqa: E501
        perf_story_ids = {
            sid for sid, stype in epic_story_types.items() if stype == "performance-optimization"
        }
        for sid in integration_story_ids:
            sfile = story_file_by_id.get(sid)
            if not sfile:
                continue
            deps = _parse_dependency_story_ids(sfile)
            dep_set = set(deps)
            if perf_story_ids and not (perf_story_ids & dep_set):
                results.append(
                    ValidationResult(
                        level=ValidationLevel.CRITICAL,
                        section=f"{epic_dir.name}/{sfile.name}",
                        message=(
                            "Integration-test story does not depend on a "
                            "performance-optimization story from the same epic. "
                            "Closure order is perf BEFORE integration-test."
                        ),
                        suggestion=(
                            "Add one of these to the Dependencies metadata field: "
                            + ", ".join(sorted(perf_story_ids))
                        ),
                    )
                )

        # CLOSURE-005: if no deploy-validation, Objective must carry the Deploy N/A note
        if "deploy-validation" not in types_present:
            objective = _get_section_content(epic_content, "Objective")
            if not DEPLOY_NA_NOTE_PATTERN.search(objective):
                results.append(
                    ValidationResult(
                        level=ValidationLevel.WARNING,
                        section=epic_dir.name,
                        message=(
                            "Layer epic has no deploy-validation story and no explicit "
                            '"Deploy: N/A — layer completes at integration-test" note in '
                            "Objective. Closure intent is unclear."
                        ),
                        suggestion=(
                            "Either add a deploy-validation story (if LLD §9 prescribes "
                            "layer-scoped deploy work) OR add this line to the Objective "
                            "section: `Deploy: N/A — layer completes at integration-test; "
                            "system-wide deploy handled in trailing release epic.`"
                        ),
                    )
                )

    elif is_trailing_epic(epic_file):
        # CLOSURE-006: trailing epics should not contain layer-specific closure stories
        leaked = [
            sid
            for sid, stype in epic_story_types.items()
            if stype in TRAILING_FORBIDDEN_STORY_TYPES
        ]
        if leaked:
            results.append(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    section=epic_dir.name,
                    message=(
                        f"Trailing epic contains {len(leaked)} layer-specific closure "
                        f"story/stories ({', '.join(sorted(leaked))}). Closure work "
                        "belongs in the layer epic, not here."
                    ),
                    suggestion=(
                        "Move these stories into their corresponding layer epic "
                        "(EPIC-02 Bronze, EPIC-03 Silver-Dims, EPIC-04 Silver-Facts, "
                        "EPIC-05 Gold). Trailing epics are only for cross-layer "
                        "concerns: CI pipeline, PROD promotion, rollback runbook, "
                        "full-pipeline E2E load test, security audit, docs, maintenance."
                    ),
                )
            )

    _ = epic_num  # reserved for future per-epic logic
    return results


# --- Backlog-level: runtime-bootstrap presence (BOOTSTRAP-001) ---


def check_backlog_has_bootstrap(
    story_type_by_id: dict[str, str],
    directory: Path,
) -> list[ValidationResult]:
    """BOOTSTRAP-001: every backlog must contain ≥1 runtime-bootstrap story."""
    results: list[ValidationResult] = []
    if "runtime-bootstrap" not in set(story_type_by_id.values()):
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section=directory.name,
                message=(
                    "Backlog has no runtime-bootstrap story. Every backlog must include "
                    "≥1 story (typically in EPIC-01) whose ACs cover the dev runtime: "
                    "JDK 17 verified, docker compose up succeeds, UC catalog/schemas created, "
                    "source data seeded, smoke curl against UC OSS API returns 200."
                ),
                suggestion=(
                    "Add a STORY-NN-NNN with `Story Type: runtime-bootstrap` to the "
                    "foundation epic. Its ACs must include the runtime prerequisites "
                    "from LLD §1 (JDK/Spark/UC OSS/Airflow versions) and §6.1 (compute)."
                ),
            )
        )
    return results


# --- Backlog-level: SE end-to-end coverage (SE-COVERAGE-001) ---
#
# Spokane case (2026-04-26): every unit test passed (against mocked SE)
# but `with_expectations(...)` was never invoked end-to-end against real
# Spark. SE was "wired and importable" but not "ran". DQ silently did
# nothing. Mirror BOOTSTRAP-COVERAGE-001 (executor reachability) for SE.

# Triggers an SE-coverage requirement when seen in a non-bootstrap story.
# We only trigger on positive SE usage (the build story actually wires
# se_runner / SparkExpectations into a runner) — `grep_absent: ...se...`
# is the fail-closed AC and does NOT trigger.
_SE_USAGE_TRIGGER_PATTERN = re.compile(
    r"(SparkExpectations\b|WrappedDataFrameWriter|with_expectations|"
    r"\bse_runner\b|run_dq\b|spark[-_]expectations)",
    re.IGNORECASE,
)
# Discharges the requirement when seen in a runtime-bootstrap story's ACs.
# "imports cleanly" alone is INSUFFICIENT — must mention end-to-end run
# / stats table / with_expectations / dq_pass_rate.
_SE_BOOTSTRAP_COVERAGE_PATTERN = re.compile(
    r"(with_expectations|bronze_se_stats|silver_se_stats|gold_se_stats|"
    r"\b\w+_se_stats\b|dq_pass_rate|\bse\s+end[-\s]to[-\s]end\b|"
    r"runs\s+end[-\s]to[-\s]end|<table>_error|"
    r"_error\s+(?:table|delta\s+table))",
    re.IGNORECASE,
)
# Discharges the integration-test SE requirement (any SE runtime
# evidence: stats table query, error table presence, dq_pass_rate gauge).
_SE_INTEGRATION_EVIDENCE_PATTERN = re.compile(
    r"(\b\w+_se_stats\b|<table>_error|dq_pass_rate|"
    r"meta_dq_run_id|test_se_stats_populated|"
    r"test_dq_pass_rate)",
    re.IGNORECASE,
)


def check_se_coverage(
    story_type_by_id: dict[str, str],
    story_file_by_id: dict[str, Path],
    directory: Path,
) -> list[ValidationResult]:
    """SE-COVERAGE-001 (CRITICAL): bootstrap must verify SE runs end-to-end.

    Importing SparkExpectations is insufficient — the bootstrap story
    must contain ≥1 AC that mentions `with_expectations`, the SE stats
    table, `dq_pass_rate`, or an SE error table. Spokane's first run
    showed every unit test passing while `with_expectations` was never
    invoked against real data.
    """
    results: list[ValidationResult] = []

    se_using_story_ids: list[str] = []
    for sid, sfile in story_file_by_id.items():
        if story_type_by_id.get(sid) == "runtime-bootstrap":
            continue
        try:
            content = sfile.read_text(encoding="utf-8")
        except OSError:
            continue
        if _SE_USAGE_TRIGGER_PATTERN.search(content):
            se_using_story_ids.append(sid)

    if not se_using_story_ids:
        return results

    bootstrap_story_ids = [
        sid for sid, stype in story_type_by_id.items() if stype == "runtime-bootstrap"
    ]
    if not bootstrap_story_ids:
        # BOOTSTRAP-001 already fires for this case — don't double-report here.
        return results

    covered = False
    for sid in bootstrap_story_ids:
        sfile = story_file_by_id.get(sid)
        if not sfile:
            continue
        try:
            content = sfile.read_text(encoding="utf-8")
        except OSError:
            continue
        ac_body = _get_section_content(content, "Acceptance Criteria")
        if ac_body and _SE_BOOTSTRAP_COVERAGE_PATTERN.search(ac_body):
            covered = True
            break

    if covered:
        return results

    sample = ", ".join(sorted(se_using_story_ids)[:3])
    if len(se_using_story_ids) > 3:
        sample += f", … ({len(se_using_story_ids)} total)"
    results.append(
        ValidationResult(
            level=ValidationLevel.CRITICAL,
            section=directory.name,
            message=(
                f"Build stories ({sample}) wire Spark Expectations "
                "(SparkExpectations / WrappedDataFrameWriter / with_expectations / "
                "se_runner.run_dq) but no runtime-bootstrap story has an AC "
                "verifying SE actually runs end-to-end. Importing the package "
                "alone is insufficient — spokane shipped a 'DQ-wired' pipeline "
                "where with_expectations was never invoked against real data."
            ),
            suggestion=(
                "Add an AC to the runtime-bootstrap story that exercises SE "
                "end-to-end. Examples:\n"
                "  • `pytest -m integration tests/bootstrap/test_se_smoke.py::"
                "test_with_expectations_runs_end_to_end` invokes "
                "`WrappedDataFrameWriter(...).with_expectations(...)` against "
                "a real Spark session\n"
                "  • The test asserts `bronze_se_stats` has ≥1 row whose "
                "`meta_dq_run_id` matches the run\n"
                "DQ is mandatory in chapter-5 — `BRONZE_SKIP_SE=1` and "
                "similar bypasses are explicitly forbidden."
            ),
        )
    )
    return results


def check_integration_se_evidence(
    epic_dir: Path,
    story_type_by_id: dict[str, str],
    story_file_by_id: dict[str, Path],
) -> list[ValidationResult]:
    """STORIES-INTEGRATION-SE-001 (CRITICAL): integration-test stories that
    trigger a layer DAG MUST assert SE runtime artifacts (stats/error table,
    dq_pass_rate). The DAG firing alone is insufficient — DQ ran is the gate.

    Operates per-epic; only fires on layer epics whose integration-test
    stories already match CLOSURE-003 (mention Airflow DAG + UC). Without
    SE runtime evidence the run can land Bronze tables in UC while DQ
    silently did nothing — exactly the spokane regression.
    """
    results: list[ValidationResult] = []
    epic_file = find_epic_file(epic_dir)
    if not epic_file:
        return results
    if not is_layer_epic(epic_file):
        return results

    story_files = find_story_files(epic_dir)
    for sf in story_files:
        sid = _extract_story_id(sf)
        if not sid:
            continue
        if story_type_by_id.get(sid) != "integration-test":
            continue
        try:
            content = sf.read_text(encoding="utf-8")
        except OSError:
            continue
        ac_body = _get_section_content(content, "Acceptance Criteria")
        verif_body = _get_section_content(content, "Verification")
        # The story must mention SE runtime evidence somewhere in AC or
        # Verification — checking both gives the author flexibility (a
        # `pytest:` verifier hitting `test_se_stats_populated` discharges
        # the rule even if the AC text is brief).
        combined = (ac_body or "") + "\n" + (verif_body or "")
        if _SE_INTEGRATION_EVIDENCE_PATTERN.search(combined):
            continue
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section=f"{epic_dir.name}/{sf.name}",
                message=(
                    "Integration-test story triggers a layer DAG but has no AC "
                    "asserting SE runtime artifacts. DQ silently doing nothing "
                    "is exactly the spokane gap — DAG ran ≠ SE ran."
                ),
                suggestion=(
                    "Add an AC asserting at least one of: (a) `bronze_se_stats` "
                    "(or the configured layer SE stats table) has ≥1 row whose "
                    "`meta_dq_run_id` matches the DAG run, (b) "
                    "`<table>_error` Delta tables created (or empty for clean "
                    "runs), (c) `dq_pass_rate` reported in Marquez run facets / "
                    "Grafana dashboard. Pair the AC with a `pytest:` verifier "
                    "such as `test_se_stats_populated` or `test_dq_pass_rate`."
                ),
            )
        )
    return results


# --- Per-story: Liquibase master-changelog scope (LIQUIBASE-MASTER-SCOPE-001) ---
#
# LLD §9.1 mandates a single project-wide `master-changelog.xml` that includes
# every per-table changelog across Bronze + Silver + Gold. A layer-scoped
# deploy-validation story that asserts the master includes only its own
# layer's tables (e.g. "all 13 Bronze changelogs") contradicts §9.1 and will
# halt the developer-plugin orchestrator (validate-ingestion + complete-stories).
#
# Spokane case (2026-05-11): STORY-02-004 AC2 read "master-changelog.xml
# includes all 13 Bronze changelogs" — on-disk file correctly contained 29
# (Bronze+Silver+Gold), so AC2 failed verification even though the artifact
# was LLD-compliant. The "13" came from an illustrative example in
# create-stories SKILL.md that the LLM applied verbatim.

_MASTER_CHANGELOG_LAYER_SCOPED_PHRASES = (
    re.compile(
        r"master[-_]changelog(?:\.xml)?[^.]{0,80}?\ball\s+\d+\s+(?:Bronze|Silver|Gold)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"master[-_]changelog(?:\.xml)?[^.]{0,80}?\b(?:Bronze|Silver|Gold)[-_\s]*(?:only|scoped|specific)",
        re.IGNORECASE,
    ),
)


def check_liquibase_master_scope(story_file: Path) -> list[ValidationResult]:
    """LIQUIBASE-MASTER-SCOPE-001 (CRITICAL): a story's AC or Verification
    block scopes `master-changelog.xml` to a single layer (e.g. "all 13
    Bronze changelogs"). LLD §9.1 mandates the master spans all
    Bronze+Silver+Gold tables.
    """
    results: list[ValidationResult] = []
    try:
        content = story_file.read_text(encoding="utf-8")
    except OSError:
        return results

    ac_body = _get_section_content(content, "Acceptance Criteria") or ""
    verif_body = _get_section_content(content, "Verification") or ""
    combined = ac_body + "\n" + verif_body

    if "master-changelog" not in combined.lower():
        return results

    for pat in _MASTER_CHANGELOG_LAYER_SCOPED_PHRASES:
        m = pat.search(combined)
        if m:
            results.append(
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    section=f"{story_file.parent.name}/{story_file.name}",
                    message=(
                        f"AC/Verification scopes `master-changelog.xml` to a "
                        f"single layer (matched: {m.group(0)!r}). LLD §9.1 "
                        f"mandates a project-wide master spanning all "
                        f"Bronze+Silver+Gold tables."
                    ),
                    suggestion=(
                        "Rewrite the AC as: \"master-changelog.xml includes "
                        "all N project changelogs (Bronze + Silver + Gold) "
                        "per LLD §9.1\" where N is the total table count "
                        "across all three layers. Update the corresponding "
                        "grep_count / include count in the Verification block "
                        "to match. Per-table changelog counts (file_count) "
                        "are layer-scoped and remain unchanged."
                    ),
                )
            )
            break
    return results


# --- Backlog-level: cross-story AC contradiction (AC-CONTRADICTION-001) ---
#
# Spokane case (2026-04-26): STORY-02-001 AC4 used `grep` for
# "WARNING: se_runner not available" while STORY-02-004 AC4 used
# `grep_absent` for the same string in the same file, both citing
# LLD §8.6. They cannot both be true. The user had to hand-edit one
# story to mark its AC superseded — exactly the gap this rule guards.
#
# A Depends-On edge from the fail-closed story to the bootstrap story
# discharges the rule (the bootstrap AC ships first, then the
# fail-closed AC supersedes it).

# Match a `[LLD §X.Y]` / `[HLD §X]` / `[DRD §X.Y]` etc. citation in AC text.
_ARTIFACT_SECTION_REF = re.compile(
    r"\[(?:LLD|HLD|DMS|DQS|STM|DRD)\s*§\s*(\d+(?:\.\d+)*)\]",
    re.IGNORECASE,
)


def _extract_lld_sections_cited(story_file: Path) -> set[str]:
    """Return the set of LLD §X.Y sections cited in the story's ## Acceptance Criteria."""
    try:
        content = story_file.read_text(encoding="utf-8")
    except OSError:
        return set()
    ac_body = _get_section_content(content, "Acceptance Criteria")
    if not ac_body:
        return set()
    return {m.group(1) for m in _ARTIFACT_SECTION_REF.finditer(ac_body)}


def _extract_grep_verifiers(
    story_file: Path,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Return (grep_pairs, grep_absent_pairs) where each pair is (file, pattern).

    Reads the story's ``## Verification`` YAML. Skips silently on parse
    errors (the existing `check_verification_block` rule reports those).
    """
    import yaml

    try:
        content = story_file.read_text(encoding="utf-8")
    except OSError:
        return [], []
    block = _get_section_content(content, "Verification")
    if not block:
        return [], []
    fence = re.search(r"```ya?ml\s*\n(.*?)\n```", block, re.DOTALL)
    payload = fence.group(1) if fence else block
    try:
        data = yaml.safe_load(payload)
    except yaml.YAMLError:
        return [], []
    if not isinstance(data, dict):
        return [], []

    grep_pairs: list[tuple[str, str]] = []
    grep_absent_pairs: list[tuple[str, str]] = []
    for specs in data.values():
        items = specs if isinstance(specs, list) else [specs]
        for spec in items:
            if not isinstance(spec, dict) or len(spec) != 1:
                continue
            kind = next(iter(spec.keys()))
            value = spec[kind]
            kind_norm = str(kind).strip().lower()
            if kind_norm not in ("grep", "grep_absent"):
                continue
            file_arg = pattern_arg = ""
            if isinstance(value, dict):
                file_arg = str(value.get("file", "")).strip()
                pattern_arg = str(value.get("pattern", "")).strip()
            if not file_arg or not pattern_arg:
                continue
            target = (file_arg, pattern_arg)
            if kind_norm == "grep":
                grep_pairs.append(target)
            else:
                grep_absent_pairs.append(target)
    return grep_pairs, grep_absent_pairs


def check_ac_contradictions(
    story_type_by_id: dict[str, str],
    story_file_by_id: dict[str, Path],
    directory: Path,
) -> list[ValidationResult]:
    """STORIES-AC-CONTRADICTION-001 (CRITICAL): two stories assert opposite
    things about the same file/pattern, both cite the same LLD §, no
    Depends-On link orders them.

    Once the create-stories SKILL adds the auto-Depends-On for phased
    contracts (Step 2.5), this rule becomes a no-op for correctly-generated
    backlogs and a regression guard for hand-edited ones.
    """
    results: list[ValidationResult] = []

    # Cache per-story artifacts so we don't reread N times.
    sections_by_id: dict[str, set[str]] = {}
    greps_by_id: dict[str, list[tuple[str, str]]] = {}
    absents_by_id: dict[str, list[tuple[str, str]]] = {}
    deps_by_id: dict[str, set[str]] = {}
    for sid, sfile in story_file_by_id.items():
        sections_by_id[sid] = _extract_lld_sections_cited(sfile)
        g, a = _extract_grep_verifiers(sfile)
        greps_by_id[sid] = g
        absents_by_id[sid] = a
        deps_by_id[sid] = set(_parse_dependency_story_ids(sfile))

    seen_pairs: set[tuple[str, str, str, str]] = set()
    sorted_ids = sorted(story_file_by_id.keys())
    for a_id in sorted_ids:
        a_greps = greps_by_id.get(a_id, [])
        a_sections = sections_by_id.get(a_id, set())
        if not a_greps or not a_sections:
            continue
        for b_id in sorted_ids:
            if a_id == b_id:
                continue
            b_absents = absents_by_id.get(b_id, [])
            b_sections = sections_by_id.get(b_id, set())
            if not b_absents or not b_sections:
                continue
            shared_sections = a_sections & b_sections
            if not shared_sections:
                continue
            # Depends-On wiring discharges the rule.
            if a_id in deps_by_id.get(b_id, set()) or b_id in deps_by_id.get(a_id, set()):
                continue
            for a_file, a_pattern in a_greps:
                for b_file, b_pattern in b_absents:
                    if a_file != b_file:
                        continue
                    if a_pattern.strip() != b_pattern.strip():
                        continue
                    key = (a_id, b_id, a_file, a_pattern)
                    if key in seen_pairs:
                        continue
                    seen_pairs.add(key)
                    sample_section = sorted(shared_sections)[0]
                    results.append(
                        ValidationResult(
                            level=ValidationLevel.CRITICAL,
                            section=directory.name,
                            message=(
                                f"AC contradiction: {a_id}'s `grep` and "
                                f"{b_id}'s `grep_absent` target the same "
                                f"file `{a_file}` and pattern `{a_pattern}`, "
                                f"and both cite LLD §{sample_section}. "
                                "Without a Depends-On link the two ACs cannot "
                                "both be true."
                            ),
                            suggestion=(
                                f"Add `| **Dependencies** | {a_id} |` to the "
                                f"metadata of {b_id} (the fail-closed side) "
                                f"so the validator sees that {b_id} ships "
                                f"after {a_id}'s bootstrap behavior, "
                                "superseding it. The phased-contract guard in "
                                "create-stories Step 2.5 emits this edge "
                                "automatically; if the backlog was hand-edited, "
                                "add the line manually."
                            ),
                        )
                    )
    return results


# --- Backlog-level: bootstrap covers every executor a build story invokes ---
# (BOOTSTRAP-COVERAGE-001)
#
# Motivation: a build story can invoke SparkSubmitOperator while the
# runtime-bootstrap story only checks UC catalogs. Bootstrap then passes,
# every build story FAILs at first execution because spark-submit is missing
# or unreachable. This rule enforces that, when build stories use Spark, the
# bootstrap story explicitly proves the Airflow→Spark bridge before any
# integration test runs against it.

# Triggers a Spark requirement when seen in a non-bootstrap story body.
_SPARK_TRIGGER_PATTERN = re.compile(
    r"SparkSubmitOperator|\bspark-submit\b|\bpyspark\b|--master\b",
    re.IGNORECASE,
)
# Discharges the requirement when seen in a runtime-bootstrap story's ACs.
_SPARK_BOOTSTRAP_COVERAGE_PATTERN = re.compile(
    r"\bspark-submit\b|\bspark\.master\b|\bpyspark\b|--master\b|airflow\s+tasks\s+test",
    re.IGNORECASE,
)


def check_bootstrap_executor_coverage(
    story_type_by_id: dict[str, str],
    story_file_by_id: dict[str, Path],
    directory: Path,
) -> list[ValidationResult]:
    """BOOTSTRAP-COVERAGE-001: bootstrap must verify every executor build stories invoke.

    Today this rule covers Spark only — when any non-bootstrap story (typically
    a `build` story) references ``SparkSubmitOperator`` / ``spark-submit`` /
    ``pyspark`` / ``--master``, the runtime-bootstrap story(ies) collectively
    must contain ≥1 line in their ``## Acceptance Criteria`` mentioning
    ``spark-submit``, ``spark.master``, ``pyspark``, ``--master``, or
    ``airflow tasks test``. Without that AC, a passing bootstrap doesn't
    actually prove the Airflow→Spark bridge works, and every Spark-backed
    build story fails on first execution.
    """
    results: list[ValidationResult] = []

    spark_using_story_ids: list[str] = []
    for sid, sfile in story_file_by_id.items():
        if story_type_by_id.get(sid) == "runtime-bootstrap":
            continue
        try:
            content = sfile.read_text(encoding="utf-8")
        except OSError:
            continue
        if _SPARK_TRIGGER_PATTERN.search(content):
            spark_using_story_ids.append(sid)

    if not spark_using_story_ids:
        return results

    bootstrap_story_ids = [
        sid for sid, stype in story_type_by_id.items() if stype == "runtime-bootstrap"
    ]
    if not bootstrap_story_ids:
        # BOOTSTRAP-001 already fires for this case — don't double-report here.
        return results

    covered = False
    for sid in bootstrap_story_ids:
        sfile = story_file_by_id.get(sid)
        if not sfile:
            continue
        try:
            content = sfile.read_text(encoding="utf-8")
        except OSError:
            continue
        ac_body = _get_section_content(content, "Acceptance Criteria")
        if ac_body and _SPARK_BOOTSTRAP_COVERAGE_PATTERN.search(ac_body):
            covered = True
            break

    if covered:
        return results

    sample = ", ".join(sorted(spark_using_story_ids)[:3])
    if len(spark_using_story_ids) > 3:
        sample += f", … ({len(spark_using_story_ids)} total)"
    results.append(
        ValidationResult(
            level=ValidationLevel.CRITICAL,
            section=directory.name,
            message=(
                f"Build stories ({sample}) invoke Spark "
                "(SparkSubmitOperator / spark-submit / pyspark / --master) but no "
                "runtime-bootstrap story has an Acceptance Criterion that verifies "
                "spark-submit reachability. The bootstrap will pass while every "
                "Spark-backed task FAILs on first execution — exactly the gap that "
                "motivated the runtime-bootstrap story type."
            ),
            suggestion=(
                "Add an AC to the runtime-bootstrap story whose wording matches the "
                "LLD §6.1 `local_executor_mode`. Examples:\n"
                "  • in-airflow-local[*]: `docker compose exec airflow-scheduler "
                "spark-submit --version` exits 0\n"
                "  • sidecar-spark: `docker compose exec airflow-scheduler "
                "spark-submit --master spark://spark-master:7077 --version` exits 0\n"
                "  • external-cluster: `airflow tasks test <bronze-dag-id> "
                "<one-spark-task> <ds>` exits 0\n"
                "Pair the AC with a `pytest:` verifier (e.g. "
                "tests/bootstrap/test_spark_smoke.py) so verify_acs.py can gate it."
            ),
        )
    )
    return results


# --- Per-story: ## Testing / ## How to Test (User) / ## Documentation Updates ---


def _has_section_with_content(content: str, heading: str) -> bool:
    """Return True if a `## heading` section exists AND contains non-whitespace content."""
    body = _get_section_content(content, heading)
    return bool(body and body.strip())


def _list_item_count(text: str) -> int:
    """Count markdown list items (bulleted or checkbox) in a section body."""
    return len(re.findall(r"^\s*-\s+(?:\[[ xX]\]\s+)?\S", text, re.MULTILINE))


def _numbered_step_count(text: str) -> int:
    """Count `1.` / `2.` numbered list steps in a section body."""
    return len(re.findall(r"^\s*\d+\.\s+\S", text, re.MULTILINE))


def _table_row_count(text: str) -> int:
    """Count data rows (post-header, post-separator) in a markdown pipe table.

    Header + separator are the first two `|...|` lines; remaining `|...|` lines
    are data rows. Returns 0 if there's no recognizable table.
    """
    pipe_lines = [
        ln for ln in text.splitlines() if ln.strip().startswith("|") and ln.count("|") >= 2
    ]
    return max(0, len(pipe_lines) - 2)


def check_testing_section(story_file: Path) -> list[ValidationResult]:
    """TESTING-001: every story must have a populated `## Testing` section with ≥1 row."""
    results: list[ValidationResult] = []
    section = f"{story_file.parent.name}/{story_file.name}"
    content = story_file.read_text(encoding="utf-8")
    body = _get_section_content(content, "Testing")
    rows = _table_row_count(body) if body else 0
    if rows < 1:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section=section,
                message=(
                    "Story has no `## Testing` section with ≥1 coverage row. Every story "
                    "must declare what automated coverage exists: Unit, Contract, Integration, "
                    "Smoke, DQ, or Benchmark, with each row mapping to a verifier in the "
                    "`## Verification` block."
                ),
                suggestion=(
                    "Add a `## Testing` table with rows appropriate to the story type. "
                    "build → Unit (required), Contract (if creates contracts/*.yml). "
                    "integration-test → Unit + Integration + Smoke + DQ (all required). "
                    "runtime-bootstrap → Smoke (required). performance-optimization → Benchmark. "
                    "Format: | Coverage | What | How |"
                ),
            )
        )
    return results


def check_user_test_section(story_file: Path, story_type: str) -> list[ValidationResult]:
    """USER-TEST-001: build/integration-test/runtime-bootstrap need user-runnable test steps.

    Requires the section to exist AND contain ≥1 numbered step under "Steps".
    A bare heading skeleton with empty subsections fails the rule — the user
    must be able to act on the section, not just see that it was rendered.
    """
    results: list[ValidationResult] = []
    section = f"{story_file.parent.name}/{story_file.name}"
    content = story_file.read_text(encoding="utf-8")
    body = _get_section_content(content, "How to Test (User)")
    step_count = _numbered_step_count(body) if body else 0
    if step_count >= 1:
        return results

    is_required = story_type in USER_TEST_REQUIRED_TYPES
    level = ValidationLevel.CRITICAL if is_required else ValidationLevel.WARNING
    qualifier = "must" if is_required else "should"
    results.append(
        ValidationResult(
            level=level,
            section=section,
            message=(
                f"Story (type={story_type}) {qualifier} have a `## How to Test (User)` "
                "section with ≥1 numbered step (prerequisites + exact commands + expected "
                "output a human can run on their own machine)."
            ),
            suggestion=(
                "Populate `## How to Test (User)` with: ### Prerequisites "
                "(deps the user must have), ### Steps (numbered shell commands the user "
                "runs — `1. cmd`, `2. cmd`), ### Expected outcome. Independent verification "
                "should not require reading the developer's mind."
            ),
        )
    )
    return results


def check_documentation_updates(story_file: Path, story_type: str) -> list[ValidationResult]:
    """DOCS-001: runtime-bootstrap/integration-test/release must list ≥1 README update.

    Build stories get a WARNING when they create new files under src/, airflow/, or
    _infra/ (detected via ``file_exists``/``file_count`` paths in the Verification block)
    but list no documentation updates — runbook drift is a real cost.
    """
    results: list[ValidationResult] = []
    section = f"{story_file.parent.name}/{story_file.name}"
    content = story_file.read_text(encoding="utf-8")
    body = _get_section_content(content, "Documentation Updates")
    item_count = _list_item_count(body) if body else 0

    is_required = story_type in DOCS_UPDATE_REQUIRED_TYPES
    if is_required and item_count < 1:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section=section,
                message=(
                    f"Story (type={story_type}) is missing a populated `## Documentation "
                    "Updates` section with ≥1 README/runbook update item."
                ),
                suggestion=(
                    "Add a `## Documentation Updates` section listing specific README "
                    "sections that must change for this story, e.g. "
                    '`- [ ] Update <project>/README.md § "Run pipeline" with the new '
                    "DAG trigger command`. Runbook drift breaks future operators."
                ),
            )
        )
        return results

    if story_type == "build" and item_count < 1:
        creates_runtime_files = _verification_creates_runtime_files(content)
        if creates_runtime_files:
            results.append(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    section=section,
                    message=(
                        "Build story creates files under src/, airflow/, or _infra/ but "
                        "lists no documentation updates. New code typically needs a "
                        "README/runbook hook so future operators can find it."
                    ),
                    suggestion=(
                        "Either add a `## Documentation Updates` item naming the README "
                        "section to update, or explicitly state `- N/A — internal-only "
                        "module, not user-facing` to record the conscious choice."
                    ),
                )
            )
    return results


_RUNTIME_PATH_PATTERN = re.compile(
    r'(?:^|["\'/])(?:src|airflow|_infra)/',
    re.IGNORECASE | re.MULTILINE,
)


def _verification_creates_runtime_files(content: str) -> bool:
    """Heuristic: does the story's Verification block reference src/, airflow/, or _infra/?

    Looks for any path in the Verification YAML body whose head component is
    `src/`, `airflow/`, or `_infra/` — anchored to start-of-line, a quote, or
    a path separator so we don't false-positive on `mysrc/` or similar.
    """
    block = _get_section_content(content, "Verification")
    if not block:
        return False
    return bool(_RUNTIME_PATH_PATTERN.search(block))


# --- Per-integration-test: automated verifier required (INTEGRATION-AUTOMATED-001) ---


def _count_non_manual_verifiers(content: str) -> int:
    """Count verifier specs in the ## Verification block whose kind is NOT 'manual'.

    Returns 0 if the block is missing or unparseable. Used to enforce that
    integration-test stories carry at least one automated verifier — the
    closure pattern previously allowed 100% manual, which meant an integration
    test could close without ever actually running.
    """
    import yaml

    block = _get_section_content(content, "Verification")
    if not block:
        return 0
    fence = re.search(r"```ya?ml\s*\n(.*?)\n```", block, re.DOTALL)
    payload = fence.group(1) if fence else block
    try:
        data = yaml.safe_load(payload)
    except yaml.YAMLError:
        return 0
    if not isinstance(data, dict):
        return 0

    n = 0
    for specs in data.values():
        items = specs if isinstance(specs, list) else [specs]
        for spec in items:
            if isinstance(spec, str):
                # Bare strings resolve to file_exists in verify_acs.py — automated.
                n += 1
                continue
            if isinstance(spec, dict) and len(spec) == 1:
                kind = next(iter(spec.keys()))
                if str(kind).strip().lower() != "manual":
                    n += 1
    return n


def check_integration_test_automated(story_file: Path, story_type: str) -> list[ValidationResult]:
    """INTEGRATION-AUTOMATED-001: integration-test stories need ≥1 non-manual verifier.

    Closes the loophole where 100% manual verifiers let an integration-test story
    pass closure validation without any test actually running. The DAG-trigger and
    UC assertion must be expressed as a `pytest:` (or `validator:`) verifier so
    `verify_acs.py` and `complete-stories` can gate Done on a real run.
    """
    if story_type != "integration-test":
        return []
    content = story_file.read_text(encoding="utf-8")
    if _count_non_manual_verifiers(content) >= 1:
        return []
    section = f"{story_file.parent.name}/{story_file.name}"
    return [
        ValidationResult(
            level=ValidationLevel.CRITICAL,
            section=section,
            message=(
                "Integration-test story has 0 automated verifiers (all `manual:` or "
                "missing `## Verification`). Local integration testing is the gate that "
                "proves data actually landed in UC — it must run, not be eyeballed."
            ),
            suggestion=(
                "Add at least one non-manual verifier to the `## Verification` block, e.g. "
                '`pytest: {node: "<project>/tests/integration/test_<layer>_uc.py", '
                'marker: "integration"}` — the test should trigger the layer DAG, wait '
                "for completion, and assert ≥1 expected table is registered in UC OSS local."
            ),
        )
    ]


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

    # Collect all story IDs for dependency checking and layer-closure checks
    all_story_ids: set[str] = set()
    all_story_files: list[Path] = []
    story_type_by_id: dict[str, str] = {}
    story_file_by_id: dict[str, Path] = {}
    for epic_dir in epic_dirs:
        story_files = find_story_files(epic_dir)
        all_story_files.extend(story_files)
        for sf in story_files:
            sid = _extract_story_id(sf)
            if sid:
                all_story_ids.add(sid)
                story_type_by_id[sid] = get_story_type(sf)
                story_file_by_id[sid] = sf

    # Backlog-level: BOOTSTRAP-001
    report.results.extend(check_backlog_has_bootstrap(story_type_by_id, directory))

    # Backlog-level: BOOTSTRAP-COVERAGE-001 (executor reachability)
    report.results.extend(
        check_bootstrap_executor_coverage(story_type_by_id, story_file_by_id, directory)
    )

    # Backlog-level: AC-CONTRADICTION-001 (cross-story phased-contract guard)
    report.results.extend(check_ac_contradictions(story_type_by_id, story_file_by_id, directory))

    # Backlog-level: SE-COVERAGE-001 (bootstrap verifies SE runs end-to-end)
    report.results.extend(check_se_coverage(story_type_by_id, story_file_by_id, directory))

    # Check each epic
    for epic_dir in epic_dirs:
        report.results.extend(check_epic_has_file(epic_dir))
        epic_file = find_epic_file(epic_dir)
        if epic_file:
            report.results.extend(check_epic_sections(epic_file))
            epic_content = epic_file.read_text(encoding="utf-8")
            report.results.extend(check_placeholders(epic_content, epic_dir.name))

        report.results.extend(check_stories_exist(epic_dir))
        report.results.extend(check_layer_closure(epic_dir, story_type_by_id, story_file_by_id))
        report.results.extend(
            check_integration_se_evidence(epic_dir, story_type_by_id, story_file_by_id)
        )

        story_files = find_story_files(epic_dir)
        for story_file in story_files:
            sid = _extract_story_id(story_file)
            stype = story_type_by_id.get(sid, "build") if sid else "build"
            report.results.extend(check_story_sections(story_file))
            report.results.extend(check_upstream_traceability(story_file))
            report.results.extend(check_verification_block(story_file))
            report.results.extend(check_story_status_value(story_file))
            report.results.extend(check_dependency_consistency(story_file, all_story_ids))
            report.results.extend(check_sprint_allocation(story_file))
            report.results.extend(check_story_points(story_file))
            report.results.extend(check_estimation_support(story_file))
            report.results.extend(check_testing_section(story_file))
            report.results.extend(check_user_test_section(story_file, stype))
            report.results.extend(check_documentation_updates(story_file, stype))
            report.results.extend(check_integration_test_automated(story_file, stype))
            report.results.extend(check_liquibase_master_scope(story_file))
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
