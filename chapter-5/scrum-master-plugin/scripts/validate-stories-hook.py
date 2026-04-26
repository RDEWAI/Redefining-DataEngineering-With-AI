#!/usr/bin/env python3
"""PostToolUse hook: auto-validate backlog/story/epic files after Write/Edit."""

import json
import os
import subprocess
import sys


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if "/outputs/stories/" not in file_path or not file_path.endswith(".md"):
        sys.exit(0)

    # Only validate the main BACKLOG file — skip individual epic/story files
    # (they are validated as part of --all directory validation)
    basename = os.path.basename(file_path)
    if not basename.startswith("BACKLOG-"):
        sys.exit(0)

    plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    validator = os.path.join(
        plugin_root, "skills", "validate-stories", "scripts", "validate_stories.py"
    )

    if not os.path.exists(validator):
        sys.exit(0)

    # Validate the entire stories output directory (backlog + epics + stories)
    stories_dir = os.path.dirname(file_path)

    try:
        result = subprocess.run(
            [sys.executable, validator, "--all", stories_dir],
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
        # WARNING issues — non-blocking additional context
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"Backlog validation warnings for {os.path.basename(file_path)}:\n"
                    f"{result.stdout}"
                ),
            }
        }
        print(json.dumps(output))
        sys.exit(0)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
