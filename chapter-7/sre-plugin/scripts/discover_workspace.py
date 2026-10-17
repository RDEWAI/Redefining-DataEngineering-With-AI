#!/usr/bin/env python3
"""Workspace discovery for the SRE plugin (copied from the developer plugin's
``status_rollup.py`` discover mode so this plugin has no cross-plugin runtime
dependency).

Walks upward from a start directory to find the chapter workspace: the folder
holding ``outputs/stories/`` and a cookiecutter-style project child
(``pyproject.toml`` + ``src/<name>/``). Prints JSON with ``workspace_root``,
``project_root``, ``project_name``, ``stories_dir`` and ``learnings_queue``
(``memory/sre/learnings-queue.jsonl``).

Usage::

    python3 discover_workspace.py [--start DIR] [--workspace-root DIR] [--project-name NAME]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROLE = "sre"


class DiscoveryError(Exception):
    """Raised when the workspace cannot be auto-discovered."""


@dataclass
class Workspace:
    """Auto-discovered workspace paths. All paths are absolute.

    Layout assumption (matches the cookiecutter-chapter template)::

        {workspace_root}/
          outputs/stories/v*/...
          {project_root}/                   <- cookiecutter-generated
            pyproject.toml
            src/{project_name}/...
          memory/developer/learnings-queue.jsonl   (may not exist yet)

    When the cookiecutter project has not yet been bootstrapped, ``project_root``
    and ``project_name`` may be ``None`` and ``needs_bootstrap`` is ``True`` —
    callers should dispatch ``create-scaffold`` before any other generator.
    """

    workspace_root: Path
    project_root: Path | None
    project_name: str | None
    stories_dir: Path
    learnings_queue: Path
    backlog_glob: str = "BACKLOG-*.md"
    needs_bootstrap: bool = False

    def as_dict(self) -> dict:
        return {
            "workspace_root": str(self.workspace_root),
            "project_root": str(self.project_root) if self.project_root else None,
            "project_name": self.project_name,
            "stories_dir": str(self.stories_dir),
            "learnings_queue": str(self.learnings_queue),
            "backlog_glob": self.backlog_glob,
            "needs_bootstrap": self.needs_bootstrap,
        }


def _find_project_children(parent: Path) -> list[tuple[Path, str]]:
    """Return immediate subdirectories of ``parent`` that look like a cookiecutter project.

    A project directory has ``pyproject.toml`` at its root and at least one
    ``src/<name>/`` subdirectory (``<name>`` is used as ``project_name``).
    """
    results: list[tuple[Path, str]] = []
    if not parent.is_dir():
        return results
    for child in sorted(parent.iterdir()):
        if not child.is_dir():
            continue
        if not (child / "pyproject.toml").is_file():
            continue
        src = child / "src"
        if not src.is_dir():
            continue
        pkgs = [p for p in sorted(src.iterdir()) if p.is_dir() and not p.name.startswith(".")]
        if not pkgs:
            continue
        # Prefer the package whose name matches the folder name (cookiecutter
        # default); otherwise pick the first.
        matching = [p for p in pkgs if p.name == child.name]
        pkg = matching[0] if matching else pkgs[0]
        results.append((child, pkg.name))
    return results


def _read_workspace_marker(ws_root: Path) -> dict[str, str]:
    """Read ``.workspace.yaml`` at ws_root if present.

    Supports keys ``project_dir:`` and ``stories_dir:`` (both relative to
    ``ws_root``). Minimal parser — flat ``key: value`` lines only.
    """
    marker = ws_root / ".workspace.yaml"
    if not marker.is_file():
        return {}
    data: dict[str, str] = {}
    for line in marker.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        data[key.strip()] = value.strip().strip("'\"")
    return data


def _build_unbootstrapped(ws_root: Path, stories_dir: Path) -> Workspace:
    """Build a Workspace for a workspace whose cookiecutter project is missing."""
    return Workspace(
        workspace_root=ws_root,
        project_root=None,
        project_name=None,
        stories_dir=stories_dir,
        learnings_queue=ws_root / "memory" / ROLE / "learnings-queue.jsonl",
        needs_bootstrap=True,
    )


def discover_workspace(
    start: Path,
    workspace_root_override: Path | None = None,
    project_name_override: str | None = None,
) -> Workspace:
    """Walk upward from ``start`` to find the workspace anchor.

    Resolution order:
      1. ``--workspace-root`` override.
      2. Any ancestor containing ``.workspace.yaml`` (explicit marker).
      3. Co-location heuristic: ancestor with ``outputs/stories/`` AND at
         least one cookiecutter-style project as an immediate subdirectory.
      4. Ancestor with ``outputs/stories/`` but no project yet → returns a
         workspace record with ``needs_bootstrap=True`` (lets EPIC-01 run).

    Raises ``DiscoveryError`` only when none of the above resolve.
    """
    if workspace_root_override is not None:
        ws_root = workspace_root_override.resolve()
        return _build_workspace(ws_root, project_name_override)

    start = start.resolve()

    # Tier 2: explicit marker file.
    for candidate in (start, *start.parents):
        marker = _read_workspace_marker(candidate)
        if not marker:
            continue
        stories_rel = marker.get("stories_dir", "outputs/stories")
        project_rel = marker.get("project_dir")
        stories_dir = (candidate / stories_rel).resolve()
        if not stories_dir.is_dir():
            raise DiscoveryError(
                f".workspace.yaml at {candidate} points at {stories_dir} which does not exist"
            )
        if project_rel:
            project_root = (candidate / project_rel).resolve()
            if (project_root / "pyproject.toml").is_file() and (project_root / "src").is_dir():
                # Resolve project_name from src/<name>/.
                pkgs = [
                    p
                    for p in sorted((project_root / "src").iterdir())
                    if p.is_dir() and not p.name.startswith(".")
                ]
                if pkgs:
                    matching = [p for p in pkgs if p.name == project_root.name]
                    pkg = matching[0] if matching else pkgs[0]
                    return Workspace(
                        workspace_root=candidate,
                        project_root=project_root,
                        project_name=pkg.name,
                        stories_dir=stories_dir,
                        learnings_queue=candidate / "memory" / ROLE / "learnings-queue.jsonl",
                    )
            # Project declared but not yet bootstrapped.
            return _build_unbootstrapped(candidate, stories_dir)
        # No project_dir declared — treat as unbootstrapped workspace.
        return _build_unbootstrapped(candidate, stories_dir)

    # Tier 3/4: walk up looking for outputs/stories/.
    first_stories_ancestor: Path | None = None
    for candidate in (start, *start.parents):
        stories_dir = candidate / "outputs" / "stories"
        if not stories_dir.is_dir():
            continue
        if first_stories_ancestor is None:
            first_stories_ancestor = candidate
        children = _find_project_children(candidate)
        if not children:
            continue
        return _pick_project(candidate, children, project_name_override)

    # Tier 4: workspace exists but project not bootstrapped yet.
    if first_stories_ancestor is not None:
        return _build_unbootstrapped(
            first_stories_ancestor, first_stories_ancestor / "outputs" / "stories"
        )

    raise DiscoveryError(
        f"no workspace found at or above {start}: need a directory with "
        f"`outputs/stories/`. Generate the backlog via scrum-master-plugin "
        f"or pass --workspace-root."
    )


def _build_workspace(ws_root: Path, project_name_override: str | None) -> Workspace:
    stories_dir = ws_root / "outputs" / "stories"
    if not stories_dir.is_dir():
        raise DiscoveryError(f"--workspace-root {ws_root}: {stories_dir} does not exist")
    children = _find_project_children(ws_root)
    if not children:
        raise DiscoveryError(
            f"--workspace-root {ws_root}: no cookiecutter-style project "
            f"(pyproject.toml + src/<name>/) found as an immediate subdirectory"
        )
    return _pick_project(ws_root, children, project_name_override)


def _pick_project(
    ws_root: Path,
    children: list[tuple[Path, str]],
    project_name_override: str | None,
) -> Workspace:
    if project_name_override:
        matches = [
            c
            for c in children
            if c[1] == project_name_override or c[0].name == project_name_override
        ]
        if not matches:
            names = ", ".join(f"{c[0].name} (pkg {c[1]})" for c in children)
            raise DiscoveryError(
                f"--project-name {project_name_override!r} did not match any "
                f"project under {ws_root}. Candidates: {names}"
            )
        project_root, project_name = matches[0]
    elif len(children) == 1:
        project_root, project_name = children[0]
    else:
        names = ", ".join(f"{c[0].name} (pkg {c[1]})" for c in children)
        raise DiscoveryError(
            f"multiple cookiecutter projects under {ws_root}: {names}. "
            f"Re-run with --project-name <name>."
        )

    return Workspace(
        workspace_root=ws_root,
        project_root=project_root,
        project_name=project_name,
        stories_dir=ws_root / "outputs" / "stories",
        learnings_queue=ws_root / "memory" / ROLE / "learnings-queue.jsonl",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=Path, default=Path.cwd())
    parser.add_argument("--workspace-root", type=Path, default=None)
    parser.add_argument("--project-name", default=None)
    args = parser.parse_args(argv)
    try:
        ws = discover_workspace(args.start, args.workspace_root, args.project_name)
    except DiscoveryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(ws.as_dict(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
