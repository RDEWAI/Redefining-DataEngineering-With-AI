.PHONY: dev-setup test integration-test lint format clean validate dev-up dev-down uc-init uc-ui-source seed-source-data wait-for-uc spark-smoke ddl-apply wait-for-thrift

UC_HOST ?= http://localhost:8080
UC_UI_HOST ?= http://localhost:3000
UC_CATALOG ?= unity
UC_SCHEMAS ?= bronze,silver,gold
UC_STORAGE_ROOT ?= file:///tmp/uc-warehouse
DOCKER_COMPOSE ?= docker compose -f _infra/docker/docker-compose.yml
# In-airflow Spark per LLD §6.1 (local_executor_mode = in-airflow-local[*]).
SPARK_MASTER ?= local[2]
# Unity Catalog UI is built from upstream source (LLD §9.1.1 upstream-reality
# note): no versioned -ui image is published on Docker Hub.
UC_UI_REPO ?= https://github.com/unitycatalog/unitycatalog
UC_UI_REF  ?= v0.5.0
UC_UI_DIR  := _infra/docker/uc-source

dev-setup:
	uv sync --all-extras

test:
	uv run pytest -m "not integration" tests/ -v

integration-test:
	uv run pytest -m integration tests/integration/ -v

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

uc-ui-source: ## Vendor the real Unity Catalog UI source from upstream (idempotent)
	@if [ ! -f $(UC_UI_DIR)/ui/Dockerfile ] \
	   || grep -q "Placeholder" $(UC_UI_DIR)/ui/Dockerfile 2>/dev/null; then \
	  echo "Vendoring Unity Catalog $(UC_UI_REF) into $(UC_UI_DIR) ..."; \
	  rm -rf $(UC_UI_DIR); \
	  git clone --depth 1 --branch $(UC_UI_REF) $(UC_UI_REPO) $(UC_UI_DIR); \
	else \
	  echo "UC UI source already vendored at $(UC_UI_DIR) — skipping."; \
	fi

dev-up: uc-ui-source ## Bring up the full local stack: docker + UC catalog/schemas + DDL pre-create + spark smoke
	# `--wait` blocks until every healthcheck-bearing service (incl.
	# spark-thrift-server) is healthy; the one-shot `ddl-apply` service is
	# started separately by `make ddl-apply` after the thrift server is up.
	$(DOCKER_COMPOSE) up -d --build --wait \
		unity-catalog unity-catalog-ui marquez-db marquez airflow otel-collector spark-thrift-server
	@$(MAKE) wait-for-uc
	@$(MAKE) uc-init
	@$(MAKE) wait-for-thrift
	@$(MAKE) ddl-apply
	@$(MAKE) spark-smoke
	@echo ""
	@echo "Note: 'seed-source-data' is NOT part of dev-up. Run it explicitly"
	@echo "once a runtime-bootstrap story implements it for your source system."
	@echo ""
	@echo "Stack is up. Verify with:"
	@echo "  curl -fsS http://localhost:8081/health      # Airflow"
	@echo "  curl -fsS $(UC_HOST)/api/2.1/unity-catalog/catalogs"
	@echo "  open      $(UC_UI_HOST)                      # Unity Catalog UI"
	@echo "  curl -fsS http://localhost:13133/           # otel-collector health_check"
	@echo "  $(DOCKER_COMPOSE) exec spark-thrift-server beeline -u 'jdbc:hive2://localhost:10000/unity'  # Thrift SQL endpoint"
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

wait-for-thrift: ## Block until the Spark Thrift Server (HiveServer2 :10000) accepts connections
	@echo "Waiting for Spark Thrift Server on localhost:10000 ..."
	@for i in $$(seq 1 60); do \
		if (exec 3<>/dev/tcp/localhost/10000) 2>/dev/null; then \
			echo "Spark Thrift Server is up."; exit 0; \
		fi; \
		sleep 2; \
	done; \
	echo "Spark Thrift Server did not become reachable in 120s." >&2; exit 1

ddl-apply: ## Pre-create UC EXTERNAL Delta tables via beeline one-shot against spark-thrift-server (LLD §9.3, §13 Decision 12)
	@echo "Applying Delta DDL (from Liquibase XML changelogs) via beeline against jdbc:hive2://spark-thrift-server:10000/unity ..."
	$(DOCKER_COMPOSE) run --rm ddl-apply

uc-init: ## Create UC catalog + bronze/silver/gold schemas with managed storage_root (idempotent)
	UC_HOST=$(UC_HOST) UC_CATALOG=$(UC_CATALOG) UC_SCHEMAS=$(UC_SCHEMAS) \
	UC_STORAGE_ROOT=$(UC_STORAGE_ROOT) \
		uv run python scripts/uc_init.py

seed-source-data: ## STUB — projects must implement against their source system.
	@echo "TODO: implement seed-source-data for your source system." >&2
	@echo "  - DuckDB:  load CSV/parquet into a local .db file" >&2
	@echo "  - Postgres: psql \\copy from CSV" >&2
	@echo "  - S3:      aws s3 sync of fixtures into a local minio" >&2
	@echo "  See your runtime-bootstrap story (STORY-01-NNN) for the expected" >&2
	@echo "  source layout and row counts." >&2
	@exit 1
