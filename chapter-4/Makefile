.PHONY: help dev-setup test test-unit validate-drd validate-hld validate-dms validate-stm validate-dqs validate-lld lint format clean

help: ##@ Show available commands
	@echo "Chapter 4: Planning with Context — Multi-Agent Artifact Chain"
	@echo ""
	@echo "=== Setup ==="
	@echo "  dev-setup        - Install dependencies with UV"
	@echo "  clean            - Remove generated files and caches"
	@echo ""
	@echo "=== Artifact Operations ==="
	@echo "  validate-drd     - Validate all DRDs in outputs/drd/"
	@echo "  validate-hld     - Validate all HLDs in outputs/hld/"
	@echo "  validate-dms     - Validate all DMSs in outputs/dms/"
	@echo "  validate-stm     - Validate all STMs in outputs/stm/"
	@echo "  validate-dqs     - Validate all DQSs in outputs/dqs/"
	@echo "  validate-lld     - Validate all LLDs in outputs/lld/"
	@echo ""
	@echo "=== Testing & Quality ==="
	@echo "  test             - Run all tests"
	@echo "  lint             - Run ruff linter"
	@echo "  format           - Auto-format code"

dev-setup: ##@ Install dependencies
	@echo "Setting up Chapter 4 development environment..."
	uv sync
	@echo "Done. Dependencies installed."

test: ##@ Run all tests
	uv run pytest tests/ -v

validate-drd: ##@ Validate all DRDs in outputs/drd/
	uv run python ba-plugin/skills/validate-drd/scripts/validate_drd.py --all outputs/drd/

validate-hld: ##@ Validate all HLDs in outputs/hld/
	uv run python architect-plugin/skills/validate-hld/scripts/validate_hld.py --all outputs/hld/

validate-dms: ##@ Validate all DMSs in outputs/dms/
	uv run python data-modeler-plugin/skills/validate-dms/scripts/validate_dms.py --all outputs/dms/

validate-stm: ##@ Validate all STMs in outputs/stm/
	uv run python mapping-analyst-plugin/skills/validate-stm/scripts/validate_stm.py --all outputs/stm/

validate-dqs: ##@ Validate all DQSs in outputs/dqs/
	uv run python dq-engineer-plugin/skills/validate-dqs/scripts/validate_dqs.py --all outputs/dqs/

validate-lld: ##@ Validate all LLDs in outputs/lld/
	uv run python technical-lead-plugin/skills/validate-lld/scripts/validate_lld.py --all outputs/lld/

lint: ##@ Run ruff linter
	uv run ruff check ba-plugin/ architect-plugin/ data-modeler-plugin/ mapping-analyst-plugin/ dq-engineer-plugin/ technical-lead-plugin/ tests/

format: ##@ Auto-format code
	uv run ruff format ba-plugin/ architect-plugin/ data-modeler-plugin/ mapping-analyst-plugin/ dq-engineer-plugin/ technical-lead-plugin/ tests/

clean: ##@ Remove generated files and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned."
