"""Unit tests for patient_360.utils.scd2.

The pure-Python ``compute_record_hash_python`` is the unit-testable
surface. :func:`apply_scd2` boots Spark and is covered by integration
tests under tests/integration/silver/ (per learning L-001).
"""

from __future__ import annotations

import hashlib

from patient_360.utils.scd2 import compute_record_hash_python


def test_compute_record_hash_is_deterministic() -> None:
    row = {"id": 1, "name": "alice", "city": "berlin"}
    h1 = compute_record_hash_python(row, ["id", "name", "city"])
    h2 = compute_record_hash_python(row, ["id", "name", "city"])
    assert h1 == h2
    assert len(h1) == 64


def test_hash_changes_when_any_column_changes() -> None:
    row = {"id": 1, "name": "alice", "city": "berlin"}
    base = compute_record_hash_python(row, ["id", "name", "city"])
    changed = compute_record_hash_python(
        {"id": 1, "name": "alice", "city": "munich"}, ["id", "name", "city"]
    )
    assert base != changed


def test_no_change_returns_same_hash() -> None:
    row_a = {"id": 1, "name": "alice"}
    row_b = {"id": 1, "name": "alice"}
    assert compute_record_hash_python(row_a, ["id", "name"]) == (
        compute_record_hash_python(row_b, ["id", "name"])
    )


def test_hash_matches_explicit_sha256() -> None:
    row = {"id": "x", "v": "y"}
    expected = hashlib.sha256(b"x|y").hexdigest()
    assert compute_record_hash_python(row, ["id", "v"]) == expected


def test_missing_column_treated_as_empty() -> None:
    row = {"id": 1}
    # Column "missing" is absent — module falls back to "".
    h = compute_record_hash_python(row, ["id", "missing"])
    expected = hashlib.sha256(b"1|").hexdigest()
    assert h == expected
