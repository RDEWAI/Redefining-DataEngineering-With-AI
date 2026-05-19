#!/usr/bin/env python3
"""AC verifier runner — turns story acceptance criteria into mechanical checks.

Each story markdown MAY append a `## Verification` section whose body is YAML
mapping AC identifiers (AC1, AC2, …) to an ordered list of verifier specs.
If the section is absent, the runner returns INDETERMINATE for every AC —
validate-stories then falls back to heuristic scanning.

Verifier types (all paths resolve relative to chapter-5 workspace root):

    - file_exists: <path>
    - file_count:   {glob: <pattern>, equals|min|max: <int>}
    - grep:         {file: <path>, pattern: <regex>}                 # >=1 match
    - grep_absent:  {file|files|glob: ..., pattern: <regex>}         # 0 matches
                    (alias: forbidden_grep — same behavior)
    - grep_count:   {files: <path|[paths]|glob>, pattern: <regex>,
                     equals|min|max: <int>}
    - pytest:       {node: <path_or_nodeid>, marker: <opt marker>}
    - validator:    <validate-* script path under developer-plugin>
    - manual:       <reason>           # explicit INDETERMINATE, human review

Example (embedded in a story file; ``<project>`` is the cookiecutter
project package — discovered at runtime, not hardcoded):

    ## Verification

    ```yaml
    AC1:
      - file_count: {glob: "<project>/airflow/configs/*.yml", equals: 13}
      - grep_count:
          glob: "<project>/airflow/configs/*.yml"
          pattern: "empty_input_behavior:\\s*fail"
          equals: 6
    AC5:
      - file_count: {glob: "<project>/ddl/liquibase/changelogs/*.xml", equals: 13}
    AC6:
      - file_exists: "<project>/tests/test_contracts.py"
      - pytest: {node: "<project>/tests/test_contracts.py"}
    ```

Exit codes: 0 = all PASS (INDETERMINATE allowed), 1 = any FAIL, 2 = runner error.
"""

from __future__ import annotations

import argparse
import glob as globlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PASS, FAIL, INDET = "PASS", "FAIL", "INDETERMINATE"


def chapter_root(start: Path) -> Path:
    env = os.environ.get("CHAPTER5_ROOT")
    if env:
        return Path(env).resolve()
    p = start.resolve()
    for cand in [p, *p.parents]:
        if (cand / ".claude-plugin" / "marketplace.json").exists() and cand.name == "chapter-5":
            return cand
        if (cand / "developer-plugin").is_dir() and (cand / "outputs").is_dir():
            return cand
    return p


@dataclass
class ACResult:
    ac: str
    status: str
    checks: list[tuple[str, str, str]] = field(default_factory=list)  # (spec, status, detail)

    def worst(self) -> str:
        if any(s == FAIL for _, s, _ in self.checks):
            return FAIL
        if self.checks and all(s == PASS for _, s, _ in self.checks):
            return PASS
        return INDET


@dataclass
class StoryResult:
    story_id: str
    path: Path
    has_verification: bool
    acs: list[ACResult] = field(default_factory=list)

    def overall(self) -> str:
        if not self.has_verification:
            return INDET
        if any(a.worst() == FAIL for a in self.acs):
            return FAIL
        if all(a.worst() == PASS for a in self.acs) and self.acs:
            return PASS
        return INDET


def parse_verification_block(text: str) -> dict[str, list] | None:
    m = re.search(r"^##\s+Verification\s*\n(.*?)(?=^##\s|\Z)", text, re.MULTILINE | re.DOTALL)
    if not m:
        return None
    body = m.group(1)
    fence = re.search(r"```ya?ml\s*\n(.*?)\n```", body, re.DOTALL)
    payload = fence.group(1) if fence else body
    try:
        data = yaml.safe_load(payload)
    except yaml.YAMLError as e:
        raise ValueError(f"Verification block YAML parse error: {e}") from e
    if not isinstance(data, dict):
        return None
    return {str(k): (v if isinstance(v, list) else [v]) for k, v in data.items()}


