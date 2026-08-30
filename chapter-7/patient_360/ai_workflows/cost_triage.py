"""Cost Anomaly Triage Agent — a forward-deployed AI workflow over the Gold cost table.

Loop (mapped to the forward-deployed-workflows pattern):

  detect   (deterministic, no AI)  outlier encounter-class cost, rolled up to the encounter
                                    taxonomy (Acute vs Ambulatory), plus claim fan-out evidence.
  triage   (AI — irreducible)       an LLM reasons over the retrieved knowledge (data contract
                                    caveats, ontology, taxonomy) to judge REAL cost driver vs
                                    known DATA ARTIFACT, and recommends an action. This judgment
                                    is open-ended and not enumerable as rules.
  deliver  (output workflows)       route real anomalies to an alert sink; suppress+annotate
                                    artifacts; write a cost report.
  feedback (closes the loop)        a run manifest records verdicts; suppressed artifacts are
                                    remembered so the next cycle does not re-alert them.

The data fetch and detection are deterministic (that part never needed AI). Only the triage
*judgment* uses the LLM, grounded in the knowledge base — the point of the semantic layer.

Providers and the reasoner are injected, so the whole loop is unit-testable with fakes and can
run from a fixture (no Spark) — only the live triage step needs an LLM key + the Gold stack.
"""

from __future__ import annotations

import json
import os
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

import yaml

from patient_360.knowledge.documents import PROJECT_ROOT

# Encounter cost lives only here (cost isolation); this is the workflow's single Gold source.
BILLING_TABLE = "unity.gold.patient_billing_summary"
_TAXONOMY_FILE = PROJECT_ROOT / "taxonomy" / "encounter.yml"
DEFAULT_OUT = PROJECT_ROOT / "outputs" / "workflows" / "cost_triage"
DEFAULT_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "cost_by_class.json"

ACUTE = "Acute"


# --------------------------------------------------------------------------- taxonomy
def load_encounter_groups(taxonomy_file: str | Path | None = None) -> dict[str, str]:
    """Map each encounter_class leaf -> its taxonomy group (Acute / Ambulatory).

    Read from ``taxonomy/encounter.yml`` (the knowledge, not a hardcoded dict) so editing the
    taxonomy changes triage grouping without touching this code.
    """
    path = Path(taxonomy_file) if taxonomy_file is not None else _TAXONOMY_FILE
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    nodes = data.get("nodes", [])
    parent_of = {n["concept"]: n.get("parent") for n in nodes}
    groups: dict[str, str] = {}
    for node in nodes:
        stored = node.get("stored_value")
        if stored:  # a leaf that maps to a real encounter_class value
            groups[stored] = parent_of.get(node["concept"]) or "Unknown"
    return groups


# --------------------------------------------------------------------------- data model
@dataclass(frozen=True)
class CostByClass:
    """One deterministic cost row per encounter_class (the Serve-step output)."""

    encounter_class: str
    n_rows: int          # raw rows (claims can fan out)
    n_distinct: int      # distinct encounters
    total_cost: float
    avg_cost: float

    @property
    def fanout_ratio(self) -> float:
        return self.n_rows / self.n_distinct if self.n_distinct else 1.0


@dataclass
class Candidate:
    """A detected cost outlier awaiting AI triage."""

    encounter_class: str
    group: str           # taxonomy group (Acute / Ambulatory)
    avg_cost: float
    zscore: float
    fanout_ratio: float
    n_distinct: int
    signature: str = ""  # stable id for dedupe across runs

    def __post_init__(self) -> None:
        if not self.signature:
            self.signature = f"{self.encounter_class}:{round(self.avg_cost)}"


@dataclass
class TriageVerdict:
    """The AI judgment for one candidate."""

    signature: str
    encounter_class: str
    group: str
    classification: str          # real | artifact | uncertain
    rationale: str
    recommended_action: str
    knowledge_used: list[str] = field(default_factory=list)


@dataclass
class Feedback:
    """A human correction: the analyst says a verdict was WRONG and explains what's wrong.

    Persisted, then read back as authoritative grounding on the next run (no retraining): the
    ``note`` (free text) is the primary signal; ``correct_classification`` is an optional explicit
    label if one was given (e.g. via the non-interactive command).
    """

    encounter_class: str
    note: str = ""                    # what is wrong / how to correct (free text — primary)
    correct_classification: str = ""  # optional explicit label (real|artifact)
    group: str = ""
    created_at: str = ""
    source: str = "human"


