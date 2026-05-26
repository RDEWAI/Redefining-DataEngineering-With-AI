"""Cross-cutting eval tests.

These pull in the chapter-6 eval harness and exercise it against the
Phase-1 exemplar skills. The 21 scaffolded skills SKIP rather than FAIL
— that's how the coverage table in `evals/README.md` is enforced
without blocking PRs while backfill is in flight.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

CH6_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = CH6_ROOT / "developer-plugin"
EVALS_ROOT = CH6_ROOT / "evals"

# Make the harness importable.
sys.path.insert(0, str(EVALS_ROOT))

from harness import golden_diff, trigger_eval  # noqa: E402

PHASE_1_FILLED = {
    "pr-process",
    "create-pipeline",
    "update-pipeline",
    "validate-pipeline",
    "create-silver",
}


def _all_skills() -> list[str]:
    return sorted(p.name for p in (PLUGIN_ROOT / "skills").iterdir() if p.is_dir())


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


class TestSkillCreatorCoverage:
    """Every skill must have an eval stub. Filled vs scaffold is tracked by
    the `status:` key in the eval file's frontmatter."""

    @pytest.mark.parametrize("skill", _all_skills())
    def test_eval_file_exists(self, skill: str) -> None:
        eval_path = EVALS_ROOT / "skill-creator" / f"{skill}.eval.md"
        assert eval_path.exists(), (
            f"missing eval stub for {skill} — create "
            f"evals/skill-creator/{skill}.eval.md with status: scaffold"
        )

    @pytest.mark.parametrize("skill", sorted(PHASE_1_FILLED))
    def test_phase_1_skill_is_filled(self, skill: str) -> None:
        eval_path = EVALS_ROOT / "skill-creator" / f"{skill}.eval.md"
        fm = _frontmatter(eval_path)
        assert (
            fm.get("status") == "filled"
        ), f"{skill} is in Phase 1 but its eval is status={fm.get('status')!r}"

    @pytest.mark.parametrize(
        "skill",
        sorted(set(_all_skills()) - PHASE_1_FILLED),
    )
    def test_other_skills_at_least_scaffolded(self, skill: str) -> None:
        eval_path = EVALS_ROOT / "skill-creator" / f"{skill}.eval.md"
        if not eval_path.exists():
            pytest.skip(f"stub not yet created for {skill}")
        fm = _frontmatter(eval_path)
        # 'scaffold' is the accepted status for unfilled stubs.
        assert fm.get("status") in {
            "scaffold",
            "filled",
        }, f"{skill} eval has unexpected status: {fm.get('status')!r}"


class TestTriggerPrompts:
    """Every Phase-1 skill must have ≥1 prompt; the static heuristic
    should agree with the expected_skill for the majority of cases."""

    @pytest.fixture
    def results(self) -> list:
        return trigger_eval.run()

    def test_every_phase_1_skill_has_prompt(self, results) -> None:
        covered = {r.case.expected_skill for r in results}
        for skill in PHASE_1_FILLED:
            assert skill in covered, f"{skill} has no entry in evals/trigger-prompts/prompts.jsonl"

    def test_static_match_sanity_floor(self, results) -> None:
        """The static heuristic is a sanity guard, not the accuracy metric.

        Lexical overlap penalises information-dense descriptions like
        ``pr-process`` (which covers four phases) and rewards short
        descriptions. The real trigger-accuracy measure requires live
        mode (``RDEWAI_LIVE_TRIGGER=1``); the static heuristic only
        guarantees that the skill SOMETIMES wins for its own prompts.
        """
        if not results:
            pytest.skip("no prompts loaded")
        ok = sum(1 for r in results if r.static_match)
        ratio = ok / len(results)
        # 30% is a floor catching gross regressions (e.g. a skill whose
        # description no longer mentions any of its trigger keywords).
        # Realistic accuracy only comes from live mode.
        misroutes = [
            f"{r.case.prompt!r} → got {r.picked} expected {r.case.expected_skill} ({r.detail})"
            for r in results
            if not r.static_match
        ]
        assert ratio >= 0.3, (
            f"trigger-accuracy {ratio:.0%} below 30% static-heuristic floor. "
            f"Misroutes:\n  " + "\n  ".join(misroutes)
        )


class TestGoldenDiffHarness:
    def test_harness_detects_match_for_pr_process_check(self) -> None:
        """Smoke: feed the harness the known --check output and it matches."""
        sample = (EVALS_ROOT / "goldens" / "pr-process" / "teardown-check.json").read_text(
            encoding="utf-8"
        )
        result = golden_diff.compare("pr-process", {"teardown-check.json": sample})
        assert result.matched, (
            f"golden_diff returned diffs={result.diffs} "
            f"missing={result.missing_goldens} extras={result.extra_artifacts}"
        )

    def test_harness_detects_drift(self) -> None:
        """Smoke: a deliberately wrong artifact must be reported as diff."""
        # Note: the golden uses a fixed names; we deliberately mutate one.
        wrong = json.dumps(
            {
                "driver": "local-docker",
                "destroyed": [{"kind": "compose-project", "name": "WRONG"}],
                "skipped": [],
            }
        )
        result = golden_diff.compare("pr-process", {"teardown-check.json": wrong})
        assert not result.matched
        assert "teardown-check.json" in result.diffs


class TestPhase1SkillShape:
    def test_pr_process_has_all_five_phases(self) -> None:
        skill_md = (PLUGIN_ROOT / "skills" / "pr-process" / "SKILL.md").read_text(encoding="utf-8")
        for phase in (
            "Phase 1 — Readiness Gate",
            "Phase 2 — Open the PR",
            "Phase 3 — Drive Review",
            "Phase 4 — Sandbox Teardown",
            "Phase 5 — Verification Compliance Self-Check",
        ):
            assert phase in skill_md, f"missing section: {phase}"

    def test_create_silver_skill_shape(self) -> None:
        skill_md = (PLUGIN_ROOT / "skills" / "create-silver" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        for phase in (
            "Phase 0 — Upstream Approval Gate",
            "Phase 1 — Read Upstream Artifacts",
            "Phase 2 — Emit Shared SCD2 Helper",
            "Phase 3 — Generate Per-Table Silver Transform Modules",
            "Phase 4 — Generate Per-Table Contracts",
            "Phase 5 — Generate Unit Tests",
            "Phase 6 — Wire the DAG Task Groups",
            "Phase 7 — Verify and Report",
        ):
            assert phase in skill_md, f"missing section: {phase}"
