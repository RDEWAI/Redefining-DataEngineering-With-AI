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


DEFAULT_SCAFFOLD_TOP_DIRS = (
    "src",
    "tests",
    "airflow",
    "contracts",
    "dq_rules",
    "ddl",
    "_infra",
)


def _load_scaffold_dirs(template_root: Path | None) -> tuple[str, ...]:
    """Read the cookiecutter scaffold tree once and return expected top-level dirs.

    Falls back to DEFAULT_SCAFFOLD_TOP_DIRS if template_root is missing or empty.
    The template_root is expected to be the directory containing
    `{{cookiecutter.project_name}}/` (i.e. the chapter-level cookiecutter dir).
    """
    if not template_root or not template_root.exists():
        return DEFAULT_SCAFFOLD_TOP_DIRS
    project_dirs = list(template_root.glob("*"))
    if not project_dirs:
        return DEFAULT_SCAFFOLD_TOP_DIRS
    inner = project_dirs[0]
    if not inner.is_dir():
        return DEFAULT_SCAFFOLD_TOP_DIRS
    dirs = [p.name for p in inner.iterdir() if p.is_dir()]
    return tuple(sorted(dirs)) if dirs else DEFAULT_SCAFFOLD_TOP_DIRS


def _find_scaffold_root(lld_path: Path) -> Path | None:
    """Walk up from the LLD and look for `inputs/lld/v*/templates/cookiecutter-chapter/`."""
    for ancestor in [lld_path.parent, *lld_path.parents]:
        candidate = list(ancestor.glob("inputs/lld/v*/templates/cookiecutter-chapter"))
        if candidate:
            latest = sorted(candidate)[-1]
            project_dir = next(
                (p for p in latest.iterdir() if p.is_dir() and p.name.startswith("{{")),
                None,
            )
            if project_dir:
                inner = next(
                    (p for p in project_dir.iterdir() if p.is_dir() and p.name.startswith("{{")),
                    None,
                )
                if inner:
                    return inner.parent
    return None


def _parse_header_metadata(content: str) -> dict[str, str]:
    """Parse the LLD header metadata table at the top of the file."""
    header_end = content.find("\n## ")
    header = content[:header_end] if header_end != -1 else content
    meta: dict[str, str] = {}
    for line in header.split("\n"):
        stripped = line.strip()
        if not stripped.startswith("|") or all(c in "|- " for c in stripped):
            continue
        cells = [c.strip() for c in stripped.split("|")[1:-1]]
        if len(cells) >= 2 and cells[0].lower() != "field":
            key = cells[0].strip("*` ")
            value = cells[1].strip("*` ")
            meta[key] = value
    return meta


def _extract_table_headers(section_content: str) -> list[str]:
    """Return the header row cells of the first markdown table in the section."""
    lines = section_content.strip().split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("|") and not all(c in "|- " for c in stripped):
            if i + 1 < len(lines) and all(c in "|- " for c in lines[i + 1].strip()):
                return [c.strip().lower() for c in stripped.split("|")[1:-1]]
    return []


def check_scaffold_metadata(content: str) -> list[ValidationResult]:
    """CRITICAL: metadata must contain Target Scaffold, Project Name, and Chapter rows."""
    results: list[ValidationResult] = []
    meta = _parse_header_metadata(content)
    for field_name in ("Target Scaffold", "Project Name", "Chapter"):
        if field_name not in meta or not meta[field_name]:
            results.append(
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    section="Metadata",
                    message=f'Metadata row "{field_name}" is missing or empty.',
                    suggestion=(
                        f'Add a "| **{field_name}** | ... |" row to the header table. '
                        "Target Scaffold should reference `inputs/lld/v{N}/templates/"
                        "cookiecutter-chapter/`; Project Name and Chapter must match "
                        "cookiecutter.json."
                    ),
                )
            )
    return results


def check_scaffold_layout(
    sections: dict[str, str], scaffold_top_dirs: tuple[str, ...]
) -> list[ValidationResult]:
    """CRITICAL: §2.1 Project Layout must list the expected scaffold top-level dirs."""
    results: list[ValidationResult] = []
    content = sections.get("2. Code Architecture", "")
    if not content:
        return results

    has_subsection = bool(re.search(r"^\s*###\s+2\.1", content, re.MULTILINE))
    if not has_subsection:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="2. Code Architecture",
                message="Missing §2.1 Project Layout subsection.",
                suggestion=(
                    "Add a `### 2.1 Project Layout` subsection that renders the "
                    "cookiecutter scaffold tree as a fenced code block."
                ),
            )
        )

    missing = [d for d in scaffold_top_dirs if d not in content]
    if missing:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="2. Code Architecture",
                message=(
                    "§2.1 Project Layout is missing scaffold top-level dirs: "
                    f"{', '.join(missing)}."
                ),
                suggestion=(
                    "Include every cookiecutter top-level directory in the §2.1 tree: "
                    + ", ".join(scaffold_top_dirs)
                    + "."
                ),
            )
        )
    return results


