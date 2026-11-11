#!/usr/bin/env python3
"""PreToolUse hook: keep the SRE (RCA) agent strictly read-only.

The RCA agent investigates a running data-pipeline stack. It may read logs,
query tables, and call GET endpoints, but it must never change the state it
is investigating: no container restarts, no Airflow task clears or re-runs,
no data mutation, no destructive git or filesystem operations.

Any Bash command matching a pattern below is denied with a message that tells
the agent to put the action in the RCA report's Remediation section instead.

Prose vs. commands
------------------
An RCA report legitimately *quotes* recovery commands ("run `airflow dags
trigger ...` after the fix"). Those quotes travel through Bash when the agent
writes the report via a heredoc or a `python3 -c` payload. To avoid blocking
the report itself, heredoc bodies and quoted string literals are removed
before matching — EXCEPT when the quoted text is itself the executable
payload: SQL handed to `beeline`/`spark-sql`/`duckdb`/`psql` (`-e "..."`,
`-f`, heredoc input) and request bodies/methods handed to `curl`/`http`.
"""

import json
import re
import sys

# Lifecycle / state / filesystem patterns: evaluated on the command with
# heredoc bodies and quoted literals stripped.
COMMAND_PATTERNS = [
    # --- filesystem / git (inherited from the developer plugin) ---
    (r"\brm\s+-[rf]+\b", "rm -rf"),
    (r"\bsudo\s+rm\b", "sudo rm"),
    (r"\bgit\s+push\s+.*(--force|-f)\b", "git push --force"),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard"),
    (r"\bgit\s+clean\s+-[fdx]+\b", "git clean -f"),
    (r"\bchmod\s+777\b", "chmod 777"),
    # --- container / stack lifecycle ---
    (
        r"\bdocker(\s+compose)?\s+(-f\s+\S+\s+)?(restart|down|up|rm|kill|pause|unpause|stop|start)\b",
        "docker lifecycle command",
    ),
    (r"\bdocker(\s+compose)?\s+(-f\s+\S+\s+)?exec\b.*\b(rm|kill|pkill)\b", "docker exec rm/kill"),
    (r"\bdocker\s+(system|volume|image|container)\s+(prune|rm)\b", "docker prune/rm"),
    # --- Airflow state mutation (CLI and REST) ---
    (
        r"\bairflow\s+(tasks|dags)\s+(clear|run|trigger|backfill|delete|pause|unpause)\b",
        "airflow state mutation",
    ),
    (r"\bairflow\s+db\s+(reset|clean|downgrade)\b", "airflow db mutation"),
    (r"-X\s*(POST|PATCH|PUT|DELETE)\b(?![^|;&]*auth/token)", "non-GET HTTP method"),
    (r"--request\s*(POST|PATCH|PUT|DELETE)\b(?![^|;&]*auth/token)", "non-GET HTTP method"),
    (r"\b(dagRuns|taskInstances)\b[^|;&]*\b(clear|dry_run)\b", "airflow REST clear"),
    # --- warehouse files ---
    (r"\bmv\b.*uc-warehouse|\bcp\b.*\buc-warehouse/", "warehouse file mutation"),
]

# SQL patterns: evaluated on the full command (quotes included) whenever a
# SQL client is invoked, because the SQL *is* the quoted payload.
SQL_PATTERNS = [
    (
        r"\binsert\s+(into|overwrite)\b|\bupdate\s+[\w.`]+\s+set\b|\bdelete\s+from\b|\bmerge\s+into\b",
        "SQL data mutation",
    ),
    (
        r"\b(drop|truncate|restore|alter)\s+(table|schema|database|catalog)\b|\b(vacuum|optimize)\s+[\w.`]+",
        "SQL DDL/maintenance",
    ),
    (r"\bcreate\s+(or\s+replace\s+)?(table|schema|database|catalog|view)\b", "SQL create"),
    (r"\b(msck|refresh)\s+table\b", "metastore mutation"),
]
SQL_CLIENT = re.compile(r"\b(beeline|spark-sql|duckdb|psql|sqlite3|mysql|hive)\b", re.IGNORECASE)
HTTP_CLIENT = re.compile(r"\b(curl|wget|http|httpie|xh)\b", re.IGNORECASE)

_HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n(.*?)\n\s*\1\b", re.DOTALL)
_DQUOTE = re.compile(r'"(?:\\.|[^"\\])*"', re.DOTALL)
_SQUOTE = re.compile(r"'(?:[^'])*'", re.DOTALL)


def strip_prose(command: str) -> str:
    """Remove heredoc bodies and quoted literals so quoted prose cannot match."""
    stripped = _HEREDOC.sub(lambda m: f"<<{m.group(1)} [heredoc]\n{m.group(1)}", command)
    stripped = _DQUOTE.sub('""', stripped)
    stripped = _SQUOTE.sub("''", stripped)
    return stripped


def find_violation(command: str) -> str | None:
    if not command:
        return None
    bare = strip_prose(command)
    for pattern, label in COMMAND_PATTERNS:
        if re.search(pattern, bare, re.IGNORECASE):
            return label
    # Quoted HTTP methods/bodies are the request itself when an HTTP client runs.
    if HTTP_CLIENT.search(bare):
        for pattern, label in COMMAND_PATTERNS:
            if "HTTP" in label and re.search(pattern, command, re.IGNORECASE):
                return label
    # Quoted SQL is the statement itself when a SQL client runs.
    if SQL_CLIENT.search(bare):
        for pattern, label in SQL_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return label
    return None


def _deny(message: str) -> None:
    # Claude Code only honours the decision when hookEventName is present;
    # permissionDecisionReason is what the agent sees, systemMessage the user.
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": message,
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
    label = find_violation(command)
    if label:
        _deny(
            f"BLOCKED: {label}. The SRE agent is read-only — it must not "
            f"change the stack, Airflow state, or data it is investigating. "
            f"Describe this action under 'Immediate recovery' in the RCA "
            f"report's Remediation section for an operator to run."
        )
    sys.exit(0)


if __name__ == "__main__":
    main()
