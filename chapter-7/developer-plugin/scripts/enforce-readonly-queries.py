#!/usr/bin/env python3
"""PreToolUse hook: guard against destructive shell operations in the Developer agent.

Blocks Bash commands that could irreversibly destroy files, force-push to remote,
or drop database state outside the sanctioned workflow.
"""

import json
import re
import sys

# Patterns that indicate destructive / dangerous operations
DESTRUCTIVE_PATTERNS = [
    (r"\brm\s+-[rf]+\b", "rm -rf"),
    (r"\bgit\s+push\s+.*--force\b", "git push --force"),
    (r"\bgit\s+push\s+.*-f\b", "git push -f"),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard"),
    (r"\bgit\s+clean\s+-[fdx]+\b", "git clean -f"),
    (r"\bchmod\s+777\b", "chmod 777"),
    (r"\btruncate\b.*\btable\b", "TRUNCATE TABLE"),
    (r"\bdrop\s+table\b", "DROP TABLE"),
    (r"\bdrop\s+schema\b", "DROP SCHEMA"),
    (r"\bdrop\s+database\b", "DROP DATABASE"),
    (r"\bsudo\s+rm\b", "sudo rm"),
]


def _deny(message: str) -> None:
    output = {
        "hookSpecificOutput": {
            "permissionDecision": "deny",
        },
        "systemMessage": message,
    }
    print(json.dumps(output))
    sys.exit(0)


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    if not command:
        sys.exit(0)

    for pattern, label in DESTRUCTIVE_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            _deny(
                f"BLOCKED: Destructive operation detected ({label}). "
                f"The Developer agent must not run commands that irreversibly "
                f"destroy files or repository history. Run this command manually "
                f"if it is intentional."
            )

    sys.exit(0)


if __name__ == "__main__":
    main()