@dataclass
class TriageReport:
    """Everything one workflow run produced."""

    generated_at: str
    candidates: list[Candidate]
    verdicts: list[TriageVerdict]
    skipped_known_artifacts: list[str] = field(default_factory=list)

    @property
    def alerts(self) -> list[TriageVerdict]:
        return [v for v in self.verdicts if v.classification == "real"]

    @property
    def suppressed(self) -> list[TriageVerdict]:
        return [v for v in self.verdicts if v.classification == "artifact"]


# --------------------------------------------------------------------------- detect
def detect(
    rows: list[CostByClass],
    groups: dict[str, str],
    *,
    z_threshold: float = 1.0,
    fanout_threshold: float = 1.05,
) -> list[Candidate]:
    """Flag cost outliers deterministically; roll up to the taxonomy; order acute-first.

    A class is a candidate if its avg cost is a statistical outlier across classes OR claims
    fan out (n_rows > n_distinct) — the latter is *evidence* for the AI, not a verdict.
    """
    if not rows:
        return []
    avgs = [r.avg_cost for r in rows]
    mean = statistics.fmean(avgs)
    stdev = statistics.pstdev(avgs) or 1.0

    candidates: list[Candidate] = []
    for r in rows:
        z = (r.avg_cost - mean) / stdev
        if z >= z_threshold or r.fanout_ratio >= fanout_threshold:
            candidates.append(
                Candidate(
                    encounter_class=r.encounter_class,
                    group=groups.get(r.encounter_class, "Unknown"),
                    avg_cost=round(r.avg_cost, 2),
                    zscore=round(z, 2),
                    fanout_ratio=round(r.fanout_ratio, 3),
                    n_distinct=r.n_distinct,
                )
            )
    # taxonomy-driven priority: Acute first, then by how extreme the cost is
    candidates.sort(key=lambda c: (c.group != ACUTE, -c.zscore))
    return candidates


# --------------------------------------------------------------------------- serve (providers)
class CostProvider(Protocol):
    """Serve step: return deterministic cost-by-class rows (no AI)."""

    def cost_by_class(self) -> list[CostByClass]: ...


class FixtureCostProvider:
    """Read cost-by-class from a JSON fixture — lets the loop run with no Spark stack."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_FIXTURE

    def cost_by_class(self) -> list[CostByClass]:
        data = json.loads(Path(self.path).read_text(encoding="utf-8"))
        return [CostByClass(**row) for row in data]


_COST_SQL = f"""
SELECT encounter_class,
       COUNT(*)                        AS n_rows,
       COUNT(DISTINCT encounter_id)    AS n_distinct,
       ROUND(SUM(total_claim_cost), 2) AS total_cost,
       ROUND(AVG(total_claim_cost), 2) AS avg_cost
FROM {BILLING_TABLE}
WHERE encounter_class IS NOT NULL AND total_claim_cost IS NOT NULL
GROUP BY encounter_class
""".strip()


class SparkCostProvider:
    """Serve step over live Gold: one deterministic GROUP BY (COUNT vs COUNT DISTINCT)."""

    def __init__(self, executor: object | None = None) -> None:
        self._executor = executor

    def _exec(self) -> object:
        if self._executor is None:
            from patient_360.semantic.executor import SparkGoldExecutor

            self._executor = SparkGoldExecutor()
        return self._executor

    def cost_by_class(self) -> list[CostByClass]:
        result = self._exec().run(_COST_SQL)
        idx = {name: i for i, name in enumerate(result.columns)}
        rows: list[CostByClass] = []
        for row in result.rows:
            rows.append(
                CostByClass(
                    encounter_class=str(row[idx["encounter_class"]]),
                    n_rows=int(row[idx["n_rows"]]),
                    n_distinct=int(row[idx["n_distinct"]]),
                    total_cost=float(row[idx["total_cost"]]),
                    avg_cost=float(row[idx["avg_cost"]]),
                )
            )
        return rows


# --------------------------------------------------------------------------- triage (AI)
_TRIAGE_INSTRUCTIONS = """\
You are a healthcare cost-analytics triage agent. A deterministic detector flagged an
encounter-class cost outlier. Using ONLY the retrieved knowledge above (data contract, ontology,
taxonomy) plus the candidate evidence, decide whether the anomaly is a REAL cost driver or a
known DATA ARTIFACT, and recommend one action.

