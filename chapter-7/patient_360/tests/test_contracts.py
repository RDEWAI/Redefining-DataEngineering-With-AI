"""Verify every ``contracts/*.yml`` points at real ``ddl_path`` / ``dq_path`` files.

Contracts must form a closed graph: every ``ddl_path`` / ``dq_path`` in a
contract must resolve to a file that actually exists on disk.

Scope:
- ``dq_path`` is validated for every contract.
- ``ddl_path`` is validated for Bronze contracts (Liquibase migration
  scope). Silver / Gold DDL typically lives in the transformation layer
  rather than Liquibase, so those contracts may reference DDL paths that
  are not materialised as XML changelogs yet.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_DIR = PROJECT_ROOT / "contracts"


def _load_contracts() -> list[tuple[Path, dict]]:
    contracts = []
    if not CONTRACTS_DIR.exists():
        return contracts
    for yml in sorted(CONTRACTS_DIR.glob("*.yml")):
        data = yaml.safe_load(yml.read_text()) or {}
        contracts.append((yml, data))
    return contracts


CONTRACTS = _load_contracts()


def test_contracts_directory_nonempty() -> None:
    assert CONTRACTS, f"No contracts found under {CONTRACTS_DIR}"


@pytest.mark.parametrize(
    "contract_file,contract",
    CONTRACTS,
    ids=[c[0].stem for c in CONTRACTS] or ["no-contracts"],
)
def test_dq_path_resolves(contract_file: Path, contract: dict) -> None:
    dq_path = contract.get("dq_path")
    assert dq_path, f"{contract_file.name}: missing dq_path"
    resolved = PROJECT_ROOT / dq_path
    assert resolved.is_file(), (
        f"{contract_file.name}: dq_path does not resolve to a file: {resolved}"
    )


BRONZE_CONTRACTS = [(p, c) for p, c in CONTRACTS if (c.get("layer") or "").lower() == "bronze"]


@pytest.mark.parametrize(
    "contract_file,contract",
    BRONZE_CONTRACTS,
    ids=[c[0].stem for c in BRONZE_CONTRACTS] or ["no-bronze"],
)
def test_bronze_ddl_path_resolves(contract_file: Path, contract: dict) -> None:
    ddl_path = contract.get("ddl_path")
    assert ddl_path, f"{contract_file.name}: missing ddl_path"
    resolved = PROJECT_ROOT / ddl_path
    assert resolved.is_file(), (
        f"{contract_file.name}: ddl_path does not resolve to a file: {resolved}"
    )
