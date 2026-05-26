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


# ---------------------------------------------------------------------------
# CLI — invoked by `make eval-update-goldens SKILL=<skill>`.
#
# The Makefile target documents this as the canonical re-baseline workflow:
#   1. Re-run the skill against the fixture to capture fresh artifacts.
#   2. Copy them over the committed goldens at `evals/goldens/<skill>/`.
#
# This module ships step 2 (the file copy) — step 1 is the user's
# responsibility because every skill's invocation context differs (some
# need docker, some need upstream LLD artifacts, etc.). Pass the
# captured artifacts via `--from <dir>`.
# ---------------------------------------------------------------------------


def _cli_update(skill: str, source_dir: Path) -> int:
    if not source_dir.exists() or not source_dir.is_dir():
        print(f"--from {source_dir} is not a directory", flush=True)
        return 1
    artifacts: dict[str, str] = {}
    for path in source_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(source_dir).as_posix()
        try:
            artifacts[rel] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"skip binary file: {rel}", flush=True)
            continue
    if not artifacts:
        print(f"no readable files under {source_dir}", flush=True)
        return 1
    result = compare(skill, artifacts, update_baseline=True)
    print(
        f"goldens for {skill}: wrote {len(artifacts)} files under " f"{GOLDENS_ROOT / skill}",
        flush=True,
    )
    return 0 if result.matched else 0  # update mode always succeeds


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="golden-output diff harness")
    parser.add_argument(
        "--update",
        metavar="SKILL",
        help="Re-baseline goldens for the named skill (read artifacts from --from)",
    )
    parser.add_argument(
        "--from",
        dest="source",
        metavar="DIR",
        help="Directory holding the fresh artifacts to copy over the goldens",
    )
    args = parser.parse_args(argv)

    if args.update:
        if not args.source:
            parser.error("--update requires --from <dir>")
        return _cli_update(args.update, Path(args.source))

    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.exit(main())
