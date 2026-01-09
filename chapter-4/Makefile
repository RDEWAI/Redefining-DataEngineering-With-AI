# PWI (Planning with Intent) Makefile
# ====================================
#
# Common commands for developing and running PWI.
#
# Usage:
#   make help          - Show available commands
#   make gui-start     - Start OpenHands GUI
#   make gui-stop      - Stop OpenHands GUI
#   make test          - Run tests

.PHONY: help install test lint format clean \
        gui-start gui-stop gui-logs gui-build \
        dashboard run session-list

# Default target
.DEFAULT_GOAL := help

# ============================================================================
# Help
# ============================================================================

help: ## Show this help message
	@echo "PWI - Planning with Intent"
	@echo "=========================="
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Setup & Development:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(install|test|lint|format|clean)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'
	@echo ""
	@echo "OpenHands GUI:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E 'gui-' | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'
	@echo ""
	@echo "PWI Commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(dashboard|run|session)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

# ============================================================================
# Setup & Development
# ============================================================================

install: ## Install dependencies with UV
	uv sync

test: ## Run all tests
	uv run pytest

test-cov: ## Run tests with coverage
	uv run pytest --cov=pwi --cov-report=term-missing

lint: ## Run linting checks
	uv run ruff check pwi tests

format: ## Format code with ruff
	uv run ruff format pwi tests

clean: ## Clean build artifacts
	rm -rf .pytest_cache
	rm -rf __pycache__
	rm -rf pwi/__pycache__
	rm -rf .coverage
	rm -rf htmlcov
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# ============================================================================
# OpenHands GUI
# ============================================================================

gui-start: ## Start OpenHands GUI (http://localhost:3000)
	@echo "Starting OpenHands GUI with PWI integration..."
	@if [ ! -f .env ]; then \
		echo ""; \
		echo "WARNING: No .env file found!"; \
		echo "Create one with your LLM configuration:"; \
		echo "  echo 'LLM_API_KEY=your-key' > .env"; \
		echo "  echo 'LLM_BASE_URL=https://openrouter.ai/api/v1' >> .env"; \
		echo ""; \
	fi
	./scripts/start-openhands-gui.sh

gui-stop: ## Stop OpenHands GUI
	./scripts/stop-openhands-gui.sh

gui-logs: ## View OpenHands GUI logs
	docker logs -f openhands-pwi

gui-build: ## Rebuild OpenHands GUI Docker image
	docker-compose -f docker-compose.openhands.yml build

gui-status: ## Check OpenHands GUI status
	@if docker ps | grep -q openhands-pwi; then \
		echo "OpenHands GUI is RUNNING"; \
		echo "Access at: http://localhost:3000"; \
	else \
		echo "OpenHands GUI is STOPPED"; \
	fi

# ============================================================================
# PWI Commands
# ============================================================================

dashboard: ## Start PWI dashboard (http://localhost:8080)
	uv run pwi dashboard

run: ## Run PWI workflow (usage: make run REQUEST=requests/my-request.md)
	@if [ -z "$(REQUEST)" ]; then \
		echo "Usage: make run REQUEST=requests/my-request.md"; \
		echo ""; \
		echo "Available requests:"; \
		ls -1 requests/*.md 2>/dev/null || echo "  No request files found in requests/"; \
	else \
		uv run pwi plan run $(REQUEST); \
	fi

run-auto: ## Run PWI workflow with auto-approve (usage: make run-auto REQUEST=requests/my-request.md)
	@if [ -z "$(REQUEST)" ]; then \
		echo "Usage: make run-auto REQUEST=requests/my-request.md"; \
	else \
		uv run pwi plan run $(REQUEST) --auto-approve; \
	fi

session-list: ## List all PWI sessions
	uv run pwi session list

session-status: ## Show session status (usage: make session-status ID=abc123)
	@if [ -z "$(ID)" ]; then \
		echo "Usage: make session-status ID=<session-id>"; \
	else \
		uv run pwi session status $(ID); \
	fi

# ============================================================================
# Docker Compose Detection
# ============================================================================

# Detect compose command (docker compose or docker-compose)
COMPOSE_CMD := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")
