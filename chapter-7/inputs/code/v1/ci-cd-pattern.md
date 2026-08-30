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

## References

- [`dependency-management.md`](dependency-management.md)
- [`test-pattern.md`](test-pattern.md) (pytest markers CI uses)
- GitHub Actions docs: https://docs.github.com/en/actions
- `astral-sh/setup-uv`: https://github.com/astral-sh/setup-uv
