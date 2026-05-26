"""Trigger-accuracy harness.

Loads `evals/trigger-prompts/prompts.jsonl` (one JSON record per line):

  {"prompt": "open a PR for STORY-01-001",
   "expected_skill": "pr-process",
   "rationale": "PR lifecycle phrasing"}

The full harness pipes each prompt to a fresh Claude session and records
which slash-command Claude invoked. That requires the user's session
budget, so by default we run the **static** check:

- The prompt's expected_skill appears in the SKILL.md
  ``description:`` of that skill (so the routing model has seen the
  phrasing).
- No OTHER skill's description matches the prompt more strongly. The
  "match strength" heuristic is a normalised token overlap with the
  description.

To run the full live-routing check, set `RDEWAI_LIVE_TRIGGER=1` and
provide a `RDEWAI_CLAUDE_BIN` pointing at a Claude CLI that takes a
prompt on stdin and prints the picked skill on stdout.
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2] / "developer-plugin"
PROMPTS_FILE = Path(__file__).resolve().parents[1] / "trigger-prompts" / "prompts.jsonl"

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9-]*")


@dataclass
class TriggerCase:
    prompt: str
    expected_skill: str
    rationale: str = ""


@dataclass
class TriggerResult:
    case: TriggerCase
    picked: str
    static_match: bool
    detail: str = ""


def load_cases() -> list[TriggerCase]:
    cases: list[TriggerCase] = []
    if not PROMPTS_FILE.exists():
        return cases
    for line in PROMPTS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        record = json.loads(line)
        cases.append(
            TriggerCase(
                prompt=record["prompt"],
                expected_skill=record["expected_skill"],
                rationale=record.get("rationale", ""),
            )
        )
    return cases


def _skill_descriptions() -> dict[str, str]:
    out: dict[str, str] = {}
    for skill_md in PLUGIN_ROOT.glob("skills/*/SKILL.md"):
        name = skill_md.parent.name
        text = skill_md.read_text(encoding="utf-8")
        m = re.search(r"^description:\s*>?\s*\n((?:\s{2,}.+\n?)+)", text, re.MULTILINE)
        if m:
            out[name] = m.group(1)
        else:
            m2 = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
            out[name] = m2.group(1) if m2 else ""
    return out


def _doc_tokens(description: str) -> set[str]:
    return {w.lower() for w in WORD_RE.findall(description) if len(w) > 2}


def _idf(descriptions: dict[str, str]) -> dict[str, float]:
    """Inverse document frequency over the skill descriptions.

    A token in every description has idf ~ 0; a token in one description
    has idf ~ log(N). This lets distinctive vocabulary (e.g. "scd2",
    "sandbox", "promote") outweigh boilerplate that appears in every
    description ("the", "skill", "generate", "use when").
    """
    n = max(len(descriptions), 1)
    df: Counter[str] = Counter()
    for desc in descriptions.values():
        for tok in _doc_tokens(desc):
            df[tok] += 1
    return {tok: math.log(n / cnt) for tok, cnt in df.items()}


def _score(
    prompt: str,
    description: str,
    idf: dict[str, float],
) -> float:
    """IDF-weighted, length-normalised token-overlap score.

    For each unique prompt token: add its IDF if it appears in the
    description (presence, not count — counts reward long descriptions
    that repeat boilerplate). Length normalisation isn't necessary once
    presence is used instead of frequency.
    """
    prompt_tokens = {w.lower() for w in WORD_RE.findall(prompt) if len(w) > 2}
    desc_tokens = _doc_tokens(description)
    return sum(idf.get(tok, 0.0) for tok in prompt_tokens if tok in desc_tokens)


def static_pick(prompt: str, descriptions: dict[str, str]) -> tuple[str, dict[str, float]]:
    idf = _idf(descriptions)
    scores = {name: _score(prompt, desc, idf) for name, desc in descriptions.items()}
    picked = max(scores.items(), key=lambda kv: (kv[1], kv[0]))[0]
    return picked, scores


def live_pick(prompt: str) -> str:
    bin_path = os.environ.get("RDEWAI_CLAUDE_BIN")
    if not bin_path:
        raise RuntimeError("RDEWAI_LIVE_TRIGGER set but RDEWAI_CLAUDE_BIN unset")
    proc = subprocess.run(
        [bin_path],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return proc.stdout.strip().splitlines()[-1] if proc.stdout else ""


def run() -> list[TriggerResult]:
    cases = load_cases()
    descriptions = _skill_descriptions()
    live = os.environ.get("RDEWAI_LIVE_TRIGGER") == "1"
    results: list[TriggerResult] = []
    for case in cases:
        if live:
            picked = live_pick(case.prompt)
            results.append(
                TriggerResult(
                    case=case,
                    picked=picked,
                    static_match=(picked == case.expected_skill),
                    detail="live",
                )
            )
        else:
            picked, scores = static_pick(case.prompt, descriptions)
            expected_score = scores.get(case.expected_skill, 0.0)
            detail = f"top-score={scores[picked]:.2f} expected-score={expected_score:.2f}"
            results.append(
                TriggerResult(
                    case=case,
                    picked=picked,
                    static_match=(picked == case.expected_skill),
                    detail=detail,
                )
            )
    return results
