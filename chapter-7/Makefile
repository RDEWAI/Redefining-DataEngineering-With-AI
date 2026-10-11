.PHONY: help dev-setup install-plugins uninstall-marketplaces test test-unit validate-ingestion validate-silver validate-gold lint format clean eval-dev-trigger eval-dev-validators eval-dev-generator eval-dev

help: ##@ Show available commands
	@echo "Chapter 7: Gold Layer — Agent Chain (BA -> ... -> Developer)"
	@echo ""
	@echo "=== Setup ==="
	@echo "  dev-setup              - Install dependencies with UV"
	@echo "  install-plugins        - Clean install: all 8 plugins from the local marketplace"
	@echo "  uninstall-marketplaces - Remove any rdewai marketplaces (ch4/ch5/ch6/ch7) if present"
	@echo "  clean                  - Remove generated files and caches"
	@echo ""
	@echo "=== Artifact Operations ==="
	@echo "  validate-ingestion   - Validate Bronze ingestion framework against the LLD"
	@echo "  validate-silver      - Validate Silver layer code + contracts + DQ rules"
	@echo "  validate-gold        - Validate Gold layer code + contracts + DQ rules"
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
PLUGINS := ba-plugin architect-plugin data-modeler-plugin mapping-analyst-plugin dq-engineer-plugin technical-lead-plugin scrum-master-plugin developer-plugin

install-plugins: uninstall-marketplaces ##@ Clean install: all 8 plugins from the local marketplace
	@echo "Adding local marketplace..."
	claude plugin marketplace add ./
	@for p in $(PLUGINS); do \
		echo "Installing $$p@$(MARKETPLACE)..."; \
		claude plugin install $$p@$(MARKETPLACE); \
	done
	@echo "All chapter-7 Claude plugins installed."

uninstall-marketplaces: ##@ Remove all rdewai marketplaces (idempotent)
	@for mp in $(STALE_MARKETPLACES); do \
		echo "Removing marketplace $$mp (if present)..."; \
		claude plugin marketplace remove $$mp 2>/dev/null || true; \
	done

test: ##@ Run all tests
	uv run pytest patient_360/tests/ -v

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
