"""Make LLM-generated SQL safe to run against the Gold tables.

The agent executes model-written SQL, so this module is the safety boundary: it extracts
the SQL from the model's reply, enforces a single **read-only** SELECT/WITH statement,
rejects any table that is not a declared Gold table (qualified names only — bare names are
treated as CTE aliases), and caps the result size with a LIMIT.

This is a defensive guard, not a full SQL parser; combined with a read-only execution path
it keeps a wrong or adversarial generation from mutating anything.
"""

from __future__ import annotations

import re

# Statement keywords that must never appear in a read-only query. All are true keywords
# (not SQL functions), so a whole-word match will not fire on legitimate SELECT expressions.
_FORBIDDEN = (
    "insert", "update", "delete", "merge", "drop", "alter", "truncate",
    "create", "grant", "revoke", "attach", "vacuum",
)
_FENCE_RE = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_FROM_JOIN_RE = re.compile(r"\b(?:from|join)\s+([A-Za-z0-9_.`\"]+)", re.IGNORECASE)
_LIMIT_RE = re.compile(r"\blimit\s+\d+", re.IGNORECASE)
_LEADING_WORD_RE = re.compile(r"\s*(\w+)")


class GuardError(ValueError):
    """Raised when generated SQL fails a safety check."""


def extract_sql(text: str) -> str:
    """Pull a single SQL statement out of an LLM reply (handles ```sql fences)."""
    match = _FENCE_RE.search(text)
    sql = match.group(1) if match else text
    return sql.strip().rstrip(";").strip()


def _referenced_tables(sql: str) -> list[str]:
    return [t.strip('`"').lower() for t in _FROM_JOIN_RE.findall(sql)]


def guard_sql(sql: str, *, allowed_tables: set[str], max_limit: int = 1000) -> str:
    """Return a safe, single read-only statement or raise :class:`GuardError`.

    - exactly one statement (no embedded ``;``)
    - starts with SELECT or WITH
    - contains no data-defining/modifying keywords
    - every *qualified* table reference is in ``allowed_tables``
    - a ``LIMIT`` is appended when the query has none
    """
    sql = sql.strip().rstrip(";").strip()
    if not sql:
        raise GuardError("empty SQL")
    if ";" in sql:
        raise GuardError("only a single statement is allowed")

    leading = _LEADING_WORD_RE.match(sql)
    verb = leading.group(1).lower() if leading else ""
    if verb not in {"select", "with"}:
        raise GuardError(f"only SELECT/WITH queries are allowed (got {verb or '?'})")

    lowered = sql.lower()
    for keyword in _FORBIDDEN:
        if re.search(rf"\b{keyword}\b", lowered):
            raise GuardError(f"forbidden keyword in query: {keyword}")

    allowed = {t.lower() for t in allowed_tables}
    for table in _referenced_tables(sql):
        # Only enforce fully-qualified references; a bare name is a CTE/derived alias.
        if "." in table and table not in allowed:
            raise GuardError(f"query references a table outside the model: {table}")

    if not _LIMIT_RE.search(sql):
        sql = f"{sql}\nLIMIT {max_limit}"
    return sql
