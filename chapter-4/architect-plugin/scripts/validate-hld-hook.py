#!/usr/bin/env python3
"""PostToolUse hook: auto-validate HLD files after Write/Edit."""

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

    if "/outputs/hld/" not in file_path or not file_path.endswith(".md"):
        sys.exit(0)

    # Skip section fragments — only validate complete top-level HLD files
    if "/outputs/hld/" in file_path and "/sections/" in file_path:
        sys.exit(0)

    plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    validator = os.path.join(plugin_root, "skills", "validate-hld", "scripts", "validate_hld.py")

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
        # WARNING issues — non-blocking additional context
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"HLD validation warnings for {os.path.basename(file_path)}:\n{result.stdout}"
                ),
            }
        }
        print(json.dumps(output))
        sys.exit(0)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
