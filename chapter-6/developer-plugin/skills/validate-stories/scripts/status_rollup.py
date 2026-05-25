#!/usr/bin/env python3
"""Parse, classify, and gate Scrum story/epic markdown files.

Shared helper for the developer plugin's orchestration skills
(implement-stories, validate-stories, complete-stories) and its per-artifact
validators. The plugin is project-agnostic: the workspace is auto-discovered
by walking upward from the CWD until a directory is found that contains both
``outputs/stories/`` and a cookiecutter-style project (``pyproject.toml`` +
``src/<project_name>/``).

Modes:

  - parse-story / parse-epic / parse-backlog: structured JSON of a single file
  - rollup:   aggregate child-story statuses under an epic
  - gate:     deterministic pass/fail for marking a story or epic Done
  - find:     resolve a story/epic ID to its file path
  - discover: print the resolved workspace paths + project_name
  - classify: return the downstream skill kind (scaffold|dag|ingestion|
              pipeline) that a story should dispatch to, based on its AC
              content alone (no config lookup)

All modes print JSON to stdout. ``gate`` exits 1 when blocked; every other
mode exits 0 on success, 2 on CLI/file/discovery error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

STORY_ID_RE = re.compile(r"STORY-\d{2}-\d{3}")
EPIC_ID_RE = re.compile(r"EPIC-\d{2}")
META_ROW_RE = re.compile(r"^\|\s*\*\*(?P<key>[^*]+)\*\*\s*\|\s*(?P<value>.+?)\s*\|\s*$")
AC_LINE_RE = re.compile(r"^\s*-\s*\[(?P<mark>[ xX])\]\s*(?P<text>.+?)\s*$")
STORY_ROW_RE = re.compile(
    r"^\|\s*(?P<id>STORY-\d{2}-\d{3})\s*\|\s*(?P<title>[^|]+?)\s*\|"
    r"(?:\s*(?P<type>[^|]+?)\s*\|)?"
    r"\s*(?P<points>\d+)\s*\|\s*(?P<sprint>[^|]+?)\s*\|"
    r"\s*(?P<deps>[^|]+?)\s*\|\s*$"
)
PATH_TOKEN_RE = re.compile(r"`([A-Za-z0-9_./*{}-]+\.(?:py|yml|yaml|md|xml|toml|json))`")
VALID_STORY_STATUSES = {"To Do", "In Progress", "Done"}
VALID_EPIC_STATUSES = {"To Do", "Updated - Pending Review", "Done"}

# Slug-based classifier rules. The scrum-master-plugin emits story files at
# `EPIC-{NN}-{epic-slug}/STORY-{NN}-{NNN}-{story-slug}.md`. Both slugs are
# hand-authored and far more reliable than pattern-matching free-form AC
# text, so they're the primary routing signal. Content-based AC rules stay
# as a last-resort fallback for stories whose slugs don't match any kind.
#
# Order within each list is priority (first match wins). The STORY slug
# rules run before the EPIC slug rules because a story-level signal
# (e.g. a foundation epic's DAG-skeleton story) must override the epic-level
# default.
STORY_SLUG_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "dag",
        re.compile(
            r"\bdag[-_](?:skeleton|factory|builder|template)\b|" r"\b(?:airflow[-_])?dag[-_]file\b",
            re.IGNORECASE,
        ),
    ),
    (
        "silver",
        re.compile(
            r"\b(?:silver[-_](?:transform|dimension|fact|scd2|merge)|"
            r"transform[-_](?:patients|encounters|conditions|medications|"
            r"observations|allergies|immunizations|procedures|careplans|"
            r"claims|organizations|providers|payers)|"
            r"scd2[-_]apply|scd2[-_]helper|silver[-_]dq|reconciliation[-_]silver)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "gold",
        re.compile(
            r"\b(?:gold[-_](?:build|builder|summary|history)|"
            r"build[-_](?:patient[-_]summary|patient[-_]clinical[-_]history|"
            r"patient[-_]billing[-_]summary)|"
            r"patient[-_]360[-_]gold|reconciliation[-_]gold)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "ingestion",
        re.compile(
            r"\b(?:ingestion[-_]runner|ingestion[-_]factory|sparksubmit|"
            r"spark[-_]submit|per[-_]table[-_]config|reconciliation[-_]bronze|"
            r"bronze[-_]dlq|perf[-_]partition|partition[-_]shuffle|"
            r"integration[-_]test[-_]bronze|bronze[-_]ingestion|"
            r"se[-_]runner)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "pipeline",
        re.compile(
            r"\b(?:github[-_]actions|gitlab[-_]ci|cicd|ci[-_]cd|"
            r"release[-_]deploy|deploy[-_]pipeline|workflow[-_]ci)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "scaffold",
        re.compile(
            r"\b(?:scaffold|cookiecutter|config[-_]loader|pipeline[-_]config|"
            r"logging|metrics|delta[-_]helpers|scd2|derived[-_]fields|"
            r"code[-_]systems|docker[-_]compose|reconciliation|"
            r"helper|test[-_]infrastructure|contracts[-_]schemas)\b",
            re.IGNORECASE,
        ),
    ),
]

EPIC_SLUG_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "scaffold",
        re.compile(r"\b(?:foundation|scaffold|bootstrap|setup|utilities)\b", re.IGNORECASE),
    ),
    (
        "ingestion",
        re.compile(r"\b(?:bronze|ingestion)\b", re.IGNORECASE),
    ),
    (
        "silver",
        re.compile(r"\bsilver\b", re.IGNORECASE),
    ),
    (
        "gold",
        re.compile(r"\b(?:gold|consumer)\b", re.IGNORECASE),
    ),
    (
        "pipeline",
        re.compile(r"\b(?:release|deploy|cicd|ci[-_]cd)\b", re.IGNORECASE),
    ),
]

# Content-based classifier rules (fallback). Tally distinct ACs that match
# each kind; the kind with the most distinct-AC matches wins. Rule order is
# the tiebreaker (earlier = more specific → wins on equal-count ties).
CLASSIFIER_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "pipeline",
        re.compile(
            r"\.github/workflows/|_infra/c[id]/[^/\s`]+\.(?:ya?ml|sh|toml)|" r"\.gitlab-ci",
            re.IGNORECASE,
        ),
    ),
    (
        "dag",
        re.compile(
            # Must reference a DAG-defining construct or a specific .py file
            # under airflow/dags/. A bare mention of `dag_id` (e.g. in a log
            # schema) is intentionally excluded — it appears in non-DAG stories.
            r"airflow/dags/[^/\s`]+\.py|_dag\.py\b|" r"TaskGroup|@dag\b|default_args\s*=",
            re.IGNORECASE,
        ),
    ),
    (
        "silver",
        re.compile(
            # Silver layer: transform_<table>.py modules, silver/ contracts,
            # silver/<domain>/ output paths, the apply_scd2 helper.
            r"/silver/[^/\s`]+\.py|src/patient_360/silver/|"
            r"warehouse/[^/\s`]+/silver/|"
            r"transform_(?:patients|encounters|conditions|medications|"
            r"observations|allergies|immunizations|procedures|careplans|"
            r"claims|organizations|providers|payers)|"
            r"clinical_(?:patients|encounters|conditions|medications|"
            r"observations|allergies|immunizations|procedures|careplans)|"
            r"reference_(?:organizations|providers|payers)|billing_claims|"
            r"apply_scd2|scd2\.py",
            re.IGNORECASE,
        ),
    ),
    (
        "gold",
        re.compile(
            # Gold layer: build_<table>.py modules, gold/ contracts,
            # the three Phase 1 Gold tables.
            r"/gold/[^/\s`]+\.py|src/patient_360/gold/|"
            r"warehouse/[^/\s`]+/gold/|"
            r"build_(?:patient_summary|patient_clinical_history|"
            r"patient_billing_summary)|"
            r"patient_summary|patient_clinical_history|patient_billing_summary",
            re.IGNORECASE,
        ),
    ),
    (
        "ingestion",
        re.compile(
            # Bronze ingestion: per-table YAML configs, bronze source files, or
            # the canonical module/identifier names that create-ingestion emits.
            r"airflow/configs/[^/\s`]+\.ya?ml|/bronze/[^/\s`]+\.py|"
            r"empty_input_behavior|spark[_-]expectations|"
            r"ingestion_runner|ingestion_factory|spark_submit_wrapper|"
            r"se_runner",
            re.IGNORECASE,
        ),
    ),
    (
        "scaffold",
        re.compile(
            # Foundation: project layout, packaging, config/logging bootstrap,
            # schema contracts, DDL migrations, docker setup. `tests/` alone is
            # deliberately NOT here — test stories belong to the kind they test.
            r"pyproject\.toml|\bMakefile\b|/utils/|schemas\.py|StructType|"
            r"SCHEMAS\[|src/[^/]+/config/|config-template|config_loader|"
            r"logging_config|docker-compose|ddl/liquibase|"
            r"_infra/docker/|dev-setup|uv sync|contracts/|dq_rules/",
            re.IGNORECASE,
        ),
    ),
]


class DiscoveryError(Exception):
    """Raised when the workspace cannot be auto-discovered."""


@dataclass
class Blocker:
    code: str
    message: str
    file: str | None = None
    line: int | None = None

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class GateResult:
    blocked: bool = False
    blockers: list[Blocker] = field(default_factory=list)

    def block(
        self,
        code: str,
        message: str,
        file: str | None = None,
        line: int | None = None,
    ) -> None:
        self.blocked = True
        self.blockers.append(Blocker(code=code, message=message, file=file, line=line))

    def as_dict(self) -> dict:
        return {
            "blocked": self.blocked,
            "blockers": [b.as_dict() for b in self.blockers],
        }


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
        learnings_queue=ws_root / "memory" / "developer" / "learnings-queue.jsonl",
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
                        learnings_queue=candidate
                        / "memory"
                        / "developer"
                        / "learnings-queue.jsonl",
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
        learnings_queue=ws_root / "memory" / "developer" / "learnings-queue.jsonl",
    )


def find_latest_stories_dir(ws: Workspace) -> Path:
    candidates = sorted(ws.stories_dir.glob("v*"), key=lambda p: p.name)
    if not candidates:
        raise FileNotFoundError(f"no v*/ subdirectories under {ws.stories_dir}")
    return candidates[-1]


def resolve_story_path(ws: Workspace, story_id: str) -> Path:
    sid = story_id.upper()
    if not STORY_ID_RE.fullmatch(sid):
        raise ValueError(f"invalid story id: {story_id!r}")
    latest = find_latest_stories_dir(ws)
    epic_num = sid.split("-")[1]
    for pattern in (f"EPIC-{epic_num}-*/{sid}*.md", f"{sid}*.md"):
        matches = sorted(latest.glob(pattern))
        if matches:
            return matches[0]
    raise FileNotFoundError(f"story file for {sid} not found under {latest}")


def resolve_epic_path(ws: Workspace, epic_id: str) -> Path:
    eid = epic_id.upper()
    if not EPIC_ID_RE.fullmatch(eid):
        raise ValueError(f"invalid epic id: {epic_id!r}")
    latest = find_latest_stories_dir(ws)
    matches = sorted(latest.glob(f"{eid}-*/{eid}.md"))
    if matches:
        return matches[0]
    raise FileNotFoundError(f"epic file for {eid} not found under {latest}")


def resolve_backlog_path(ws: Workspace) -> Path:
    latest = find_latest_stories_dir(ws)
    candidates = sorted(
        p
        for p in latest.glob(ws.backlog_glob)
        if not p.name.endswith(".bak") and ".bak" not in p.suffixes
    )
    if not candidates:
        raise FileNotFoundError(f"no {ws.backlog_glob} under {latest}")
    return candidates[-1]


def parse_metadata_table(text: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for line in text.splitlines():
        m = META_ROW_RE.match(line)
        if m:
            meta[m.group("key").strip()] = m.group("value").strip()
        elif meta:
            break
    return meta


def parse_ac_section(text: str, heading_re: re.Pattern[str]) -> list[dict]:
    lines = text.splitlines()
    in_section = False
    items: list[dict] = []
    idx = 0
    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("## "):
            in_section = bool(heading_re.match(stripped[3:].strip()))
            continue
        if not in_section:
            continue
        m = AC_LINE_RE.match(line)
        if m:
            idx += 1
            items.append(
                {
                    "index": idx,
                    "checked": m.group("mark").lower() == "x",
                    "text": m.group("text").strip(),
                    "line": lineno,
                }
            )
    return items


def extract_deliverable_paths(ac_text: str) -> list[str]:
    return [m.group(1) for m in PATH_TOKEN_RE.finditer(ac_text)]


def parse_story(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    meta = parse_metadata_table(text)
    sid_match = STORY_ID_RE.search(path.name) or STORY_ID_RE.search(text)
    story_id = sid_match.group(0) if sid_match else path.stem

    epic_raw = meta.get("Epic", "")
    epic_match = EPIC_ID_RE.search(epic_raw)
    epic_id = epic_match.group(0) if epic_match else None

    deps_raw = meta.get("Dependencies", "").strip()
    if deps_raw.lower() in {"none", "n/a", ""}:
        depends_on: list[str] = []
    else:
        depends_on = sorted({m.group(0) for m in STORY_ID_RE.finditer(deps_raw)})

    ac_lines = parse_ac_section(text, re.compile(r"^Acceptance Criteria$"))

    return {
        "story_id": story_id,
        "file": str(path),
        "title": _extract_h1(text),
        "status": meta.get("Status", "").strip(),
        "epic_id": epic_id,
        "sprint": meta.get("Sprint", "").strip(),
        "story_points": _to_int(meta.get("Story Points")),
        "priority": meta.get("Priority", "").strip(),
        "story_type": meta.get("Story Type", "").strip(),
        "depends_on": depends_on,
        "ac_lines": ac_lines,
        "ac_total": len(ac_lines),
        "ac_checked": sum(1 for a in ac_lines if a["checked"]),
    }


def parse_epic(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    meta = parse_metadata_table(text)
    eid_match = EPIC_ID_RE.search(path.name) or EPIC_ID_RE.search(text)
    epic_id = eid_match.group(0) if eid_match else path.stem

    ac_lines = parse_ac_section(text, re.compile(r"^Acceptance Criteria \(Epic-Level\)$"))
    child_stories = _parse_stories_table(text)

    return {
        "epic_id": epic_id,
        "file": str(path),
        "title": _extract_h1(text),
        "status": meta.get("Status", "").strip(),
        "sprints": meta.get("Sprints", "").strip(),
        "total_points": _to_int(meta.get("Total Points")),
        "child_stories": child_stories,
        "epic_ac_lines": ac_lines,
        "epic_ac_total": len(ac_lines),
        "epic_ac_checked": sum(1 for a in ac_lines if a["checked"]),
    }


def parse_backlog(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    meta = parse_metadata_table(text)
    return {
        "file": str(path),
        "version": meta.get("Version", "").strip(),
        "created": meta.get("Created", "").strip(),
        "last_modified": meta.get("Last Modified", "").strip(),
        "status": meta.get("Status", "").strip(),
        "lld_reference": meta.get("LLD Reference", "").strip(),
    }


def rollup(ws: Workspace, epic_id: str) -> dict:
    epic = parse_epic(resolve_epic_path(ws, epic_id))
    counts = {"To Do": 0, "In Progress": 0, "Done": 0}
    per_child: list[dict] = []
    for child in epic["child_stories"]:
        try:
            story = parse_story(resolve_story_path(ws, child["id"]))
            status = story["status"] or "To Do"
            counts[status] = counts.get(status, 0) + 1
            per_child.append(
                {
                    "story_id": child["id"],
                    "status": status,
                    "ac_checked": story["ac_checked"],
                    "ac_total": story["ac_total"],
                }
            )
        except FileNotFoundError:
            counts["To Do"] = counts.get("To Do", 0) + 1
            per_child.append(
                {
                    "story_id": child["id"],
                    "status": "To Do",
                    "ac_checked": 0,
                    "ac_total": 0,
                    "file_missing": True,
                }
            )

    total = sum(counts.values())
    all_done = total > 0 and counts.get("Done", 0) == total
    if all_done and epic["epic_ac_total"] > 0 and epic["epic_ac_checked"] == epic["epic_ac_total"]:
        implied = "Done"
    elif counts.get("Done", 0) > 0 or counts.get("In Progress", 0) > 0:
        implied = "Updated - Pending Review"
    else:
        implied = "To Do"

    return {
        "epic_id": epic["epic_id"],
        "epic_status_recorded": epic["status"],
        "epic_status_implied": implied,
        "total_stories": total,
        "done": counts.get("Done", 0),
        "in_progress": counts.get("In Progress", 0),
        "to_do": counts.get("To Do", 0),
        "all_done": all_done,
        "epic_ac_total": epic["epic_ac_total"],
        "epic_ac_checked": epic["epic_ac_checked"],
        "stories": per_child,
    }


def classify_story(ws: Workspace, story_id: str) -> dict:
    """Return the downstream skill kind for a story.

    Resolution order:
      0. **Story Type metadata cell** — when the story declares its type
         as ``integration-test`` or ``deploy-validation``, route to the
         matching skill kind directly. These story types have runtime-
         behavioural ACs (no path tokens) so the slug / content rules
         would otherwise mis-classify them.
      1. **Story filename slug** (e.g. ``STORY-02-001-ingestion-runner``) —
         the scrum-master-plugin's hand-authored slug is the single most
         reliable signal for kind.
      2. **Epic folder slug** (e.g. ``EPIC-01-foundation``) — disambiguates
         stories whose own slug is ambiguous ("reconciliation" could be
         either a foundation util or a bronze pipeline task).
      3. **AC content rules** — last-resort text match. Used only when the
         slugs say nothing.

    ``unknown`` means the caller must ask the user which kind applies.
    """
    story_path = resolve_story_path(ws, story_id)
    story = parse_story(story_path)

    # Signal 0: story-type metadata cell. These types have no reliable
    # path / slug / AC-text signal, so the metadata is authoritative.
    STORY_TYPE_DIRECT_KINDS = {
        "integration-test": "integration-test",
        "deploy-validation": "deploy-validation",
    }
    story_type = story.get("story_type", "").strip().lower()
    direct_kind = STORY_TYPE_DIRECT_KINDS.get(story_type)
    if direct_kind:
        return {
            "story_id": story["story_id"],
            "skill_kind": direct_kind,
            "confidence": "high",
            "reasons": [f"Story Type metadata = {story_type!r} → {direct_kind}"],
            "matched_rule_count": 1,
            "all_matches": {direct_kind: [0]},
        }

    # Signal 1: story filename slug.
    story_slug = story_path.stem  # e.g. STORY-02-001-ingestion-runner
    for kind, pattern in STORY_SLUG_RULES:
        m = pattern.search(story_slug)
        if m:
            return {
                "story_id": story["story_id"],
                "skill_kind": kind,
                "confidence": "high",
                "reasons": [f"story slug {story_slug!r} matched /{m.group(0)}/ → {kind}"],
                "matched_rule_count": 1,
                "all_matches": {kind: [0]},
            }

    # Signal 2: epic folder slug.
    epic_slug = story_path.parent.name  # e.g. EPIC-01-foundation
    for kind, pattern in EPIC_SLUG_RULES:
        m = pattern.search(epic_slug)
        if m:
            return {
                "story_id": story["story_id"],
                "skill_kind": kind,
                "confidence": "high",
                "reasons": [f"epic slug {epic_slug!r} matched /{m.group(0)}/ → {kind}"],
                "matched_rule_count": 1,
                "all_matches": {kind: [0]},
            }

    # Signal 3: fall back to AC content rules.
    # {kind: [reason_string, ...]} — one reason per AC that matched.
    per_kind_reasons: dict[str, list[str]] = {}
    matched_ac_indices: dict[str, set[int]] = {}

    for ac in story["ac_lines"]:
        for kind, pattern in CLASSIFIER_RULES:
            m = pattern.search(ac["text"])
            if not m:
                continue
            if ac["index"] in matched_ac_indices.setdefault(kind, set()):
                continue
            matched_ac_indices[kind].add(ac["index"])
            per_kind_reasons.setdefault(kind, []).append(f"AC {ac['index']} matched /{m.group(0)}/")

    # Full-body fallback: only for kinds that didn't already match an AC.
    if not per_kind_reasons:
        full_text = story_path.read_text(encoding="utf-8")
        for kind, pattern in CLASSIFIER_RULES:
            m = pattern.search(full_text)
            if not m:
                continue
            per_kind_reasons.setdefault(kind, []).append(f"story body matched /{m.group(0)}/")
            matched_ac_indices.setdefault(kind, set()).add(0)

    if not per_kind_reasons:
        return {
            "story_id": story["story_id"],
            "skill_kind": "unknown",
            "confidence": "low",
            "reasons": [],
            "matched_rule_count": 0,
            "all_matches": {},
        }

    rule_priority = {kind: idx for idx, (kind, _) in enumerate(CLASSIFIER_RULES)}
    chosen = max(
        per_kind_reasons.keys(),
        # Higher AC-match count wins; ties go to the earlier (more specific) rule.
        key=lambda k: (len(matched_ac_indices[k]), -rule_priority[k]),
    )

    n_matches = len(matched_ac_indices[chosen])
    if n_matches >= 2:
        confidence = "high"
    elif len(per_kind_reasons) == 1:
        confidence = "medium"
    else:
        # Multiple kinds matched once each — ambiguous; flag for review.
        confidence = "low"

    return {
        "story_id": story["story_id"],
        "skill_kind": chosen,
        "confidence": confidence,
        "reasons": per_kind_reasons[chosen],
        "matched_rule_count": n_matches,
        "all_matches": {k: sorted(v) for k, v in matched_ac_indices.items()},
    }


def load_deliverable_owners(ws: Workspace) -> dict:
    """Load the DELIVERABLE-OWNERS.yaml routing registry.

    Resolution: latest ``inputs/code/v*/DELIVERABLE-OWNERS.yaml`` under
    the workspace root. The registry lists ``owners`` (glob → skill),
    ``dispatch_order``, and an optional ``fallback_skill``. Globs are
    sorted at load time by length descending so that the most-specific
    match wins when the orchestrator scans them.

    Returns ``{"owners": [], "dispatch_order": [], "fallback_skill": None}``
    when the file is absent, so callers can fall back gracefully to the
    classifier-based routing.
    """
    patterns_dirs = sorted(
        (ws.workspace_root / "inputs" / "code").glob("v*"),
        key=lambda p: p.name,
    )
    if not patterns_dirs:
        return {"owners": [], "dispatch_order": [], "fallback_skill": None}
    owners_file = patterns_dirs[-1] / "DELIVERABLE-OWNERS.yaml"
    if not owners_file.is_file():
        return {"owners": [], "dispatch_order": [], "fallback_skill": None}
    try:
        import yaml  # type: ignore
    except ImportError:
        return {"owners": [], "dispatch_order": [], "fallback_skill": None}
    data = yaml.safe_load(owners_file.read_text(encoding="utf-8")) or {}
    owners = [o for o in data.get("owners", []) if o.get("glob") and o.get("skill")]
    # Longest-glob-wins: sort descending by length, preserving file order on ties.
    owners.sort(key=lambda o: len(o["glob"]), reverse=True)
    return {
        "owners": owners,
        "dispatch_order": list(data.get("dispatch_order") or []),
        "fallback_skill": data.get("fallback_skill"),
    }


def _glob_to_regex(glob: str) -> re.Pattern[str]:
    """Translate a shell-style glob (with ``**`` support) to a regex.

    - ``**/`` matches zero or more path segments (e.g. ``a/**/b`` matches
      ``a/b``, ``a/x/b``, ``a/x/y/b``).
    - ``**`` at tail matches any suffix including slashes.
    - ``*`` matches any run of non-slash characters.
    - ``?`` matches any single non-slash character.
    - All other regex metacharacters are escaped literally.
    """
    out: list[str] = []
    i = 0
    while i < len(glob):
        c = glob[i]
        if c == "*" and i + 1 < len(glob) and glob[i + 1] == "*":
            if i + 2 < len(glob) and glob[i + 2] == "/":
                out.append(r"(?:.*/)?")
                i += 3
            else:
                out.append(r".*")
                i += 2
        elif c == "*":
            out.append(r"[^/]*")
            i += 1
        elif c == "?":
            out.append(r"[^/]")
            i += 1
        elif c in r".+^$()|[]{}\\":
            out.append(re.escape(c))
            i += 1
        else:
            out.append(c)
            i += 1
    return re.compile(r"\A" + "".join(out) + r"\Z")


def _candidate_path_variants(path: str, project_name: str | None) -> list[str]:
    """Return path variants to try against owner globs.

    Stories sometimes write deliverables workspace-relative
    (``<project>/pyproject.toml``) and sometimes project-relative
    (``pyproject.toml``). Try both so the registry only needs the
    project-relative form.
    """
    variants = [path]
    if project_name and path.startswith(f"{project_name}/"):
        variants.append(path[len(project_name) + 1 :])
    return variants


def _skill_for_path(
    path: str,
    owners: list[dict],
    project_name: str | None = None,
    _regex_cache: dict[str, re.Pattern[str]] | None = None,
) -> str | None:
    """Return the owning skill for a path, or None if no glob matches."""
    cache = _regex_cache if _regex_cache is not None else {}
    variants = _candidate_path_variants(path, project_name)
    for owner in owners:
        g = owner["glob"]
        pattern = cache.get(g)
        if pattern is None:
            pattern = _glob_to_regex(g)
            cache[g] = pattern
        for v in variants:
            if pattern.match(v):
                return owner["skill"]
    return None


def _strip_placeholder_segments(path: str) -> str:
    """Strip ``{placeholder}`` segments so glob matching works on template paths.

    ``warehouse/{env}/dead-letter/{table}/{ds}/`` has no literal slashes for
    fnmatch to align against. We collapse placeholder segments into ``*`` so
    the glob can still match on the stable fragments.
    """
    return re.sub(r"\{[^}/]+\}", "*", path)


def _expand_glob_token(token: str, ws: Workspace) -> list[str]:
    """Expand a token containing literal ``*`` against the workspace.

    Tries ``workspace_root`` first (handles workspace-relative tokens like
    ``<project>/contracts/<prefix>_*.yml``). Falls back to ``project_root``
    (handles project-relative tokens like ``contracts/<prefix>_*.yml``) and
    re-prefixes matches with ``project_name`` so callers always see a
    workspace-relative path.

    Returns ``[]`` if the glob matches nothing on disk -- caller decides
    whether to keep the unexpanded token (so the verifier can mark it
    INDETERMINATE) or drop it.
    """
    matches: list[str] = []
    try:
        for hit in sorted(ws.workspace_root.glob(token)):
            if hit.is_file():
                matches.append(str(hit.relative_to(ws.workspace_root)))
    except (OSError, ValueError):
        pass
    if matches:
        return matches
    if ws.project_root and ws.project_name:
        try:
            for hit in sorted(ws.project_root.glob(token)):
                if hit.is_file():
                    rel = hit.relative_to(ws.project_root)
                    matches.append(f"{ws.project_name}/{rel}")
        except (OSError, ValueError):
            pass
    return matches


def extract_deliverables(ws: Workspace, story_id: str) -> dict:
    """Extract deliverable paths from a story's AC and group by owning skill.

    Output shape::

        {
          "story_id": "STORY-NN-NNN",
          "paths": ["...", ...],             # preserves discovery order
          "by_skill": {"ingestion": [...], "dag": [...]},
          "dispatch_order": ["ingestion", "dag"],  # subset of registry order
          "unmatched": [...],                # paths not hit by any glob
          "fallback_kind": "ingestion",      # classifier's kind (for fallback)
        }

    When the story's ACs have no backtick-quoted paths at all (pure-
    behaviour story), ``paths`` is empty and the caller falls back to
    single classify+dispatch.
    """
    story = parse_story(resolve_story_path(ws, story_id))
    registry = load_deliverable_owners(ws)
    owners = registry["owners"]

    seen: set[str] = set()
    paths: list[str] = []
    for ac in story["ac_lines"]:
        for token in extract_deliverable_paths(ac["text"]):
            if "*" in token:
                expanded = _expand_glob_token(token, ws)
                if expanded:
                    for p in expanded:
                        if p in seen:
                            continue
                        seen.add(p)
                        paths.append(p)
                    continue
            normalised = _strip_placeholder_segments(token)
            if normalised in seen:
                continue
            seen.add(normalised)
            paths.append(normalised)

    by_skill: dict[str, list[str]] = {}
    unmatched: list[str] = []
    regex_cache: dict[str, re.Pattern[str]] = {}
    for path in paths:
        skill = _skill_for_path(path, owners, ws.project_name, regex_cache)
        if skill:
            by_skill.setdefault(skill, []).append(path)
        else:
            unmatched.append(path)

    # Classifier fallback for unmatched paths and for empty extraction.
    fallback_kind: str | None = None
    if unmatched or not by_skill:
        classified = classify_story(ws, story_id)
        fk = classified.get("skill_kind")
        if fk and fk != "unknown":
            fallback_kind = fk
    explicit_fallback = registry.get("fallback_skill")
    fb = explicit_fallback or fallback_kind
    if fb and unmatched:
        by_skill.setdefault(fb, []).extend(unmatched)

    configured_order = registry["dispatch_order"] or [
        "scaffold",
        "ingestion",
        "dag",
        "pipeline",
    ]
    ordered_skills: list[str] = [s for s in configured_order if s in by_skill]
    # Any skills present in by_skill but missing from dispatch_order go last,
    # in the order they were first seen. This preserves determinism without
    # hiding an accidentally-misnamed skill.
    for s in by_skill:
        if s not in ordered_skills:
            ordered_skills.append(s)

    return {
        "story_id": story["story_id"],
        "paths": paths,
        "by_skill": {s: by_skill[s] for s in ordered_skills},
        "dispatch_order": ordered_skills,
        "unmatched": unmatched,
        "fallback_kind": fallback_kind,
    }


def _ac_path_tokens(ac_text: str) -> list[str]:
    return [_strip_placeholder_segments(t) for t in extract_deliverable_paths(ac_text)]


def build_plan(ws: Workspace, story_id: str) -> dict:
    """Construct a story execution plan (the persistent ledger).

    Plan lifecycle:
      - ``planned``     — just built, no task started
      - ``in_progress`` — at least one task started
      - ``implemented`` — every task done (awaits validation)
      - ``validated``   — every AC passed validation
      - ``done``        — complete-stories has marked the story Done
      - ``failed``      — a task failed or validation found a failing AC

    The plan is regenerated from scratch every time this function runs,
    so re-running ``build_plan`` after a scrum-master re-run picks up AC
    changes. ``save_plan`` bumps ``plan_version`` and preserves prior task
    outcomes when the task set is unchanged; callers decide when to
    persist.
    """
    story = parse_story(resolve_story_path(ws, story_id))
    deliverables = extract_deliverables(ws, story_id)
    classified = classify_story(ws, story_id)

    # Build tasks: one per (skill, paths) group in dispatch order.
    tasks: list[dict] = []
    if deliverables["by_skill"]:
        prev_ids: list[str] = []
        for idx, skill in enumerate(deliverables["dispatch_order"], start=1):
            paths = deliverables["by_skill"][skill]
            # Decide create vs update based on whether any path exists.
            project_root = ws.project_root or ws.workspace_root
            any_present = any((project_root / p).exists() for p in paths)
            mode = "update" if any_present else "create"
            tid = f"T{idx}"
            tasks.append(
                {
                    "id": tid,
                    "skill": f"{mode}-{skill}",
                    "kind": skill,
                    "mode": mode,
                    "paths": paths,
                    "depends_on": list(prev_ids),
                    "status": "todo",
                    "started_at": None,
                    "finished_at": None,
                    "artifacts": [],
                    "files_created": 0,
                    "files_updated": 0,
                    "critical_findings": [],
                    "validator": f"validate-{skill}",
                    "validator_status": "pending",
                    "notes": "",
                }
            )
            prev_ids.append(tid)
    else:
        # Behavioural story — single task dispatched to classifier's kind.
        fb = deliverables.get("fallback_kind") or classified.get("skill_kind")
        if fb and fb != "unknown":
            tasks.append(
                {
                    "id": "T1",
                    "skill": f"create-{fb}",
                    "kind": fb,
                    "mode": "create",
                    "paths": [],
                    "depends_on": [],
                    "status": "todo",
                    "started_at": None,
                    "finished_at": None,
                    "artifacts": [],
                    "files_created": 0,
                    "files_updated": 0,
                    "critical_findings": [],
                    "validator": f"validate-{fb}",
                    "validator_status": "pending",
                    "notes": "behavioural story — no path tokens; sub-skill handles AC scope",
                }
            )

    # Map ACs to the task(s) that cover their paths.
    acs: list[dict] = []
    for ac in story["ac_lines"]:
        tokens = _ac_path_tokens(ac["text"])
        task_ids: list[str] = []
        for task in tasks:
            if not tokens:
                task_ids.append(task["id"])
                continue
            if any(tok in task["paths"] for tok in tokens):
                task_ids.append(task["id"])
        # If tokens exist but no task covers them, attach to ALL tasks as a
        # soft link so validators still attempt coverage.
        if tokens and not task_ids:
            task_ids = [t["id"] for t in tasks]
        acs.append(
            {
                "index": ac["index"],
                "text": ac["text"],
                "line": ac["line"],
                "task_ids": task_ids,
                "validation": {"status": "pending", "evidence": ""},
            }
        )

    return {
        "story_id": story["story_id"],
        "story_file": story["file"],
        "epic_id": story["epic_id"],
        "plan_version": 1,
        "status": "planned",
        "generated_at": None,  # caller fills on save
        "summary": (
            f"{len(tasks)} task(s) across "
            f"{sorted({t['kind'] for t in tasks})} — "
            f"{len(acs)} AC(s)."
        ),
        "classifier": {
            "kind": classified.get("skill_kind"),
            "confidence": classified.get("confidence"),
        },
        "deliverables": deliverables,
        "tasks": tasks,
        "acceptance_criteria": acs,
        "completion": {"status": "pending", "completed_at": None, "blocking_reasons": []},
    }


def plan_path(ws: Workspace, story_id: str) -> Path:
    """Return the on-disk path for a story's plan JSON."""
    latest = find_latest_stories_dir(ws)
    plans_dir = latest / "plans"
    return plans_dir / f"{story_id.upper()}.plan.json"


