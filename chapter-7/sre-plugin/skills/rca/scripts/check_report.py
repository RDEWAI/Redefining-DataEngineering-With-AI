#!/usr/bin/env python3
"""Self-check for an RCA report written by the `rca` skill.

Static, deterministic checks on ``RCA-*.md`` plus the sibling ``alert.json``
and ``evidence/manifest.json``. Prints the same block the chapter's validators
use (``CRITICAL: N issue(s)`` ... ``Result: PASS/FAIL``) and exits 1 when any
CRITICAL finding exists.

CRITICAL
  - a required section is missing
  - §5 Root Cause is INDETERMINATE but names no missing evidence
  - a hypothesis marked CONFIRMED / REFUTED cites no evidence file, or cites
    one that does not exist under evidence/
  - §7 permanent fix names no owner skill that exists (developer-plugin) and
    does not state "No code change required"
  - an SE evidence claim (§3, §4, or an "Evidence:" line of §5) is filtered by
    the data ds (meta_dq_run_date = <ds>); explaining the gate's own query in
    §5 prose is fine
WARNING
  - §8 severity / channel disagree with LLD §8.5 for the stated condition
  - hedging words in §5 ("might", "probably", "seems", "likely", "possibly")
  - manifest surfaces that are unavailable/skipped but not acknowledged in §3
INFO
  - Marquez / OTel unavailable (expected on this stack today)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rca_common import discover, expected_for_condition  # noqa: E402

REQUIRED_SECTIONS = [
    (1, "Alert Summary"),
    (2, "Timeline"),
    (3, "Evidence Collected"),
    (4, "Hypotheses"),
    (5, "Root Cause"),
    (6, "Blast Radius"),
    (7, "Remediation"),
    (8, "Severity & Escalation"),
    (9, "References"),
]
HEDGES = ("might", "probably", "seems", "likely", "possibly", "perhaps", "may be", "could be")
NO_CODE_CHANGE = re.compile(r"no code change required", re.IGNORECASE)
OWNER_CMD = re.compile(r"/developer-plugin:([\w-]+)")
EVIDENCE_REF = re.compile(r"evidence/([\w./-]+)")
DS_FILTER = re.compile(r"meta_dq_run_date\s*=\s*'?(\d{4}-\d{2}-\d{2})")


class Findings:
    def __init__(self) -> None:
        self.critical: list[str] = []
        self.warning: list[str] = []
        self.info: list[str] = []

    def render(self) -> str:
        out = [f"CRITICAL: {len(self.critical)} issue(s)"]
        out += [f"  - {m}" for m in self.critical]
        out += ["", f"WARNING: {len(self.warning)} issue(s)"]
        out += [f"  - {m}" for m in self.warning]
        out += ["", f"INFO: {len(self.info)} item(s)"]
        out += [f"  - {m}" for m in self.info]
        out += ["", f"Result: {'FAIL' if self.critical else 'PASS'}"]
        return "\n".join(out)


def split_sections(text: str) -> dict[int, str]:
    """Map section number -> body for `## N. Title` headings."""
    parts: dict[int, str] = {}
    matches = list(re.finditer(r"^## (\d+)\.\s+(.+?)\s*$", text, re.MULTILINE))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        parts[int(m.group(1))] = text[m.end() : end]
    return parts


def section_titles(text: str) -> dict[int, str]:
    return {
        int(m.group(1)): m.group(2).strip()
        for m in re.finditer(r"^## (\d+)\.\s+(.+?)\s*$", text, re.MULTILINE)
    }


def table_rows(body: str) -> list[list[str]]:
    rows = []
    for line in body.splitlines():
        if line.strip().startswith("|") and not re.match(r"^\|\s*-+", line.strip()):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rows.append(cells)
    return rows[1:] if rows else []  # drop header


def check(report: Path, workspace_root: Path | None = None) -> Findings:
    f = Findings()
    text = report.read_text(encoding="utf-8")
    report_dir = report.parent
    evidence_dir = report_dir / "evidence"
    alert = {}
    if (report_dir / "alert.json").is_file():
        alert = json.loads((report_dir / "alert.json").read_text())
    manifest = {}
    if (evidence_dir / "manifest.json").is_file():
        manifest = json.loads((evidence_dir / "manifest.json").read_text())

    titles = section_titles(text)
    sections = split_sections(text)
    for num, title in REQUIRED_SECTIONS:
        if num not in titles:
            f.critical.append(f"missing section '## {num}. {title}'")
        elif title.lower().split()[0] not in titles[num].lower():
            f.warning.append(f"section {num} is titled '{titles[num]}', expected '{title}'")

    # --- §5 root cause -------------------------------------------------------
    rc = sections.get(5, "")
    if "INDETERMINATE" in rc.upper():
        if not re.search(
            r"missing evidence|evidence (needed|required|not available)", rc, re.IGNORECASE
        ):
            f.critical.append(
                "§5 Root Cause is INDETERMINATE but does not list the missing evidence"
            )
    elif rc.strip() and not re.search(r"CONFIRMED", rc):
        f.warning.append("§5 Root Cause does not state CONFIRMED (or INDETERMINATE)")
    for word in HEDGES:
        if re.search(rf"\b{re.escape(word)}\b", rc, re.IGNORECASE):
            f.warning.append(f"§5 Root Cause uses hedging language: '{word}'")

    # --- §4 hypotheses must cite existing evidence ---------------------------
    for row in table_rows(sections.get(4, "")):
        joined = " | ".join(row)
        verdict = next(
            (
                c
                for c in row
                if re.fullmatch(r"(CONFIRMED|REFUTED|RULED OUT|INDETERMINATE|OPEN)", c.upper())
            ),
            None,
        )
        if verdict and verdict.upper() in ("CONFIRMED", "REFUTED", "RULED OUT"):
            refs = EVIDENCE_REF.findall(joined)
            if not refs:
                f.critical.append(
                    f"§4 hypothesis '{row[0][:60]}' is {verdict} but cites no evidence/<file>"
                )
            for ref in refs:
                p = evidence_dir / ref.split(":")[0].split("#")[0]
                if evidence_dir.is_dir() and not p.exists():
                    f.critical.append(f"§4 cites evidence/{ref} which does not exist")

    # --- §7 remediation owner ------------------------------------------------
    rem = sections.get(7, "")
    owners = OWNER_CMD.findall(rem)
    if not owners and not NO_CODE_CHANGE.search(rem):
        f.critical.append(
            "§7 Remediation names no owner skill (/developer-plugin:<skill>) "
            "and does not state 'No code change required'"
        )
    if owners and workspace_root is not None:
        skills_dir = workspace_root / "developer-plugin" / "skills"
        for skill in set(owners):
            if skills_dir.is_dir() and not (skills_dir / skill).is_dir():
                f.critical.append(
                    f"§7 names /developer-plugin:{skill} but no such skill exists "
                    "under developer-plugin/skills/"
                )
    if not re.search(r"immediate recovery|permanent fix|prevention", rem, re.IGNORECASE):
        f.warning.append(
            "§7 Remediation should be split into Immediate recovery / Permanent fix / Prevention"
        )

    # --- SE evidence filtered by ds (false-evidence pattern) ----------------
    # Scoped to evidence CLAIMS: §3, §4, and "Evidence:" lines of §5. Prose that
    # explains the gate's own query (the mechanism) is allowed elsewhere.
    ds = alert.get("ds")
    claim_text = (
        sections.get(3, "")
        + sections.get(4, "")
        + "\n".join(
            ln
            for ln in sections.get(5, "").splitlines()
            if ln.strip().lower().startswith("evidence")
        )
    )
    for m in DS_FILTER.finditer(claim_text):
        if ds and m.group(1) == ds:
            f.critical.append(
                f"SE evidence claim filtered by meta_dq_run_date = ds ({ds}); "
                "meta_dq_run_date is SE wall-clock, not the data ds"
            )

    # --- §8 severity vs LLD §8.5 -------------------------------------------
    cond = alert.get("condition")
    expected = expected_for_condition(cond) if cond else None
    sev_section = sections.get(8, "") + sections.get(1, "")
    if expected and cond != "unknown":
        if expected.severity not in sev_section:
            f.warning.append(
                f"§8 does not state the LLD §8.5 severity {expected.severity} "
                f"for condition '{cond}'"
            )
        chan = expected.channel.split()[0]
        if chan.lower() not in sev_section.lower():
            f.warning.append(
                f"§8 does not mention the LLD §8.5 channel '{expected.channel}' "
                f"for condition '{cond}'"
            )

    # --- §3 acknowledges unavailable surfaces --------------------------------
    ev = sections.get(3, "")
    for name, s in (manifest.get("surfaces") or {}).items():
        if s.get("status") in ("unavailable", "skipped"):
            if name in ("marquez_runs",) or name.startswith("docker_logs_marquez"):
                f.info.append(
                    f"{name} unavailable (expected: OpenLineage transport is not configured "
                    "on this stack)"
                )
            elif name not in ev:
                f.warning.append(
                    f"§3 does not acknowledge that evidence surface '{name}' was {s.get('status')}"
                )

    return f


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("report", type=Path)
    parser.add_argument("--workspace-root", type=Path, default=None)
    args = parser.parse_args(argv)
    if not args.report.is_file():
        print(f"error: {args.report} is not a file", file=sys.stderr)
        return 2
    try:
        ws_root = discover(workspace_root=args.workspace_root).workspace_root
    except Exception:  # noqa: BLE001 — checks still run without a workspace
        ws_root = args.workspace_root
    findings = check(args.report, ws_root)
    print(findings.render())
    return 1 if findings.critical else 0


if __name__ == "__main__":
    sys.exit(main())
