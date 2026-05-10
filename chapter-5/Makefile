.PHONY: help dev-setup test test-unit validate-drd validate-hld validate-dms validate-stm validate-dqs validate-lld validate-stories lint format clean

help: ##@ Show available commands
	@echo "Chapter 5: Full Artifact Chain + Story-Driven Implementation"
	@echo ""
	@echo "=== Setup ==="
	@echo "  dev-setup        - Install dependencies with UV"
	@echo "  clean            - Remove generated files and caches"
	@echo ""
	@echo "=== Artifact Operations ==="
	@echo "  validate-drd     - Validate all DRDs in outputs/drd/    (plugin sourced from chapter-4)"
	@echo "  validate-hld     - Validate all HLDs in outputs/hld/    (plugin sourced from chapter-4)"
	@echo "  validate-dms     - Validate all DMSs in outputs/dms/    (plugin sourced from chapter-4)"
	@echo "  validate-stm     - Validate all STMs in outputs/stm/    (plugin sourced from chapter-4)"
	@echo "  validate-dqs     - Validate all DQSs in outputs/dqs/    (plugin sourced from chapter-4)"
	@echo "  validate-lld     - Validate all LLDs in outputs/lld/    (plugin sourced from chapter-4)"
	@echo "  validate-stories - Validate all Stories in outputs/stories/"
	@echo ""
	@echo "=== Testing & Quality ==="
	@echo "  test             - Run all tests"
	@echo "  lint             - Run ruff linter"
	@echo "  format           - Auto-format code"

dev-setup: ##@ Install dependencies
	@echo "Setting up Chapter 5 development environment..."
	uv sync
	@echo "Done. Dependencies installed."

test: ##@ Run all tests
	uv run pytest tests/ -v

# Planning-phase validators are sourced from chapter-4 (single source of truth).
validate-drd: ##@ Validate all DRDs in outputs/drd/
	uv run python ../chapter-4/ba-plugin/skills/validate-drd/scripts/validate_drd.py --all outputs/drd/

validate-hld: ##@ Validate all HLDs in outputs/hld/
	uv run python ../chapter-4/architect-plugin/skills/validate-hld/scripts/validate_hld.py --all outputs/hld/

validate-dms: ##@ Validate all DMSs in outputs/dms/
	uv run python ../chapter-4/data-modeler-plugin/skills/validate-dms/scripts/validate_dms.py --all outputs/dms/

validate-stm: ##@ Validate all STMs in outputs/stm/
	uv run python ../chapter-4/mapping-analyst-plugin/skills/validate-stm/scripts/validate_stm.py --all outputs/stm/

validate-dqs: ##@ Validate all DQSs in outputs/dqs/
	uv run python ../chapter-4/dq-engineer-plugin/skills/validate-dqs/scripts/validate_dqs.py --all outputs/dqs/

validate-lld: ##@ Validate all LLDs in outputs/lld/
	uv run python ../chapter-4/technical-lead-plugin/skills/validate-lld/scripts/validate_lld.py --all outputs/lld/

validate-stories: ##@ Validate all Stories in outputs/stories/
	uv run python scrum-master-plugin/skills/validate-stories/scripts/validate_stories.py --all outputs/stories/

lint: ##@ Run ruff linter
	uv run ruff check scrum-master-plugin/ developer-plugin/ tests/

format: ##@ Auto-format code
	uv run ruff format scrum-master-plugin/ developer-plugin/ tests/

clean: ##@ Remove generated files and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned."
