#!/usr/bin/env python3
"""Resolve latest versions for every row in LIBRARIES.md and emit a diff JSON.

This script does not rewrite LIBRARIES.md — that's the skill's job.
It returns a structured diff the skill consumes for its AskUserQuestion prompt.

Usage:
    python3 refresh_libraries.py \\
        --current /path/to/LIBRARIES.md \\
        --filter all|{library-name} \\
        --out /tmp/refresh_libraries.diff.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

PYPI_RESOLVERS = {
    "pyspark": "pyspark",
    "pyspark [pipelines]": "pyspark",
    "delta lake": "delta-spark",
    "delta-spark": "delta-spark",
    "nike spark expectations": "spark-expectations",
    "spark-expectations": "spark-expectations",
    "duckdb": "duckdb",
    "pytest": "pytest",
    "pytest-mock": "pytest-mock",
    "ruff": "ruff",
    "apache airflow": "apache-airflow",
}

GITHUB_RESOLVERS = {
    "unity catalog oss": "unitycatalog/unitycatalog",
    "unity catalog": "unitycatalog/unitycatalog",
    "marquez": "MarquezProject/marquez",
    "openlineage spark listener": "OpenLineage/OpenLineage",
    "openlineage": "OpenLineage/OpenLineage",
    "uv": "astral-sh/uv",
}


@dataclass
class Row:
    library: str
    version: str
    docs_url: str
    note: str


@dataclass
class Diff:
    library: str
    old_version: str
    new_version: str
    old_url: str
    new_url: str
    breaking_change_note: str
    resolver: str
    unresolved: bool = False
    canonical_imports: list[str] | None = None
    spark_jars_packages: list[str] | None = None
    overlay_notes: str | None = None
    min_version: str | None = None
    floor_violation: bool = False


def parse_libraries_md(path: Path) -> list[Row]:
    text = path.read_text()
    rows: list[Row] = []
    table_re = re.compile(
        r"^\|\s*(?P<library>[^|]+?)\s*\|"
        r"\s*(?P<version>[^|]+?)\s*\|"
        r"\s*(?P<url>[^|]+?)\s*\|"
        r"\s*(?P<note>[^|]*?)\s*\|$",
        re.MULTILINE,
    )
    for m in table_re.finditer(text):
        library = m.group("library").strip()
        if library.lower() in {"library", "---"} or library.startswith(":-"):
            continue
        rows.append(
            Row(
                library=library,
                version=m.group("version").strip(),
                docs_url=m.group("url").strip(),
                note=m.group("note").strip(),
            )
        )
    return rows


def fetch_pypi_latest(package: str) -> str | None:
    url = f"https://pypi.org/pypi/{package}/json"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.load(resp)
        return data.get("info", {}).get("version")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None


def fetch_github_latest(repo: str) -> str | None:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
        tag = data.get("tag_name", "")
        return tag.lstrip("v") or None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None


def normalize(name: str) -> str:
    return name.lower().strip("` ")


def resolve_latest(row: Row) -> tuple[str | None, str]:
    key = normalize(row.library)
    if key in PYPI_RESOLVERS:
        return fetch_pypi_latest(PYPI_RESOLVERS[key]), "pypi"
    if key in GITHUB_RESOLVERS:
        return fetch_github_latest(GITHUB_RESOLVERS[key]), "github"
    for k, v in PYPI_RESOLVERS.items():
        if k in key:
            return fetch_pypi_latest(v), "pypi"
    for k, v in GITHUB_RESOLVERS.items():
        if k in key:
            return fetch_github_latest(v), "github"
    return None, "unresolved"


def version_delta(old: str, new: str) -> str:
    old_clean = old.lstrip(">=<~").split(",")[0].strip()
    new_clean = new.strip()
    if old_clean == new_clean:
        return "—"

    def parts(v: str) -> list[int]:
        out: list[int] = []
        for chunk in re.split(r"[.\-+]", v):
            if chunk.isdigit():
                out.append(int(chunk))
            else:
                break
        return out

    op, np = parts(old_clean), parts(new_clean)
    if op and np and np[0] > op[0]:
        return "MAJOR — review changelog"
    if op and np and len(op) > 1 and len(np) > 1 and np[1] > op[1]:
        return "minor"
    return "patch"


def load_imports_overlay(path: Path | None) -> dict[str, dict]:
    """Return a {library_key: overlay_entry} dict from the imports YAML.

    Returns an empty dict if the overlay isn't present (back-compat —
    refresh-libraries pre-Fix-10 didn't have one). The library_key is
    the lowercased package name; matching against LIBRARIES.md rows uses
    the same case-insensitive substring rules as PYPI_RESOLVERS.
    """
    if path is None or not path.is_file():
        return {}
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError:
        # Fallback: minimal YAML subset parser is overkill — pyyaml is
        # already a chapter-5 dep. If it ever isn't, surface a warning.
        sys.stderr.write("WARNING: pyyaml not available; overlay ignored\n")
        return {}
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        return {}
    return {key.lower(): val for key, val in raw.items() if isinstance(val, dict)}


def _normalize_for_match(s: str) -> str:
    """Lowercase + treat dashes/underscores/spaces as equivalent for matching."""
    return re.sub(r"[-_\s]+", " ", s.lower()).strip()


def _match_overlay(library: str, overlay: dict[str, dict]) -> dict | None:
    """Match a LIBRARIES.md row against an overlay key.

    Matching is case-insensitive AND treats `-`/`_`/whitespace as
    interchangeable, so:
      - "Nike Spark Expectations" matches overlay key "spark-expectations"
      - "PySpark `pyspark[pipelines]`" matches "pyspark"
    """
    lib_n = _normalize_for_match(library)
    for key, entry in overlay.items():
        key_n = _normalize_for_match(key)
        if key_n in lib_n or lib_n in key_n:
            return entry
    return None


def _version_below(resolved: str, floor: str) -> bool:
    """True if resolved version is strictly below the overlay floor."""

    def parts(v: str) -> tuple[int, ...]:
        out: list[int] = []
        for chunk in re.split(r"[.\-+]", v.lstrip(">=<~ ").strip()):
            if chunk.isdigit():
                out.append(int(chunk))
            else:
                break
        return tuple(out)

    try:
        return parts(resolved) < parts(floor)
    except Exception:
        return False


def build_diff(  # noqa: E501
    rows: list[Row], filter_name: str, overlay: dict[str, dict] | None = None
) -> list[Diff]:
    out: list[Diff] = []
    wanted = filter_name.lower().strip()
    overlay = overlay or {}
    for row in rows:
        if wanted != "all" and wanted not in row.library.lower():
            continue
        latest, resolver = resolve_latest(row)
        unresolved = latest is None
        note = (
            row.note
            if unresolved or latest == row.version.lstrip(">=<~").strip()
            else version_delta(row.version, latest)
        )
        diff = Diff(
            library=row.library,
            old_version=row.version,
            new_version=latest or row.version,
            old_url=row.docs_url,
            new_url=row.docs_url,
            breaking_change_note=note,
            resolver=resolver,
            unresolved=unresolved,
        )
        entry = _match_overlay(row.library, overlay)
        if entry:
            diff.canonical_imports = list(entry.get("canonical_imports") or [])
            diff.spark_jars_packages = list(entry.get("spark_jars_packages") or [])
            diff.overlay_notes = entry.get("notes")
            floor = entry.get("min_version")
            if floor:
                diff.min_version = str(floor)
                resolved = diff.new_version if not unresolved else row.version
                if _version_below(resolved, str(floor)):
                    diff.floor_violation = True
                    diff.breaking_change_note = (
                        f"CRITICAL: resolved {resolved} is below overlay floor {floor} — "
                        f"canonical imports will fail at runtime."
                    )
        out.append(diff)
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--current", required=True, type=Path)
    p.add_argument("--filter", default="all")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument(
        "--imports-overlay",
        type=Path,
        default=None,
        help=(
            "Optional YAML file with curated canonical imports per library. "
            "Defaults to <current>.parent / 'library-imports.yaml'."
        ),
    )
    args = p.parse_args()

    if not args.current.exists():
        print(f"CRITICAL: {args.current} not found", file=sys.stderr)
        return 1

    rows = parse_libraries_md(args.current)
    if not rows:
        print(f"CRITICAL: no library rows parsed from {args.current}", file=sys.stderr)
        return 1

    overlay_path = args.imports_overlay or (args.current.parent / "library-imports.yaml")
    overlay = load_imports_overlay(overlay_path if overlay_path.is_file() else None)

    diff = build_diff(rows, args.filter, overlay=overlay)
    args.out.write_text(json.dumps([asdict(d) for d in diff], indent=2))
    floor_violations = sum(1 for d in diff if d.floor_violation)
    overlay_msg = f" (overlay: {overlay_path.name})" if overlay else " (no overlay loaded)"
    print(f"Resolved {len(diff)} rows{overlay_msg}; diff → {args.out}")
    if floor_violations:
        print(
            f"CRITICAL: {floor_violations} library/libraries below overlay floor "
            "— see breaking_change_note fields.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
