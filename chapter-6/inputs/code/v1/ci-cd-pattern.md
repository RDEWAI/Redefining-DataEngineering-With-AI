---
Version: 1.0
Status: Approved
Topic: GitHub Actions — lint → test → package → deploy workflow
---

# CI/CD Pattern

## Purpose

One GitHub Actions workflow per project, with stages that fail fast:
lint before test, test before package, package before deploy. Every
PR runs the full pipeline; `main` pushes also trigger the deploy job.
Reproducibility rests on pinned `uv.lock` and pinned action versions.

## Pattern

- **One workflow file per project** — `.github/workflows/ci.yml` in
  the project root.
- **Matrix on Python version** — matches `pyproject.toml`
  `requires-python` range (e.g. 3.11, 3.12, 3.13).
- **Pinned action SHAs** — `actions/checkout@v5`, `astral-sh/setup-uv@v4`;
  use the latest **major**, not `@main`.
- **Cache `uv` downloads** — `setup-uv` handles it; explicit
  `actions/cache` isn't needed.
- **Stages** — `lint` (ruff), `test` (pytest unit), `test-integration`
  (pytest `-m integration`, optional on PRs via label),
  `package` (build sdist + wheel), `deploy` (push artifact,
  protected by `environment:`).
- **Fail-fast job dependencies** — `test` needs `lint`; `deploy` needs
  `test` + `test-integration`. Use `needs:` not time-based waits.
- **Secrets via GitHub environments** — never in workflow files. Use
  `environment: production` to gate deploys.
- **Concurrency guard** — `cancel-in-progress: true` on PRs so a
  force-push kills the prior run.

## Key APIs

- GitHub Actions — `actions/checkout@v5`, `astral-sh/setup-uv@v4`,
  `actions/setup-python@v6`, `actions/upload-artifact@v5`.
- UV — `uv sync --all-groups`, `uv run pytest`, `uv build`.

## Illustrative snippet

```yaml
# .github/workflows/ci.yml
name: ci
on:
  pull_request:
  push:
    branches: [main]

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --all-groups
      - run: uv run ruff check src/ pipelines/ tests/ scripts/
      - run: uv run ruff format --check .

  test:
    needs: lint
    runs-on: ubuntu-latest
    strategy:
      matrix: { python-version: ["3.11", "3.12", "3.13"] }
    steps:
      - uses: actions/checkout@v5
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --all-groups --python ${{ matrix.python-version }}
      - run: uv run pytest tests/ -v --tb=short

  package:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: astral-sh/setup-uv@v4
      - run: uv build
      - uses: actions/upload-artifact@v5
        with:
          name: dist
          path: dist/

  deploy:
    needs: package
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/download-artifact@v5
        with: { name: dist, path: dist/ }
      - run: echo "deploy dist/ to runtime (Databricks asset bundle / S3 / PyPI)"
```

## Common pitfalls

- `uses: actions/checkout@main` — ties reproducibility to upstream
  HEAD; pin to a major version.
- Installing deps via `pip install -r requirements.txt` — diverges
  from local `uv sync`. Use UV in CI too.
- `continue-on-error: true` on `lint` or `test` — green checkmarks
  that hide real failures. Let the job fail.
- Running integration tests on every PR — slow and flaky; gate on a
  label (`integration-ok`) or a manual workflow dispatch.
- Committing `dist/` — artifacts are ephemeral. Build in CI, upload,
  deploy; never vendor build output.

## PR lifecycle workflows

Chapter-6 adds three workflow files that mirror the post-DE-work lifecycle
demonstrated by the [`pr-process`](../../developer-plugin/skills/pr-process/SKILL.md)
skill. The local skill and the CI workflows share **one teardown driver**
(see [`teardown-pattern.md`](teardown-pattern.md)), so the same destroy
logic runs whether the engineer ran `pr-process` on their laptop or the
PR was approved via the GitHub UI.

| Workflow | Trigger | Owns | Pairs with |
|---|---|---|---|
| `pr-preview.yml` | `pull_request: opened/synchronize/reopened` | Bring up the docker-compose stack, run integration smoke, **always** tear down. | `pr-process` Phase 1 readiness — the same smoke that runs locally also runs in CI. |
| `sandbox-cleanup.yml` | `pull_request: closed` (merged or not) | Invoke the shared teardown driver, upload the summary JSON as an artifact. | `pr-process` Phase 4 — same driver, same JSON schema. |
| `promote.yml` | `push: tags: ['v*']` + `workflow_dispatch` | Build sdist/wheel, deploy to STAGING automatically on tag, then PROD behind a required-reviewer environment gate. | `_infra/cd/config/{DEV,STAGING,PROD}.yaml`. |

### Why both local and CI teardown?

The local `pr-process` skill destroys the sandbox on **the engineer's
machine** the moment the PR is approved — that's the immediate
cost/state benefit. `sandbox-cleanup.yml` is the **safety net**: if the
PR was approved by another reviewer in the GitHub UI, or the engineer
never ran the skill, or the laptop is closed, the CI workflow still
runs the same driver on a fresh runner. The runner's docker daemon is
ephemeral, so the practical effect is verifying that the driver works
against a clean state.

Hard rule: **never** inline `docker compose down` directly in
`sandbox-cleanup.yml`. Always call the driver script under
`developer-plugin/skills/pr-process/scripts/teardown_drivers/`. That
contract is what lets readers swap in a `cloud-databricks` driver
later without rewriting CI.

### Illustrative snippet — `pr-preview.yml`

```yaml
name: pr-preview
on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  preview:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --all-groups
      - run: docker compose -f patient_360/_infra/docker/docker-compose.yml up -d --wait
      - run: uv run pytest patient_360/tests/integration -m "not e2e" --tb=short
      - name: Always tear down — never leak volumes on the runner
        if: always()
        run: docker compose -f patient_360/_infra/docker/docker-compose.yml down -v --remove-orphans
```

The `if: always()` step is the single most important convention in this
workflow. A failing test must still tear the stack down or the runner
inherits orphan volumes for the next job.

## References

- [`dependency-management.md`](dependency-management.md)
- [`test-pattern.md`](test-pattern.md) (pytest markers CI uses)
- [`teardown-pattern.md`](teardown-pattern.md) — driver contract shared with `pr-process`.
- [`docker-compose-conventions.md`](docker-compose-conventions.md) — services + named volumes the teardown driver removes.
- GitHub Actions docs: https://docs.github.com/en/actions
- `astral-sh/setup-uv`: https://github.com/astral-sh/setup-uv
