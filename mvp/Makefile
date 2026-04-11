.PHONY: dev-setup bronze silver gold pipeline test lint clean \
        uc-start uc-stop uc-logs uc-status spark-sql pyspark-shell

PYTHON   := uv run python
PYTEST   := uv run pytest
PIPELINES := uv run spark-pipelines

# ── Unity Catalog + OpenLineage Spark conf ────────────────────────────────────

SPARK_PACKAGES := io.delta:delta-spark_4.1_2.13:4.1.0,io.unitycatalog:unitycatalog-spark_2.13:0.4.0
UC_CONF := --conf spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension \
           --conf spark.sql.catalog.spark_catalog=io.unitycatalog.spark.UCSingleCatalog \
           --conf spark.sql.catalog.spark_catalog.uri=http://localhost:8080 \
           --conf spark.sql.catalog.spark_catalog.token= \
           --conf spark.jars.packages=$(SPARK_PACKAGES)

INIT_SQL := $(shell pwd)/conf/init.sql

# ── Environment ──────────────────────────────────────────────────────────────

dev-setup:
	uv sync --all-groups
	@echo "Dependencies installed. Run 'make uc-start && make pipeline'."

# ── Unity Catalog + Marquez (Docker) ─────────────────────────────────────────
# UC server  : http://localhost:8080
# Marquez API: http://localhost:5001   (host port; avoids macOS AirPlay on 5000)
# Marquez UI : http://localhost:3000

uc-start:
	@mkdir -p etc/conf
	docker compose up -d server marquez-db marquez marquez-web
	$(PYTHON) scripts/uc_init.py
	@echo "UC server : http://localhost:8080"
	@echo "Marquez UI: http://localhost:3000"

uc-stop:
	docker compose down

uc-logs:
	docker compose logs -f

uc-status:
	@docker compose ps
	@echo ""
	@curl -sf http://localhost:8080/api/2.1/unity-catalog/catalogs > /dev/null \
		&& echo "UC REST API : reachable" \
		|| echo "UC REST API : not responding"

# ── Pipeline layers ───────────────────────────────────────────────────────────

bronze:
	$(PYTHON) run_local.py --layer bronze --ds $(or $(DS),2026-03-06)

silver:
	$(PYTHON) run_local.py --layer silver --ds $(or $(DS),2026-03-06)

gold:
	$(PYTHON) run_local.py --layer gold --ds $(or $(DS),2026-03-06)

pipeline:
	$(PYTHON) run_local.py --layer all --ds $(or $(DS),2026-03-06)
	@echo "Full pipeline complete: Bronze → Silver → Gold"

# ── Spark Declarative Pipelines (production / cloud with Delta built-in) ──────

sdp-run:
	$(PIPELINES) run --spec spark-pipeline.yml --full-refresh

sdp-dry-run:
	$(PIPELINES) dry-run --spec spark-pipeline.yml

# ── Query ─────────────────────────────────────────────────────────────────────

query:
	$(PYTHON) query.py $(TABLE) $(LIMIT)

# Interactive Spark shells — UC persists table metadata; no manual registration needed.

spark-sql:
	$(PYTHON) generate_init_sql.py
	uv run spark-sql $(UC_CONF) -i $(INIT_SQL)

pyspark-shell:
	uv run pyspark $(UC_CONF)

# ── Testing ───────────────────────────────────────────────────────────────────

test:
	$(PYTEST) tests/ -v

test-bronze:
	$(PYTEST) tests/test_bronze/ -v

test-silver:
	$(PYTEST) tests/test_silver/ -v

test-gold:
	$(PYTEST) tests/test_gold/ -v

# ── Code quality ──────────────────────────────────────────────────────────────

lint:
	uv run ruff check src/ pipelines/ tests/

lint-fix:
	uv run ruff check --fix src/ pipelines/ tests/

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	rm -rf warehouse/
	rm -rf spark-warehouse/
	rm -rf metastore_db/
	rm -rf derby.log
	@echo "Cleaned up Spark and Delta artifacts."
