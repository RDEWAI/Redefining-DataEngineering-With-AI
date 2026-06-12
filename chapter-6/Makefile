.PHONY: help dev-setup install-plugins install-plugins-ch4 install-plugins-ch5 install-plugins-ch6 uninstall-marketplaces test test-unit validate-silver validate-gold lint format clean

help: ##@ Show available commands
	@echo "Chapter 6: Silver and Gold Layer Implementation"
	@echo ""
	@echo "=== Setup ==="
	@echo "  dev-setup              - Install dependencies with UV"
	@echo "  install-plugins        - Clean install: chapter-4 planning + chapter-5 scrum-master + chapter-6 developer"
	@echo "  install-plugins-ch4    - Install chapter-4 planning plugins"
	@echo "  install-plugins-ch5    - Install chapter-5 scrum-master-plugin only (skip developer to avoid name collision)"
	@echo "  install-plugins-ch6    - Install chapter-6 developer-plugin (Bronze + Silver + Gold)"
	@echo "  uninstall-marketplaces - Remove rdewai-plugins / rdewai-chapter5-plugins / rdewai-chapter6-plugins if present"
	@echo "  clean                  - Remove generated files and caches"
	@echo ""
	@echo "=== Artifact Operations ==="
	@echo "  validate-silver      - Validate Silver layer code + contracts + DQ rules"
	@echo "  validate-gold        - Validate Gold layer code + contracts + DQ rules"
	@echo ""
	@echo "=== Testing & Quality ==="
	@echo "  test                 - Run all tests"
	@echo "  lint                 - Run ruff linter"
	@echo "  format               - Auto-format code"

dev-setup: ##@ Install dependencies
	@echo "Setting up Chapter 6 development environment..."
	uv sync
	@echo "Done. Dependencies installed."

# --- Claude plugin installation -----------------------------------------------
# Chapter-6 is atomic: it ships its own developer-plugin (Bronze + Silver + Gold).
# The chapter-5 developer-plugin shares the same name and CANNOT be installed
# simultaneously with chapter-6's — slash-command namespace collision. We
# therefore source ONLY scrum-master-plugin from chapter-5 and skip its
# developer-plugin. Planning plugins live in chapter-4 (no name collisions).
CH4_MARKETPLACE := rdewai-plugins
CH5_MARKETPLACE := rdewai-chapter5-plugins
CH6_MARKETPLACE := rdewai-chapter6-plugins
CH4_PLUGINS := ba-plugin architect-plugin data-modeler-plugin mapping-analyst-plugin dq-engineer-plugin technical-lead-plugin
CH5_PLUGINS := scrum-master-plugin
CH6_PLUGINS := developer-plugin

install-plugins: uninstall-marketplaces install-plugins-ch4 install-plugins-ch5 install-plugins-ch6 ##@ Clean install: ch4 planning + ch5 scrum-master + ch6 developer
	@echo "All chapter-6 Claude plugins installed."
	@echo "Note: chapter-5/developer-plugin is intentionally skipped (name collision with chapter-6/developer-plugin)."

uninstall-marketplaces: ##@ Remove existing rdewai marketplaces (idempotent)
	@for mp in $(CH4_MARKETPLACE) $(CH5_MARKETPLACE) $(CH6_MARKETPLACE); do \
		echo "Removing marketplace $$mp (if present)..."; \
		claude plugin marketplace remove $$mp 2>/dev/null || true; \
	done

install-plugins-ch4: ##@ Install chapter-4 planning plugins
	@echo "Adding chapter-4 marketplace..."
	claude plugin marketplace add ../chapter-4/
	@for p in $(CH4_PLUGINS); do \
		echo "Installing $$p@$(CH4_MARKETPLACE)..."; \
		claude plugin install $$p@$(CH4_MARKETPLACE); \
	done

install-plugins-ch5: ##@ Install chapter-5 scrum-master-plugin only
	@echo "Adding chapter-5 marketplace..."
	claude plugin marketplace add ../chapter-5/
	@for p in $(CH5_PLUGINS); do \
		echo "Installing $$p@$(CH5_MARKETPLACE)..."; \
		claude plugin install $$p@$(CH5_MARKETPLACE); \
	done
	@echo "Skipping chapter-5/developer-plugin (collides with chapter-6/developer-plugin)."

install-plugins-ch6: ##@ Install chapter-6 developer-plugin
	@echo "Adding chapter-6 marketplace..."
	claude plugin marketplace add ./
	@for p in $(CH6_PLUGINS); do \
		echo "Installing $$p@$(CH6_MARKETPLACE)..."; \
		claude plugin install $$p@$(CH6_MARKETPLACE); \
	done

test: ##@ Run all tests
	uv run pytest tests/ -v

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
