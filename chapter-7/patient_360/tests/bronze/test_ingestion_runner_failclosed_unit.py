"""STORY-01-009 — SE runner diagnostic import (fail-closed).

These tests assert the LLD §8.6 / §13 Decision 14 contract:

* When ``patient_360.utils.se_runner`` cannot be imported, the runner emits
  an ERROR-level log line containing ``se_runner not available`` (so a
  human operator sees a readable diagnostic above the stack trace).
* The runner **re-raises** the ImportError — there is no soft-degradation
  path. Fail-closed semantics are preserved.

The tests intentionally do NOT depend on PySpark; they exercise the import
diagnostic wrapper only.
"""

from __future__ import annotations

import builtins
import importlib
import logging
import sys

import pytest

_RUNNER_MOD = "patient_360.bronze.ingestion_runner"
_SE_MOD = "patient_360.utils.se_runner"


@pytest.fixture
def fresh_import(monkeypatch):
    """Force a clean re-import of ingestion_runner so the try/except runs."""

    def _reimport():
        # Drop any cached copies so the import logic actually executes.
        for mod_name in (_RUNNER_MOD, _SE_MOD):
            sys.modules.pop(mod_name, None)
        return importlib.import_module(_RUNNER_MOD)

    yield _reimport

    # Best-effort cleanup so other tests get a clean slate.
    for mod_name in (_RUNNER_MOD, _SE_MOD):
        sys.modules.pop(mod_name, None)


def test_missing_se_runner_logs_diagnostic_and_reraises(fresh_import, monkeypatch, caplog):
    """ImportError on se_runner must emit ERROR log AND propagate."""
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "patient_360.utils" and fromlist and "se_runner" in fromlist:
            raise ImportError("No module named 'spark_expectations'")
        if name == _SE_MOD:
            raise ImportError("No module named 'spark_expectations'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with caplog.at_level(logging.ERROR, logger="patient_360.bronze.ingestion_runner"):
        with pytest.raises(ImportError) as exc_info:
            fresh_import()

    # The original ImportError propagates (fail-closed contract).
    assert "spark_expectations" in str(exc_info.value)

    # Exactly one ERROR-level diagnostic line carrying the agreed substring.
    error_records = [
        r
        for r in caplog.records
        if r.levelno == logging.ERROR and "se_runner not available" in r.getMessage()
    ]
    assert error_records, (
        "Expected ERROR-level log line containing 'se_runner not available' before re-raise"
    )
    # Diagnostic must surface the underlying exception so the operator can act.
    assert "spark_expectations" in error_records[0].getMessage()


def test_successful_import_emits_no_error_log(fresh_import, caplog):
    """When se_runner imports cleanly, no ERROR diagnostic is emitted."""
    # se_runner may or may not exist in this checkout — both outcomes are
    # acceptable signals. We only care that IF the import succeeds, the
    # diagnostic line is NOT emitted.
    try:
        with caplog.at_level(logging.ERROR, logger="patient_360.bronze.ingestion_runner"):
            fresh_import()
    except ImportError:
        pytest.skip("se_runner not present in this checkout — covered by the other test")

    bad = [
        r
        for r in caplog.records
        if r.levelno == logging.ERROR and "se_runner not available" in r.getMessage()
    ]
    assert not bad, "ERROR diagnostic must only fire on ImportError"
