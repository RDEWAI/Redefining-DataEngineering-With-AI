"""Unit tests for patient_360.utils.code_systems (STM Tab:Code Systems)."""

from __future__ import annotations

from patient_360.utils.code_systems import (
    CodeEntry,
    display_for,
    lookup,
    register_codes,
)


def test_lookup_hl7_seed_entries() -> None:
    entry = lookup("HL7", "F")
    assert entry is not None
    assert entry.display == "Female"
    assert entry.system == "HL7"


def test_lookup_snomed_seed() -> None:
    entry = lookup("SNOMED", "44054006")
    assert entry is not None
    assert entry.display == "Diabetes mellitus type 2"


def test_lookup_loinc_seed() -> None:
    entry = lookup("LOINC", "8302-2")
    assert entry is not None
    assert entry.display == "Body height"


def test_lookup_unknown_returns_none() -> None:
    assert lookup("HL7", "ZZZZ") is None


def test_display_for_returns_default_when_missing() -> None:
    assert display_for("HL7", "ZZZZ", default="unknown") == "unknown"


def test_register_codes_adds_to_cache() -> None:
    register_codes([CodeEntry(code="X9", display="custom", system="HL7")])
    assert display_for("HL7", "X9") == "custom"
