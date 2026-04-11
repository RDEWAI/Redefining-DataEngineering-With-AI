#!/usr/bin/env python3
"""Generate DAG definition YAML and Mermaid export from LLD Section 4.

Reads an LLD markdown file, extracts the DAG Specification section (§4),
parses DAG metadata and task inventory tables, and generates:
  1. dag-definition.yaml — structured DAG config with tasks and dependencies
  2. dag-pipeline.mmd — standalone Mermaid diagram extracted from §4.3

Usage:
    python generate_dag_definition.py <path-to-lld.md> -o <output-dir>

Exit Codes:
    0: Files generated successfully
    1: Section 4 not found or no tasks extracted
    2: File not found or parse error
"""

from __future__ import annotations

import argparse
import os
import re
import sys
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


def parse_metadata_table(section_content: str) -> dict[str, str]:
    """Parse a 2-column key-value metadata table from section content.

    Looks for the first table with exactly 2 columns (Property | Value).
    """
    metadata: dict[str, str] = {}
    lines = section_content.strip().split("\n")

    in_table = False
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            if in_table:
                break  # end of table
            continue

        if all(c in "|- " for c in stripped):
            in_table = True
            continue

        cells = [c.strip() for c in stripped.split("|")[1:-1]]
        if not in_table:
            continue  # skip header row

        if len(cells) >= 2:
            key = cells[0].strip("* `")
            value = cells[1].strip("` ")
            metadata[key] = value

    return metadata


def parse_task_table(section_content: str) -> list[dict[str, str]]:
    """Parse the task inventory table from section content.

    Returns a list of dicts with keys matching table headers.
    """
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
    """Extract content of a subsection (e.g., '4.1') from section text."""
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


def extract_mermaid(section_content: str) -> str | None:
    """Extract the first Mermaid diagram from a section."""
    match = re.search(r"```mermaid\n(.*?)```", section_content, re.DOTALL)
    return match.group(1).strip() if match else None


def parse_critical_path(section_content: str) -> list[str]:
    """Extract critical path steps from §4.4 content."""
    subsection = extract_subsection(section_content, "4.4")
    if not subsection:
        return []

    steps: list[str] = []
    # Look for indented lines with --> arrows or task-like names
    for line in subsection.split("\n"):
        stripped = line.strip()
        if stripped.startswith("-->"):
            task = stripped.lstrip("--> ").split("(")[0].strip()
            if task:
                steps.append(task)
        elif re.match(r"^[a-z_]+_(?:bronze|silver|gold|check)", stripped.split("(")[0].strip()):
            steps.append(stripped.split("(")[0].strip())

    return steps


def parse_dependencies(dep_string: str) -> list[str]:
    """Parse a dependency cell value into a list of task IDs."""
    dep_string = dep_string.strip("`")
    if not dep_string or dep_string.lower() in ("none", "-", ""):
        return []
    # Split on comma, strip backticks and whitespace
    return [d.strip().strip("`") for d in dep_string.split(",") if d.strip()]