def check_task_table_columns(sections: dict[str, str]) -> list[ValidationResult]:
    """CRITICAL: §5 task table must have the scaffold-aligned column set."""
    results: list[ValidationResult] = []
    content = sections.get("5. Task Implementation Details", "")
    if not content:
        return results
    headers = _extract_table_headers(content)
    required = ["module path", "contract file", "dq rules file", "dag task node"]
    missing = [h for h in required if h not in headers]
    if missing:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="5. Task Implementation Details",
                message=(
                    "§5 task table is missing required columns: "
                    + ", ".join(m.title() for m in missing)
                    + "."
                ),
                suggestion=(
                    "Task table must include: Task ID | Layer | Module Path | "
                    "Contract File | DQ Rules File | DAG Task Node | Inputs | Outputs "
                    "| Transform Ref | DQ Check."
                ),
            )
        )
    return results


def check_scaffold_paths(sections: dict[str, str], content: str) -> list[ValidationResult]:
    """WARNING: src/, contracts/, dq_rules/ paths in §5 must match scaffold conventions."""
    results: list[ValidationResult] = []
    meta = _parse_header_metadata(content)
    project_name = meta.get("Project Name", "").strip()
    section_5 = sections.get("5. Task Implementation Details", "")
    if not section_5:
        return results

    src_paths = re.findall(r"`(src/[^`]+)`", section_5)
    if project_name:
        bad_src = [
            p
            for p in src_paths
            if not re.match(rf"^src/{re.escape(project_name)}/(bronze|silver|gold|utils)/", p)
        ]
        if bad_src:
            results.append(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    section="5. Task Implementation Details",
                    message=(
                        f"§5 has src/ paths that don't match the scaffold shape "
                        f"`src/{project_name}/{{bronze|silver|gold|utils}}/`: "
                        f"{', '.join(bad_src[:5])}" + ("..." if len(bad_src) > 5 else "")
                    ),
                    suggestion=(
                        "Rename modules to live under `src/{project_name}/"
                        "{bronze|silver|gold|utils}/` or log the deviation in §13 "
                        "Decision Log."
                    ),
                )
            )

    contract_paths = re.findall(r"`(contracts/[^`]+)`", section_5)
    bad_contracts = [p for p in contract_paths if not re.match(r"^contracts/[^/]+\.yml$", p)]
    if bad_contracts:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="5. Task Implementation Details",
                message=(
                    "Contract file paths in §5 don't match `contracts/*.yml`: "
                    + ", ".join(bad_contracts[:5])
                ),
                suggestion="Use one-file-per-table contract paths like `contracts/<table>.yml`.",
            )
        )

    dq_paths = re.findall(r"`(dq_rules/[^`]+)`", section_5)
    bad_dq = [p for p in dq_paths if not re.match(r"^dq_rules/[^/]+\.yml$", p)]
    if bad_dq:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="5. Task Implementation Details",
                message=(
                    "DQ rules paths in §5 don't match `dq_rules/*.yml`: " + ", ".join(bad_dq[:5])
                ),
                suggestion="Use `dq_rules/<table>.yml` per Spark-Expectations convention.",
            )
        )
    return results


def check_deployment_infra_paths(sections: dict[str, str]) -> list[ValidationResult]:
    """WARNING: §9 must reference _infra/ci/, _infra/cd/, _infra/docker/, ddl/liquibase/."""
    results: list[ValidationResult] = []
    content = sections.get("9. Deployment", "")
    if not content:
        return results
    required_refs = ["_infra/ci", "_infra/cd", "_infra/docker", "ddl/liquibase"]
    missing = [r for r in required_refs if r not in content]
    if missing:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section="9. Deployment",
                message=("§9 does not reference scaffold infra directories: " + ", ".join(missing)),
                suggestion=(
                    "Structure §9 as 9.1 `_infra/ci/`, 9.2 `_infra/cd/`, "
                    "9.3 `_infra/docker/`, 9.4 `ddl/liquibase/`."
                ),
            )
        )
    return results