Judge with the domain knowledge, not fixed rules:
- Claim fan-out: the billing contract says claims are LEFT-joined and can fan out; a high
  fanout_ratio (n_rows > n_distinct) inflates raw sums — that points to ARTIFACT unless the
  per-encounter avg is itself high.
- Taxonomy expectation: Acute encounters (Emergency/Inpatient/UrgentCare) are EXPECTED to cost
  more; a costly Ambulatory class is more suspicious/real.
- Contract caveats: payer fields are null in this load — never base a verdict on payer coverage.

If a "Human feedback" item above matches this candidate, the analyst judged the previous
verdict WRONG — correct your verdict and action to honour their note, say in the rationale that
you applied the human correction, and add "human_feedback" to knowledge_used.

Return ONLY a JSON object, no prose:
{"classification": "real|artifact|uncertain",
 "rationale": "<= 2 sentences citing the specific knowledge used",
 "recommended_action": "<one concrete next step>",
 "knowledge_used": ["<short tags, e.g. data_contract: claim fan-out; taxonomy: Acute>"]}
"""


class TriageReasoner(Protocol):
    """The AI judgment step: candidate + knowledge -> verdict."""

    def triage(self, candidate: Candidate) -> TriageVerdict: ...


def _extract_json(text: str) -> dict:
    body = text.strip()
    if "```" in body:
        body = body.split("```")[1] if body.count("```") >= 2 else body
        body = body.removeprefix("json").strip()
    start, end = body.find("{"), body.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object in reasoner reply: {text[:200]!r}")
    return json.loads(body[start : end + 1])


class LLMTriageReasoner:
    """Ground the judgment in retrieved knowledge, then ask the LLM for a structured verdict."""

    def __init__(
        self,
        llm: object,
        retriever: object | None = None,
        *,
        knowledge_k: int = 4,
        feedback: list[Feedback] | None = None,
        max_tokens: int = 1500,
    ):
        self.llm = llm
        self.retriever = retriever
        self.knowledge_k = knowledge_k
        self.feedback = feedback or []
        # Reasoning models (e.g. gpt-oss) spend tokens "thinking"; give the JSON room to appear.
        self.max_tokens = max_tokens

    def _knowledge(self, candidate: Candidate) -> str:
        if self.retriever is None:
            return ""
        query = (
            f"{candidate.encounter_class} {candidate.group} encounter cost anomaly "
            f"claim fan-out data contract timing artifact taxonomy acute ambulatory"
        )
        try:
            return self.retriever.context(query, k=self.knowledge_k)
        except Exception:  # noqa: BLE001 - RAG grounding is best-effort
            return ""

    def _feedback_block(self, candidate: Candidate) -> str:
        """Past human corrections that apply to this candidate (by class, or its taxonomy group)."""
        matches = [
            f for f in self.feedback
            if f.encounter_class.upper() == candidate.encounter_class.upper()
            or (f.group and f.group == candidate.group)
        ]
        if not matches:
            return ""
        lines = [
            "# Human feedback (AUTHORITATIVE): an analyst said the earlier verdict was WRONG — "
            "re-evaluate and correct accordingly."
        ]
        for f in matches:
            label = (
                f" [correct verdict: {f.correct_classification}]"
                if f.correct_classification else ""
            )
            lines.append(f"- {f.encounter_class or f.group}{label}: {f.note}")
        return "\n".join(lines)

    def _prompt(self, candidate: Candidate) -> str:
        evidence = (
            f"Candidate evidence:\n"
            f"- encounter_class: {candidate.encounter_class}\n"
            f"- taxonomy group: {candidate.group}\n"
            f"- avg_claim_cost: {candidate.avg_cost}\n"
            f"- cost z-score vs other classes: {candidate.zscore}\n"
            f"- fanout_ratio (n_rows / n_distinct): {candidate.fanout_ratio}\n"
            f"- distinct encounters: {candidate.n_distinct}\n"
        )
        parts = [
            self._knowledge(candidate),   # retrieved metadata (ontology / taxonomy / contract)
            self._feedback_block(candidate),  # human corrections read back as grounding
            evidence,
            _TRIAGE_INSTRUCTIONS,
        ]
        return "\n\n".join(p for p in parts if p)

    def triage(self, candidate: Candidate) -> TriageVerdict:
        from patient_360.semantic.llm import Message

        msgs = [Message("user", self._prompt(candidate))]
        last_exc: Exception | None = None
        # Retry once with a nudged temperature: a reasoning model can return empty content
        # (all budget spent thinking) on the first pass; a second attempt usually emits the JSON.
        for attempt in range(2):
            try:
                reply = self.llm.complete(
                    msgs, temperature=0.0 if attempt == 0 else 0.5, max_tokens=self.max_tokens
                )
                data = _extract_json(reply)
                classification = str(data.get("classification", "uncertain")).lower()
                if classification not in {"real", "artifact", "uncertain"}:
                    classification = "uncertain"
                return TriageVerdict(
                    signature=candidate.signature,
                    encounter_class=candidate.encounter_class,
                    group=candidate.group,
                    classification=classification,
                    rationale=str(data.get("rationale", "")).strip(),
                    recommended_action=str(data.get("recommended_action", "")).strip(),
                    knowledge_used=[str(x) for x in data.get("knowledge_used", [])],
                )
            except Exception as exc:  # noqa: BLE001 - retry once, then degrade to uncertain
                last_exc = exc
        return TriageVerdict(
            signature=candidate.signature,
            encounter_class=candidate.encounter_class,
            group=candidate.group,
            classification="uncertain",
            rationale=f"triage unavailable ({type(last_exc).__name__}: {last_exc})",
            recommended_action="manual review",
        )


# --------------------------------------------------------------------------- run + deliver
def load_prior_artifacts(out_dir: str | Path) -> set[str]:
    """Signatures previously judged ARTIFACT — so we don't re-triage/re-alert them (feedback)."""
    manifest = Path(out_dir) / "run_manifest.json"
    if not manifest.is_file():
        return set()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return set(data.get("suppressed_signatures", []))


