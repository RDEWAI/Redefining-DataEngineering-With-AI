"""Load the AI-metadata folders into flat, retrievable :class:`KnowledgeDoc` records.

Four metadata layers live at the project root, each a folder of YAML:

    semantic/        business meaning for SQL   (entities, measures, glossary, verified queries)
    ontology/        domain map                 (entities, attributes, relations, constraints)
    taxonomy/        parent -> child hierarchies (inheritance / classification)
    data_contracts/  producer<->consumer SLAs   (freshness, latency, versioning)

Each ``*.yml`` becomes one document whose ``text`` is a human-readable flattening of the YAML,
so a lexical index (see :mod:`patient_360.knowledge.index`) can retrieve it and an AI can read
the retrieved chunk verbatim as context.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

# knowledge/documents.py -> src/patient_360/knowledge -> parents[3] == project root
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# metadata kind -> folder name (relative to the project root), in retrieval-priority order.
KIND_DIRS: dict[str, str] = {
    "semantic": "semantic",
    "ontology": "ontology",
    "taxonomy": "taxonomy",
    "data_contract": "data_contracts",
}


class KnowledgeDoc(BaseModel):
    """One metadata file rendered as a retrievable document."""

    id: str            # stable id, e.g. "ontology:ontology/entities/patient.yml"
    kind: str          # semantic | ontology | taxonomy | data_contract
    source: str        # project-relative path
    title: str         # concept/table/contract name
    text: str          # readable flattening of the YAML (indexed + shown as context)
    tags: list[str] = []


def _flatten(value: Any, indent: int = 0) -> list[str]:
    """Render a parsed-YAML value as indented ``key: value`` / bullet lines."""
    pad = "  " * indent
    lines: list[str] = []
    if isinstance(value, dict):
        for key, val in value.items():
            if isinstance(val, (dict, list)) and val:
                lines.append(f"{pad}{key}:")
                lines.extend(_flatten(val, indent + 1))
            else:
                lines.append(f"{pad}{key}: {val}")
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{pad}-")
                lines.extend(_flatten(item, indent + 1))
            else:
                lines.append(f"{pad}- {item}")
    else:
        lines.append(f"{pad}{value}")
    return lines


def _title(data: dict[str, Any], path: Path) -> str:
    for key in ("name", "id", "concept", "table"):
        val = data.get(key)
        if isinstance(val, str) and val:
            return val
    return path.stem


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if isinstance(data, dict) else {}


def load_documents(project_root: str | Path | None = None) -> list[KnowledgeDoc]:
    """Discover every ``*.yml`` under the four metadata folders and load it as a document.

    Missing folders are skipped (so the loader works before every layer exists). Files are
    returned sorted by (kind priority, path) for a deterministic index.
    """
    root = Path(project_root) if project_root is not None else PROJECT_ROOT
    docs: list[KnowledgeDoc] = []
    for kind, dirname in KIND_DIRS.items():
        base = root / dirname
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.yml")):
            data = _read_yaml(path)
            if not data:
                continue
            rel = path.relative_to(root).as_posix()
            title = _title(data, path)
            is_manifest = path.name == "manifest.yml"
            body = "\n".join(_flatten(data))
            text = f"[{kind}] {title}\n{body}"
            tags = [kind, "manifest" if is_manifest else "entry", path.stem]
            docs.append(
                KnowledgeDoc(
                    id=f"{kind}:{rel}", kind=kind, source=rel, title=title, text=text, tags=tags
                )
            )
    return docs
