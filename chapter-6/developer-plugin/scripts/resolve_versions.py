#!/usr/bin/env python3
"""Resolve pinned upstream artifact versions for the developer plugin.

Writes/reads ``outputs/dev-lock.yaml`` at the workspace root. The
lockfile pins the exact v{N} folder used for each upstream artifact (lld,
stm, dqs, stories) during a single ``implement-stories`` batch so every
downstream create-*/update-* skill observes the same versions.

Modes:

  --write    Resolve the latest v{N}/ for each upstream under outputs/ and
             write the lockfile. If the lockfile already exists it is left
             untouched (implement-stories owns creation).
  --read     Print the lockfile contents as JSON. Exits 2 if the lockfile
             does not exist.
  --export   Print shell-evalable ``export KEY=VAL`` lines with the pinned
             directory paths. Falls back to latest v{N}/ if no lockfile is
             found so create-* skills that use this as an optional
             fast-path never hard-fail.

Environment variables exported by --export:

  LATEST_LLD_DIR, LATEST_STM_DIR, LATEST_DQS_DIR, LATEST_STORIES_DIR
  DEV_LOCK_FILE (path to lockfile, if present)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

UPSTREAMS = ("lld", "stm", "dqs", "stories")
LOCKFILE_NAME = "dev-lock.yaml"


def upstream_root(ws_root: Path, name: str) -> Path:
    """Return the ``outputs/<name>`` root for the given upstream artifact.

    All upstream artifacts (LLD, STM, DQS, stories, plus DMS/HLD/DRD) live under
    the workspace's own ``outputs/`` directory.
    """
    return ws_root / "outputs" / name


def find_workspace_root(start: Path) -> Path:
    """Walk upward from start until a dir with outputs/ and a CLAUDE.md-ish marker is found.

    Falls back to the first ancestor containing ``outputs/`` if no better
    signal is present.
    """
    start = start.resolve()
    for candidate in (start, *start.parents):
        if (candidate / "outputs").is_dir() and (
            (candidate / "CLAUDE.md").is_file() or (candidate / "pyproject.toml").is_file()
        ):
            return candidate
    # Fallback: first ancestor with outputs/
    for candidate in (start, *start.parents):
        if (candidate / "outputs").is_dir():
            return candidate
    return start


def latest_version_dir(base: Path) -> Path | None:
    if not base.is_dir():
        return None
    versions = sorted(
        (p for p in base.glob("v*") if p.is_dir()),
        key=lambda p: p.name,
    )
    return versions[-1] if versions else None


def resolve_latest(ws_root: Path) -> dict[str, str | None]:
    resolved: dict[str, str | None] = {}
    for name in UPSTREAMS:
        latest = latest_version_dir(upstream_root(ws_root, name))
        resolved[name] = latest.name if latest else None
    return resolved


def read_lockfile(path: Path) -> dict[str, str]:
    """Minimal YAML reader for a flat key: value lockfile."""
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        data[key.strip()] = value.strip().strip("'\"")
    return data


def write_lockfile(path: Path, pinned: dict[str, str | None]) -> None:
    lines = [
        "# developer-plugin version lockfile — pins upstream v{N}/ folders.",
        "# Written by implement-stories; consumed by create-*/update-* skills.",
        "# Delete to re-pin on the next implement-stories run.",
    ]
    for key in UPSTREAMS:
        val = pinned.get(key) or ""
        lines.append(f"{key}: {val}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def cmd_write(ws_root: Path) -> int:
    lockfile = ws_root / "outputs" / LOCKFILE_NAME
    if lockfile.exists():
        print(f"lockfile already present: {lockfile}", file=sys.stderr)
        data = read_lockfile(lockfile)
        print(json.dumps(data, indent=2))
        return 0
    pinned = resolve_latest(ws_root)
    lockfile.parent.mkdir(parents=True, exist_ok=True)
    write_lockfile(lockfile, pinned)
    print(json.dumps({"lockfile": str(lockfile), "pinned": pinned}, indent=2))
    return 0


def cmd_read(ws_root: Path) -> int:
    lockfile = ws_root / "outputs" / LOCKFILE_NAME
    if not lockfile.exists():
        print(f"no lockfile at {lockfile}", file=sys.stderr)
        return 2
    print(json.dumps(read_lockfile(lockfile), indent=2))
    return 0


def cmd_export(ws_root: Path) -> int:
    lockfile = ws_root / "outputs" / LOCKFILE_NAME
    if lockfile.exists():
        pinned = read_lockfile(lockfile)
        print(f"export DEV_LOCK_FILE={lockfile}")
    else:
        pinned = resolve_latest(ws_root)
    for name in UPSTREAMS:
        version = pinned.get(name) or ""
        if not version:
            continue
        path = upstream_root(ws_root, name) / version
        if not path.is_dir():
            continue
        var = f"LATEST_{name.upper()}_DIR"
        print(f"export {var}={path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="Create lockfile pinning latest v{N}/")
    group.add_argument("--read", action="store_true", help="Print lockfile contents as JSON")
    group.add_argument(
        "--export", action="store_true", help="Emit shell export lines for LATEST_*_DIR"
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=None,
        help="Workspace root override (default: walk up from CWD)",
    )
    args = parser.parse_args()

    ws_root = (
        args.workspace_root.resolve() if args.workspace_root else find_workspace_root(Path.cwd())
    )

    if args.write:
        return cmd_write(ws_root)
    if args.read:
        return cmd_read(ws_root)
    if args.export:
        return cmd_export(ws_root)
    return 2


if __name__ == "__main__":
    sys.exit(main())
