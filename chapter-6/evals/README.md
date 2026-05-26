# Chapter-6 Skill Evals

Four eval classes cover the 26 skills shipped by `chapter-6/developer-plugin`:

| Class | What it measures | Where it lives |
|---|---|---|
| **skill-creator** | Description quality, argument-hint clarity, phase coverage | `evals/skill-creator/<skill>.eval.md` |
| **golden-output regression** | Generated files match committed goldens (whitespace + YAML aware) | `evals/goldens/<skill>/` + `tests/test_*.py` harness invocations |
| **trigger-accuracy** | Claude picks the right skill for a given prompt (collision detection) | `evals/trigger-prompts/prompts.jsonl` |
| **end-to-end behavioural** | Skill drives a real side-effect (docker stack, gh PR, etc.) | `evals/harness/e2e_sandbox.py`, gated by `@pytest.mark.e2e` |

## Phased rollout

This chapter does not ship full coverage for every skill at once.

- **Phase 1** (this PR) — harness + **5 exemplar skills** fully covered:
  - `pr-process` — the new skill
  - `create-pipeline`, `update-pipeline`, `validate-pipeline` — the CI/CD trio
  - `create-silver` — exemplar of an existing data-generation skill
- **Phase 2** (next PR) — backfill goldens + e2e for `create-gold`,
  `create-ingestion`, `create-dag`, `create-scaffold` and their
  `update-*` / `validate-*` siblings.
- **Phase 3** (next PR) — backfill the remaining utility / orchestrator
  skills: `implement-stories`, `validate-stories`, `complete-stories`,
  `apply-learnings`, `refresh-libraries`, `create-deploy-validation`,
  `create-integration-test`.

The remaining skills ship with **scaffolded** `.eval.md` stubs under
`evals/skill-creator/`. A pre-commit hook enforces the stub presence:
adding a new skill without an eval stub fails the hook.

## Coverage status

| Skill | skill-creator | golden | trigger | e2e |
|---|:-:|:-:|:-:|:-:|
| pr-process | ✅ | ✅ | ✅ | ✅ |
| create-pipeline | ✅ | ✅ | ✅ | ✅ |
| update-pipeline | ✅ | ✅ | ✅ | — |
| validate-pipeline | ✅ | ✅ | ✅ | — |
| create-silver | ✅ | ✅ | ✅ | ✅ |
| create-gold | scaffold | — | scaffold | — |
| update-silver, validate-silver | scaffold | — | scaffold | — |
| update-gold, validate-gold | scaffold | — | scaffold | — |
| create-ingestion, update-ingestion, validate-ingestion | scaffold | — | scaffold | — |
| create-dag, update-dag, validate-dag | scaffold | — | scaffold | — |
| create-scaffold, update-scaffold, validate-scaffold | scaffold | — | scaffold | — |
| create-deploy-validation, create-integration-test | scaffold | — | scaffold | — |
| implement-stories, validate-stories, complete-stories | scaffold | — | scaffold | — |
| apply-learnings, refresh-libraries | scaffold | — | scaffold | — |

(`scaffold` = `.eval.md` stub committed; tests SKIP rather than FAIL.)

## Running

```bash
make eval          # golden + trigger + skill-creator (fast, no docker)
make eval-e2e      # adds the e2e tier (slow, brings up docker-compose)
make eval-update-goldens SKILL=create-pipeline  # re-baseline goldens
```

## Adding a new skill

1. Create `developer-plugin/skills/<name>/SKILL.md`.
2. Add a stub eval at `evals/skill-creator/<name>.eval.md` (the pre-commit
   hook will fail otherwise).
3. Add at least one trigger prompt for the skill in
   `evals/trigger-prompts/prompts.jsonl`.
4. When goldens are ready, drop them under `evals/goldens/<name>/` and
   set `enabled: true` in the eval stub.

## Harness layout

```
evals/
├── harness/
│   ├── __init__.py
│   ├── skill_runner.py    # Invoke a skill in a controlled subprocess
│   ├── golden_diff.py     # YAML/markdown-aware diff vs goldens
│   ├── trigger_eval.py    # Score skill selection against prompts.jsonl
│   └── e2e_sandbox.py     # docker-compose lifecycle harness
├── fixtures/
│   ├── stories/           # Minimal STORY-NN-NNN files
│   └── workspace/         # Tiny patient_360 skeleton for runs
├── goldens/<skill>/       # Expected output files (one folder per skill)
├── trigger-prompts/
│   └── prompts.jsonl      # {prompt, expected_skill, rationale}
└── skill-creator/
    └── <skill>.eval.md    # One per skill (5 filled, 21 scaffolds)
```
