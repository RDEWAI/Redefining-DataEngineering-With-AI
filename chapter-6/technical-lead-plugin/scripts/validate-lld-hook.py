#!/usr/bin/env python3
"""PostToolUse hook: auto-validate LLD files after Write/Edit.

When validation passes (no CRITICALs), auto-generates:
  - config-template.yaml from LLD Section 7
  - dag-definition.yaml + dag-pipeline.mmd from LLD Section 4
  - impl-sequence.md from LLD Sections 2, 4, 9, 12
"""

import json
import os
import subprocess
import sys


def _generate_config_template(lld_path: str, plugin_root: str) -> str | None:
    """Attempt to generate config-template.yaml from LLD Section 7.

    Returns status message or None if generation was skipped.
    """
    generator = os.path.join(
        plugin_root,
        "skills",
        "generate-config-template",
        "scripts",
        "generate_config_template.py",
    )

    if not os.path.exists(generator):
        return None

    # Determine output directory (same parent as LLD file + /config/)
    lld_dir = os.path.dirname(lld_path)
    config_dir = os.path.join(lld_dir, "config")

    try:
        result = subprocess.run(
            [sys.executable, generator, lld_path, "-o", config_dir],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode == 0:
            return f"Config template generated in {config_dir}/\n{result.stdout}"
        else:
            return f"Config template generation had issues:\n{result.stderr}"
    except (subprocess.TimeoutExpired, OSError) as e:
        return f"Config template generation failed: {e}"


def _generate_dag_definition(lld_path: str, plugin_root: str) -> str | None:
    """Attempt to generate dag-definition.yaml + dag-pipeline.mmd from LLD §4."""
    generator = os.path.join(
        plugin_root,
        "skills",
        "create-lld",
        "scripts",
        "generate_dag_definition.py",
    )
    if not os.path.exists(generator):
        return None

    lld_dir = os.path.dirname(lld_path)
    dag_dir = os.path.join(lld_dir, "dag")

    try:
        result = subprocess.run(
            [sys.executable, generator, lld_path, "-o", dag_dir],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode == 0:
            return f"DAG definition generated in {dag_dir}/\n{result.stdout}"
        else:
            return f"DAG definition generation had issues:\n{result.stderr}"
    except (subprocess.TimeoutExpired, OSError) as e:
        return f"DAG definition generation failed: {e}"


def _generate_impl_sequence(lld_path: str, plugin_root: str) -> str | None:
    """Attempt to generate impl-sequence.md from LLD §2, §4, §9, §12."""
    generator = os.path.join(
        plugin_root,
        "skills",
        "create-lld",
        "scripts",
        "generate_impl_sequence.py",
    )
    if not os.path.exists(generator):
        return None

    lld_dir = os.path.dirname(lld_path)
    output_path = os.path.join(lld_dir, "impl-sequence.md")

    try:
        result = subprocess.run(
            [sys.executable, generator, lld_path, "-o", output_path],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode == 0:
            return f"Implementation sequence generated: {output_path}\n{result.stdout}"
        else:
            return f"Implementation sequence generation had issues:\n{result.stderr}"
    except (subprocess.TimeoutExpired, OSError) as e:
        return f"Implementation sequence generation failed: {e}"


def _run_all_generators(lld_path: str, plugin_root: str) -> str:
    """Run all three generators and collect status messages."""
    parts = []
    config_status = _generate_config_template(lld_path, plugin_root)
    if config_status:
        parts.append(f"Config Template:\n{config_status}")
    dag_status = _generate_dag_definition(lld_path, plugin_root)
    if dag_status:
        parts.append(f"DAG Definition:\n{dag_status}")
    impl_status = _generate_impl_sequence(lld_path, plugin_root)
    if impl_status:
        parts.append(f"Implementation Sequence:\n{impl_status}")
    return "\n\n".join(parts)


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if "/outputs/lld/" not in file_path or not file_path.endswith(".md"):
        sys.exit(0)

    # Skip config, dag directory files and impl-sequence
    if "/config/" in file_path or "/dag/" in file_path:
        sys.exit(0)
    if file_path.endswith("impl-sequence.md"):
        sys.exit(0)

    plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    validator = os.path.join(plugin_root, "skills", "validate-lld", "scripts", "validate_lld.py")

    if not os.path.exists(validator):
        sys.exit(0)

    try:
        result = subprocess.run(
            [sys.executable, validator, file_path],
            capture_output=True,
            text=True,
            timeout=25,
        )
    except (subprocess.TimeoutExpired, OSError):
        sys.exit(0)

    if result.returncode == 1:
        # CRITICAL issues — exit 2 blocks and feeds stderr back to Claude
        print(result.stdout, file=sys.stderr)
        sys.exit(2)
    elif result.returncode == 2:
        # WARNING issues — non-blocking, try generation anyway
        gen_status = _run_all_generators(file_path, plugin_root)
        context = f"LLD validation warnings for {os.path.basename(file_path)}:\n" f"{result.stdout}"
        if gen_status:
            context += f"\n\n{gen_status}"
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": context,
            }
        }
        print(json.dumps(output))
        sys.exit(0)
    elif result.returncode == 0:
        # All passed — generate all derived artifacts
        gen_status = _run_all_generators(file_path, plugin_root)
        if gen_status:
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": (
                        f"LLD validation passed for {os.path.basename(file_path)}.\n\n"
                        f"{gen_status}"
                    ),
                }
            }
            print(json.dumps(output))
        sys.exit(0)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
