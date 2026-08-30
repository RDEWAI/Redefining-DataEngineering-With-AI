"""Load the ``semantic/`` directory into a validated :class:`SemanticModel`.

Layout expected under ``semantic_dir``::

    manifest.yml            # model metadata + relationships + metrics + glossary + verified_queries
    entities/*.yml          # one file per entity (Gold table)

The manifest may either list entities inline under an ``entities:`` key, or (the
convention used here) reference them by file via ``entity_files:`` / rely on every
``entities/*.yml`` being auto-discovered. Auto-discovery is the default.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from patient_360.semantic.schema import SemanticModel

# semantic/ lives at the project root, a sibling of contracts/ and dq_rules/.
# schema.py is at src/patient_360/semantic/schema.py -> parents[3] == project root.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SEMANTIC_DIR = _PROJECT_ROOT / "semantic"


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(
            f"{path}: expected a YAML mapping at the top level, got {type(data).__name__}"
        )
    return data


def load_model(semantic_dir: str | Path | None = None) -> SemanticModel:
    """Parse ``semantic_dir`` into a validated :class:`SemanticModel`.

    Entities are read from ``entities/*.yml`` (sorted by filename for determinism) unless
    the manifest already carries an inline ``entities`` list. Raises ``FileNotFoundError``
    if the directory or manifest is missing and ``pydantic.ValidationError`` on a bad model.
    """
    root = Path(semantic_dir) if semantic_dir is not None else DEFAULT_SEMANTIC_DIR
    if not root.is_dir():
        raise FileNotFoundError(f"semantic directory not found: {root}")

    manifest_path = root / "manifest.yml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")
    manifest = _read_yaml(manifest_path)

    if not manifest.get("entities"):
        entities_dir = root / "entities"
        if not entities_dir.is_dir():
            raise FileNotFoundError(f"entities directory not found: {entities_dir}")
        entity_files = sorted(entities_dir.glob("*.yml"))
        if not entity_files:
            raise FileNotFoundError(f"no entity files under {entities_dir}")
        manifest["entities"] = [_read_yaml(p) for p in entity_files]

    return SemanticModel.model_validate(manifest)
