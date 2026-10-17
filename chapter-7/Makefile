.PHONY: rca-runner rca-runner-smoke help dev-setup install-plugins uninstall-marketplaces test test-unit validate-ingestion validate-silver validate-gold lint format clean eval-dev-trigger eval-dev-validators eval-dev-generator eval-dev rca eval-sre-trigger eval-sre-rca

help: ##@ Show available commands
	@echo "Chapter 7: Gold Layer — Agent Chain (BA -> ... -> Developer)"
	@echo ""
	@echo "=== Setup ==="
	@echo "  dev-setup              - Install dependencies with UV"
	@echo "  install-plugins        - Clean install: all 9 plugins from the local marketplace"
	@echo "  uninstall-marketplaces - Remove any rdewai marketplaces (ch4/ch5/ch6/ch7) if present"
	@echo "  clean                  - Remove generated files and caches"
	@echo ""
	@echo "=== Artifact Operations ==="
	@echo "  validate-ingestion   - Validate Bronze ingestion framework against the LLD"
	@echo "  validate-silver      - Validate Silver layer code + contracts + DQ rules"
	@echo "  validate-gold        - Validate Gold layer code + contracts + DQ rules"
	@echo ""
	@echo "=== Operations (sre-plugin) ==="
	@echo "  rca ALERT=<target>   - Alert intake + evidence collection for an RCA (target: alert json | ALERT-id | latest | dag/task)"
	@echo "  eval-sre-trigger     - Eval: rca skill routing"
	@echo "  eval-sre-rca         - Eval: offline RCA case on a pre-collected evidence bundle"
	@echo ""
	@echo "=== Testing & Quality ==="
	@echo "  test                 - Run all tests"
	@echo "  lint                 - Run ruff linter"
	@echo "  format               - Auto-format code"

dev-setup: ##@ Install dependencies
	@echo "Setting up Chapter 7 development environment..."
	uv sync
	@echo "Done. Dependencies installed."

# --- Claude plugin installation -----------------------------------------------
# Chapter-7 is self-contained: all eight plugins ship from the single local
# marketplace (.claude-plugin/marketplace.json). No cross-chapter sourcing and
# no name collisions — there is exactly one developer-plugin here.
MARKETPLACE := rdewai-chapter7-plugins
# Stale rdewai marketplaces from earlier chapters are removed first so the
# chapter-7 marketplace is the only source (avoids duplicate-plugin conflicts).
STALE_MARKETPLACES := rdewai-plugins rdewai-chapter5-plugins rdewai-chapter6-plugins rdewai-chapter7-plugins
PLUGINS := ba-plugin architect-plugin data-modeler-plugin mapping-analyst-plugin dq-engineer-plugin technical-lead-plugin scrum-master-plugin developer-plugin sre-plugin

install-plugins: uninstall-marketplaces ##@ Clean install: all 9 plugins from the local marketplace
	@echo "Adding local marketplace..."
	claude plugin marketplace add ./
	@for p in $(PLUGINS); do \
		echo "Installing $$p@$(MARKETPLACE)..."; \
		claude plugin install $$p@$(MARKETPLACE); \
	done
	@echo "All chapter-7 Claude plugins installed (9, incl. sre-plugin)."

uninstall-marketplaces: ##@ Remove all rdewai marketplaces (idempotent)
	@for mp in $(STALE_MARKETPLACES); do \
		echo "Removing marketplace $$mp (if present)..."; \
		claude plugin marketplace remove $$mp 2>/dev/null || true; \
	done

test: ##@ Run all tests (project + sre-plugin)
	uv run pytest patient_360/tests/ sre-plugin -v

validate-ingestion: ##@ Validate Bronze ingestion framework
	uv run python developer-plugin/skills/validate-ingestion/scripts/validate_ingestion.py

validate-silver: ##@ Validate Silver layer artifacts
	uv run python developer-plugin/skills/validate-silver/scripts/validate_silver.py --project-root patient_360/

validate-gold: ##@ Validate Gold layer artifacts
	uv run python developer-plugin/skills/validate-gold/scripts/validate_gold.py --project-root patient_360/

lint: ##@ Run ruff linter
	uv run ruff check developer-plugin/ patient_360/

format: ##@ Auto-format code
	uv run ruff format developer-plugin/ patient_360/

clean: ##@ Remove generated files and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned."

# ---- developer-plugin evals (claude plugin eval) ----
EVAL_COMMON = --trust-plugin --no-publish --judge-model claude-haiku-4-5

eval-dev-trigger: ##@ Eval: skill routing only (cheap, no Bash sandbox)
	claude plugin eval ./developer-plugin $(EVAL_COMMON) --tag trigger --runs 1 --ablation none

eval-dev-validators: ##@ Eval: validate-* skills on a scaffolded fixture
	claude plugin eval ./developer-plugin $(EVAL_COMMON) --tag validator --scaffold --allow-tools Bash

eval-dev-generator: ##@ Eval: create-dag end-to-end (expensive, cost-capped)
	claude plugin eval ./developer-plugin $(EVAL_COMMON) --tag generator --scaffold --allow-tools Bash Write Edit --max-cost-usd 10

eval-dev: ##@ Eval: full developer-plugin suite, CI shape
	claude plugin eval ./developer-plugin $(EVAL_COMMON) --scaffold --allow-tools Bash Write Edit --threshold 0.8 --json evals-result.json

# ---- sre-plugin: alert-driven RCA --------------------------------------------
# `make rca` runs the deterministic halves of the rca skill (intake + evidence
# collection) so the bundle is on disk; the analysis itself runs in Claude via
# /sre-plugin:rca <target>. ALERT defaults to the newest failed task in Airflow.
ALERT ?= latest
rca: ##@ Alert intake + read-only evidence collection into outputs/rca/v1/<alert_id>/
	@set -e; out=$$(python3 sre-plugin/skills/rca/scripts/find_alert.py "$(ALERT)"); echo "$$out"; \
	p=$$(echo "$$out" | python3 -c 'import json,sys; print(json.load(sys.stdin)["alert_path"])'); \
	python3 sre-plugin/skills/rca/scripts/collect_evidence.py --alert "$$p" $(RCA_FLAGS)

eval-sre-trigger: ##@ Eval: rca skill routing (cheap, no Bash sandbox)
	claude plugin eval ./sre-plugin $(EVAL_COMMON) --tag trigger --runs 1 --ablation none

RCA_RUNNER_PORT ?= 8090
rca-runner: ##@ Start the incident webhook receiver that runs /sre-plugin:rca headless and comments the result on the incident
	RCA_RUNNER_PORT=$(RCA_RUNNER_PORT) python3 sre-plugin/service/rca_runner.py --workspace-root . $(RCA_RUNNER_FLAGS)

rca-runner-smoke: ##@ Dry-run the runner end to end with a synthetic alert (no claude, no stack)
	@python3 sre-plugin/service/smoke.py

eval-sre-rca: ##@ Eval: offline RCA on a pre-collected evidence bundle (scaffold + Bash/Write)
	claude plugin eval ./sre-plugin $(EVAL_COMMON) --tag rca --scaffold --allow-tools Bash Write --max-cost-usd 10
