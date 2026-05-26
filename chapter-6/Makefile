.PHONY: help dev-setup install-plugins install-plugins-ch4 install-plugins-ch6 test test-unit validate-silver validate-gold lint format clean eval eval-e2e eval-update-goldens

help: ##@ Show available commands
	@echo "Chapter 6: Silver and Gold Layer Implementation"
	@echo ""
	@echo "=== Setup ==="
	@echo "  dev-setup            - Install dependencies with UV"
	@echo "  install-plugins      - Install chapter-4 planning plugins + chapter-6 developer-plugin (atomic)"
	@echo "  install-plugins-ch4  - Install chapter-4 planning plugins"
	@echo "  install-plugins-ch6  - Install chapter-6 developer-plugin (Bronze + Silver + Gold)"
	@echo "  clean                - Remove generated files and caches"
	@echo ""
	@echo "=== Artifact Operations ==="
	@echo "  validate-silver      - Validate Silver layer code + contracts + DQ rules"
	@echo "  validate-gold        - Validate Gold layer code + contracts + DQ rules"
	@echo ""
	@echo "=== Testing & Quality ==="
	@echo "  test                 - Run all tests"
	@echo "  eval                 - Run skill evals (skill-creator + trigger + golden, no docker)"
	@echo "  eval-e2e             - Run end-to-end evals (brings up docker-compose stack)"
	@echo "  eval-update-goldens  - Re-baseline goldens (SKILL=<name>, e.g. SKILL=create-pipeline)"
	@echo "  lint                 - Run ruff linter"
	@echo "  format               - Auto-format code"

dev-setup: ##@ Install dependencies
	@echo "Setting up Chapter 6 development environment..."
	uv sync
	@echo "Done. Dependencies installed."

# --- Claude plugin installation -----------------------------------------------
# Chapter-6 is atomic: it ships its own developer-plugin (Bronze + Silver + Gold).
# The chapter-5 developer-plugin shares the same name and CANNOT be installed
# simultaneously with chapter-6's — slash-command namespace collision.
# Planning plugins still live in chapter-4 (no name collisions there).
CH4_PLUGINS := ba-plugin architect-plugin data-modeler-plugin mapping-analyst-plugin dq-engineer-plugin technical-lead-plugin
CH6_PLUGINS := developer-plugin

install-plugins: install-plugins-ch4 install-plugins-ch6 ##@ Install chapter-4 planning + chapter-6 developer
	@echo "All chapter-6 Claude plugins installed."
	@echo "Note: chapter-5/developer-plugin shares this name. Do NOT install ../chapter-5 marketplace concurrently."

install-plugins-ch4: ##@ Install chapter-4 planning plugins
	@echo "Adding chapter-4 marketplace..."
	claude plugin marketplace add ../chapter-4/
	@for p in $(CH4_PLUGINS); do \
		echo "Installing $$p@rdewai-plugins..."; \
		claude plugin install $$p@rdewai-plugins; \
	done

install-plugins-ch6: ##@ Install chapter-6 developer-plugin
	@echo "Adding chapter-6 marketplace..."
	claude plugin marketplace add ./
	@for p in $(CH6_PLUGINS); do \
		echo "Installing $$p@rdewai-chapter6-plugins..."; \
		claude plugin install $$p@rdewai-chapter6-plugins; \
	done

test: ##@ Run all tests
	uv run pytest tests/ -v -m "not e2e"

eval: ##@ Run skill evals (skill-creator + trigger + golden, no docker)
	uv run pytest tests/test_skill_evals.py tests/test_pipeline_skill_templates.py -v

eval-e2e: ##@ Run end-to-end evals (brings up docker-compose stack)
	uv run pytest tests/ -v -m e2e

eval-update-goldens: ##@ Re-baseline goldens (SKILL=<name> FROM=<dir>)
	@if [ -z "$(SKILL)" ] || [ -z "$(FROM)" ]; then \
		echo "usage: make eval-update-goldens SKILL=<name> FROM=<artifacts-dir>"; \
		echo "  re-runs the skill against your fixture first, then copies the"; \
		echo "  captured outputs over the committed goldens at evals/goldens/<SKILL>/."; \
		exit 1; \
	fi
	uv run python -m evals.harness.golden_diff --update "$(SKILL)" --from "$(FROM)"

validate-silver: ##@ Validate Silver layer artifacts
	uv run python developer-plugin/skills/validate-silver/scripts/validate_silver.py --all patient_360/

validate-gold: ##@ Validate Gold layer artifacts
	uv run python developer-plugin/skills/validate-gold/scripts/validate_gold.py --all patient_360/

lint: ##@ Run ruff linter
	uv run ruff check developer-plugin/ tests/

format: ##@ Auto-format code
	uv run ruff format developer-plugin/ tests/

clean: ##@ Remove generated files and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned."