def load_plan(ws: Workspace, story_id: str) -> dict | None:
    """Load a story's plan from disk, or None if it does not exist."""
    path = plan_path(ws, story_id)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_plan(ws: Workspace, plan: dict) -> Path:
    """Persist a story's plan. Increments plan_version on re-save."""
    from datetime import datetime, timezone

    path = plan_path(ws, plan["story_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    prior = None
    if path.is_file():
        prior = json.loads(path.read_text(encoding="utf-8"))
    if prior and prior.get("plan_version"):
        plan["plan_version"] = int(prior["plan_version"]) + 1
    plan["generated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return path


def gate(ws: Workspace, target: str) -> GateResult:
    result = GateResult()
    target = target.strip().upper()

    if STORY_ID_RE.fullmatch(target):
        _gate_story(ws, target, result)
    elif EPIC_ID_RE.fullmatch(target):
        _gate_epic(ws, target, result)
    else:
        result.block(
            "invalid_target",
            f"Target {target!r} is not a STORY-NN-NNN or EPIC-NN identifier",
        )
    return result


def _gate_story(ws: Workspace, story_id: str, result: GateResult) -> None:
    try:
        story = parse_story(resolve_story_path(ws, story_id))
    except (FileNotFoundError, ValueError) as exc:
        result.block("story_file_missing", str(exc))
        return

    if story["status"] not in VALID_STORY_STATUSES:
        result.block(
            "invalid_status",
            (
                f"{story_id}: Status cell {story['status']!r} is not one of "
                f"{sorted(VALID_STORY_STATUSES)}"
            ),
            file=story["file"],
        )

    unchecked = [ac for ac in story["ac_lines"] if not ac["checked"]]
    for ac in unchecked:
        result.block(
            "ac_unchecked",
            f"{story_id} AC {ac['index']} is still unchecked: {ac['text']}",
            file=story["file"],
            line=ac["line"],
        )

    for dep_id in story["depends_on"]:
        try:
            dep = parse_story(resolve_story_path(ws, dep_id))
        except FileNotFoundError:
            result.block(
                "dependency_missing",
                f"{story_id} depends on {dep_id} but that story file was not found",
            )
            continue
        if dep["status"] != "Done":
            result.block(
                "dependency_not_done",
                (
                    f"{story_id} depends on {dep_id} "
                    f"(Status: {dep['status'] or 'To Do'}) — must be Done first"
                ),
                file=dep["file"],
            )

    for ac in story["ac_lines"]:
        for token in extract_deliverable_paths(ac["text"]):
            if "{" in token or "}" in token:
                continue
            if (ws.project_root / token).exists():
                continue
            if (ws.workspace_root / token).exists():
                continue
            result.block(
                "missing_deliverable",
                f"{story_id} AC {ac['index']} references `{token}` but it is absent on disk",
                file=story["file"],
                line=ac["line"],
            )


def _gate_epic(ws: Workspace, epic_id: str, result: GateResult) -> None:
    try:
        epic = parse_epic(resolve_epic_path(ws, epic_id))
    except (FileNotFoundError, ValueError) as exc:
        result.block("epic_file_missing", str(exc))
        return

    for child in epic["child_stories"]:
        child_result = GateResult()
        _gate_story(ws, child["id"], child_result)
        for blocker in child_result.blockers:
            result.block(
                f"child:{blocker.code}",
                f"[{child['id']}] {blocker.message}",
                file=blocker.file,
                line=blocker.line,
            )

    for ac in epic["epic_ac_lines"]:
        if not ac["checked"]:
            result.block(
                "epic_ac_unchecked",
                f"{epic_id} epic-level AC {ac['index']} unchecked: {ac['text']}",
                file=epic["file"],
                line=ac["line"],
            )


def _parse_stories_table(text: str) -> list[dict]:
    lines = text.splitlines()
    in_section = False
    rows: list[dict] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            in_section = stripped[3:].strip() == "Stories"
            continue
        if not in_section:
            continue
        m = STORY_ROW_RE.match(line)
        if not m:
            continue
        deps_raw = m.group("deps").strip()
        if deps_raw.lower() in {"none", "n/a", "-", ""}:
            deps: list[str] = []
        else:
            deps = sorted({d.group(0) for d in STORY_ID_RE.finditer(deps_raw)})
        rows.append(
            {
                "id": m.group("id"),
                "title": m.group("title").strip(),
                "points": int(m.group("points")),
                "sprint": m.group("sprint").strip(),
                "depends_on": deps,
            }
        )
    return rows


def _extract_h1(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    m = re.search(r"\d+", value)
    return int(m.group(0)) if m else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        required=True,
        choices=[
            "parse-story",
            "parse-epic",
            "parse-backlog",
            "rollup",
            "gate",
            "find",
            "discover",
            "classify",
            "extract-deliverables",
            "build-plan",
            "load-plan",
        ],
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="For --mode build-plan: persist the plan to disk",
    )
    parser.add_argument("--story", help="Story ID (STORY-NN-NNN)")
    parser.add_argument("--epic", help="Epic ID (EPIC-NN)")
    parser.add_argument("--backlog", help="Path to a specific BACKLOG-*.md (optional)")
    parser.add_argument("--target", help="Story ID or Epic ID for --mode gate")
    parser.add_argument(
        "--workspace-root",
        type=Path,
        help="Workspace root override (skips walk-up discovery)",
    )
    parser.add_argument(
        "--project-name",
        help="Disambiguate when the workspace has multiple cookiecutter projects",
    )
    args = parser.parse_args()

    try:
        ws = discover_workspace(
            Path.cwd(),
            workspace_root_override=args.workspace_root,
            project_name_override=args.project_name,
        )
    except DiscoveryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        if args.mode == "parse-story":
            if not args.story:
                parser.error("--story is required for --mode parse-story")
            payload = parse_story(resolve_story_path(ws, args.story))
        elif args.mode == "parse-epic":
            if not args.epic:
                parser.error("--epic is required for --mode parse-epic")
            payload = parse_epic(resolve_epic_path(ws, args.epic))
        elif args.mode == "parse-backlog":
            path = Path(args.backlog) if args.backlog else resolve_backlog_path(ws)
            payload = parse_backlog(path)
        elif args.mode == "rollup":
            if not args.epic:
                parser.error("--epic is required for --mode rollup")
            payload = rollup(ws, args.epic)
        elif args.mode == "find":
            if args.story:
                payload = {"path": str(resolve_story_path(ws, args.story))}
            elif args.epic:
                payload = {"path": str(resolve_epic_path(ws, args.epic))}
            else:
                parser.error("--story or --epic is required for --mode find")
        elif args.mode == "discover":
            payload = ws.as_dict()
        elif args.mode == "classify":
            if not args.story:
                parser.error("--story is required for --mode classify")
            payload = classify_story(ws, args.story)
        elif args.mode == "extract-deliverables":
            if not args.story:
                parser.error("--story is required for --mode extract-deliverables")
            payload = extract_deliverables(ws, args.story)
        elif args.mode == "build-plan":
            if not args.story:
                parser.error("--story is required for --mode build-plan")
            payload = build_plan(ws, args.story)
            if args.save:
                saved = save_plan(ws, payload)
                payload["_saved_to"] = str(saved)
        elif args.mode == "load-plan":
            if not args.story:
                parser.error("--story is required for --mode load-plan")
            loaded = load_plan(ws, args.story)
            if loaded is None:
                print(f"error: no plan found for {args.story}", file=sys.stderr)
                return 2
            payload = loaded
        elif args.mode == "gate":
            if not args.target:
                parser.error("--target is required for --mode gate")
            result = gate(ws, args.target)
            print(json.dumps(result.as_dict(), indent=2))
            return 1 if result.blocked else 0
        else:  # pragma: no cover — argparse enforces choices
            raise AssertionError(f"unhandled mode {args.mode}")
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
