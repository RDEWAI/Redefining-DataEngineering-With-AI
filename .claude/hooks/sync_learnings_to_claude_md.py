#!/usr/bin/env python3
"""SessionEnd hook: fold pending learnings-queue entries into CLAUDE.md.

A SessionEnd hook is a plain command — it cannot reason. So this does the one
thing that IS deterministic: it scans every `memory/*/learnings-queue.jsonl`
under the repo, and folds any entry whose generalized `pattern` is not already
present in CLAUDE.md into one of two MANAGED blocks:

  - "## Learnings"        <- patterns phrased as "Always ..." / neutral
  - "## What Not To Do"   <- patterns phrased as "Never ..." / "Do NOT ..."

The managed blocks are delimited by HTML-comment markers and are regenerated
wholesale each run, so the hook is idempotent: curated prose outside the markers
is never touched, and an entry already captured by hand is skipped (substring
match). The hook never fails the session — it always exits 0.
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
from pathlib import Path

LEARN_START = "<!-- AUTO-LEARNINGS:START (managed by .claude/hooks/sync_learnings_to_claude_md.py — do not edit by hand) -->"
LEARN_END = "<!-- AUTO-LEARNINGS:END -->"
WHATNOT_START = "<!-- AUTO-WHATNOT:START (managed by .claude/hooks/sync_learnings_to_claude_md.py — do not edit by hand) -->"
WHATNOT_END = "<!-- AUTO-WHATNOT:END -->"

NEGATIVE_PREFIXES = ("never", "do not", "don't", "dont", "avoid", "no ")


def repo_root() -> Path:
    # hook lives at <root>/.claude/hooks/this.py
    return Path(__file__).resolve().parents[2]


def load_entries(root: Path) -> list[dict]:
    entries: list[dict] = []
    for qf in glob.glob(str(root / "**" / "memory" / "**" / "learnings-queue.jsonl"), recursive=True):
        if "/.venv/" in qf or "/node_modules/" in qf:
            continue
        try:
            with open(qf, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    # only NEW corrections — applied entries are already folded
                    # into their SKILL.md (and usually the curated CLAUDE.md)
                    if (obj.get("status") or "").strip().lower() != "pending":
                        continue
                    pattern = (obj.get("pattern") or "").strip()
                    if not pattern:
                        continue
                    entries.append(
                        {
                            "skill": (obj.get("skill") or "?").strip(),
                            "date": (obj.get("date") or "").strip(),
                            "pattern": pattern,
                        }
                    )
        except OSError:
            continue
    return entries


def is_negative(pattern: str) -> bool:
    p = pattern.lstrip("-* ").lower()
    return p.startswith(NEGATIVE_PREFIXES)


def dedup(entries: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for e in entries:
        key = re.sub(r"\s+", " ", e["pattern"].lower()).strip()
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def already_curated(pattern: str, curated_text: str) -> bool:
    # skip if the core of the pattern already appears in hand-written CLAUDE.md
    core = re.sub(r"\s+", " ", pattern.lower()).strip().rstrip(".")
    return core[:60] in re.sub(r"\s+", " ", curated_text.lower())


def render_block(start: str, end: str, bullets: list[dict]) -> str:
    if not bullets:
        body = "_No new auto-captured learnings this session._"
    else:
        lines = []
        for b in sorted(bullets, key=lambda x: (x["skill"], x["date"])):
            tag = f"`{b['skill']}`" + (f" ({b['date']})" if b["date"] else "")
            lines.append(f"- {tag}: {b['pattern']}")
        body = "\n".join(lines)
    return f"{start}\n{body}\n{end}"


def upsert_block(text: str, heading: str, start: str, end: str, block: str) -> str:
    pat = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if pat.search(text):
        return pat.sub(lambda _: block, text)

    # no markers yet — insert right after the heading line
    hpat = re.compile(r"^(#{1,6})\s+" + re.escape(heading) + r"\s*$", re.MULTILINE)
    m = hpat.search(text)
    if not m:
        # heading absent — append a new section at end of file
        return text.rstrip() + f"\n\n## {heading}\n\n{block}\n"
    insert_at = m.end()
    return text[:insert_at] + "\n\n" + block + text[insert_at:]


def main() -> int:
    # consume stdin (hook payload) but we don't need it
    try:
        sys.stdin.read()
    except Exception:
        pass

    root = repo_root()
    claude_md = root / "CLAUDE.md"
    if not claude_md.exists():
        return 0

    text = claude_md.read_text(encoding="utf-8")

    # curated text = everything OUTSIDE the two managed blocks (for dedup)
    curated = text
    for s, e in ((LEARN_START, LEARN_END), (WHATNOT_START, WHATNOT_END)):
        curated = re.sub(re.escape(s) + r".*?" + re.escape(e), "", curated, flags=re.DOTALL)

    entries = dedup(load_entries(root))
    entries = [e for e in entries if not already_curated(e["pattern"], curated)]

    learnings = [e for e in entries if not is_negative(e["pattern"])]
    whatnot = [e for e in entries if is_negative(e["pattern"])]

    new_text = upsert_block(
        text, "Learnings", LEARN_START, LEARN_END, render_block(LEARN_START, LEARN_END, learnings)
    )
    new_text = upsert_block(
        new_text,
        "What Not To Do",
        WHATNOT_START,
        WHATNOT_END,
        render_block(WHATNOT_START, WHATNOT_END, whatnot),
    )

    if new_text != text:
        claude_md.write_text(new_text, encoding="utf-8")
        print(
            f"[sync-learnings] folded {len(learnings)} learning(s) / {len(whatnot)} don't(s) into CLAUDE.md",
            file=sys.stderr,
        )
    else:
        print("[sync-learnings] CLAUDE.md already up to date", file=sys.stderr)
    return 0


if __name__ == "__main__":
    # never fail the session
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"[sync-learnings] skipped: {exc}", file=sys.stderr)
        sys.exit(0)