def parse_ac_ids(text: str) -> list[str]:
    m = re.search(
        r"^##\s+Acceptance Criteria\s*\n(.*?)(?=^##\s|\Z)", text, re.MULTILINE | re.DOTALL
    )
    if not m:
        return []
    items = re.findall(r"^\s*-\s*\[([ xX])\]", m.group(1), re.MULTILINE)
    return [f"AC{i + 1}" for i in range(len(items))]


def _coerce(spec: Any) -> tuple[str, dict | str]:
    """Normalize a verifier spec to (kind, payload)."""
    if isinstance(spec, str):
        return ("_bare", spec)
    if not isinstance(spec, dict) or len(spec) != 1:
        raise ValueError(f"Invalid verifier spec: {spec!r}")
    kind, payload = next(iter(spec.items()))
    return kind, payload


_BRACE_RE = re.compile(r"\{([^{}]+)\}")


def _expand_braces(pattern: str) -> list[str]:
    """Expand ``{a,b,c}`` brace alternations bash-style.

    Python's ``glob.glob`` does not natively expand braces. Stories often write
    ``contracts/{clinical,reference,billing}_*.yml`` to match three layer
    prefixes in one pattern; expand to three separate globs and union.

    Handles nested-free single-level braces (sufficient for AC patterns).
    """
    m = _BRACE_RE.search(pattern)
    if not m:
        return [pattern]
    prefix, suffix = pattern[: m.start()], pattern[m.end() :]
    expanded: list[str] = []
    for alt in m.group(1).split(","):
        expanded.extend(_expand_braces(prefix + alt + suffix))
    return expanded


def _resolve_files(payload: dict, root: Path) -> list[Path]:
    if "file" in payload:
        return [root / payload["file"]]
    if "files" in payload:
        vals = payload["files"]
        return [root / v for v in (vals if isinstance(vals, list) else [vals])]
    if "glob" in payload:
        seen: set[str] = set()
        out: list[Path] = []
        for pat in _expand_braces(payload["glob"]):
            for p in globlib.glob(str(root / pat), recursive=True):
                if p in seen:
                    continue
                seen.add(p)
                out.append(Path(p))
        return out
    raise ValueError(f"Need one of file|files|glob in {payload!r}")


def _count_cmp(n: int, payload: dict) -> tuple[str, str]:
    # Accept `at_least` / `at_most` aliases for `min` / `max` (story authors
    # frequently use the human-language forms).
    if "at_least" in payload and "min" not in payload:
        payload = {**payload, "min": payload["at_least"]}
    if "at_most" in payload and "max" not in payload:
        payload = {**payload, "max": payload["at_most"]}
    if "greater_or_equal" in payload and "min" not in payload:
        payload = {**payload, "min": payload["greater_or_equal"]}
    if "less_or_equal" in payload and "max" not in payload:
        payload = {**payload, "max": payload["less_or_equal"]}
    if "equals" in payload:
        ok = n == payload["equals"]
        return (PASS if ok else FAIL, f"{n} vs equals {payload['equals']}")
    if "min" in payload and "max" in payload:
        ok = payload["min"] <= n <= payload["max"]
        return (PASS if ok else FAIL, f"{n} vs [{payload['min']},{payload['max']}]")
    if "min" in payload:
        ok = n >= payload["min"]
        return (PASS if ok else FAIL, f"{n} vs min {payload['min']}")
    if "max" in payload:
        ok = n <= payload["max"]
        return (PASS if ok else FAIL, f"{n} vs max {payload['max']}")
    raise ValueError(f"Need equals|min|max|at_least|at_most|greater_or_equal|less_or_equal in {payload!r}")


