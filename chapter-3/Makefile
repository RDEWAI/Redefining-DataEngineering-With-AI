.PHONY: help dev-setup test test-unit validate-drd lint format clean

help: ##@ Show available commands
	@echo "Chapter 3: BA Agent for Data Requirements Documents"
	@echo ""
	@echo "=== Setup ==="
	@echo "  dev-setup        - Install dependencies with UV"
	@echo "  clean            - Remove generated files and caches"
	@echo ""
	@echo "=== DRD Operations ==="
	@echo "  validate-drd     - Validate all DRDs in outputs/drd/"
	@echo ""
	@echo "=== Testing & Quality ==="
	@echo "  test             - Run all tests"
	@echo "  lint             - Run ruff linter"
	@echo "  format           - Auto-format code"

dev-setup: ##@ Install dependencies
	@echo "Setting up Chapter 3 development environment..."
	uv sync
	@echo "Done. Dependencies installed."

test: ##@ Run all tests
	uv run pytest tests/ -v

validate-drd: ##@ Validate all DRDs in outputs/drd/
	uv run python ba-agent-drd/skills/validate-drd/scripts/validate_drd.py --all outputs/drd/

lint: ##@ Run ruff linter
	uv run ruff check ba-agent-drd/ tests/

format: ##@ Auto-format code
	uv run ruff format ba-agent-drd/ tests/

clean: ##@ Remove generated files and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned."
