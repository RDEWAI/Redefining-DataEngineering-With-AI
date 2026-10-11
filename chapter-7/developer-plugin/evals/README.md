# developer-plugin eval suite

Runnable evals for the `claude plugin eval` runner (Claude Code >= 2.1.28x).
Deterministic graders (`tool_used`, `tool_order`, `regex`, `file_exists`) carry
the score; a single `llm` grader is used only where a regex cannot express the
criterion (citation of a pattern doc).

## Tiers (tags)

| Tag | Cases | Needs | What it proves |
|---|---|---|---|
| `trigger` | 6 | nothing | A natural-language prompt routes to the right skill and not to a sibling. One negative case proves an unrelated request fires no skill. |
| `validator` | 4 | `--scaffold --allow-tools Bash` | `validate-ingestion` / `validate-dag` run their discovery and validator scripts in a fixture workspace and report the expected CRITICAL / PASS / FAIL strings. Two cases inject a known defect. |
| `generator` | 1 | `--scaffold --allow-tools Bash Write Edit` | `create-dag` regenerates the hourly DAG from the approved LLD for STORY-02-006, self-validates, and runs the AC verifier. Expensive; run on demand. |

## Why scaffolding

Every run executes in a fresh temp directory with only this plugin loaded.
Developer skills locate their workspace by walking up from `$PWD` looking for
`outputs/stories/` plus a project with `pyproject.toml` + `src/<name>/`, so each
scaffolded case calls `scaffold/build_workspace.sh`, which copies an allow-list
of the chapter (outputs, inputs/code, the project minus `uc-warehouse/`) and
runs `uv sync --frozen` so `uv run python` resolves. It never copies runtime
data or secrets. `--defect NAME` applies `scaffold/defects/NAME.sh` after the
copy; `--drop-dag` removes the shipped DAG for the generator case.

The builder always excludes `.skill-arg` / `.skill-paths`. A stale `.skill-arg`
at the chapter root silently overrides every skill's target resolution.

## Running

From `chapter-7/`:

```bash
make eval-dev-trigger      # ~2 min, ~$1.50, no sandboxed Bash needed
make eval-dev-validators   # scaffold + Bash
make eval-dev-generator    # scaffold + Bash/Write/Edit, cost-capped
make eval-dev              # full suite, CI shape (threshold 0.8, JSON out)
```

Iterate on one case cheaply:

```bash
claude plugin eval ./developer-plugin --trust-plugin --no-publish \
  --case validate-dag-relative-path --runs 1 --ablation none \
  --scaffold --allow-tools Bash --keep-temp
```

Results land in `evals/results/<timestamp>/` (gitignored): `report.html` and
`aggregate-result.json` (`schemaVersion: 1`).

## Grader conventions

- `tool_order` matches tool *names*, not call inputs, so "discovery before validator" cannot be expressed with it.
- `uv` panics inside the macOS eval sandbox (system-configuration crate). Scaffolded cases tell the agent via `append_system_prompt` to use the fixture `.venv/bin/python` in place of `uv run python`.
- `max: 0` graders must also set `min: 0` (the default `min` is 1, which makes
  "expected 1..0" unsatisfiable).
- "Must not fire" graders carry `arm: both` so they are scored in the no-plugin
  baseline arm too; `tool_used: Skill` positives are with-arm only by design.
- Expected strings come from dry-running the validator scripts against the
  defect fixture, not from guessing:
  - validate_ingestion.py prints `CRITICAL: N issue(s)` and `Result: PASS|FAIL`
  - validate_dag.py prints `Summary: N critical, M warnings` and rule ids like `DAG-PATHS-001`

## Machine prerequisites for Bash-granting tiers

The runner's Bash sandbox refuses to start if `~/.docker` contains a symbolic
link inside it (Docker Desktop's `cli-plugins/` entries are the usual cause).
Check with `find ~/.docker -type l`. Keep that store as one plain directory
(its root may itself be a link). Setting `DOCKER_CONFIG` does not bypass the
check. The `trigger` tier is unaffected.

## Known findings from the first runs (2026-10-01)

- `banner` fails in every scaffolded case: neither validate-ingestion nor
  validate-dag runs the Phase 0.a resolver (`scripts/resolve_skill_arg.sh`) or
  prints the mandated `RESOLVED TARGET:` line. Skill-instruction gap, kept as a
  failing grader on purpose.
- `create-dag-from-lld`: the skill ignored the STORY-02-006 scope and built the
  full Bronze+Silver+Gold DAG, editing docker-compose.yml and tests/silver on the
  way. The two `story-scope-*` graders now catch this.
- AC5 of STORY-02-006 (pytest on the DAG) skips in the sandbox because the fixture
  venv has no airflow/pyspark. Not gradable here by design.
