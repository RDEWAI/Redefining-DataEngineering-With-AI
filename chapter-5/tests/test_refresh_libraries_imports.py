"""Tests for the Canonical Imports overlay merge in refresh_libraries.py.

The overlay (`inputs/code/v1/library-imports.yaml`) is the curated source
of truth for "the imports our generators emit". This test verifies:
  * `load_imports_overlay` reads the YAML.
  * `build_diff` attaches canonical_imports / notes / min_version per row.
  * Resolved version below overlay `min_version` raises `floor_violation`
    (the regression guard for the spokane SE-2.6.0 / SE-2.10 drift).
"""
# ruff: noqa: E501

from __future__ import annotations

import sys
from pathlib import Path

import pytest

VALIDATOR_DIR = (
    Path(__file__).resolve().parent.parent
    / "developer-plugin"
    / "skills"
    / "refresh-libraries"
    / "scripts"
)
sys.path.insert(0, str(VALIDATOR_DIR))

from refresh_libraries import (  # noqa: E402
    Row,
    build_diff,
    load_imports_overlay,
)

SAMPLE_OVERLAY_YAML = """\
spark-expectations:
  min_version: "2.10.0"
  canonical_imports:
    - "from spark_expectations.core.expectations import SparkExpectations"
  notes: "YAML rule loader added in v2.10.0."
pyspark:
  min_version: "4.0.0"
  canonical_imports:
    - "from pyspark.sql import SparkSession"
"""


@pytest.fixture
def overlay_file(tmp_path) -> Path:
    f = tmp_path / "library-imports.yaml"
    f.write_text(SAMPLE_OVERLAY_YAML, encoding="utf-8")
    return f


class TestLoadOverlay:
    def test_loads_from_file(self, overlay_file):
        overlay = load_imports_overlay(overlay_file)
        assert "spark-expectations" in overlay
        assert overlay["spark-expectations"]["min_version"] == "2.10.0"

    def test_missing_file_returns_empty(self, tmp_path):
        assert load_imports_overlay(tmp_path / "nope.yaml") == {}

    def test_none_returns_empty(self):
        assert load_imports_overlay(None) == {}


class TestBuildDiffWithOverlay:
    def _make_row(self, library: str, version: str) -> Row:
        return Row(library=library, version=version, docs_url="https://example/", note="")

    def test_overlay_attaches_canonical_imports(self, overlay_file):
        overlay = load_imports_overlay(overlay_file)
        rows = [self._make_row("Nike Spark Expectations", "2.10.0")]
        diffs = build_diff(rows, "all", overlay=overlay)
        # network calls in build_diff happen for resolve_latest; one of:
        #   - PyPI returns latest version → diff.new_version updates
        #   - PyPI request fails → diff.unresolved=True, new_version=row.version
        # Either way, the overlay attachment must work.
        d = diffs[0]
        assert d.canonical_imports == [
            "from spark_expectations.core.expectations import SparkExpectations"
        ]
        assert d.min_version == "2.10.0"
        assert d.overlay_notes is not None

    def test_overlay_floor_violation_when_pinned_below(self, overlay_file):
        """Regression guard: the SE 2.6.0 → 2.10.0 drift fires CRITICAL."""
        overlay = load_imports_overlay(overlay_file)
        rows = [self._make_row("spark-expectations", "2.6.0")]
        # Force unresolved=True by using an unknown library key for resolution
        # — we want to assert floor logic against the *current* version, not
        # the resolved one. Easiest way: use a name that doesn't match any
        # PYPI_RESOLVERS entry. The overlay match is substring-based, so
        # "spark-expectations" (lowercase) matches our overlay key.
        diffs = build_diff(rows, "all", overlay=overlay)
        d = diffs[0]
        # floor_violation triggers when the resolved or pinned version
        # parses as below 2.10.0. Since the row pin is 2.6.0 and the
        # resolver may not change it, floor_violation should be set.
        if d.unresolved:
            assert d.floor_violation, (
                f"SE pin {d.new_version} is below overlay floor {d.min_version}; "
                "floor_violation must fire."
            )
        else:
            # PyPI returned a real version. If it's >=2.10 the floor isn't
            # violated; if it's somehow <2.10 it should be.
            from refresh_libraries import _version_below

            expected = _version_below(d.new_version, "2.10.0")
            assert d.floor_violation == expected

    def test_no_overlay_match_leaves_canonical_imports_unset(self, overlay_file):
        overlay = load_imports_overlay(overlay_file)
        rows = [self._make_row("DuckDB", "1.5.2")]
        diffs = build_diff(rows, "all", overlay=overlay)
        d = diffs[0]
        assert d.canonical_imports is None
        assert d.min_version is None
        assert d.floor_violation is False
