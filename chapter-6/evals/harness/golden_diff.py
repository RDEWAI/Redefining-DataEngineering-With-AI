"""YAML/markdown-aware diff harness.

For YAML files, we round-trip through PyYAML so whitespace + key-order
differences don't trigger spurious failures. For markdown / plain text,
we normalise line endings and trailing whitespace.

Re-baseline command: `make eval-update-goldens SKILL=<skill>` which
re-runs the eval and copies the new outputs over the committed goldens.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

GOLDENS_ROOT = Path(__file__).resolve().parents[1] / "goldens"


@dataclass
class DiffResult:
    skill: str
    matched: bool
    diffs: dict[str, str]  # path -> unified diff text
    missing_goldens: list[str]
    extra_artifacts: list[str]


def _normalise(text: str, kind: str) -> str:
    if kind == "yaml":
        try:
            parsed = list(yaml.safe_load_all(text))
            return yaml.safe_dump_all(parsed, sort_keys=True)
        except yaml.YAMLError:
            pass
    if kind == "json":
        try:
            return json.dumps(json.loads(text), indent=2, sort_keys=True)
        except json.JSONDecodeError:
            pass
    # Default: strip trailing whitespace per line, ensure final newline.
    lines = [re.sub(r"[ \t]+$", "", line) for line in text.splitlines()]
    return "\n".join(lines).rstrip() + "\n"


def _kind_for(path: str) -> str:
    if path.endswith((".yml", ".yaml")):
        return "yaml"
    if path.endswith(".json"):
        return "json"
    return "text"


def compare(
    skill: str,
    artifacts: dict[str, str],
    *,
    update_baseline: bool = False,
) -> DiffResult:
    golden_dir = GOLDENS_ROOT / skill
    diffs: dict[str, str] = {}
    missing: list[str] = []

    if not golden_dir.exists():
        if update_baseline:
            golden_dir.mkdir(parents=True)
        else:
            return DiffResult(skill, False, {}, list(artifacts), [])

    seen_goldens: set[str] = set()
    for rel, content in artifacts.items():
        golden_path = golden_dir / rel
        if update_baseline:
            golden_path.parent.mkdir(parents=True, exist_ok=True)
            golden_path.write_text(content, encoding="utf-8")
            seen_goldens.add(rel)
            continue
        if not golden_path.exists():
            missing.append(rel)
            continue
        kind = _kind_for(rel)
        expected = _normalise(golden_path.read_text(encoding="utf-8"), kind)
        actual = _normalise(content, kind)
        if expected != actual:
            diff = "\n".join(
                difflib.unified_diff(
                    expected.splitlines(),
                    actual.splitlines(),
                    fromfile=f"goldens/{skill}/{rel}",
                    tofile=f"actual/{rel}",
                    lineterm="",
                )
            )
            diffs[rel] = diff
        seen_goldens.add(rel)

    # Goldens present but not produced.
    extras: list[str] = []
    for golden in golden_dir.rglob("*"):
        if not golden.is_file():
            continue
        rel = golden.relative_to(golden_dir).as_posix()
        # Skip documentation-only goldens — they're notes for readers,
        # not artifacts we expect a skill to reproduce verbatim. Use the
        # `*-shape.json` / `README.md` conventions, or any path under a
        # `_doc/` subdirectory.
        if (
            rel.endswith("README.md")
            or rel.endswith("-shape.json")
            or "/_doc/" in f"/{rel}"
            or rel.startswith("_doc/")
        ):
            continue
        if rel not in seen_goldens and not update_baseline:
            extras.append(rel)

    return DiffResult(
        skill=skill,
        matched=not (diffs or missing or extras),
        diffs=diffs,
        missing_goldens=missing,
        extra_artifacts=extras,
    )