# --- Chapter-5 specific checks (added 2026-04-26 after spokane's green Bronze run) ---

VALID_EXECUTOR_MODES = ("in-airflow-local[*]", "sidecar-spark", "external-cluster")
_LOCAL_EXECUTOR_LINE = re.compile(
    r"^\s*local_executor_mode\s*:\s*(\S.*?)\s*$",
    re.MULTILINE,
)
_FENCED_YAML_BLOCK = re.compile(r"```ya?ml\s*\n(.*?)\n```", re.DOTALL)
_BRONZE_RUNNER_HEADING = re.compile(
    r"(ingestion_runner|Bronze\s+(?:Runner|Ingestion))",
    re.IGNORECASE,
)
_PATH_BASED_BRONZE = re.compile(
    r"(warehouse/\{?env\}?/bronze|/tmp/uc-warehouse/.*?/bronze|"
    r"\.format\(\s*[\'\"]delta[\'\"]\s*\)\s*\.save\()",
    re.IGNORECASE,
)
_UC_SAVE_AS_TABLE = re.compile(
    r"(saveAsTable\([^)]*unity\.bronze|UCSingleCatalog|unity\.bronze\.\w+)",
    re.IGNORECASE,
)
_SE_PIN_BELOW_2_10 = re.compile(
    r"spark[-_]expectations\s*==\s*[\"']?2\.[0-9](?!\d)",
    re.IGNORECASE,
)


def check_local_executor_mode(sections: dict[str, str]) -> list[ValidationResult]:
    """CRITICAL: §6 must declare `local_executor_mode` in a fenced YAML block.

    Added after spokane's first green Bronze run revealed that LLDs without
    an explicit `local_executor_mode` produce a runtime stack the bootstrap
    story can't smoke-test (the "DAG runs but spark-submit fails" failure
    mode the chapter-5 sample-stories now warn against).
    """
    results: list[ValidationResult] = []
    section_key = "6. Performance & Optimization"
    content = sections.get(section_key, "")
    if not content:
        return results

    # The declaration must live inside a fenced YAML block so downstream
    # plugins can grep it deterministically. A bare `local_executor_mode: foo`
    # outside a code fence is brittle.
    yaml_blocks = _FENCED_YAML_BLOCK.findall(content)
    declared_value: str | None = None
    for block in yaml_blocks:
        match = _LOCAL_EXECUTOR_LINE.search(block)
        if match:
            declared_value = match.group(1).strip().strip("\"'")
            break

    if declared_value is None:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section=section_key,
                message=(
                    "§6.1 missing `local_executor_mode` declaration in a fenced " "YAML block."
                ),
                suggestion=(
                    "Add a `### 6.1 Compute & Local Executor Mode` subsection with "
                    "a fenced ```yaml block declaring `local_executor_mode: "
                    "<in-airflow-local[*]|sidecar-spark|external-cluster>` plus "
                    "`spark_master_url`, `spark_version`, `provider_pin`. "
                    "Educational default for chapter-5 is `in-airflow-local[*]`."
                ),
            )
        )
        return results

    if declared_value not in VALID_EXECUTOR_MODES:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section=section_key,
                message=(
                    f"`local_executor_mode: {declared_value}` is not one of the "
                    f"three accepted modes: {', '.join(VALID_EXECUTOR_MODES)}."
                ),
                suggestion=(
                    "Pick exactly one mode. `in-airflow-local[*]` bakes Spark into "
                    "the Airflow image (chapter-5 default). `sidecar-spark` uses "
                    "bitnami/spark master+worker services. `external-cluster` "
                    "submits to a remote YARN/k8s cluster."
                ),
            )
        )
    return results


