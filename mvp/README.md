# MVP — Patient 360 Medallion Pipeline

A production-grade **Bronze → Silver → Gold** data pipeline built with **PySpark 4.1 + Delta Lake**.
Source data: [Synthea](https://synthea.mitre.org/) synthetic healthcare records (5,767 patients).

---

## Architecture

```
data/raw/          (Synthea CSV files)
     │
     ▼ bronze layer — schema enforcement, partitioned by ds
bronze.patients, bronze.encounters, bronze.conditions, ...
     │
     ▼ silver layer — SCD Type 2 dims + fact transformations
silver.dim_patients   silver.dim_providers
silver.dim_organizations  silver.dim_payers
silver.fct_encounters  silver.fct_conditions
silver.fct_medications  silver.fct_observations
silver.fct_allergies   silver.fct_claims
     │
     ▼ gold layer — consumer-ready wide table
gold.patient_summary   (one row per current patient)
```

All tables are stored as **Delta Lake** tables in `warehouse/` (local dev).
In production, point `spark.sql.warehouse.dir` to cloud storage (S3 / ADLS / GCS).

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.10 – 3.12 | [python.org](https://www.python.org) |
| UV | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Java | 11 or 17 | required by Spark |
| Docker | 24+ | [docker.com](https://www.docker.com) |

> **Java check:** `java -version` — must show 11 or 17.

---

## Setup

```bash
cd mvp
make dev-setup          # creates .venv and installs all dependencies
make uc-start           # start Unity Catalog + Marquez via Docker
```

`make dev-setup` installs PySpark 4.1, Delta Lake, and dev tools (pytest, ruff) via `uv`.

On first pipeline run, Spark downloads the UC connector and OpenLineage JARs (~200 MB)
into `~/.ivy2/`. Subsequent runs use the local cache.

---

## Metadata — Unity Catalog OSS

Table schemas persist in **Unity Catalog** (OSS) instead of Derby (embedded Hive metastore).
This means:

- Running `--layer silver` independently always finds the bronze tables — no re-run required.
- Metadata survives process restarts and is shared across tools.
- The interactive SQL shell (`make spark-sql`) sees all tables immediately.

The catalog server runs at `http://localhost:8080`. Start and stop it with:

```bash
make uc-start     # docker compose up + create catalog/schemas
make uc-stop      # docker compose down
```

Verify the server and inspect registered tables:

```bash
# List catalogs
curl http://localhost:8080/api/2.1/unity-catalog/catalogs

# List tables registered in silver
curl "http://localhost:8080/api/2.1/unity-catalog/tables?catalog_name=unity&schema_name=silver"
```

---

## Lineage — Marquez + OpenLineage

Every pipeline run emits **OpenLineage** events to **Marquez** via the
`OpenLineageSparkListener`. No code changes needed — the listener is registered
in the SparkSession configuration.

- **Lineage API**: `http://localhost:5000` (OpenLineage ingest endpoint)
- **Lineage UI**: `http://localhost:3000` (Marquez web UI — job graph, dataset lineage)

Open `http://localhost:3000` after running the pipeline to see the full Bronze → Silver → Gold
lineage graph.

> **Note:** Unity Catalog OSS 0.4.0 does not have built-in lineage REST endpoints.
> Lineage is captured by the OpenLineage Spark listener and stored in Marquez, not in UC itself.
> Column-level lineage requires Databricks Unity Catalog or DataHub.

---

## Data

The raw Synthea CSV files live at `../data/raw/` (one level above `mvp/`).
The pipeline expects these 10 files:

```
patients.csv       encounters.csv     conditions.csv
medications.csv    observations.csv   allergies.csv
claims.csv         organizations.csv  providers.csv
payers.csv
```

---

## Running the Pipeline

> Unity Catalog must be running before executing the pipeline: `make uc-start`

### Full pipeline (all three layers)

```bash
make pipeline
# or with an explicit load date:
make pipeline DS=2026-03-06
```

### Individual layers

```bash
make bronze          # ingest CSVs → Delta bronze tables
make silver          # SCD2 dims + fact transforms
make gold            # Patient 360 summary table
```

### Run layers individually via Python

```bash
uv run python run_local.py --layer bronze --ds 2026-03-06
uv run python run_local.py --layer silver --ds 2026-03-06
uv run python run_local.py --layer gold   --ds 2026-03-06
uv run python run_local.py --layer all    --ds 2026-03-06
```

Each layer is **idempotent** — re-running for the same `ds` replaces that partition (no duplicates).

### Using a different data directory

```bash
uv run python run_local.py --layer all --ds 2026-03-13 \
    --raw-path /absolute/path/to/your/csv/directory
```

---

## Querying Tables

### Interactive SQL shell

```bash
make spark-sql
```

Tables are registered in Unity Catalog and available immediately. Query directly:

```sql
SHOW TABLES IN bronze;
SHOW TABLES IN silver;
SHOW TABLES IN gold;

-- Row counts per layer
SELECT 'bronze.patients'     AS tbl, count(*) AS rows FROM bronze.patients
UNION ALL
SELECT 'silver.dim_patients' AS tbl, count(*) AS rows FROM silver.dim_patients
UNION ALL
SELECT 'gold.patient_summary' AS tbl, count(*) AS rows FROM gold.patient_summary;

-- Current patient demographics
SELECT patient_id, full_name, city, state, age_years, gender
FROM silver.dim_patients
WHERE dim_is_current = true
LIMIT 10;

-- Patient 360 summary
SELECT patient_id, full_name, total_encounters, total_conditions,
       active_medications, severe_allergies, total_visit_cost
FROM gold.patient_summary
ORDER BY total_visit_cost DESC
LIMIT 10;
```

---

## SCD Type 2

Dimensions use SCD Type 2 to track historical changes. Each row has:

| Column | Description |
|--------|-------------|
| `surrogate_key` | UUID — stable identifier for this version |
| `start_ts` | Date this version became active |
| `end_ts` | Date this version was superseded (NULL = still current) |
| `dim_is_current` | `true` for the active version |
| `record_hash` | SHA-256 of tracked columns — change detection |

**Tracked columns per dimension:**

| Dimension | Triggers new version when... |
|-----------|------------------------------|
| `dim_patients` | address, city, state, zip, gender, race, ethnicity, deceased_flag, deathdate |
| `dim_providers` | speciality, address, city, state, organization_id |
| `dim_organizations` | name, address, city, state, zip, phone |
| `dim_payers` | name, member_months, amount_covered |

**Query all versions for a patient:**

```sql
SELECT patient_id, city, state, start_ts, end_ts, dim_is_current
FROM silver.dim_patients
WHERE patient_id = '<uuid>'
ORDER BY start_ts;
```

---

## Testing SCD2 with a Second Load

A script generates a realistic delta load for testing:

```bash
# Step 1 — generate delta data (skips observations — 4.4M rows)
uv run python scripts/gen_delta_load.py

# Step 2 — run the second load
uv run python run_local.py --layer all --ds 2026-03-13 \
    --raw-path /path/to/repo/data/raw_delta
```

What the delta load produces:
- **577 patients** moved to a new city → SCD2 expires old row, inserts new current row
- **54 providers** changed speciality → same pattern
- **organizations / payers** unchanged → no-op (zero new rows)
- **300 new encounters**, 500 conditions, 400 medications, 200 allergies, 300 claims

### Verify SCD2 correctness

```bash
uv run python scripts/verify_scd2.py
```

Expected output (all 14 checks):
```
PASS  current + expired = total
PASS  changed patients have 2 versions
PASS  unchanged patients have 1 version
PASS  no surrogate_key duplicates
PASS  expired rows have end_ts = 2026-03-12
...
ALL CHECKS PASSED
```

---

## Tests

```bash
make test                  # all 38 tests
make test-bronze           # bronze ingest tests only
make test-silver           # SCD2 + transformation tests only
```

Tests use an in-process local SparkSession — no cluster required.

---

## Project Structure

```
mvp/
├── run_local.py                    # pipeline runner (bronze/silver/gold/all)
├── Makefile                        # make targets for all common tasks
├── docker-compose.yml              # Unity Catalog + Marquez services
├── pyproject.toml                  # dependencies and tool config
│
├── src/patient_360/
│   ├── bronze/
│   │   ├── ingest.py               # CSV → Delta, partitioned by ds
│   │   └── schemas.py              # PySpark schemas for all 10 source tables
│   ├── silver/
│   │   ├── scd2.py                 # reusable apply_scd2() — Delta MERGE INTO
│   │   ├── dims.py                 # dim_patients, dim_providers, dim_organizations, dim_payers
│   │   ├── facts.py                # fct_encounters, fct_conditions, fct_medications, ...
│   │   └── transformations.py      # business rules (TR-001 … TR-015)
│   ├── gold/
│   │   └── patient_summary.py      # wide Patient 360 table
│   └── utils/
│       └── spark.py                # SparkSession factory with UC + OpenLineage config
│
├── tests/
│   ├── conftest.py                 # shared SparkSession fixture (isolated, no UC)
│   ├── test_bronze/                # ingest unit + integration tests
│   └── test_silver/                # SCD2 behaviour + transformation tests
│
├── scripts/
│   ├── uc_init.py                  # bootstrap Unity Catalog (run once after uc-start)
│   ├── gen_delta_load.py           # generate second-load CSV data for SCD2 testing
│   └── verify_scd2.py              # 14-point SCD2 correctness checks
│
├── pipelines/                      # Spark Declarative Pipelines specs (cloud/Databricks)
├── expectations/                   # data quality rule files (JSON)
├── conf/                           # Spark init.sql for interactive shell (generated)
└── warehouse/                      # local Delta Lake storage (git-ignored)
```

---

## Cleanup

```bash
make clean      # remove warehouse/, metastore_db/, spark-warehouse/, derby.log
make uc-stop    # stop Unity Catalog + Marquez containers
```

After cleaning, re-run `make uc-start && make pipeline` to rebuild from scratch.
The UC server state (table metadata) is stored in `uc-data/` (local volume, gitignored).

---

## Common Issues

**`java.lang.UnsupportedClassVersionError`**
Spark requires Java 11 or 17. Check with `java -version` and update `JAVA_HOME` if needed.

**`FileNotFoundError: Source file not found: .../patients.csv`**
The default raw data path is `../data/raw/` (relative to `mvp/`).
Use `--raw-path /absolute/path` if your data is elsewhere.

**Pipeline slow on first run**
Delta, UC connector, and OpenLineage JARs (~200 MB) are downloaded on first execution and
cached in `~/.ivy2/`. Subsequent runs use the cache.

**`Cannot reach Unity Catalog server at http://localhost:8080`**
Unity Catalog is not running. Start it with `make uc-start` before running the pipeline.

**`DELTA_CREATE_EXTERNAL_TABLE_WITHOUT_TXN_LOG`**
A previous run failed mid-write, leaving a partial directory. Run `make clean` and restart.
