"""Regression test for brace expansion in verify_acs.py glob payloads.

Stories often write `{a,b,c}_*.yml` to match multiple layer prefixes in a
single verifier glob. Python's `glob.glob` does not natively support brace
expansion; the verifier must expand them itself.
"""

from __future__ import annotations

import sys
from pathlib import Path

VERIFY_ACS = Path(__file__).resolve().parents[1] / "developer-plugin" / "scripts" / "verify_acs.py"
sys.path.insert(0, str(VERIFY_ACS.parent))
import verify_acs as va  # type: ignore[import-not-found]  # noqa: E402


def test_expand_braces_single_group() -> None:
    out = va._expand_braces("contracts/{a,b,c}_*.yml")
    assert out == ["contracts/a_*.yml", "contracts/b_*.yml", "contracts/c_*.yml"]


def test_expand_braces_no_braces_passthrough() -> None:
    assert va._expand_braces("contracts/foo_*.yml") == ["contracts/foo_*.yml"]


def test_expand_braces_two_groups() -> None:
    out = va._expand_braces("{x,y}/{a,b}.yml")
    assert sorted(out) == ["x/a.yml", "x/b.yml", "y/a.yml", "y/b.yml"]


def test_resolve_files_brace_glob_unions_matches(tmp_path: Path) -> None:
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    for name in ("clinical_patients.yml", "reference_orgs.yml", "billing_claims.yml"):
        (contracts / name).write_text("", encoding="utf-8")
    files = va._resolve_files(
        {"glob": "contracts/{clinical,reference,billing}_*.yml"},
        tmp_path,
    )
    assert len(files) == 3
    names = sorted(p.name for p in files)
    assert names == ["billing_claims.yml", "clinical_patients.yml", "reference_orgs.yml"]


def test_resolve_files_brace_glob_dedupes_overlap(tmp_path: Path) -> None:
    """Overlapping brace alternatives should not double-count files."""
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "patients.yml").write_text("", encoding="utf-8")
    files = va._resolve_files(
        {"glob": "contracts/{patients,patients}.yml"},
        tmp_path,
    )
    assert len(files) == 1
