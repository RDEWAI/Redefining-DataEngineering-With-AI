"""Lookup helpers for the HL7, SNOMED, and LOINC code systems.

The STM Tab:Code Systems sheet (see ``outputs/stm/v2/STM-*.xlsx``) lists the
authoritative code-to-display mappings used by Silver transforms. This
module exposes a small in-process cache (loaded on first lookup) so callers
can resolve codes without round-tripping to a database.

The cache is intentionally minimal — extend it via :func:`register_codes`
or by editing the inline dictionaries below as the STM evolves.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CodeSystem = Literal["HL7", "SNOMED", "LOINC"]


@dataclass(frozen=True)
class CodeEntry:
    code: str
    display: str
    system: CodeSystem


# Seed entries — projects extend via register_codes() at startup or by
# editing this map. Real systems are much larger and typically backed by a
# Delta lookup table; the in-memory map keeps Silver tests dependency-free.
_CODES: dict[tuple[CodeSystem, str], CodeEntry] = {
    ("HL7", "F"): CodeEntry("F", "Female", "HL7"),
    ("HL7", "M"): CodeEntry("M", "Male", "HL7"),
    ("SNOMED", "44054006"): CodeEntry("44054006", "Diabetes mellitus type 2", "SNOMED"),
    ("LOINC", "8302-2"): CodeEntry("8302-2", "Body height", "LOINC"),
}


def lookup(system: CodeSystem, code: str) -> CodeEntry | None:
    """Return the registered entry for ``(system, code)`` or ``None``."""
    return _CODES.get((system, code))


def display_for(system: CodeSystem, code: str, default: str | None = None) -> str | None:
    """Convenience: return the display name or ``default`` if not found."""
    entry = lookup(system, code)
    return entry.display if entry else default


def register_codes(entries: list[CodeEntry]) -> None:
    """Append entries to the in-memory cache (idempotent on duplicates)."""
    for entry in entries:
        _CODES[(entry.system, entry.code)] = entry
