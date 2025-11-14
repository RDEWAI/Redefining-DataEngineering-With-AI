# Makefile for Redefining Data Engineering with AI
# UV Package Manager Migration and Development Workflow Automation
#
# This Makefile provides a standardized development workflow using UV package manager.
# For detailed documentation, see: specs/001-uv-makefile-migration/contracts/makefile-api.md

.PHONY: help dev-setup raw-data-copy clean test superset-init superset-run

# Default target: Display help
.DEFAULT_GOAL := help

##@ General

help: ## Display this help message
	@echo "Redefining Data Engineering with AI - Development Workflow"
	@echo ""
	@echo "Usage:"
	@echo "  make <target>"
	@echo ""
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*##"; printf "\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Development Environment

dev-setup: ## Set up local development environment with UV (< 5 minutes)
	@echo "=== Setting up development environment with UV ==="
	@echo ""
	@echo "[1/4] Checking prerequisites..."
	@if ! command -v uv &> /dev/null; then \
		echo "ERROR: UV package manager not found."; \
		echo ""; \
		echo "Install UV:"; \
		echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		echo ""; \
		echo "For more information: https://docs.astral.sh/uv/"; \
		exit 1; \
	fi
	@echo "✓ UV found: $$(uv --version)"
	@echo ""
	@echo "[2/4] Creating virtual environment with UV (Python 3.12)..."
	@uv venv --python 3.12 || { echo "ERROR: Failed to create virtual environment"; exit 3; }
	@echo ""
	@echo "[3/4] Installing dependencies with UV sync..."
	@uv sync || { echo "ERROR: Failed to install dependencies"; exit 3; }
	@echo ""
	@echo "[4/4] Validating environment..."
	@if ! .venv/bin/python -c "import duckdb; import sqlmesh; import superset; import pytest; print('✅ All packages successfully installed')"; then \
		echo "ERROR: Package validation failed"; \
		exit 3; \
	fi
	@echo ""
	@echo "✅ Development environment setup complete!"
	@echo ""
	@echo "To activate the virtual environment:"
	@echo "  source .venv/bin/activate"
	@echo ""

##@ Data Management

raw-data-copy: ## Extract Synthea CSV data from Docker image to data/raw/ (< 2 minutes)
	@echo "Extracting raw data from Docker image..."
	@echo "This target will be implemented in Phase 4"

##@ Tool Management

superset-init: ## Initialize Apache Superset database and admin user
	@echo "Initializing Apache Superset..."
	@echo "This target will be implemented in Phase 5"

superset-run: ## Start Apache Superset web server on localhost:8088
	@echo "Starting Apache Superset..."
	@echo "This target will be implemented in Phase 5"

##@ Maintenance

clean: ## Remove generated files (.venv, data/raw, __pycache__, build artifacts)
	@echo "Cleaning up..."
	@echo "This target will be implemented in Phase 6"

test: ## Run all tests with pytest
	@echo "Running tests..."
	@echo "This target will be implemented in Phase 6"
