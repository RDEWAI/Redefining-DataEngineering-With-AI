#!/usr/bin/env python3
"""PreToolUse hook: enforce read-only and inventory-only access for the Patron Plugin.

Inspects Bash commands before execution and blocks:
1. Any database write operations (INSERT, UPDATE, DELETE, DROP, etc.)
2. Any DuckDB invocation without the -readonly flag
3. Any access to library.lending or library.replenish tables
   (those tables are restricted to the Coordinator Plugin)
"""

import json
import re
import sys

# Patterns that indicate write operations (case-insensitive)
WRITE_PATTERNS = [
    r"\b(INSERT)\b",
    r"\b(UPDATE)\b",
    r"\b(DELETE)\b",
    r"\b(DROP)\b",
    r"\b(ALTER)\b",
    r"\b(CREATE)\b",
    r"\b(TRUNCATE)\b",
    r"\b(REPLACE)\b",
    r"\b(MERGE)\b",
    r"\b(GRANT)\b",
    r"\b(REVOKE)\b",
]

# Indicators that a command involves database operations
DB_INDICATORS = [
    r"\bduckdb\b",
    r"\.db\b",
]

# Tables restricted from the patron plugin (coordinator only)
RESTRICTED_TABLES = [
    r"\blibrary\.lending\b",
    r"\blibrary\.replenish\b",
]


def _deny(message: str) -> None:
    """Print a deny decision and exit."""
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

    # Only inspect commands that look like database operations
    is_db_command = any(
        re.search(pattern, command, re.IGNORECASE) for pattern in DB_INDICATORS
    )

    if not is_db_command:
        sys.exit(0)

    # Check for restricted table access (lending / replenishment)
    for pattern in RESTRICTED_TABLES:
        match = re.search(pattern, command, re.IGNORECASE)
        if match:
            _deny(
                f"BLOCKED: Access to '{match.group(0)}' is not permitted in the Patron Plugin. "
                f"Lending and replenishment data is restricted to the Coordinator Plugin. "
                f"The Patron Plugin can only query library.books."
            )

    # Check for write operations
    for pattern in WRITE_PATTERNS:
        match = re.search(pattern, command, re.IGNORECASE)
        if match:
            _deny(
                f"BLOCKED: Database write operation detected ({match.group(0)}). "
                f"The Patron Plugin must only run read-only SELECT queries against library.books. "
                f"Use 'duckdb <path> -readonly' for all database access."
            )

    # Check that duckdb commands use -readonly flag
    if re.search(r"\bduckdb\b", command, re.IGNORECASE):
        if "-readonly" not in command and "-read_only" not in command:
            _deny(
                "BLOCKED: DuckDB must be invoked with the -readonly flag. "
                'Use: duckdb <path> -readonly -c "<query>"'
            )

    sys.exit(0)


if __name__ == "__main__":
    main()
