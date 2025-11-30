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
	@echo "=== Extracting Synthea CSV data from Docker image ==="
	@echo ""
	@echo "[1/6] Checking Docker prerequisites..."
	@if ! command -v docker &> /dev/null; then \
		echo "ERROR: Docker not found."; \
		echo ""; \
		echo "Docker is required to extract raw Synthea data from the container image."; \
		echo ""; \
		echo "Install Docker:"; \
		echo "  macOS: https://docs.docker.com/desktop/install/mac-install/"; \
		echo "  Linux: https://docs.docker.com/engine/install/"; \
		echo "  Windows: https://docs.docker.com/desktop/install/windows-install/"; \
		echo ""; \
		echo "After installation, start Docker and try again."; \
		exit 1; \
	fi
	@echo "✓ Docker found: $$(docker --version)"
	@if ! docker info &> /dev/null; then \
		echo "ERROR: Docker daemon is not running."; \
		echo ""; \
		echo "Start Docker:"; \
		echo "  macOS/Windows: Open Docker Desktop"; \
		echo "  Linux: sudo systemctl start docker"; \
		echo ""; \
		echo "Then try again."; \
		exit 2; \
	fi
	@echo "✓ Docker daemon is running"
	@echo ""
	@echo "[2/6] Creating data/raw directory..."
	@mkdir -p data/raw
	@echo "✓ Directory created"
	@echo ""
	@echo "[3/6] Pulling Docker image (ghcr.io/rdewai/redefining-dataengineering-with-ai:raw-data)..."
	@docker pull ghcr.io/rdewai/redefining-dataengineering-with-ai:raw-data || { echo "ERROR: Failed to pull Docker image"; exit 3; }
	@echo ""
	@echo "[4/6] Creating temporary container..."
	@CONTAINER_ID=$$(docker create ghcr.io/rdewai/redefining-dataengineering-with-ai:raw-data) && \
	echo "✓ Container created: $$CONTAINER_ID" && \
	echo "" && \
	echo "[5/6] Copying CSV files from container to data/raw/..." && \
	docker cp $$CONTAINER_ID:/workspace/data/synthea/csv/. data/raw/ && \
	echo "✓ Files copied successfully" && \
	echo "" && \
	echo "[6/6] Cleaning up temporary container..." && \
	docker rm $$CONTAINER_ID > /dev/null && \
	echo "✓ Container removed" || { echo "ERROR: Failed to copy files or cleanup"; docker rm -f $$CONTAINER_ID 2>/dev/null; exit 3; }
	@echo ""
	@echo "✅ Raw data extraction complete!"
	@echo ""
	@echo "CSV files are now available in: data/raw/"
	@echo "Files: $$(ls -1 data/raw/*.csv 2>/dev/null | wc -l | tr -d ' ') CSV files"
	@echo ""

##@ Tool Management

superset-init: ## Initialize Apache Superset database and admin user
	@echo "=== Initializing Apache Superset ==="
	@echo ""
	@echo "[1/5] Checking prerequisites..."
	@if [ ! -d ".venv" ]; then \
		echo "ERROR: Development environment not set up."; \
		echo ""; \
		echo "Please run 'make dev-setup' first to create the virtual environment."; \
		exit 1; \
	fi
	@echo "✓ Virtual environment exists"
	@echo ""
	@echo "[2/5] Initializing Superset database..."
	@export SUPERSET_CONFIG_PATH=$$(pwd)/superset_config.py && export FLASK_APP=superset && .venv/bin/superset db upgrade || { echo "ERROR: Database upgrade failed"; exit 3; }
	@echo "✓ Database initialized"
	@echo ""
	@echo "[3/5] Creating Superset roles and permissions..."
	@export SUPERSET_CONFIG_PATH=$$(pwd)/superset_config.py && export FLASK_APP=superset && .venv/bin/superset init || { echo "ERROR: Superset init failed"; exit 3; }
	@echo "✓ Roles and permissions created"
	@echo ""
	@echo "[4/5] Creating default admin user..."
	@export SUPERSET_CONFIG_PATH=$$(pwd)/superset_config.py && export FLASK_APP=superset && \
	.venv/bin/superset fab create-admin \
		--username admin \
		--firstname Admin \
		--lastname User \
		--email admin@superset.com \
		--password admin || { echo "ERROR: Admin user creation failed"; exit 3; }
	@echo "✓ Admin user created"
	@echo ""
	@echo "[5/5] Adding DuckDB data source..."
	@export SUPERSET_CONFIG_PATH=$$(pwd)/superset_config.py && export FLASK_APP=superset && \
	.venv/bin/python scripts/add_duckdb_connection.py || { echo "ERROR: Failed to add DuckDB connection"; exit 3; }
	@echo ""
	@echo "✅ Superset initialization complete!"
	@echo ""
	@echo "Default admin credentials:"
	@echo "  Username: admin"
	@echo "  Password: admin"
	@echo ""
	@echo "Data sources configured:"
	@echo "  - DuckDB Analytics (duckdb:///data/duckdb/analytics.db)"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Run 'make superset-run' to start the web server"
	@echo "  2. Access Superset at the URL shown"
	@echo "  3. Use DuckDB Analytics to create charts and dashboards"
	@echo ""

