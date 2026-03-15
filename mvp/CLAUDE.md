# Chapter 4: Spark Declarative Pipelines — Patient 360

## Stack
- **PySpark 4.1** with Delta Lake for storage
- **Unity Catalog OSS 0.4.0** — metastore (replaces Derby)
- **OpenLineage + Marquez** — pipeline lineage
- **Spark Expectations (Nike)** for data quality
- **UV** for Python environment management
- **pytest** for unit testing (local Spark mode — no cluster needed)

## Key Commands
```bash
make dev-setup   # Install dependencies
make uc-start    # Start Unity Catalog + Marquez (Docker)
make uc-stop     # Stop containers
make bronze      # Run bronze ingestion pipeline
make silver      # Run silver SCD2 + transformation pipeline
make gold        # Run gold consumer layer pipeline
make pipeline    # Run all three layers in sequence
make test        # Run all pytest tests
make lint        # Run ruff linter
make clean       # Remove Spark/Delta local artifacts
```

## Project Structure
- `src/patient_360/` — source code (bronze, silver, gold, utils)
- `pipelines/` — Spark Declarative Pipeline entry points (bronze, silver, gold)
- `scripts/uc_init.py` — bootstrap Unity Catalog (catalog + schemas)
- `docker-compose.yml` — UC server + Marquez services
- `tests/` — pytest unit tests with local SparkSession fixture (isolated, no UC)
- `data/raw/` — Synthea CSV source files

## Unity Catalog (local dev)
- Server: `http://localhost:8080` (Docker container)
- Spark catalog name: `spark_catalog` (backed by UC via `UCSingleCatalog`)
- UC catalog: `unity` (created by `scripts/uc_init.py`)
- Schemas: `bronze`, `silver`, `gold`
- Tables persist across Spark sessions — no re-registration needed

## Lineage
- OpenLineage Spark listener emits events on every pipeline run
- Backend: Marquez at `http://localhost:5000` (API) / `http://localhost:3000` (UI)
- UC OSS 0.4.0 has no built-in lineage REST API — lineage lives in Marquez only

## SCD Type 2
- Reusable function: `src/patient_360/silver/scd2.py:apply_scd2()`
- Config-driven via `SCD2_CONFIG` dict in `silver/dims.py`
- Uses Delta `MERGE INTO` for expire + insert pattern
- All 4 dims (`dim_patients`, `dim_providers`, `dim_organizations`, `dim_payers`) use the same function

## Spark JARs
Downloaded automatically via `spark.jars.packages` on first run (~200 MB):
- `io.delta:delta-spark_2.12:4.1.0`
- `io.unitycatalog:unitycatalog-spark_2.12:0.3.1`
- `io.openlineage:openlineage-spark_2.12:1.44.1`

Cached in `~/.ivy2/` after first execution.

## Test Isolation
Tests use `DeltaCatalog` (not UC) with a temp warehouse — no UC server required.
The `conftest.py` fixture is fully isolated from the running UC instance.
