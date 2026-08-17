"""Offline tests for the Cost Anomaly Triage Agent (fakes; no LLM key / Spark / network)."""

from __future__ import annotations

import json

from ai_workflows.cost_triage import (
    ACUTE,
    Candidate,
    CostByClass,
    Feedback,
    FixtureCostProvider,
    LLMTriageReasoner,
    TriageVerdict,
    deliver,
    detect,
    load_encounter_groups,
    load_feedback,
    load_prior_artifacts,
    record_feedback,
    review_feedback,
    run,
)


# --- taxonomy grouping is sourced from taxonomy/encounter.yml, not hardcoded ---
def test_taxonomy_groups_map_leaves_to_acute_ambulatory() -> None:
    groups = load_encounter_groups()
    assert groups["EMERGENCY"] == "Acute"
    assert groups["INPATIENT"] == "Acute"
    assert groups["OUTPATIENT"] == "Ambulatory"
    assert groups["WELLNESS"] == "Ambulatory"


# --- deterministic detector ---
def test_detect_flags_outliers_and_fanout_acute_first() -> None:
    rows = FixtureCostProvider().cost_by_class()
    groups = load_encounter_groups()
    cands = detect(rows, groups, z_threshold=1.0)

    classes = [c.encounter_class for c in cands]
    assert "EMERGENCY" in classes           # cost outlier
    assert "INPATIENT" in classes           # flagged via claim fan-out (n_rows > n_distinct)
    assert "WELLNESS" not in classes        # neither outlier nor fan-out
    # taxonomy-driven ordering: Acute candidates come first
    assert cands[0].group == ACUTE
    emergency = next(c for c in cands if c.encounter_class == "EMERGENCY")
    assert emergency.fanout_ratio == round(80 / 60, 3)


def test_detect_empty_input() -> None:
    assert detect([], {}) == []


# --- AI triage reasoner: grounds in retrieved knowledge, parses structured verdict ---
class _FakeRetriever:
    def __init__(self):
        self.queries = []

    def context(self, query, *, k=5, kind=None, exclude=None):
        self.queries.append(query)
        return "# Retrieved knowledge\nbilling contract: claims fan out; taxonomy: Acute costs more"


class _FakeLLM:
    def __init__(self, reply):
        self.reply = reply
        self.prompts = []

    def complete(self, messages, **_):
        self.prompts.append(messages[-1].content)
        return self.reply


def test_reasoner_injects_knowledge_and_parses_json_verdict() -> None:
    retr = _FakeRetriever()
    llm = _FakeLLM(
        '```json\n{"classification": "artifact",'
        ' "rationale": "claim fan-out inflates the sum",'
        ' "recommended_action": "use COUNT(DISTINCT)",'
        ' "knowledge_used": ["data_contract: fan-out"]}\n```'
    )
    reasoner = LLMTriageReasoner(llm, retr)
    cand = Candidate("INPATIENT", "Acute", 300.0, -0.3, 2.0, 100)

    verdict = reasoner.triage(cand)

    assert isinstance(verdict, TriageVerdict)
    assert verdict.classification == "artifact"
    assert "fan-out" in verdict.rationale
    assert verdict.knowledge_used == ["data_contract: fan-out"]
    # the retrieved knowledge + the candidate evidence were both in the prompt
    assert "Retrieved knowledge" in llm.prompts[0]
    assert "fanout_ratio" in llm.prompts[0] and "INPATIENT" in llm.prompts[0]


def test_reasoner_malformed_reply_is_uncertain_not_crash() -> None:
    reasoner = LLMTriageReasoner(_FakeLLM("not json at all"), _FakeRetriever())
    verdict = reasoner.triage(Candidate("EMERGENCY", "Acute", 900.0, 1.7, 1.33, 60))
    assert verdict.classification == "uncertain"


class _EmptyThenValidLLM:
    """First call returns empty content (reasoning model quirk); retry returns valid JSON."""

    def __init__(self):
        self.calls = 0

    def complete(self, messages, **_):
        self.calls += 1
        if self.calls == 1:
            return ""   # empty -> no JSON -> should trigger a retry, not a crash
        return '{"classification":"real","rationale":"ok","recommended_action":"alert"}'


