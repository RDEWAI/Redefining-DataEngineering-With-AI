.PHONY: dev-setup test integration-test lint format clean validate dev-up dev-down uc-init uc-ui-source seed-source-data wait-for-uc spark-smoke bootstrap-uc help

UC_HOST ?= http://localhost:8080
UC_UI_HOST ?= http://localhost:3000
UC_CATALOG ?= unity
UC_SCHEMAS ?= bronze,silver,gold
DOCKER_COMPOSE ?= docker compose -f _infra/docker/docker-compose.yml
# In-airflow Spark per LLD §6.1 (local_executor_mode = in-airflow-local[*]).
SPARK_MASTER ?= local[2]
# Unity Catalog UI is built from upstream source (LLD §9.1.1 upstream-reality
# note): no versioned -ui image is published on Docker Hub.
UC_UI_REPO ?= https://github.com/unitycatalog/unitycatalog
UC_UI_REF  ?= v0.4.0
UC_UI_DIR  := _infra/docker/uc-source

dev-setup: ## Install dependencies via uv (`uv sync --all-extras`)
	uv sync --all-extras

test: ## Run unit tests (excludes the `integration` mark)
	uv run pytest -m "not integration" tests/ -v

integration-test: ## Run integration tests (requires docker stack via `make dev-up`)
	uv run pytest -m integration tests/integration/ -v

lint: ## Run ruff linter against src/ and tests/
	uv run ruff check src/ tests/

format: ## Auto-format src/ and tests/ with ruff
	uv run ruff format src/ tests/

validate: ## Validate contracts + DQ rules
	@echo "Running contract + DQ rule validation..."
	uv run pytest tests/test_contracts.py -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null; \
	find . -name "*.pyc" -delete 2>/dev/null; true

uc-ui-source: ## Vendor the real Unity Catalog UI source from upstream (idempotent)
	@if [ ! -f $(UC_UI_DIR)/ui/Dockerfile ] \
	   || grep -q "Placeholder" $(UC_UI_DIR)/ui/Dockerfile 2>/dev/null; then \
	  echo "Vendoring Unity Catalog $(UC_UI_REF) into $(UC_UI_DIR) ..."; \
	  rm -rf $(UC_UI_DIR); \
	  git clone --depth 1 --branch $(UC_UI_REF) $(UC_UI_REPO) $(UC_UI_DIR); \
	else \
	  echo "UC UI source already vendored at $(UC_UI_DIR) — skipping."; \
	fi

dev-up: uc-ui-source ## Bring up the local stack: docker + UC catalog/schemas + spark smoke
	$(DOCKER_COMPOSE) up -d --build
	@$(MAKE) wait-for-uc
	@$(MAKE) uc-init
	@$(MAKE) spark-smoke
	@echo ""
	@echo "Note: 'seed-source-data' is NOT part of dev-up. Run it explicitly"
	@echo "once a runtime-bootstrap story implements it for your source system."
	@echo ""
	@echo "Stack is up. Verify with:"
	@echo "  curl -fsS http://localhost:8081/health      # Airflow"
	@echo "  curl -fsS $(UC_HOST)/api/2.1/unity-catalog/catalogs"
	@echo "  open      $(UC_UI_HOST)                      # Unity Catalog UI"
	@echo "  $(DOCKER_COMPOSE) exec airflow spark-submit --master '$(SPARK_MASTER)' --version"

spark-smoke: ## Verify spark-submit runs in-airflow (LLD §6.1 local_executor_mode = in-airflow-local[*])
	@echo "Verifying in-airflow Spark via --master $(SPARK_MASTER) ..."
	$(DOCKER_COMPOSE) exec -T airflow spark-submit --master '$(SPARK_MASTER)' --version

dev-down:
	$(DOCKER_COMPOSE) down

wait-for-uc: ## Block until Unity Catalog OSS REST API returns 200
	@echo "Waiting for Unity Catalog OSS at $(UC_HOST) ..."
	@for i in $$(seq 1 60); do \
		if curl -fsS -o /dev/null "$(UC_HOST)/api/2.1/unity-catalog/catalogs"; then \
			echo "UC OSS is up."; exit 0; \
		fi; \
		sleep 2; \
	done; \
	echo "UC OSS did not become healthy in 120s." >&2; exit 1

uc-init: ## Create UC catalog + bronze/silver/gold schemas (idempotent)
	UC_HOST=$(UC_HOST) UC_CATALOG=$(UC_CATALOG) UC_SCHEMAS=$(UC_SCHEMAS) \
		uv run python scripts/uc_init.py

seed-source-data: ## STUB — projects must implement against their source system.
	@echo "TODO: implement seed-source-data for your source system." >&2
	@echo "  - DuckDB:  load CSV/parquet into a local .db file" >&2
	@echo "  - Postgres: psql \\copy from CSV" >&2
	@echo "  - S3:      aws s3 sync of fixtures into a local minio" >&2
	@echo "  See your runtime-bootstrap story (STORY-01-NNN) for the expected" >&2
	@echo "  source layout and row counts." >&2
	@exit 1

# ---------------------------------------------------------------------------
# Deploy-time UC table registration -- LLD v1.18 §13 Decision 17 (Revised
# 2026-05-23 second pivot -- pure-Python REST client)
# ---------------------------------------------------------------------------
# `bootstrap-uc` is kept SEPARATE from `dev-up` so contributors can re-run
# UC table registration after editing `contracts/*.yml` without bouncing
# the docker stack. Canonical local bring-up sequence:
#
#     make dev-up && make bootstrap-uc
#
# Both targets are idempotent. `bootstrap-uc` runs `scripts/bootstrap_uc_tables.py`
# directly -- a pure-Python httpx client that POSTs to the UC OSS REST API
# (`/api/2.1/unity-catalog/{schemas,tables}`) for every populated contract.
# GET-before-POST per object. NO Spark, NO spark-submit, NO JDBC, NO
# Liquibase invocation for UC. Runtime DAG tasks remain `DeltaCatalog`
# per LLD §13 Decision 12. The v1.17 Spark-DDL path was abandoned because
# `io.unitycatalog:unitycatalog-spark_2.13:0.3.0` is binary-incompat with
# Spark 4.x (NoSuchMethodError on `LogKey.$init$`). The v1.16
# Liquibase-over-UC-JDBC path was abandoned because
# `io.unitycatalog:unitycatalog-jdbc` is not published on Maven Central.

ENV ?= dev

bootstrap-uc: ## Register every contract-declared Delta table in UC OSS via REST API (Decision 17 v1.18, idempotent)
	uv run python scripts/bootstrap_uc_tables.py --env $(ENV) --verbose

help: ## Show available Make targets
	@awk 'BEGIN { FS = ":.*## "; printf "Available targets:\n\n" } \
	      /^[a-zA-Z0-9_-]+:.*## / { printf "  %-22s %s\n", $$1, $$2 } \
	      END { printf "\nDeploy-time: \`make dev-up && make bootstrap-uc\` (Decision 17).\n" }' \
	    $(MAKEFILE_LIST)