def run_verifier(spec: Any, root: Path) -> tuple[str, str, str]:
    """Returns (label, status, detail)."""
    kind, payload = _coerce(spec)
    label = f"{kind}: {payload if isinstance(payload, str) else json.dumps(payload, default=str)}"

    try:
        if kind == "file_exists" or (kind == "_bare"):
            path = root / (payload if isinstance(payload, str) else payload.get("path", ""))
            ok = path.exists()
            return (label, PASS if ok else FAIL, str(path))

        if kind == "file_count":
            files = (
                _resolve_files(payload, root)
                if ("file" in payload or "files" in payload or "glob" in payload)
                else []
            )
            status, detail = _count_cmp(len(files), payload)
            return (label, status, detail)

        if kind == "grep":
            files = _resolve_files(payload, root)
            pat = re.compile(payload["pattern"], re.MULTILINE)
            for f in files:
                if not f.exists():
                    continue
                if pat.search(f.read_text(errors="replace")):
                    return (label, PASS, f"matched in {f.name}")
            return (label, FAIL, "no match")

        if kind in ("grep_absent", "forbidden_grep"):
            files = _resolve_files(payload, root)
            existing = [f for f in files if f.exists()]
            if not existing:
                return (label, FAIL, "no files to check")
            pat = re.compile(payload["pattern"], re.MULTILINE)
            for f in existing:
                if pat.search(f.read_text(errors="replace")):
                    return (label, FAIL, f"pattern found in {f.name}")
            return (label, PASS, f"absent across {len(existing)} file(s)")

        if kind == "grep_count":
            files = _resolve_files(payload, root)
            pat = re.compile(payload["pattern"], re.MULTILINE)
            n = 0
            for f in files:
                if not f.exists():
                    continue
                n += len(pat.findall(f.read_text(errors="replace")))
            status, detail = _count_cmp(n, payload)
            return (label, status, detail)

        if kind == "pytest":
            node = payload if isinstance(payload, str) else payload["node"]
            abs_node = (root / node).resolve()
            # Run pytest from the nearest pyproject.toml ancestor of the test
            # node so `uv run` resolves the right project venv. Generated
            # sub-projects (e.g. patient_360/) ship their own pyproject.
            search_start = abs_node.parent if abs_node.is_file() else abs_node
            cwd = root
            for cand in [search_start, *search_start.parents]:
                if (cand / "pyproject.toml").exists():
                    cwd = cand
                    break
                if cand == root:
                    break
            try:
                rel_node = str(abs_node.relative_to(cwd))
            except ValueError:
                rel_node = str(abs_node)
            cmd = ["uv", "run", "pytest", rel_node, "-q", "--no-header", "-x"]
            if isinstance(payload, dict) and payload.get("marker"):
                cmd += ["-m", payload["marker"]]
            r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=120)
            return (label, PASS if r.returncode == 0 else FAIL, f"pytest exit={r.returncode} (cwd={cwd.name})")

        if kind == "validator":
            script = root / (payload if isinstance(payload, str) else payload["script"])
            if not script.exists():
                return (label, FAIL, f"validator script not found: {script}")
            r = subprocess.run(
                ["python3", str(script)], capture_output=True, text=True, cwd=root, timeout=300
            )
            return (label, PASS if r.returncode == 0 else FAIL, f"exit={r.returncode}")

        if kind == "manual":
            return (label, INDET, str(payload))

        return (label, FAIL, f"unknown verifier kind: {kind}")

    except (subprocess.TimeoutExpired, OSError, ValueError, KeyError) as e:
        return (label, FAIL, f"runner error: {e}")


