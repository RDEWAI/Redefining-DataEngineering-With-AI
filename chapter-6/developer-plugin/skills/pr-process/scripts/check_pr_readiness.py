#!/usr/bin/env python3
"""PR readiness aggregator for the pr-process skill.

Runs seven gates in order and emits a single JSON report. The skill's
Phase 1 reads the report; the PR body template reads the same report to
populate the validator-summary table and the teardown-plan block.

Gates (matches SKILL.md Phase 1):
  1. git tree clean (no uncommitted changes)
  2. current branch != main and ahead of origin/main by >= 1
  3. story file exists and is Approved / Done
  4. make lint exits 0
  5. make test exits 0
  6. verify_acs.py reports no FAIL ACs
  7. /developer-plugin:validate-stories reports PASS

Exit codes:
  0 — PASS (all gates green; ok to open PR)
  1 — FAIL (one or more gates red; do not open PR)
  2 — WARN (no FAIL but at least one gate emitted a warning)

Emit modes:
  --json (default) → full JSON report to stdout
  --emit labels    → comma-separated label list for `gh pr create --label`
  --emit plan      → human-readable plan (for debugging)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class GateResult:
    name: str
    status: str  # PASS | WARN | FAIL
    detail: str = ""


@dataclass
class ACResult:
    id: str
    spec: str
    status: str  # PASS | FAIL | INDETERMINATE | WARN
    detail: str = ""


@dataclass
class ReadinessReport:
    story: str
    branch: str
    workspace_root: str
    project_root: str
    timestamp: str
    gates: list[GateResult] = field(default_factory=list)
    acs: list[ACResult] = field(default_factory=list)
    story_path: str = ""
    story_title: str = ""
    epic_id: str = ""
    epic_path: str = ""
    files_by_layer: dict[str, list[str]] = field(default_factory=dict)
    validators: list[dict] = field(default_factory=list)
    teardown_driver: str = "local-docker"
    teardown_plan: list[dict] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    result: str = "FAIL"  # PASS | WARN | FAIL


def _run(cmd: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=300, check=False
        )
        return proc.returncode, proc.stdout, proc.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return 127, "", str(exc)


def _git_tree_clean(project_root: str) -> GateResult:
    rc, out, _ = _run(["git", "status", "--porcelain"], cwd=project_root)
    if rc != 0:
        return GateResult("git_tree_clean", "FAIL", "git status failed")
    if out.strip():
        return GateResult(
            "git_tree_clean",
            "FAIL",
            f"uncommitted changes:\n{out.strip()}",
        )
    return GateResult("git_tree_clean", "PASS")


def _branch_state(project_root: str, branch: str) -> GateResult:
    if branch == "main":
        return GateResult("branch_state", "FAIL", "current branch is main")
    rc, out, _ = _run(["git", "rev-list", "--count", f"origin/main..{branch}"], cwd=project_root)
    if rc != 0:
        return GateResult(
            "branch_state",
            "WARN",
            "could not compare against origin/main — is the remote fetched?",
        )
    try:
        ahead = int(out.strip() or "0")
    except ValueError:
        ahead = 0
    if ahead < 1:
        return GateResult("branch_state", "FAIL", f"branch {branch} is not ahead of origin/main")
    return GateResult("branch_state", "PASS", f"ahead by {ahead}")


def _locate_story(workspace_root: str, story_id: str) -> tuple[GateResult, Path | None]:
    stories_dir = Path(workspace_root) / "outputs" / "stories"
    if not stories_dir.exists():
        # chapter-6 reads stories from chapter-5/outputs/stories or chapter-6/outputs
        candidates = [
            Path(workspace_root) / "outputs",
            Path(workspace_root).parent / "chapter-5" / "outputs" / "stories",
        ]
        stories_dir = next((c for c in candidates if c.exists()), candidates[0])
    matches = list(stories_dir.rglob(f"{story_id}-*.md"))
    if not matches:
        matches = list(stories_dir.rglob(f"{story_id}.md"))
    if not matches:
        return (
            GateResult(
                "story_exists",
                "FAIL",
                f"no {story_id}*.md under {stories_dir}",
            ),
            None,
        )
    story_path = sorted(matches)[-1]
    content = story_path.read_text(encoding="utf-8")
    status_match = re.search(r"^Status:\s*(\S+)", content, re.MULTILINE)
    status = (status_match.group(1) if status_match else "").strip()
    if status not in {"Approved", "Done"}:
        return (
            GateResult(
                "story_approved",
                "FAIL",
                f"{story_path.name}: Status={status or 'missing'}",
            ),
            story_path,
        )
    return GateResult("story_approved", "PASS", str(story_path)), story_path


def _make_target(project_root: str, target: str) -> GateResult:
    if not (Path(project_root) / "Makefile").exists():
        return GateResult(f"make_{target}", "WARN", "no Makefile — skipped")
    rc, out, err = _run(["make", target], cwd=project_root)
    if rc != 0:
        tail = (err or out).strip().splitlines()[-10:]
        return GateResult(f"make_{target}", "FAIL", "\n".join(tail))
    return GateResult(f"make_{target}", "PASS")


def _run_verify_acs(workspace_root: str, story_id: str) -> tuple[GateResult, list[ACResult]]:
    plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", ""))
    if not plugin_root.exists():
        # fall back to the conventional location
        plugin_root = Path(workspace_root) / "developer-plugin"
    script = plugin_root / "scripts" / "verify_acs.py"
    if not script.exists():
        return (
            GateResult("verify_acs", "WARN", f"verify_acs.py not found at {script}"),
            [],
        )
    rc, out, err = _run([sys.executable, str(script), story_id, "--json"])
    if rc not in (0, 1, 2):
        return GateResult("verify_acs", "WARN", err.strip() or "non-standard exit"), []
    try:
        payload = json.loads(out or "{}")
    except json.JSONDecodeError:
        return GateResult("verify_acs", "WARN", "verify_acs emitted non-JSON"), []
    ac_list = []
    for ac in payload.get("acs", []) or []:
        ac_list.append(
            ACResult(
                id=str(ac.get("id", "?")),
                spec=ac.get("spec", "")[:200],
                status=ac.get("status", "INDETERMINATE"),
                detail="; ".join(
                    c.get("detail", "") for c in ac.get("checks", []) if c.get("status") == "FAIL"
                )[:300],
            )
        )
    has_fail = any(
        a.status == "FAIL"
        and not all(
            c.get("kind", "").startswith("manual")
            for c in (ac.get("checks", []) for ac in payload.get("acs", []))
        )
        for a in ac_list
    )
    status = "FAIL" if has_fail else ("WARN" if not ac_list else "PASS")
    detail = f"{sum(1 for a in ac_list if a.status == 'PASS')}/{len(ac_list)} ACs PASS"
    return GateResult("verify_acs", status, detail), ac_list


def _validate_stories(workspace_root: str, story_id: str) -> GateResult:
    plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", ""))
    if not plugin_root.exists():
        plugin_root = Path(workspace_root) / "developer-plugin"
    script = plugin_root / "skills" / "validate-stories" / "scripts" / "validate_stories.py"
    if not script.exists():
        return GateResult(
            "validate_stories",
            "WARN",
            f"validate_stories.py not found at {script}",
        )
    rc, out, err = _run([sys.executable, str(script), "--story", story_id, "--json"])
    if rc == 0:
        return GateResult("validate_stories", "PASS")
    if rc == 2:
        return GateResult("validate_stories", "WARN", (err or out).strip()[:200])
    return GateResult("validate_stories", "FAIL", (err or out).strip()[:300])


def _files_by_layer(project_root: str, branch: str) -> dict[str, list[str]]:
    rc, out, _ = _run(["git", "diff", "--name-only", "origin/main...HEAD"], cwd=project_root)
    if rc != 0:
        return {}
    layers: dict[str, list[str]] = {}

    def _classify(path: str) -> str:
        p = path
        if "/bronze/" in p:
            return "bronze"
        if "/silver/" in p:
            return "silver"
        if "/gold/" in p:
            return "gold"
        if "/airflow/" in p or "/dags/" in p:
            return "dag"
        if "/.github/workflows/" in p or "/_infra/ci/" in p:
            return "pipeline"
        if "/contracts/" in p:
            return "contracts"
        if "/dq_rules/" in p:
            return "dq_rules"
        if "/tests/" in p:
            return "tests"
        if "/_infra/" in p:
            return "infra"
        return "other"

    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        layers.setdefault(_classify(line), []).append(line)
    return layers


def _resolve_epic(story_path: Path) -> tuple[str, str]:
    # Walk up looking for an EPIC-NN-* directory
    for parent in story_path.parents:
        if re.match(r"^EPIC-\d+-", parent.name):
            return parent.name.split("-")[0] + "-" + parent.name.split("-")[1], str(parent)
    return "", ""


def _story_title(story_path: Path) -> str:
    try:
        for line in story_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        pass
    return story_path.stem


def _labels(epic_id: str, layers: dict[str, list[str]]) -> list[str]:
    labels: list[str] = []
    if epic_id:
        # _resolve_epic returns "EPIC-NN"; strip the prefix so we don't
        # emit "epic-epic-NN" labels on PRs.
        slug = epic_id.lower().removeprefix("epic-")
        labels.append(f"epic-{slug}")
    # Dominant layer
    if layers:
        dominant = max(layers.items(), key=lambda kv: len(kv[1]))[0]
        if dominant in {"bronze", "silver", "gold", "infra"}:
            labels.append(f"layer:{dominant}")
    labels.append("requires-sandbox-teardown")
    return labels


def _teardown_plan(project_root: str) -> tuple[str, list[dict]]:
    """Resolve which driver applies + emit its --check plan."""
    compose = Path(project_root) / "_infra" / "docker" / "docker-compose.yml"
    if not compose.exists():
        return "none", []
    # Static plan from compose service names (the driver itself re-derives at destroy time)
    return (
        "local-docker",
        [
            {"kind": "compose-project", "name": Path(project_root).name},
            {"kind": "volume", "name": "uc-data"},
            {"kind": "volume", "name": "marquez-db"},
        ],
    )


def aggregate(args) -> ReadinessReport:
    report = ReadinessReport(
        story=args.story,
        branch=args.branch,
        workspace_root=args.workspace_root,
        project_root=args.project_root,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    g1 = _git_tree_clean(args.project_root)
    g2 = _branch_state(args.project_root, args.branch)
    g3, story_path = _locate_story(args.workspace_root, args.story)
    g4 = _make_target(args.project_root, "lint")
    g5 = _make_target(args.project_root, "test")
    g6, acs = _run_verify_acs(args.workspace_root, args.story)
    g7 = _validate_stories(args.workspace_root, args.story)

    report.gates = [g1, g2, g3, g4, g5, g6, g7]
    report.acs = acs

    if story_path is not None:
        report.story_path = str(story_path)
        report.story_title = _story_title(story_path)
        report.epic_id, report.epic_path = _resolve_epic(story_path)

    report.files_by_layer = _files_by_layer(args.project_root, args.branch)
    report.validators = [
        {
            "name": g.name,
            "result": g.status,
            "notes": (g.detail or "")[:120],
        }
        for g in report.gates
    ]
    driver, plan = _teardown_plan(args.project_root)
    report.teardown_driver = driver
    report.teardown_plan = plan
    report.labels = _labels(report.epic_id, report.files_by_layer)

    statuses = {g.status for g in report.gates}
    if "FAIL" in statuses:
        report.result = "FAIL"
    elif "WARN" in statuses:
        report.result = "WARN"
    else:
        report.result = "PASS"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="PR readiness aggregator")
    parser.add_argument("--story", required=True, help="STORY-NN-NNN")
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument(
        "--emit",
        choices=["json", "labels", "plan"],
        default="json",
        help="Output mode",
    )
    parser.add_argument("--json", action="store_true", help="Alias for --emit json")
    args = parser.parse_args()

    if args.json:
        args.emit = "json"

    report = aggregate(args)

    # Persist for the SKILL to read in Phase 2 templating
    cache = Path("/tmp") / f"pr-readiness-{args.story}.json"
    cache.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")

    if args.emit == "labels":
        print(",".join(report.labels))
    elif args.emit == "plan":
        for g in report.gates:
            print(f"  {g.status:<5} {g.name}: {g.detail}")
    else:
        print(json.dumps(asdict(report), indent=2))

    return {"PASS": 0, "WARN": 2, "FAIL": 1}[report.result]


if __name__ == "__main__":
    sys.exit(main())