def check_performance_subsections(sections: dict[str, str]) -> list[ValidationResult]:
    """WARNING: §6 should be split into §6.1–§6.5 subsections.

    Subsection numbering is load-bearing — downstream Scrum Master rules
    (`STORIES-BOOTSTRAP-COVERAGE-001` and per-layer `performance-optimization`
    stories) cite §6.1 / §6.2 / §6.3 / §6.4 / §6.5 specifically.
    """
    results: list[ValidationResult] = []
    section_key = "6. Performance & Optimization"
    content = sections.get(section_key, "")
    if not content:
        return results

    expected = {
        "6.1": "Compute & Local Executor Mode",
        "6.2": "Join",
        "6.3": "Shuffle",
        "6.4": "Caching",
        "6.5": "Partition",
    }
    missing = []
    for num, hint in expected.items():
        # Match `### 6.1 ...`, `**§6.1**`, or `§6.1` form. We just need
        # *some* heading-like marker that the LLD splits §6 into pieces.
        pattern = re.compile(
            rf"(?:^\s*###\s*{re.escape(num)}\b|§\s*{re.escape(num)}\b)",
            re.MULTILINE,
        )
        if not pattern.search(content):
            missing.append(f"{num} {hint}")

    if missing:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section=section_key,
                message=(
                    "§6 is missing the load-bearing subsection structure: " + ", ".join(missing)
                ),
                suggestion=(
                    "Split §6 into `### 6.1 Compute & Local Executor Mode`, "
                    "`### 6.2 Join Strategies`, `### 6.3 Shuffle & Parallelism`, "
                    "`### 6.4 Caching`, `### 6.5 Partition Tuning`. Downstream "
                    "rules cite these subsection numbers."
                ),
            )
        )
    return results


def check_bronze_uc_wiring(sections: dict[str, str]) -> list[ValidationResult]:
    """CRITICAL: Bronze runner contract must use UC saveAsTable, not path-based Delta.

    LLD Decision 15 (added 2026-04-26 after spokane's manual `docker cp` +
    REST registration workaround) mandates `UCSingleCatalog` +
    `saveAsTable("unity.bronze.<table>")`. Path-based writes leave UC
    empty until manual external-table registration — and the gap recurs
    every DAG run.
    """
    results: list[ValidationResult] = []

    # Inspect §2 Code Architecture (where §2.3 module contracts live) and
    # §5 Task Implementation Details (where output paths land).
    bronze_runner_sources = [
        ("2. Code Architecture", sections.get("2. Code Architecture", "")),
        ("5. Task Implementation Details", sections.get("5. Task Implementation Details", "")),
    ]
    for section_key, content in bronze_runner_sources:
        if not content:
            continue
        # Only fire when the section actually discusses a Bronze runner / output.
        if not _BRONZE_RUNNER_HEADING.search(content) and "bronze" not in content.lower():
            continue
        path_based = _PATH_BASED_BRONZE.search(content)
        uc_wired = _UC_SAVE_AS_TABLE.search(content)
        if path_based and not uc_wired:
            results.append(
                ValidationResult(
                    level=ValidationLevel.CRITICAL,
                    section=section_key,
                    message=(
                        f"{section_key} describes a Bronze write target as "
                        "path-based Delta (e.g. `warehouse/{env}/bronze/<table>/`) "
                        "without any UCSingleCatalog / saveAsTable wiring. "
                        "Decision 15 forbids path-based Bronze writes."
                    ),
                    suggestion=(
                        "Update the Bronze runner contract to land in "
                        "`unity.bronze.<table>` via `UCSingleCatalog` + "
                        "`saveAsTable(...)`. See `inputs/code/v1/scripts/"
                        "ingestion_runner.py.snippet` for the canonical pattern."
                    ),
                )
            )
    return results


def check_catalog_config(sections: dict[str, str]) -> list[ValidationResult]:
    """WARNING: §7 Configuration Schema should declare the UC catalog block.

    The Bronze runner reads `catalog.uc_uri`, `catalog.bronze_catalog_name`,
    `catalog.bronze_schema` from the per-env config. Missing keys mean the
    generated `_infra/cd/config/<env>.yaml` won't have the values the
    runner expects.
    """
    results: list[ValidationResult] = []
    section_key = "7. Configuration Schema"
    content = sections.get(section_key, "")
    if not content:
        return results

    expected_keys = ("catalog_uc_uri", "catalog_bronze_catalog_name", "catalog_bronze_schema")
    # Also accept the dotted form `catalog.uc_uri` etc.
    missing = []
    for key in expected_keys:
        dotted = key.replace("_", ".", 1)
        if key not in content and dotted not in content:
            missing.append(key)
    if missing:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section=section_key,
                message=(
                    "§7 Configuration Schema is missing UC catalog parameter(s): "
                    + ", ".join(missing)
                ),
                suggestion=(
                    "Add rows for `catalog_uc_uri` (e.g. http://unity-catalog:8080), "
                    "`catalog_bronze_catalog_name` (e.g. `unity`), and "
                    "`catalog_bronze_schema` (e.g. `bronze`). The Bronze runner "
                    "consumes these via the `UC_URI` env var."
                ),
            )
        )
    return results


