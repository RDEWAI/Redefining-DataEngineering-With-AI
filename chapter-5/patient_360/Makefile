.PHONY: dev-setup test lint format clean validate dev-up dev-down uc-init seed-source-data wait-for-uc spark-smoke smoke-se

UC_HOST ?= http://localhost:8080
UC_UI_HOST ?= http://localhost:3001
UC_CATALOG ?= unity
UC_SCHEMAS ?= bronze,silver,gold
DOCKER_COMPOSE ?= docker compose -f _infra/docker/docker-compose.yml
# In-airflow Spark per LLD §6.1 (local_executor_mode = in-airflow-local[*]).
SPARK_MASTER ?= local[2]

dev-setup:
	uv sync --all-extras

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

validate:
	@echo "Running contract + DQ rule validation..."
	uv run pytest tests/test_contracts.py -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null; \
	find . -name "*.pyc" -delete 2>/dev/null; true

dev-up: ## Bring up the local stack: docker + UC catalog/schemas + source data + spark smoke
	$(DOCKER_COMPOSE) up -d --build
	@$(MAKE) wait-for-uc
	@$(MAKE) uc-init
	@$(MAKE) seed-source-data
	@$(MAKE) spark-smoke
	@echo ""
	@echo "Stack is up. Verify with:"
	@echo "  curl -fsS http://localhost:8081/health      # Airflow"
	@echo "  curl -fsS $(UC_HOST)/api/2.1/unity-catalog/catalogs"
	@echo "  open      $(UC_UI_HOST)                      # Unity Catalog UI"
	@echo "  $(DOCKER_COMPOSE) exec airflow spark-submit --master '$(SPARK_MASTER)' --version"

spark-smoke: ## Verify spark-submit runs in-airflow (LLD §6.1 local_executor_mode = in-airflow-local[*])
	@echo "Verifying in-airflow Spark via --master $(SPARK_MASTER) ..."
	$(DOCKER_COMPOSE) exec -T airflow spark-submit --master '$(SPARK_MASTER)' --version

smoke-se: ## Spark-Expectations bootstrap smoke (LLD §8.6.1) — populates bronze_se_stats
	@echo "Running Spark-Expectations smoke test inside airflow container..."
	$(DOCKER_COMPOSE) exec -T -e SE_SMOKE_RUN_ID=$${SE_SMOKE_RUN_ID:-smoke-local} \
		-e RUN_SE_SMOKE=1 \
		airflow uv run pytest -m integration tests/integration/test_se_smoke.py -v

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
