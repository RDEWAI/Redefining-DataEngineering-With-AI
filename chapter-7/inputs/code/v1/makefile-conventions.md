---
Version: 1.0
Status: Approved
Topic: Standard Makefile targets for data-pipeline projects
---

# Makefile Conventions

## Purpose

The `Makefile` is the uniform entry-point for every local-dev workflow
(setup, run a layer, run all layers, test, lint, start/stop supporting
services, clean up). Every generated project exposes the same target
names so engineers switching projects don't need to re-learn commands.

## Pattern

- **Shell vars at top** — `PYTHON := uv run python`,
  `PYTEST := uv run pytest`, `SPARK_PACKAGES := io.delta:delta-spark_2.13:4.3.0,io.unitycatalog:unitycatalog-spark_4.1_2.13:0.5.0,...`
- **`.PHONY` declares all targets** (everything is a command, not a
  file).
- **Targets are grouped by domain prefix**:
  - `dev-*` — local setup
  - `uc-*` — Unity Catalog + Marquez docker lifecycle
  - `bronze` / `silver` / `gold` / `pipeline` — pipeline layers
  - `test` / `test-integration` — pytest runs
  - `lint` / `lint-fix` / `format` — ruff
  - `clean` — remove Spark/Delta local artifacts
- **Layer targets accept `DS=YYYY-MM-DD`** — pass the partition date
  through to `run_local.py`; default to a pinned dev date when absent.

## Required targets

| Target | Purpose |
|---|---|
| `dev-setup` | `uv sync --all-groups` |
| `uc-start` | `docker compose up -d` + run `scripts/uc_init.py` to create catalog/schemas |
| `uc-stop` | `docker compose down` |
| `bronze` / `silver` / `gold` | `$(PYTHON) run_local.py --layer {layer} --ds $(or $(DS),...)` |
| `pipeline` | Run bronze → silver → gold in sequence |
| `test` | `$(PYTEST) tests/ -v` |
| `test-integration` | `$(PYTEST) tests/ -v -m integration` |
| `lint` | `uv run ruff check src/ pipelines/ tests/ scripts/` |
| `lint-fix` | `uv run ruff check --fix src/ pipelines/ tests/ scripts/` |
| `format` | `uv run ruff format src/ pipelines/ tests/ scripts/` |
| `clean` | remove `warehouse/`, `spark-warehouse/`, `metastore_db/`, `__pycache__/` |

## Illustrative snippet

```makefile
.PHONY: dev-setup uc-start uc-stop bronze silver gold pipeline \
        test test-integration lint lint-fix format clean

PYTHON := uv run python
PYTEST := uv run pytest
DEFAULT_DS := 2026-04-24

dev-setup:
	uv sync --all-groups

uc-start:
	docker compose up -d server marquez-db marquez marquez-web
	$(PYTHON) scripts/uc_init.py

uc-stop:
	docker compose down

bronze:
	$(PYTHON) run_local.py --layer bronze --ds $(or $(DS),$(DEFAULT_DS))

silver:
	$(PYTHON) run_local.py --layer silver --ds $(or $(DS),$(DEFAULT_DS))

gold:
	$(PYTHON) run_local.py --layer gold --ds $(or $(DS),$(DEFAULT_DS))

pipeline: bronze silver gold

test:
	$(PYTEST) tests/ -v

lint:
	uv run ruff check src/ pipelines/ tests/ scripts/

lint-fix:
	uv run ruff check --fix src/ pipelines/ tests/ scripts/

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf warehouse/ spark-warehouse/ metastore_db/
```

## Common pitfalls

- Omitting `.PHONY` — a target named `clean` will be skipped if a file
  called `clean` ever appears in the repo.
- Hard-coding a date — use `$(or $(DS),$(DEFAULT_DS))` so callers can
  override via `make bronze DS=2026-05-01`.
- Putting Spark launch commands in the Makefile — they belong in
  `run_local.py` (argparse-driven); the Makefile only invokes the runner.
- Forgetting `uc-start` to call `uc_init.py` — the first `make bronze`
  after `docker compose up -d` fails because no schemas exist.

## References

- `/mvp/Makefile`
- [`docker-compose-conventions.md`](docker-compose-conventions.md)
- [`dependency-management.md`](dependency-management.md)
