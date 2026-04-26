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
}

LAYER_REQUIRED_STORY_TYPES = {"performance-optimization", "integration-test"}
TRAILING_FORBIDDEN_STORY_TYPES = {
    "performance-optimization",
    "integration-test",
    "deploy-validation",
}


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

        story_files = find_story_files(epic_dir)
        for story_file in story_files:
            report.results.extend(check_story_sections(story_file))
            report.results.extend(check_upstream_traceability(story_file))
            report.results.extend(check_verification_block(story_file))
            report.results.extend(check_story_status_value(story_file))
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