def check_se_version_floor(content: str) -> list[ValidationResult]:
    """CRITICAL: spark-expectations must not be pinned below 2.10.

    The YAML/JSON rule loader (`spark_expectations.rules.load_rules_from_yaml`)
    was added in v2.10.0 (PR #300). Earlier 2.x releases (e.g. 2.6.0 — what
    spokane shipped pre-fix) raise `ModuleNotFoundError` on every generated
    `se_runner.py` and force a `BRONZE_SKIP_SE=1` bypass that defeats DQ.
    The `library-imports.yaml` overlay enforces this floor; the LLD must
    not contradict it.
    """
    results: list[ValidationResult] = []
    offenders: list[str] = []
    for match in _SE_PIN_BELOW_2_10.finditer(content):
        offenders.append(match.group(0))
    if offenders:
        results.append(
            ValidationResult(
                level=ValidationLevel.CRITICAL,
                section="11. Upstream Artifact References",
                message=(
                    "LLD pins `spark-expectations` below 2.10: "
                    + ", ".join(sorted(set(offenders)))
                    + ". The YAML rule loader the developer-plugin emits "
                    "requires v2.10.0+ (PR #300)."
                ),
                suggestion=(
                    "Reference `spark-expectations >= 2.10.0` in §11 / "
                    "`dq_rules/{table}.yml` notes. The `library-imports.yaml` "
                    "overlay (`min_version: 2.10.0`) is the floor; "
                    "`refresh-libraries` flags any drift below."
                ),
            )
        )
    return results


def check_uc_decision_log(sections: dict[str, str]) -> list[ValidationResult]:
    """INFO: when Bronze is UC-wired, §13 should record Decision 15 (or equivalent).

    Decision 15 = "Bronze writes use UCSingleCatalog + saveAsTable instead of
    path-based Delta." If §2/§5 mention `unity.bronze.` or
    `UCSingleCatalog`, §13 should explain *why* (rationale + trade-off) so
    future maintainers don't drift back to the path-based pattern.
    """
    results: list[ValidationResult] = []
    code_arch = sections.get("2. Code Architecture", "")
    task_impl = sections.get("5. Task Implementation Details", "")
    decisions = sections.get("13. Decision Log", "")
    bronze_uc_referenced = bool(
        _UC_SAVE_AS_TABLE.search(code_arch) or _UC_SAVE_AS_TABLE.search(task_impl)
    )
    if not bronze_uc_referenced:
        return results
    decision_recorded = bool(
        re.search(
            r"(Decision\s*15|UCSingleCatalog|Bronze\s+UC\s+wiring|"
            r"saveAsTable\([^)]*unity\.bronze)",
            decisions,
            re.IGNORECASE,
        )
    )
    if not decision_recorded:
        results.append(
            ValidationResult(
                level=ValidationLevel.INFO,
                section="13. Decision Log",
                message=(
                    "§2 / §5 reference UC-managed Bronze writes but §13 has no "
                    "Decision 15 (or equivalent) explaining the policy choice."
                ),
                suggestion=(
                    'Add a Decision 15 entry: "Bronze writes use UCSingleCatalog '
                    '+ saveAsTable(\\"unity.bronze.<table>\\") instead of '
                    'path-based Delta." Include Options Considered, Rationale '
                    "(spokane invisible-tables gap), and Trade-off (UC catalog "
                    "wiring required at session build time)."
                ),
            )
        )
    return results