superset-run: ## Start Apache Superset web server on localhost:8088
	@echo "=== Starting Apache Superset ==="
	@echo ""
	@echo "[1/3] Checking prerequisites..."
	@if [ ! -d ".venv" ]; then \
		echo "ERROR: Development environment not set up."; \
		echo ""; \
		echo "Please run 'make dev-setup' first."; \
		exit 1; \
	fi
	@echo "✓ Virtual environment exists"
	@echo ""
	@echo "[2/3] Finding available port..."
	@PORT=8088; \
	while lsof -Pi :$$PORT -sTCP:LISTEN -t >/dev/null 2>&1; do \
		echo "  Port $$PORT is in use, trying next port..."; \
		PORT=$$((PORT + 1)); \
		if [ $$PORT -gt 8100 ]; then \
			echo "ERROR: No available ports found between 8088-8100"; \
			exit 2; \
		fi; \
	done; \
	echo "✓ Using port $$PORT"; \
	echo ""; \
	echo "[3/3] Starting Superset web server..."; \
	echo ""; \
	echo "============================================"; \
	echo "  Superset is starting..."; \
	echo "  URL: http://localhost:$$PORT"; \
	echo "  Username: admin"; \
	echo "  Password: admin"; \
	echo "  Press Ctrl+C to stop"; \
	echo "============================================"; \
	echo ""; \
	export SUPERSET_CONFIG_PATH=$$(pwd)/superset_config.py && export FLASK_APP=superset && .venv/bin/superset run -h 0.0.0.0 -p $$PORT --with-threads --reload --debugger || { echo "ERROR: Superset startup failed"; exit 3; }

##@ Maintenance

clean: ## Remove generated files (.venv, data/raw, __pycache__, build artifacts)
	@echo "=== Cleaning up development environment ==="
	@echo ""
	@echo "Removing generated files and directories..."
	@echo ""
	@if [ -d ".venv" ]; then \
		echo "  - Removing .venv/"; \
		rm -rf .venv; \
	fi
	@if [ -d "data/raw" ]; then \
		echo "  - Removing data/raw/"; \
		rm -rf data/raw; \
	fi
	@echo "  - Removing __pycache__/ directories"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "  - Removing .pyc files"
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "  - Removing .pytest_cache/"
	@rm -rf .pytest_cache 2>/dev/null || true
	@echo "  - Removing .superset/ (Superset metadata)"
	@rm -rf .superset superset.db* 2>/dev/null || true
	@echo ""
	@echo "✅ Clean complete!"
	@echo ""
	@echo "To rebuild the environment, run: make dev-setup"
	@echo ""

test: ## Run all tests with pytest
	@echo "=== Running test suite ==="
	@echo ""
	@if [ ! -d ".venv" ]; then \
		echo "ERROR: Development environment not set up."; \
		echo ""; \
		echo "Please run 'make dev-setup' first."; \
		exit 1; \
	fi
	@echo "Running all integration and unit tests..."
	@echo ""
	@.venv/bin/pytest tests/ -v --tb=short || { echo ""; echo "❌ Tests failed"; exit 1; }
	@echo ""
	@echo "✅ All tests passed!"
	@echo ""