def verify_story(path: Path, root: Path) -> StoryResult:
    text = path.read_text()
    story_id = re.search(r"STORY-\d{2}-\d{3}", path.name)
    sid = story_id.group(0) if story_id else path.stem

    ac_ids = parse_ac_ids(text)
    try:
        verif = parse_verification_block(text)
    except ValueError as e:
        # Malformed YAML in the Verification block — surface as a synthetic FAIL
        # AC instead of crashing the whole batch.
        result = StoryResult(story_id=sid, path=path, has_verification=True)
        result.acs.append(
            ACResult(
                ac="AC0",
                status=FAIL,
                checks=[("verification-block parse", FAIL, str(e))],
            )
        )
        return result
    result = StoryResult(story_id=sid, path=path, has_verification=verif is not None)

    if verif is None:
        for ac in ac_ids:
            result.acs.append(
                ACResult(ac=ac, status=INDET, checks=[("(no verification block)", INDET, "")])
            )
        return result

    for ac in ac_ids or list(verif.keys()):
        specs = verif.get(ac, [])
        ac_res = ACResult(ac=ac, status=INDET)
        if not specs:
            ac_res.checks.append(("(no verifier)", INDET, ""))
        else:
            for spec in specs:
                ac_res.checks.append(run_verifier(spec, root))
        ac_res.status = ac_res.worst()
        result.acs.append(ac_res)

    return result


def discover(target: str, root: Path) -> list[Path]:
    stories_dir = next((root / "outputs" / "stories").glob("v*"), None)
    if stories_dir is None:
        raise SystemExit(f"No outputs/stories/v*/ under {root}")
    latest = sorted((root / "outputs" / "stories").glob("v*"))[-1]

    if target.upper().startswith("STORY-"):
        hits = list(latest.rglob(f"{target.upper()}-*.md"))
        return hits
    if target.upper().startswith("EPIC-"):
        folder = next(
            (d for d in latest.iterdir() if d.is_dir() and d.name.startswith(target.upper())), None
        )
        if not folder:
            raise SystemExit(f"No folder for {target} under {latest}")
        return sorted(p for p in folder.glob("STORY-*.md"))
    if target.upper() == "ALL":
        return sorted(latest.rglob("STORY-*.md"))
    raise SystemExit(f"Target must be STORY-NN-NNN, EPIC-NN, or ALL (got {target!r})")


def format_report(results: list[StoryResult]) -> str:
    lines = []
    overall_fail = False
    for r in results:
        badge = r.overall()
        lines.append(f"\n=== {r.story_id}  [{badge}]  {r.path.name}")
        if not r.has_verification:
            lines.append("    (no ## Verification block — all ACs INDETERMINATE)")
        for ac in r.acs:
            lines.append(f"  {ac.ac}: {ac.status}")
            for spec, status, detail in ac.checks:
                lines.append(f"    - [{status}] {spec}" + (f"  :: {detail}" if detail else ""))
        if badge == FAIL:
            overall_fail = True
    lines.append("")
    if overall_fail:
        verdict = FAIL
    elif results and all(r.overall() == PASS for r in results):
        verdict = PASS
    else:
        verdict = INDET
    lines.append(f"OVERALL: {verdict}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify story acceptance criteria against the repo.")
    ap.add_argument("target", help="STORY-NN-NNN, EPIC-NN, or ALL")
    ap.add_argument("--json", action="store_true", help="JSON output instead of text report")
    ap.add_argument("--root", help="Chapter-5 root (default: auto-detect)")
    args = ap.parse_args()

    root = Path(args.root).resolve() if args.root else chapter_root(Path(__file__).parent)
    stories = discover(args.target, root)
    if not stories:
        print(f"No stories matched target {args.target!r} under {root}", file=sys.stderr)
        return 2

    results = [verify_story(s, root) for s in stories]

    if args.json:
        print(
            json.dumps(
                [
                    {
                        "story": r.story_id,
                        "overall": r.overall(),
                        "has_verification": r.has_verification,
                        "acs": [
                            {
                                "ac": a.ac,
                                "status": a.status,
                                "checks": [
                                    {"spec": s, "status": st, "detail": d} for s, st, d in a.checks
                                ],
                            }
                            for a in r.acs
                        ],
                    }
                    for r in results
                ],
                indent=2,
            )
        )
    else:
        print(format_report(results))

    return 1 if any(r.overall() == FAIL for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