def generate_dag_yaml(
    metadata: dict[str, str],
    tasks: list[dict[str, str]],
    critical_path: list[str],
    lld_filename: str,
) -> str:
    """Generate DAG definition YAML from parsed data."""
    dag_id = metadata.get("DAG ID", "unknown").strip("`")
    schedule = metadata.get("Schedule", "").split("(")[0].strip().strip("`")

    lines = [
        f"# DAG Definition: {dag_id}",
        f"# Derived from: {lld_filename}, Section 4",
        "# Generated by: generate_dag_definition.py",
        "",
        "dag:",
        f"  dag_id: {dag_id}",
        f'  schedule: "{schedule}"',
        f"  timezone: {metadata.get('Timezone', 'UTC')}",
        f"  catchup: {metadata.get('Catchup', 'false').lower().startswith('yes')}",
        f"  max_active_runs: {metadata.get('Max active runs', '1')}",
        f"  concurrency: {metadata.get('Concurrency', '1').split('(')[0].strip()}",
        f"  default_timeout_minutes: {metadata.get('Default timeout', '120').split()[0]}",
        "",
        "default_args:",
    ]

    # Extract most common retry value
    retry_vals = [t.get("retries", "1") for t in tasks if t.get("retries")]
    most_common_retry = max(set(retry_vals), key=retry_vals.count) if retry_vals else "1"
    lines.append(f"  retries: {most_common_retry}")

    delay_vals = [
        t.get("retry delay", "60s").split()[0].rstrip("s") for t in tasks if t.get("retry delay")
    ]
    most_common_delay = max(set(delay_vals), key=delay_vals.count) if delay_vals else "60"
    lines.append(f"  retry_delay_seconds: {most_common_delay}")
    lines.append("")

    lines.append("tasks:")
    for task in tasks:
        task_id = task.get("task id", "unknown").strip("`")
        deps = parse_dependencies(task.get("dependencies", ""))
        timeout_raw = task.get("timeout", "30 min")
        timeout = timeout_raw.split()[0] if timeout_raw else "30"
        retries = task.get("retries", most_common_retry)
        retry_delay = task.get("retry delay", f"{most_common_delay}s")

        lines.append(f"  - task_id: {task_id}")
        lines.append(f"    type: {task.get('type', 'PySpark')}")
        lines.append(f"    layer: {task.get('layer', 'unknown').lower()}")

        if deps:
            dep_str = ", ".join(deps)
            lines.append(f"    dependencies: [{dep_str}]")
        else:
            lines.append("    dependencies: []")

        lines.append(f"    timeout_minutes: {timeout}")
        lines.append(f"    retries: {retries}")
        lines.append(f'    retry_delay: "{retry_delay}"')
        lines.append("")

    if critical_path:
        lines.append("critical_path:")
        lines.append("  steps:")
        for step in critical_path:
            lines.append(f"    - {step}")

    return "\n".join(lines) + "\n"


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate DAG definition YAML and Mermaid export from LLD Section 4",
    )
    parser.add_argument("path", type=Path, help="Path to LLD markdown file")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: same dir as LLD + /dag/)",
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
    section_4 = sections.get("4. DAG Specification")
    if not section_4:
        print("Error: Section '4. DAG Specification' not found in LLD.", file=sys.stderr)
        return 1

    # Parse metadata from §4.1
    metadata_content = extract_subsection(section_4, "4.1")
    metadata = parse_metadata_table(metadata_content) if metadata_content else {}

    # Parse task inventory from §4.2
    task_content = extract_subsection(section_4, "4.2")
    tasks = parse_task_table(task_content) if task_content else []

    if not tasks:
        # Try parsing tables from the full section as fallback
        tasks = parse_task_table(section_4)

    if not tasks:
        print("Error: No tasks found in Section 4 task inventory.", file=sys.stderr)
        return 1

    # Parse critical path from §4.4
    critical_path = parse_critical_path(section_4)

    # Extract Mermaid diagram
    mermaid = extract_mermaid(section_4)

    output_dir = args.output_dir or (args.path.parent / "dag")
    os.makedirs(output_dir, exist_ok=True)

    # Generate DAG definition YAML
    yaml_content = generate_dag_yaml(metadata, tasks, critical_path, args.path.name)
    yaml_path = output_dir / "dag-definition.yaml"
    yaml_path.write_text(yaml_content, encoding="utf-8")
    print(f"DAG definition written to: {yaml_path}")

    # Write Mermaid export
    if mermaid:
        mmd_path = output_dir / "dag-pipeline.mmd"
        mmd_path.write_text(mermaid + "\n", encoding="utf-8")
        print(f"Mermaid diagram written to: {mmd_path}")
    else:
        print("Warning: No Mermaid diagram found in Section 4.3.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
