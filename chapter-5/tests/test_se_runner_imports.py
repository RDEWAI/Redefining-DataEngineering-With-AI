"""Regression guard: SE imports our generators emit must resolve, and SE
version pins below 2.10 must be rejected.

The chapter-5 developer-plugin generates code that imports:
- `spark_expectations.core.expectations.SparkExpectations`
- `spark_expectations.core.expectations.WrappedDataFrameWriter`
- `spark_expectations.config.user_config.Constants`
- `spark_expectations.rules.load_rules_from_yaml` (public API, SE >= 2.10)
- `spark_expectations.rules.plugins.yaml_loader.SparkExpectationsYamlRuleLoaderImpl`

The `spark_expectations.rules` package was added in SE v2.10.0 (PR #300):
https://github.com/Nike-Inc/spark-expectations/releases/tag/v2.10.0

Pinning SE below 2.10 — as the spokane sibling branch did at 2.6.0 —
raises `ModuleNotFoundError` at import time. Spokane bypassed this via
`BRONZE_SKIP_SE=1`, which we explicitly do NOT permit (DQ is mandatory).
This test fires CRITICAL on either:
  (a) the canonical imports failing at runtime when SE is installed, or
  (b) any chapter-5 file pinning `spark-expectations==2.x.y` with x.y < 10.
"""

# ruff: noqa: E501  # regex literals are clearer when inline

from __future__ import annotations

import re
from pathlib import Path

import pytest

CHAPTER5_ROOT = Path(__file__).resolve().parent.parent

# Match `spark-expectations==2.0.0` through `spark-expectations==2.9.x` —
# anything below 2.10 is a downgrade we must reject. 2.10+ uses two digits
# in the minor position, so `2.\d{2}` (10+) does NOT match. Reject pins
# without a >= specifier too: `spark-expectations==2.6.0` fails the gate
# even when surrounded by quotes.
SE_DOWNGRADE_PIN_PATTERN = re.compile(
    r'spark[-_]expectations\s*==\s*["\']?2\.[0-9](?!\d)',
    re.IGNORECASE,
)

# Files we'd expect to scan: snippets, dockerfiles, docs, tests, requirements.
SCAN_GLOBS = (
    "**/Dockerfile*",
    "**/*.snippet",
    "**/*.py",
    "**/*.md",
    "**/*.toml",
    "**/*.yaml",
    "**/*.yml",
)
# Skip the test file itself (it must contain the pattern as a literal) and
# any cached / vendored noise. Also skip test fixtures and validator
# eval-case YAMLs — they intentionally embed the bad pin as a regression
# input. The static-pin guard is for production-track files only
# (snippets, Dockerfiles, project configs).
SKIP_PARTS = {".venv", "__pycache__", ".pytest_cache", "node_modules", "outputs"}
SKIP_NAMES = {
    "test_validate_lld.py",
    "test_validate_dag.py",
    "test_refresh_libraries_imports.py",
    "test_uc_wiring.py",
    "test_dag_factory_wrappers.py",
    "eval-cases.yaml",
}


def _iter_chapter5_files() -> list[Path]:
    out: list[Path] = []
    for glob in SCAN_GLOBS:
        for p in CHAPTER5_ROOT.glob(glob):
            if any(part in SKIP_PARTS for part in p.parts):
                continue
            if p.name == Path(__file__).name or p.name in SKIP_NAMES:
                continue
            out.append(p)
    return out


class TestSparkExpectationsCanonicalImports:
    """Public API must resolve at runtime when SE is installed.

    Skips when SE isn't on the dev machine — the regression guard still fires
    on every CI run that has the package, and the static-pin gate below
    runs unconditionally.
    """

    def test_core_expectations_imports(self):
        pytest.importorskip("spark_expectations")
        from spark_expectations.core.expectations import (  # noqa: F401
            SparkExpectations,
            WrappedDataFrameWriter,
        )

        assert callable(SparkExpectations)
        assert callable(WrappedDataFrameWriter)

    def test_user_config_constants_import(self):
        pytest.importorskip("spark_expectations")
        from spark_expectations.config.user_config import Constants  # noqa: F401

    def test_yaml_rule_loader_public_api(self):
        """SE >=2.10 exposes `load_rules_from_yaml` from the rules package."""
        pytest.importorskip("spark_expectations")
        from spark_expectations.rules import load_rules_from_yaml  # noqa: F401

        assert callable(load_rules_from_yaml)

    def test_yaml_rule_loader_plugin_internal(self):
        pytest.importorskip("spark_expectations")
        from spark_expectations.rules.plugins.yaml_loader import (  # noqa: F401
            SparkExpectationsYamlRuleLoaderImpl,
        )


class TestSparkExpectationsVersionFloor:
    """No chapter-5 file may pin `spark-expectations==2.x.y` below 2.10."""

    def test_no_se_pin_below_2_10(self):
        offenders: list[tuple[Path, int, str]] = []
        for path in _iter_chapter5_files():
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for lineno, line in enumerate(content.splitlines(), start=1):
                if SE_DOWNGRADE_PIN_PATTERN.search(line):
                    offenders.append((path.relative_to(CHAPTER5_ROOT), lineno, line.strip()))
        assert not offenders, (
            "spark-expectations pinned below 2.10 — earlier versions don't have "
            "the YAML rule loader our DQ generator depends on:\n"
            + "\n".join(f"  {p}:{ln} → {body}" for p, ln, body in offenders)
        )