def test_reasoner_retries_on_empty_reply() -> None:
    llm = _EmptyThenValidLLM()
    cand = Candidate("EMERGENCY", "Acute", 900.0, 1.7, 1.0, 6)
    verdict = LLMTriageReasoner(llm, None).triage(cand)
    assert llm.calls == 2 and verdict.classification == "real"


def test_preflight_llm_reports_unreachable_endpoint() -> None:
    from ai_workflows.cost_triage import preflight_llm

    class _OK:
        def complete(self, messages, **_):
            return "ok"

    class _Down:
        def complete(self, messages, **_):
            raise ConnectionError("connection refused")

    assert preflight_llm(_OK()) is None
    msg = preflight_llm(_Down())
    assert msg is not None and "unreachable" in msg.lower() and "re-run" in msg.lower()


# --- full loop: run + deliver + feedback dedupe ---
class _RuleReasoner:
    """Stand-in judge for loop tests: artifact when fan-out dominates, else real."""

    def triage(self, candidate: Candidate) -> TriageVerdict:
        real = candidate.avg_cost >= 500 or candidate.fanout_ratio < 1.1
        return TriageVerdict(
            signature=candidate.signature,
            encounter_class=candidate.encounter_class,
            group=candidate.group,
            classification="real" if real else "artifact",
            rationale="test",
            recommended_action="test",
        )


def test_run_and_deliver_writes_outputs_and_feedback(tmp_path) -> None:
    report = run(FixtureCostProvider(), _RuleReasoner(), now="2026-08-09T00:00:00+00:00")
    # EMERGENCY (avg 900) -> real ; INPATIENT (fan-out 2.0, avg 300) -> artifact
    assert {v.encounter_class for v in report.alerts} == {"EMERGENCY"}
    assert {v.encounter_class for v in report.suppressed} == {"INPATIENT"}

    out = deliver(report, tmp_path)
    manifest = json.loads((out / "run_manifest.json").read_text())
    assert manifest["alerts"] == 1 and manifest["suppressed"] == 1
    inpatient_sig = next(v.signature for v in report.suppressed)
    assert inpatient_sig in manifest["suppressed_signatures"]

    # feedback: a second run that knows the artifact skips it (no re-alert)
    prior = load_prior_artifacts(out)
    assert inpatient_sig in prior
    report2 = run(FixtureCostProvider(), _RuleReasoner(), prior_artifacts=prior)
    assert inpatient_sig in report2.skipped_known_artifacts
    assert all(v.encounter_class != "INPATIENT" for v in report2.verdicts)


def test_costbyclass_fanout_ratio() -> None:
    assert CostByClass("X", 200, 100, 1.0, 1.0).fanout_ratio == 2.0
    assert CostByClass("Y", 0, 0, 0.0, 0.0).fanout_ratio == 1.0


# --- human-in-the-loop feedback: recorded correction -> AI uses it next run ---
def test_record_and_load_feedback_roundtrip(tmp_path) -> None:
    record_feedback(
        tmp_path, Feedback(encounter_class="EMERGENCY", note="cost is genuine, not fan-out")
    )
    loaded = load_feedback(tmp_path)
    assert len(loaded) == 1 and loaded[0].encounter_class == "EMERGENCY"
    assert loaded[0].note == "cost is genuine, not fan-out"


def test_feedback_unsuppresses_class(tmp_path) -> None:
    # a prior run had suppressed EMERGENCY; any human correction must un-suppress it for re-triage
    (tmp_path / "run_manifest.json").write_text(
        json.dumps({"suppressed_signatures": ["EMERGENCY:900", "INPATIENT:300"]})
    )
    record_feedback(tmp_path, Feedback(encounter_class="EMERGENCY", note="this is a real driver"))
    remaining = json.loads((tmp_path / "run_manifest.json").read_text())["suppressed_signatures"]
    assert remaining == ["INPATIENT:300"]