def check_scaffold_decision_entry(sections: dict[str, str]) -> list[ValidationResult]:
    """INFO: §13 Decision Log should contain the bootstrap scaffold-adoption entry."""
    results: list[ValidationResult] = []
    content = sections.get("13. Decision Log", "")
    if not content:
        return results
    if not re.search(r"cookiecutter[- ]chapter", content, re.IGNORECASE):
        results.append(
            ValidationResult(
                level=ValidationLevel.INFO,
                section="13. Decision Log",
                message="§13 does not record the scaffold-adoption bootstrap entry.",
                suggestion=(
                    'Add: "Adopted cookiecutter-chapter scaffold at '
                    'inputs/lld/v{N}/templates/cookiecutter-chapter/ as target project layout."'
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
    """Check Error Handling covers the four failure classes.

    Spark Expectations owns row-level DQ rejections via the `<target>_error`
    table, so the LLD must reference that (not invent a custom writer). The
    term "dead letter" is reserved for the ingest DLQ covering pre-validation
    parse/schema/encoding failures that SE never sees.
    """
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
                    "Cover retry policies; SE `_error` table for row_dq; SE stats"
                    " table for agg_dq/query_dq; ingest DLQ for pre-validation"
                    " parse/schema failures; and alerting thresholds."
                ),
            )
        )
        return results

    has_retry = bool(re.search(r"\bretry\b", content, re.IGNORECASE))
    has_se_error = bool(
        re.search(
            r"(_error\s+table|spark[- ]expectations.{0,40}error|se[._ ]error)",
            content,
            re.IGNORECASE,
        )
    )
    has_stats = bool(
        re.search(r"(stats\s+table|se[._ ]stats|agg_dq|query_dq)", content, re.IGNORECASE)
    )
    has_ingest_dlq = bool(
        re.search(
            r"(ingest\s+DLQ|dead.letter|pre.validation|parse|schema\s+fail)", content, re.IGNORECASE
        )
    )
    has_alert = bool(re.search(r"\balert\b", content, re.IGNORECASE))

    missing = []
    if not has_retry:
        missing.append("retry policies")
    if not has_se_error:
        missing.append("SE `_error` table (row_dq)")
    if not has_stats:
        missing.append("SE stats/detailed tables (agg_dq/query_dq)")
    if not has_ingest_dlq:
        missing.append("ingest DLQ (pre-validation)")
    if not has_alert:
        missing.append("alerting")

    if missing:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section=section_key,
                message=f"Error Handling is missing: {', '.join(missing)}.",
                suggestion=(
                    "Structure §8 as: 8.1 Retry, 8.2 SE `_error` table (row_dq),"
                    " 8.3 SE stats/detailed (agg_dq/query_dq), 8.4 Ingest DLQ"
                    " (pre-validation only), 8.5 Alerting."
                ),
            )
        )

    # Anti-pattern: a custom writer for row-level DQ rejections duplicates SE's
    # built-in `_error` table. Flag it so reviewers catch the redundancy.
    custom_row_dq_writer = re.search(
        r"custom.{0,20}(writer|dlq|dead.letter).{0,120}(row_dq|row.level\s+DQ|rejected\s+row)",
        content,
        re.IGNORECASE | re.DOTALL,
    )
    if custom_row_dq_writer:
        results.append(
            ValidationResult(
                level=ValidationLevel.WARNING,
                section=section_key,
                message=("§8 appears to define a custom writer for row-level DQ rejections."),
                suggestion=(
                    "Spark Expectations already writes row_dq drops to `<target>_error`"
                    " automatically (se.enable.error.table=true). Remove the custom"
                    " writer and reference the SE `_error` table instead. Reserve the"
                    " ingest DLQ for pre-validation parse/schema failures only."
                ),
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

    # Resolve scaffold top-level dirs (falls back to default tuple if not found)
    scaffold_root = _find_scaffold_root(file_path)
    scaffold_top_dirs = _load_scaffold_dirs(scaffold_root)

    # CRITICAL checks
    report.results.extend(check_required_sections(sections))
    report.results.extend(check_metadata(content))
    report.results.extend(check_scaffold_metadata(content))
    report.results.extend(check_design_overview(sections))
    report.results.extend(check_dag_specification(sections))
    report.results.extend(check_task_implementation(sections))
    report.results.extend(check_task_table_columns(sections))
    report.results.extend(check_scaffold_layout(sections, scaffold_top_dirs))
    report.results.extend(check_configuration_schema(sections))
    report.results.extend(check_upstream_references(sections))
    # Chapter-5 specific CRITICAL rules
    report.results.extend(check_local_executor_mode(sections))
    report.results.extend(check_bronze_uc_wiring(sections))
    report.results.extend(check_se_version_floor(content))

    # WARNING checks
    report.results.extend(check_upstream_traceability(content))
    report.results.extend(check_error_handling(sections))
    report.results.extend(check_deployment_environments(sections))
    report.results.extend(check_deployment_infra_paths(sections))
    report.results.extend(check_monitoring_metrics(sections))
    report.results.extend(check_mermaid_diagram(content))
    report.results.extend(check_decision_documentation(content))
    report.results.extend(check_performance_numerics(sections))
    report.results.extend(check_scaffold_paths(sections, content))
    # Chapter-5 specific WARNING rules
    report.results.extend(check_performance_subsections(sections))
    report.results.extend(check_catalog_config(sections))

    # INFO checks
    report.results.extend(check_placeholders(content))
    report.results.extend(check_rollback(sections))
    report.results.extend(check_critical_path(sections))
    report.results.extend(check_scaffold_decision_entry(sections))
    report.results.extend(check_uc_decision_log(sections))
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
