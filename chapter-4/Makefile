.PHONY: help dev-setup test test-unit validate-drd validate-hld lint format clean

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

lint: ##@ Run ruff linter
	uv run ruff check ba-plugin/ architect-plugin/ tests/

format: ##@ Auto-format code
	uv run ruff format ba-plugin/ architect-plugin/ tests/

clean: ##@ Remove generated files and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned."
