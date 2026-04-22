#!/usr/bin/env python3
"""PostToolUse hook: auto-validate developer outputs after Write/Edit.

Detects which artifact type was written and invokes the appropriate
validate-* skill script. Validation errors at CRITICAL level block
the tool response (exit 2); warnings are surfaced as additional context.
"""

import json
import os
import subprocess
import sys


def _skill_validate(validator_path: str, args: list[str]) -> None:
    if not os.path.exists(validator_path):
        sys.exit(0)

    try:
        result = subprocess.run(
            [sys.executable, validator_path] + args,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        sys.exit(0)

    if result.returncode == 1:
        print(result.stdout, file=sys.stderr)
        sys.exit(2)
    elif result.returncode == 2:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": result.stdout,
            }
        }
        print(json.dumps(output))
    sys.exit(0)


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        sys.exit(0)

    plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Ingestion framework: runner/factory/wrapper modules or per-table configs
    if (
        "/patient_360/src/patient_360/bronze/" in file_path
        or "/patient_360/airflow/configs/" in file_path
    ) and (file_path.endswith(".py") or file_path.endswith(".yml")):
        validator = os.path.join(
            plugin_root,
            "skills", "ingestion", "validate-ingestion", "scripts", "validate_ingestion.py",
        )
        # Derive project-root and LLD from the file path
        chapter5_root = _find_chapter5_root(file_path)
        if chapter5_root is None:
            sys.exit(0)
        project_root = os.path.join(chapter5_root, "patient_360")
        # Locate the latest LLD
        import glob
        lld_files = sorted(
            glob.glob(os.path.join(chapter5_root, "inputs", "lld", "v*", "LLD-*.md"))
        )
        lld_files = [f for f in lld_files if not f.endswith(".bak")]
        if not lld_files:
            sys.exit(0)
        lld_path = lld_files[-1]
        _skill_validate(validator, ["--project-root", project_root, "--lld", lld_path])

    sys.exit(0)


def _find_chapter5_root(file_path: str) -> str | None:
    """Walk up from file_path to find the chapter-5 directory."""
    parts = file_path.split(os.sep)
    for i, part in enumerate(parts):
        if part == "chapter-5":
            return os.sep.join(parts[: i + 1])
    return None


if __name__ == "__main__":
    main()
