#!/usr/bin/env python3
"""Generate Implementation Sequence document from LLD Sections 2, 4, 9, 12.

Reads an LLD markdown file and produces impl-sequence.md with:
  - Build phases with prerequisites and milestones
  - Module build order table
  - Critical path mapped to build phases
  - Traceability cross-reference

Usage:
    python generate_impl_sequence.py <path-to-lld.md> -o <output-path>

Exit Codes:
    0: Document generated successfully
    1: Required sections not found
    2: File not found or parse error
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path


def parse_sections(content: str) -> dict[str, str]:
    """Parse markdown H2 sections into a dict keyed by heading text."""
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


def extract_title(content: str) -> str:
    """Extract the LLD title from the first H1 heading."""
    match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
    return match.group(1).strip() if match else "Pipeline"


def extract_lld_filename(content: str) -> str:
    """Try to derive the LLD filename from metadata or return generic."""
    return "LLD"


def parse_lld_header(content: str) -> dict[str, str]:
    """Parse the LLD header metadata table (Field | Value) at the top of the doc."""
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


def parse_code_tree(section_content: str) -> list[dict[str, str]]:
    """Parse a project structure code block into module entries.

    Handles tree-drawing format like:
        +-- src/
        |   +-- pipelines/
        |   |   +-- bronze/
        |   |   |   +-- ingest_patients.py

    Nesting depth is determined by counting '|' and '+' markers.
    Returns list of dicts with 'path' and 'comment' keys.
    """
    modules: list[dict[str, str]] = []
    match = re.search(r"```\n(.*?)```", section_content, re.DOTALL)
    if not match:
        return modules

    tree_text = match.group(1)
    dir_stack: list[tuple[int, str]] = []  # (depth, dir_name)

    for line in tree_text.split("\n"):
        if not line.strip():
            continue

        # Calculate depth by counting nesting markers (| or +)
        depth = 0
        for ch in line:
            if ch in ("|", "+"):
                depth += 1
            elif ch == "-":
                continue
            elif ch == " ":
                continue
            else:
                break

        # A root-level entry (e.g., "patient-360-pipeline/") has depth 0
        # "+-- src/" has depth 1 (one + marker)
        # "|   +-- pipelines/" has depth 2 (one | and one +)

        # Strip tree drawing chars to get name
        name_part = re.sub(r"^[+|`\- ]+", "", line).strip()
        if not name_part:
            continue

        # Extract comment
        parts = name_part.split("#", 1)
        name = parts[0].strip().rstrip("/")
        comment = parts[1].strip() if len(parts) > 1 else ""

        if not name:
            continue

        # Pop dirs at same or deeper depth
        while dir_stack and dir_stack[-1][0] >= depth:
            dir_stack.pop()

        if name.endswith(".py") and not name.startswith("__init__"):
            path_parts = [d[1] for d in dir_stack] + [name]
            full_path = "/".join(path_parts)
            modules.append({"path": full_path, "comment": comment})
        elif "." not in name:
            dir_stack.append((depth, name))

    return modules


def classify_module_layer(path: str) -> str:
    """Classify a module into a build layer based on its path."""
    if "config/" in path or "utils/" in path:
        return "foundation"
    if "transforms/" in path or "quality/" in path:
        return "shared"
    if "bronze/" in path:
        return "bronze"
    if "silver/" in path:
        return "silver"
    if "gold/" in path:
        return "gold"
    if "dags/" in path or "docker/" in path:
        return "orchestration"
    return "other"


def parse_task_table(section_content: str) -> list[dict[str, str]]:
    """Parse task inventory table from section 4."""
    tasks: list[dict[str, str]] = []
    lines = section_content.strip().split("\n")

    in_table = False
    headers: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            in_table = False
            headers = []
            continue

        if all(c in "|- " for c in stripped):
            in_table = True
            continue

        cells = [c.strip() for c in stripped.split("|")[1:-1]]

        if not in_table:
            headers = [h.lower().strip("* ") for h in cells]
            continue

        if headers and len(cells) >= len(headers):
            row = dict(zip(headers, cells))
            if any(v for v in row.values()):
                tasks.append(row)

    return tasks


def extract_subsection(section_content: str, subsection_prefix: str) -> str:
    """Extract content of a subsection (e.g., '4.2') from section text."""
    lines = section_content.split("\n")
    result_lines: list[str] = []
    capturing = False

    for line in lines:
        if line.startswith("### ") and subsection_prefix in line:
            capturing = True
            continue
        elif line.startswith("### ") and capturing:
            break
        elif capturing:
            result_lines.append(line)

    return "\n".join(result_lines).strip()


def parse_traceability_table(section_content: str) -> list[dict[str, str]]:
    """Parse traceability matrix tables from section 12."""
    return parse_task_table(section_content)


def build_phases(
    modules: list[dict[str, str]],
) -> list[dict[str, object]]:
    """Group modules into ordered build phases."""
    layer_order = ["foundation", "shared", "bronze", "silver", "gold", "orchestration"]
    layer_names = {
        "foundation": "Foundation",
        "shared": "Shared Transforms & Quality",
        "bronze": "Bronze Layer",
        "silver": "Silver Layer",
        "gold": "Gold Layer",
        "orchestration": "Orchestration & Deployment",
    }
    layer_prereqs = {
        "foundation": "Development environment setup",
        "shared": "Phase 1 (Foundation) complete",
        "bronze": "Phase 2 (Shared Transforms) complete",
        "silver": "Phase 3 (Bronze Layer) complete, DQ gate passing",
        "gold": "Phase 4 (Silver Layer) complete, DQ gate passing",
        "orchestration": "Phase 5 (Gold Layer) complete",
    }
    layer_milestones = {
        "foundation": "Config loads successfully, SparkSession creates in DEV",
        "shared": "Unit tests pass for all transform and quality functions",
        "bronze": "All source tables land in Bronze Delta, SE DQ checks pass",
        "silver": "All Silver tables populated, SCD2 applied, referential integrity verified",
        "gold": "Gold tables queryable, SLA targets met",
        "orchestration": "DAG runs end-to-end in DEV, CI/CD pipeline functional",
    }

    grouped: dict[str, list[dict[str, str]]] = {}
    for mod in modules:
        layer = classify_module_layer(mod["path"])
        grouped.setdefault(layer, []).append(mod)

    phases: list[dict[str, object]] = []
    for i, layer in enumerate(layer_order, 1):
        if layer in grouped:
            phases.append(
                {
                    "number": i,
                    "name": layer_names.get(layer, layer.title()),
                    "prerequisites": layer_prereqs.get(layer, "Previous phase complete"),
                    "modules": grouped[layer],
                    "milestone": layer_milestones.get(layer, "Phase complete"),
                }
            )

    return phases


def generate_impl_sequence(
    title: str,
    lld_filename: str,
    phases: list[dict[str, object]],
    modules: list[dict[str, str]],
    traceability: list[dict[str, str]],
) -> str:
    """Generate the implementation sequence markdown document."""
    today = date.today().isoformat()

    lines = [
        f"# Implementation Sequence: {title}",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| **Derived From** | {lld_filename} |",
        f"| **Generated** | {today} |",
        "| **Generator** | generate_impl_sequence.py |",
        "",
        "---",
        "",
        "## 1. Build Phases",
        "",
    ]

    for phase in phases:
        lines.append(f"### Phase {phase['number']}: {phase['name']}")
        lines.append(f"**Prerequisites**: {phase['prerequisites']}")
        lines.append("**Modules**:")
        for mod in phase["modules"]:  # type: ignore[union-attr]
            comment = f" — {mod['comment']}" if mod.get("comment") else ""
            lines.append(f"- `{mod['path']}`{comment}")
        lines.append(f"**Milestone**: {phase['milestone']}")
        lines.append("")

    # Module build order table
    lines.extend(
        [
            "---",
            "",
            "## 2. Module Build Order",
            "",
            "| # | Module | Layer | Description | LLD Section |",
            "|---|--------|-------|-------------|-------------|",
        ]
    )

    for i, mod in enumerate(modules, 1):
        layer = classify_module_layer(mod["path"])
        desc = mod.get("comment", "")
        lld_section = "§2.1"
        lines.append(f"| {i} | `{mod['path']}` | {layer.title()} | {desc} | {lld_section} |")

    # Milestones summary
    lines.extend(
        [
            "",
            "---",
            "",
            "## 3. Milestones & Checkpoints",
            "",
            "| Milestone | Phase | Acceptance Criteria |",
            "|-----------|-------|---------------------|",
        ]
    )

    for phase in phases:
        lines.append(
            f"| {phase['name']} complete | Phase {phase['number']} | {phase['milestone']} |"
        )

    # Traceability cross-reference
    if traceability:
        lines.extend(
            [
                "",
                "---",
                "",
                "## 4. Traceability",
                "",
                "Requirements mapped to build phases (from LLD §12):",
                "",
                "| Requirement | Source | Implementation | LLD Section |",
                "|-------------|--------|----------------|-------------|",
            ]
        )

        for row in traceability[:20]:  # Cap at 20 rows for readability
            req = row.get("requirement", "")
            ref = row.get("drd ref", row.get("hld ref", ""))
            impl = row.get("implementation component", row.get("lld implementation", ""))
            section = row.get("lld section", "")
            lines.append(f"| {req} | {ref} | {impl} | {section} |")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate Implementation Sequence from LLD Sections 2, 4, 9, 12",
    )
    parser.add_argument("path", type=Path, help="Path to LLD markdown file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output path (default: same dir as LLD / impl-sequence.md)",
    )
    args = parser.parse_args()

    if not args.path.is_file():
        print(f"Error: {args.path} is not a file.", file=sys.stderr)
        return 2

    try:
        content = args.path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return 2

    sections = parse_sections(content)

    # Require at least section 2 and section 4
    section_2 = sections.get("2. Code Architecture")
    section_4 = sections.get("4. DAG Specification")

    if not section_2 and not section_4:
        print(
            "Error: Neither Section 2 (Code Architecture) nor Section 4 "
            "(DAG Specification) found in LLD.",
            file=sys.stderr,
        )
        return 1

    title = extract_title(content)

    # Read project_name / chapter from LLD header for scaffold-aligned paths
    header = parse_lld_header(content)
    project_name = header.get("Project Name", "project")

    # Parse modules from §2 code tree
    modules = parse_code_tree(section_2) if section_2 else []

    # Parse traceability from §12
    section_12 = sections.get("12. Traceability Matrix", "")
    traceability = parse_traceability_table(section_12) if section_12 else []

    # Build phases
    phases = build_phases(modules)

    # If no modules parsed from code tree, derive scaffold paths from §5 task table
    if not modules:
        section_5 = sections.get("5. Task Implementation Details", "")
        s5_tasks = parse_task_table(section_5) if section_5 else []
        for task in s5_tasks:
            module_path = task.get("module path", "").strip("` ")
            if not module_path:
                layer = task.get("layer", "").strip().lower() or "utils"
                tid = task.get("task id", "unknown").strip("`").lower()
                module_path = f"src/{project_name}/{layer}/{tid}.py"
            modules.append({"path": module_path, "comment": task.get("layer", "")})

        # Last-resort fallback: §4 task inventory
        if not modules and section_4:
            task_content = extract_subsection(section_4, "4.2")
            tasks = parse_task_table(task_content) if task_content else parse_task_table(section_4)
            for task in tasks:
                layer = task.get("layer", "").strip().lower() or "utils"
                tid = task.get("task id", "unknown").strip("`").lower()
                modules.append(
                    {
                        "path": f"src/{project_name}/{layer}/{tid}.py",
                        "comment": f"{task.get('type', '')} task",
                    }
                )
        phases = build_phases(modules)

    output_path = args.output or (args.path.parent / "impl-sequence.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = generate_impl_sequence(title, args.path.name, phases, modules, traceability)
    output_path.write_text(doc, encoding="utf-8")
    print(f"Implementation sequence written to: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
