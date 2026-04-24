#!/usr/bin/env python3
"""Parse, classify, and gate Scrum story/epic markdown files.

Shared helper for the developer plugin's orchestration skills
(implement-stories, validate-stories, complete-stories) and its per-artifact
validators. The plugin is project-agnostic: the workspace is auto-discovered
by walking upward from the CWD until a directory is found that contains both
``inputs/stories/`` and a cookiecutter-style project (``pyproject.toml`` +
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
    r"\s*(?P<points>\d+)\s*\|\s*(?P<sprint>[^|]+?)\s*\|"
    r"\s*(?P<deps>[^|]+?)\s*\|\s*$"
)
PATH_TOKEN_RE = re.compile(r"`([A-Za-z0-9_./{}-]+\.(?:py|yml|yaml|md|xml|toml|json))`")
VALID_STORY_STATUSES = {"To Do", "In Progress", "Done"}
VALID_EPIC_STATUSES = {"To Do", "Updated - Pending Review", "Done"}

# Content-based classifier rules. Tally distinct ACs that match each kind;
# the kind with the most distinct-AC matches wins. Rule order is only a
# tiebreaker (earlier = more specific → wins on equal-count ties). Patterns
# match path fragments, filenames, and identifiers that appear in the
# cookiecutter-chapter template.
#
# Rule shapes:
#   * Path-file patterns (e.g. `airflow/dags/<name>.py`) — match a specific
#     file, NOT bare directory references. This stops a scaffold story that
#     creates the empty `airflow/dags/` directory from being misclassified
#     as a DAG story.
#   * Identifier patterns (e.g. `StructType`, `ingestion_runner`) — match
#     domain concepts that uniquely belong to one kind.
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
          inputs/stories/v*/...
          {project_root}/                   <- cookiecutter-generated
            pyproject.toml
            src/{project_name}/...
          memory/developer/learnings-queue.jsonl   (may not exist yet)
    """

    workspace_root: Path
    project_root: Path
    project_name: str
    stories_dir: Path
    learnings_queue: Path
    backlog_glob: str = "BACKLOG-*.md"

    def as_dict(self) -> dict:
        return {
            "workspace_root": str(self.workspace_root),
            "project_root": str(self.project_root),
            "project_name": self.project_name,
            "stories_dir": str(self.stories_dir),
            "learnings_queue": str(self.learnings_queue),
            "backlog_glob": self.backlog_glob,
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


def discover_workspace(
    start: Path,
    workspace_root_override: Path | None = None,
    project_name_override: str | None = None,
) -> Workspace:
    """Walk upward from ``start`` to find the workspace anchor.

    Raises ``DiscoveryError`` with a clear remediation hint if no ancestor
    contains both ``inputs/stories/`` and a cookiecutter-style project. When
    multiple projects qualify (e.g. two cookiecutter projects side-by-side),
    ``project_name_override`` disambiguates.
    """
    if workspace_root_override is not None:
        ws_root = workspace_root_override.resolve()
        return _build_workspace(ws_root, project_name_override)

    start = start.resolve()
    for candidate in (start, *start.parents):
        stories_dir = candidate / "inputs" / "stories"
        if not stories_dir.is_dir():
            continue
        children = _find_project_children(candidate)
        if not children:
            continue
        return _pick_project(candidate, children, project_name_override)

    # Fallback: CWD itself may BE the cookiecutter project root (nested CWD,
    # no inputs/stories/ in the tree). In that case the caller should invoke
    # from the workspace root. Surface a clear error either way.
    raise DiscoveryError(
        f"no workspace found at or above {start}: need a directory with both "
        f"`inputs/stories/` and a cookiecutter-style project "
        f"(pyproject.toml + src/<name>/). Generate one from "
        f"chapter-4/inputs/lld/v1/templates/cookiecutter-chapter/ or pass "
        f"--workspace-root."
    )


def _build_workspace(ws_root: Path, project_name_override: str | None) -> Workspace:
    stories_dir = ws_root / "inputs" / "stories"
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
        stories_dir=ws_root / "inputs" / "stories",
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
    """Return the downstream skill kind for a story based on its AC content.

    Count distinct ACs that match each kind; the kind with the most matches
    wins. Rule order in ``CLASSIFIER_RULES`` is the tiebreaker (earlier rule =
    more specific = wins at a tie). If no AC matches any rule, fall back to
    scanning the whole story body (Description, Technical Notes) before
    returning ``unknown``.

    ``unknown`` means the caller must ask the user which kind applies.
    """
    story_path = resolve_story_path(ws, story_id)
    story = parse_story(story_path)

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
        ],
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
