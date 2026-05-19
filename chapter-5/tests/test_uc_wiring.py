"""Regression guard: Bronze ingestion patterns must use UC-managed writes,
not path-based Delta.

Spokane's first green Bronze run produced 13 invisible tables in Unity
Catalog because the pipeline wrote `df.write.format("delta").save("/tmp/...")`
instead of `df.write.format("delta").saveAsTable("unity.bronze.<table>")`.
LLD Decision 15 reverses that policy: Bronze MUST land in UC at write time
via `UCSingleCatalog` + `saveAsTable`. This test fires CRITICAL on any
chapter-5 generator-template file (snippets, ingestion-skill prose, LLD)
that reintroduces path-based Bronze writes.

A second guard ensures the Bronze runner snippet ships with the
`UCSingleCatalog` Spark-session config block — without that, even
`saveAsTable` falls back to `spark_catalog` and tables don't appear in UC.
"""
# ruff: noqa: E501  # regex literals are clearer when inline

from __future__ import annotations

import re
from pathlib import Path

import pytest

CHAPTER5_ROOT = Path(__file__).resolve().parent.parent

# Match `df.write.format("delta").save("/tmp/...` style — the path-based
# write pattern Decision 15 forbids for Bronze. Match either single or
# double quotes; allow whitespace + chained `.option(...)`/`.mode(...)` calls
# between `format("delta")` and `.save(...)`. Multi-line via DOTALL.
PATH_BASED_BRONZE_WRITE = re.compile(
    r'\.format\(\s*[\'"]delta[\'"]\s*\)\s*(?:\.[a-zA-Z_]+\([^)]*\)\s*)*\.save\s*\(',
    re.DOTALL,
)

# Files that should be scanned for Bronze write patterns. Limited to
# .py / .snippet generator templates — markdown skill prose is allowed to
# quote the anti-pattern in inline code blocks for documentation purposes,
# and the developer-plugin's `validate-dag UC-WIRING-001` rule scans
# generated `src/**/*.py` directly.
BRONZE_PATTERN_FILES = [
    "inputs/code/v1/scripts/ingestion_runner.py.snippet",
    "inputs/code/v1/scripts/dag_factory.py.snippet",
    "inputs/code/v1/scripts/reconciliation.py.snippet",
]


def _is_anti_pattern_docline(line: str) -> bool:
    """Skip lines that are documentation *warning* against the anti-pattern.

    Heuristics:
    - Pure comment lines in .snippet/.py (start with `#`) — documentation only.
    - Markdown lines inside a list item or prose that mention the pattern alongside
      a negative-keyword (NEVER, don't, instead, pitfall, forbid, reject).
    """
    stripped = line.lstrip()
    if stripped.startswith("#"):
        return True
    lower = line.lower()
    negative_markers = (
        "never ",
        "don't",
        "do not",
        "instead",
        "pitfall",
        "forbid",
        "reject",
        "not the bronze",
    )
    return any(marker in lower for marker in negative_markers)


class TestUcWiringRegression:
    def test_no_path_based_bronze_writes_in_generator_templates(self):
        offenders: list[tuple[str, int, str]] = []
        for rel in BRONZE_PATTERN_FILES:
            path = CHAPTER5_ROOT / rel
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if not PATH_BASED_BRONZE_WRITE.search(line):
                    continue
                if _is_anti_pattern_docline(line):
                    continue
                offenders.append((rel, lineno, line.strip()))
        assert not offenders, (
            "Path-based Bronze write found in generator template — Bronze "
            "must use UC-managed `saveAsTable` per Decision 15. Offenders:\n"
            + "\n".join(f"  {p}:{ln} → {body}" for p, ln, body in offenders)
        )

    def test_ingestion_runner_snippet_uses_uc_single_catalog(self):
        snippet = CHAPTER5_ROOT / "inputs/code/v1/scripts/ingestion_runner.py.snippet"
        if not snippet.is_file():
            pytest.skip("ingestion_runner.py.snippet not present yet")
        text = snippet.read_text(encoding="utf-8")
        assert "UCSingleCatalog" in text, (
            "ingestion_runner.py.snippet must wire UCSingleCatalog so saveAsTable "
            "lands tables in UC. See Decision 15."
        )
        assert "saveAsTable" in text, (
            "ingestion_runner.py.snippet must use saveAsTable for Bronze writes "
            "(not path-based `.save(...)`). See Decision 15."
        )
        assert "spark.sql.defaultCatalog" in text and "unity" in text, (
            "ingestion_runner.py.snippet must set defaultCatalog=unity so "
            "saveAsTable resolves to unity.bronze.* without explicit prefix."
        )