class _FeedbackAwareLLM:
    """Follows a human note if present in the prompt; otherwise defaults to artifact."""

    def __init__(self):
        self.prompts = []

    def complete(self, messages, **_):
        p = messages[-1].content
        self.prompts.append(p)
        if "actually a real cost driver" in p:   # the analyst's note
            return '{"classification":"real","rationale":"applied human correction",' \
                   '"recommended_action":"alert","knowledge_used":["human_feedback"]}'
        return '{"classification":"artifact","rationale":"default","recommended_action":"suppress"}'


def test_feedback_is_injected_and_flips_verdict() -> None:
    cand = Candidate("EMERGENCY", "Acute", 900.0, 1.7, 1.33, 60)

    # without feedback -> the model's default (artifact)
    assert LLMTriageReasoner(_FeedbackAwareLLM(), None).triage(cand).classification == "artifact"

    # with a human note on file -> injected into the prompt, verdict flips to real
    llm = _FeedbackAwareLLM()
    reasoner = LLMTriageReasoner(
        llm, None,
        feedback=[
            Feedback(encounter_class="EMERGENCY", note="this is actually a real cost driver")
        ],
    )
    verdict = reasoner.triage(cand)
    assert verdict.classification == "real"
    assert "human_feedback" in verdict.knowledge_used
    assert "Human feedback" in llm.prompts[0]
    assert "actually a real cost driver" in llm.prompts[0]


def test_feedback_matches_by_taxonomy_group() -> None:
    # feedback filed against the Acute group applies to any acute class candidate
    reasoner = LLMTriageReasoner(
        _FeedbackAwareLLM(), None,
        feedback=[Feedback(encounter_class="", note="acute is always reviewed", group="Acute")],
    )
    block = reasoner._feedback_block(Candidate("INPATIENT", "Acute", 300.0, 0.1, 2.0, 100))
    assert "acute is always reviewed" in block


# --- interactive in-flow review (the make cost-triage prompt) ---
def _scripted(answers):
    it = iter(answers)
    return lambda *_a, **_k: next(it)


def test_interactive_review_records_correction(tmp_path) -> None:
    report = run(FixtureCostProvider(), _RuleReasoner(), now="2026-08-09T00:00:00+00:00")
    # candidates (acute-first): EMERGENCY, INPATIENT. Mark #1 wrong + note; keep #2 (Enter).
    prompt = _scripted(["w", "cost is overstated by claim fan-out", ""])
    out_lines: list[str] = []
    n = review_feedback(report, tmp_path, prompt=prompt, echo=out_lines.append)

    assert n == 1
    fb = load_feedback(tmp_path)
    assert len(fb) == 1
    assert fb[0].encounter_class == "EMERGENCY"
    assert fb[0].note == "cost is overstated by claim fan-out"
    assert any("noted" in ln.lower() for ln in out_lines)


def test_interactive_review_wrong_without_note_is_ignored(tmp_path) -> None:
    report = run(FixtureCostProvider(), _RuleReasoner(), now="2026-08-09T00:00:00+00:00")
    # say wrong but give no note -> not recorded; then keep the 2nd
    n = review_feedback(report, tmp_path, prompt=_scripted(["w", "", ""]), echo=lambda *_: None)
    assert n == 0 and load_feedback(tmp_path) == []


def test_interactive_review_decline_records_nothing(tmp_path) -> None:
    report = run(FixtureCostProvider(), _RuleReasoner(), now="2026-08-09T00:00:00+00:00")
    # Enter (keep) for each of the two candidates
    n = review_feedback(report, tmp_path, prompt=_scripted(["", ""]), echo=lambda *_: None)
    assert n == 0 and load_feedback(tmp_path) == []


def test_render_report_shows_verdict_and_action() -> None:
    report = run(FixtureCostProvider(), _RuleReasoner(), now="2026-08-09T00:00:00+00:00")
    from ai_workflows.cost_triage import render_report

    lines: list[str] = []
    render_report(report, echo=lines.append)
    blob = "\n".join(lines)
    assert "Cost Anomaly Triage" in blob
    assert "EMERGENCY" in blob and "REAL" in blob and "action:" in blob