FEEDBACK_FILE = "feedback.jsonl"


def load_feedback(out_dir: str | Path) -> list[Feedback]:
    """Read all human corrections recorded for this workflow (used as RAG grounding next run)."""
    path = Path(out_dir) / FEEDBACK_FILE
    if not path.is_file():
        return []
    items: list[Feedback] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            items.append(Feedback(**json.loads(line)))
    return items


def record_feedback(out_dir: str | Path, feedback: Feedback) -> Path:
    """Append a human correction and un-suppress that class so the next run re-triages it
    (a correction always means 'look at this again', regardless of the old verdict)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / FEEDBACK_FILE
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(feedback), ensure_ascii=False) + "\n")
    _unsuppress_class(out, feedback.encounter_class)
    return path


def _unsuppress_class(out_dir: str | Path, encounter_class: str) -> None:
    manifest = Path(out_dir) / "run_manifest.json"
    if not manifest.is_file():
        return
    data = json.loads(manifest.read_text(encoding="utf-8"))
    prefix = f"{encounter_class.upper()}:"
    data["suppressed_signatures"] = [
        s for s in data.get("suppressed_signatures", []) if not s.upper().startswith(prefix)
    ]
    manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def run(
    provider: CostProvider,
    reasoner: TriageReasoner,
    *,
    groups: dict[str, str] | None = None,
    prior_artifacts: set[str] | None = None,
    now: str | None = None,
    z_threshold: float = 1.0,
) -> TriageReport:
    """Detect -> dedupe against known artifacts -> AI triage each candidate."""
    groups = groups if groups is not None else load_encounter_groups()
    prior = prior_artifacts or set()
    stamp = now or _utc_now()

    candidates = detect(provider.cost_by_class(), groups, z_threshold=z_threshold)
    fresh, skipped = [], []
    for c in candidates:
        (skipped if c.signature in prior else fresh).append(c)

    verdicts = [reasoner.triage(c) for c in fresh]
    return TriageReport(
        generated_at=stamp,
        candidates=fresh,
        verdicts=verdicts,
        skipped_known_artifacts=[c.signature for c in skipped],
    )


def deliver(report: TriageReport, out_dir: str | Path | None = None) -> Path:
    """Output workflows: write alerts / suppressed / report / feedback manifest."""
    out = Path(out_dir) if out_dir is not None else DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)

    def _dump(name: str, payload: object) -> None:
        (out / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    _dump("alerts.json", [asdict(v) for v in report.alerts])
    _dump("suppressed.json", [asdict(v) for v in report.suppressed])
    _dump("report.json", [asdict(c) for c in report.candidates])
    # Accumulate artifact signatures across runs (so we don't re-alert a known artifact), but
    # drop any signature that was judged REAL this run — a flip back to real must re-alert.
    prior = load_prior_artifacts(out)
    alert_sigs = {v.signature for v in report.alerts}
    suppressed_sigs = (
        prior | {v.signature for v in report.suppressed} | set(report.skipped_known_artifacts)
    ) - alert_sigs
    _dump(
        "run_manifest.json",
        {
            "generated_at": report.generated_at,
            "candidate_count": len(report.candidates),
            "alerts": len(report.alerts),
            "suppressed": len(report.suppressed),
            "skipped_known_artifacts": report.skipped_known_artifacts,
            "verdicts": [asdict(v) for v in report.verdicts],
            "suppressed_signatures": sorted(suppressed_sigs),
        },
    )
    return out


def _utc_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- interactive UI
_ICON = {"real": "🔺", "artifact": "🟡", "uncertain": "❔"}


def _render_verdict(cand: Candidate, v: TriageVerdict, *, echo=print) -> None:
    applied = "   (applied your feedback)" if "human_feedback" in v.knowledge_used else ""
    echo(f"\n{_ICON.get(v.classification, '·')} {v.classification.upper()} — "
         f"{v.group} / {cand.encounter_class}{applied}")
    echo(f"   avg claim cost ${cand.avg_cost}  ·  fanout {cand.fanout_ratio}  ·  z {cand.zscore}")
    if v.rationale:
        echo(f"   why:    {v.rationale}")
    if v.recommended_action:
        echo(f"   action: {v.recommended_action}")


def render_report(report: TriageReport, *, echo=print) -> None:
    """Concise console output: the flagged cost anomaly, the AI verdict, and the action."""
    echo(f"\nCost Anomaly Triage · {report.generated_at}")
    if not report.verdicts:
        echo("  ✅ No cost anomalies to triage.")
        return
    for cand, v in zip(report.candidates, report.verdicts):
        _render_verdict(cand, v, echo=echo)


def review_feedback(report: TriageReport, out_dir: str | Path, *, prompt=input, echo=print) -> int:
    """Ask (per candidate) whether the verdict is right; record corrections. Returns #recorded.

    Injectable ``prompt``/``echo`` keep it unit-testable.
    """
    recorded = 0
    for cand, v in zip(report.candidates, report.verdicts):
        try:
            choice = prompt("\nIs this verdict correct? [Enter=yes  w=wrong] ").strip().lower()
        except EOFError:
            break
        if choice not in {"w", "wrong", "n", "no"}:
            continue
        try:
            note = prompt("   what's wrong? (tell the AI what to correct) ").strip()
        except EOFError:
            note = ""
        if not note:
            echo("   (no note given — left unchanged)")
            continue
        record_feedback(
            out_dir,
            Feedback(
                encounter_class=cand.encounter_class,
                note=note,
                group=cand.group,
                created_at=_utc_now(),
            ),
        )
        recorded += 1
        echo(f"   ✔ noted — the AI will correct {cand.encounter_class} on the next pass")
    return recorded


# --------------------------------------------------------------------------- CLI
def preflight_llm(llm: object) -> str | None:
    """Return a human-readable message if the triage LLM can't be reached, else None.

    A tiny 1-token ping so we fail fast with a clear reason (unreachable local server, bad key,
    wrong base) instead of every candidate coming back UNCERTAIN with a raw stack error.
    """
    from patient_360.semantic.llm import Message

    try:
        llm.complete([Message("user", "ping")], max_tokens=1)
        return None
    except Exception as exc:  # noqa: BLE001 - surface any connectivity/auth failure cleanly
        base = (
            os.environ.get("LLM_API_BASE")
            or os.environ.get("LLM_BASE_URL")
            or "(provider default)"
        )
        model = os.environ.get("LLM_MODEL", "anthropic/claude-opus-5")
        return (
            f"LLM endpoint unreachable — model={model}  base={base}\n"
            f"   {type(exc).__name__}: {exc}\n"
            f"   Start your local server (or fix LLM_MODEL / LLM_API_BASE / LLM_API_KEY), "
            f"then re-run."
        )


def build_reasoner(out_dir: str | Path | None = None) -> LLMTriageReasoner:
    """Wire the live reasoner: LiteLLM (any provider via LLM_MODEL) + RAG + recorded feedback."""
    from patient_360.knowledge.retriever import load_default_retriever
    from patient_360.semantic.llm import build_llm_from_env

    try:
        retriever = load_default_retriever()
    except FileNotFoundError:
        from patient_360.knowledge.index import build_default_index
        from patient_360.knowledge.retriever import Retriever

        retriever = Retriever(build_default_index())
    feedback = load_feedback(out_dir or DEFAULT_OUT)
    return LLMTriageReasoner(build_llm_from_env(), retriever, feedback=feedback)


def _cli_run(args: object) -> int:
    import sys

    out_dir = getattr(args, "out", None) or DEFAULT_OUT
    # Live Gold from the pipeline (Spark/Unity Catalog); FIXTURE=1 is a tiny dev/test sample.
    if args.fixture:
        provider: CostProvider = FixtureCostProvider(args.fixture)
    else:
        provider = SparkCostProvider()
    def _once(reasoner=None):
        report = run(
            provider,
            reasoner or build_reasoner(out_dir),   # reloads any recorded feedback each time
            prior_artifacts=load_prior_artifacts(out_dir),
            z_threshold=args.z,
        )
        deliver(report, out_dir)
        return report

    # Fail fast with a clear message if the triage LLM isn't reachable.
    reasoner = build_reasoner(out_dir)
    problem = preflight_llm(reasoner.llm)
    if problem:
        print(f"\n⚠ {problem}")
        return 1

    report = _once(reasoner)
    render_report(report)

    interactive = (
        not getattr(args, "no_review", False)
        and sys.stdin.isatty()
        and sys.stdout.isatty()
    )
    if interactive:
        if review_feedback(report, out_dir):
            print(
                "\n💾 Feedback saved. Re-run the same command — the AI will apply it next time."
            )
    elif report.verdicts and not getattr(args, "no_review", False):
        print(
            "\nTip: correct a verdict with "
            "`make cost-triage-feedback CLASS=<class> VERDICT=real|artifact NOTE=\"...\"`"
        )
    return 0


def _cli_feedback(args: object) -> int:
    out_dir = getattr(args, "out", None) or DEFAULT_OUT
    cls = args.encounter_class.upper()
    fb = Feedback(
        encounter_class=cls,
        correct_classification=args.correct,
        note=args.note,
        group=load_encounter_groups().get(cls, ""),
        created_at=_utc_now(),
    )
    path = record_feedback(out_dir, fb)
    print(f"Recorded feedback: {cls} should be '{fb.correct_classification}'"
          + (f" — {fb.note}" if fb.note else ""))
    print(f"  appended to: {path}")
    print("  the next `cost-triage run` will read this back into the AI prompt as authoritative.")
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog="python -m ai_workflows.cost_triage")
    sub = parser.add_subparsers(dest="command")

    p_run = sub.add_parser("run", help="run the triage workflow (detect -> AI triage -> deliver)")
    p_run.add_argument(
        "--fixture", nargs="?", const=str(DEFAULT_FIXTURE), default=None,
        help="run from a cost fixture (no Spark); optional path overrides the default fixture",
    )
    p_run.add_argument("--out", default=None, help=f"output dir (default {DEFAULT_OUT})")
    p_run.add_argument("--z", type=float, default=1.0, help="cost z-score threshold")
    p_run.add_argument(
        "--no-review", action="store_true",
        help="skip the interactive feedback prompt (for CI / non-interactive runs)",
    )
    p_run.set_defaults(func=_cli_run)

    p_fb = sub.add_parser("feedback", help="record a human correction the AI will use next run")
    p_fb.add_argument("--class", dest="encounter_class", required=True, help="encounter class")
    p_fb.add_argument(
        "--correct", required=True, choices=["real", "artifact"],
        help="the correct classification a human asserts",
    )
    p_fb.add_argument("--note", default="", help="why (cited back to the AI)")
    p_fb.add_argument("--out", default=None)
    p_fb.set_defaults(func=_cli_feedback)

    # default to `run` so `python -m ai_workflows.cost_triage --fixture` keeps working
    if not argv or argv[0] not in {"run", "feedback", "-h", "--help"}:
        argv = ["run", *argv]
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

