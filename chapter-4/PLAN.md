# Chapter 4 — Spark Declarative Pipelines: Patient 360

| Field | Value |
|---|---|
| **Chapter** | 4 |
| **Topic** | Data Engineering with AI — Spark Declarative Pipelines |
| **Stack** | PySpark · Spark Declarative Pipelines · Spark Expectations · Apache Iceberg |
| **Data** | Synthea Healthcare (sourced from chapter-2) |
| **Created** | 2026-03-06 |

---

## Objective

Build a production-grade Patient 360 pipeline using Spark Declarative Pipelines across three medallion layers — Bronze, Silver, Gold — with Spark Expectations (SE) for data quality and SCD Type 2 for dimension history tracking.

The narrative focus is: **how AI accelerates each stage** — generating ingestion logic, DQ expectation suites, SCD merge functions, and transformation models from the DRD.

---

## Directory Structure

```
chapter-4/
├── CLAUDE.md
├── PLAN.md                             # This file
├── README.md
├── Makefile
├── pyproject.toml
├── data/
│   └── raw/                            # Synthea CSVs (sourced from chapter-2)
├── src/
│   └── patient_360/
│       ├── __init__.py
│       ├── bronze/
│       │   ├── __init__.py
│       │   └── ingest.py               # Generic ingestor — raw CSV → Delta, partitioned by ds
│       ├── silver/
│       │   ├── __init__.py
│       │   ├── scd2.py                 # Reusable SCD Type 2 function
│       │   ├── dims.py                 # dim_patients, dim_providers, dim_organizations, dim_payers
│       │   ├── facts.py                # fct_encounters, fct_conditions, fct_medications, etc.
│       │   └── transformations.py      # Business rules, derived fields, code lookups
│       ├── gold/
│       │   ├── __init__.py
│       │   └── patient_summary.py      # Final joined patient 360 table
│       └── utils/
│           ├── __init__.py
│           └── spark.py                # SparkSession factory
├── pipelines/
│   ├── bronze_pipeline.py              # Spark Declarative Pipeline — all bronze tables
│   ├── silver_pipeline.py              # Spark Declarative Pipeline — dims + facts
│   └── gold_pipeline.py               # Spark Declarative Pipeline — patient summary
├── expectations/
│   ├── bronze/                         # SE rules per bronze table (JSON)
│   │   ├── patients_expectations.json
│   │   ├── encounters_expectations.json
│   │   ├── conditions_expectations.json
│   │   ├── medications_expectations.json
│   │   ├── observations_expectations.json
│   │   ├── allergies_expectations.json
│   │   └── claims_expectations.json
│   └── silver/                         # SE rules per silver table (JSON)
│       ├── dim_patients_expectations.json
│       ├── fct_encounters_expectations.json
│       └── fct_conditions_expectations.json
└── tests/
    ├── conftest.py                      # Local SparkSession fixture
    ├── test_bronze/
    │   └── test_ingest.py              # Partition correctness, schema validation
    ├── test_silver/
    │   ├── test_scd2.py                # SCD Type 2 — insert, expire, no-change cases
    │   ├── test_dims.py                # Dimension transformation logic
    │   └── test_facts.py              # Fact transformation, surrogate key resolution
    └── test_gold/
        └── test_patient_summary.py     # Aggregation correctness, join completeness
```

---

## Layer Design

### Bronze — Raw Ingestion

**Goal**: Land raw source files as Delta tables, partitioned by `ds`, with row-level DQ.

| Concern | Design |
|---|---|
| Source | Synthea CSV files (`data/raw/*.csv`) |
| Format | Apache Iceberg |
| Partition | `ds=YYYY-MM-DD` (daily load date) |
| Catalog | Local filesystem catalog for dev; REST/Glue/Nessie for production |
| DQ | Spark Expectations — runs inline; failures quarantined to `<table>_rejected` |
| Tables | One bronze Iceberg table per source: `bronze.patients`, `bronze.encounters`, etc. |

**Pattern** — one generic `ingest()` call per table, no duplication:

```python
# bronze_pipeline.py
@dlt.table(name="bronze_patients", partition_cols=["ds"])
@dlt.expect_or_drop("patient_id not null", "id IS NOT NULL")
@dlt.expect_or_drop("valid birthdate", "birthdate <= current_date()")
def bronze_patients():
    return ingest("patients", schema=PATIENTS_SCHEMA)
```

**SE DQ Actions**:

| SE Action | Behaviour |
|---|---|
| `expect` | Warn — row passes, metric recorded |
| `expect_or_drop` | Reject row — written to `_rejected` table |
| `expect_or_fail` | Fail pipeline — critical rules (NULL PKs, missing FKs) |

---

### Silver — Dimensions, Facts & Transformations

**Goal**: Apply SCD Type 2 to all dims, join facts to surrogate keys, apply business transformation rules.

#### SCD Type 2 — Reusable Function

Single function, called by every dimension — no repeated merge logic.
Uses Iceberg's native `MERGE INTO` for the upsert:

```python
# silver/scd2.py
def apply_scd2(
    spark: SparkSession,
    source_df: DataFrame,
    target_table: str,
    natural_key: str,
    tracked_columns: list[str],
    effective_date_col: str = "ds",
) -> None:
    """
    Applies SCD Type 2 merge to target Iceberg table.
    - Computes SHA256 hash of tracked_columns to detect changes
    - MERGE INTO: matched + hash changed  → expire old row (expiry_date, is_current=False)
    - INSERT new version for changed rows (new surrogate_key, effective_date=today)
    - INSERT net-new rows (first seen natural_key)
    - Unchanged rows: no-op
    """
```

#### Dimensions (all use `apply_scd2`)

| Target Table | Natural Key | Tracked Columns |
|---|---|---|
| `silver.dim_patients` | `patient_id` | `address`, `city`, `state`, `zip`, `phone`, `gender`, `race`, `ethnicity`, `deceased_flag`, `deathdate` |
| `silver.dim_providers` | `provider_id` | `specialty`, `address`, `city`, `state`, `org_id` |
| `silver.dim_organizations` | `org_id` | `org_name`, `address`, `city`, `state`, `zip`, `phone` |
| `silver.dim_payers` | `payer_id` | `payer_name`, `member_months`, `amount_covered` |

#### Facts (joins + transformations)

| Target Table | Key Joins | Key Transformations |
|---|---|---|
| `silver.fct_encounters` | `dim_patients` (SK), `dim_providers` (SK), `dim_organizations` (SK) | Duration, readmission flag, encounter status |
| `silver.fct_conditions` | `dim_patients` (SK) | Active flag, SNOMED description |
| `silver.fct_medications` | `dim_patients` (SK), `dim_payers` (SK) | Active flag, payer display, RxNorm description |
| `silver.fct_observations` | `dim_patients` (SK) | Result status, LOINC description |
| `silver.fct_allergies` | `dim_patients` (SK) | Severity display, sort order |
| `silver.fct_claims` | `dim_patients` (SK), `dim_payers` (SK), `dim_providers` (SK) | Payer rank, service date |

#### Silver DQ (SE)

SE runs a second pass on silver tables — validates surrogate key resolution, transformation output ranges, and referential integrity post-join.

---

### Gold — Patient 360 Tables

**Goal**: Consumer-ready Iceberg tables — current state dims + clean facts + summary aggregation.

| Gold Table | Source | Description |
|---|---|---|
| `gold.dim_patients` | `silver.dim_patients` | Current state only (`is_current=True`), no SCD columns exposed |
| `gold.dim_providers` | `silver.dim_providers` | Current state only |
| `gold.dim_organizations` | `silver.dim_organizations` | Current state only |
| `gold.dim_payers` | `silver.dim_payers` | Current state only |
| `gold.fct_encounters` | `silver.fct_encounters` | Full history, surrogate keys resolved to natural keys for consumers |
| `gold.fct_conditions` | `silver.fct_conditions` | Full history |
| `gold.fct_medications` | `silver.fct_medications` | Full history |
| `gold.fct_observations` | `silver.fct_observations` | Full history |
| `gold.fct_allergies` | `silver.fct_allergies` | Full history |
| `gold.fct_claims` | `silver.fct_claims` | Full history |
| `gold.patient_summary` | All silver tables | One row per patient — aggregated search result (last encounter, active counts, payer) |

---

## Pipelines

Three independent Spark Declarative Pipeline files, chainable via Make:

```
bronze_pipeline.py  →  silver_pipeline.py  →  gold_pipeline.py
```

Each pipeline is a self-contained DAG. Bronze output feeds silver; silver output feeds gold.

---

## Make Targets

```makefile
make dev-setup   # Install uv dependencies + PySpark
make bronze      # Run bronze_pipeline.py
make silver      # Run silver_pipeline.py
make gold        # Run gold_pipeline.py
make pipeline    # Run bronze → silver → gold in sequence
make test        # Run pytest (local Spark mode)
make lint        # Run ruff
make clean       # Remove __pycache__, .spark-warehouse, checkpoints
```

---

## Testing Strategy

All tests run locally using a `SparkSession` in local mode — no cluster required.

| Test File | What It Tests |
|---|---|
| `test_ingest.py` | Schema enforcement, `ds` partition written correctly, rejected rows quarantined |
| `test_scd2.py` | New row insert, changed row expires old + inserts new, unchanged row skips |
| `test_dims.py` | Transformation outputs (full_name, age_years, ssn_masked, deceased_flag) |
| `test_facts.py` | Surrogate key resolution, duration_minutes, is_readmission, severity_sort_order |
| `test_patient_summary.py` | Aggregation correctness, one row per patient, correct counts |

---

## Reusable SCD Type 2 Function Design

**File**: `src/patient_360/silver/scd2.py`

The function is completely generic — it works for any dimension table by accepting config parameters.
No dimension-specific logic lives inside it.

### Signature

```python
def apply_scd2(
    spark: SparkSession,
    source_df: DataFrame,
    target_table: str,          # e.g. "silver.dim_patients"
    natural_key: str,           # e.g. "patient_id"
    tracked_columns: list[str], # columns that trigger a new version when changed
    ds: str,                    # load date "YYYY-MM-DD" — becomes effective_date
) -> None:
```

### What It Does Internally

```
1. Compute record_hash
   SHA2(CONCAT_WS('|', col1, col2, ...), 256) over tracked_columns on source_df

2. Create Iceberg target table if not exists
   With SCD columns: surrogate_key (UUID), natural_key, ..., effective_date,
   expiry_date (nullable), is_current, record_hash, dw_created_at, dw_updated_at

3. MERGE INTO target USING source ON natural_key match:

   WHEN MATCHED AND is_current = true AND record_hash != source.record_hash THEN
     UPDATE SET is_current = false,
                expiry_date = date(ds) - 1 day,
                dw_updated_at = now()

   WHEN NOT MATCHED BY TARGET THEN
     INSERT (surrogate_key=uuid(), ..., effective_date=ds,
             expiry_date=null, is_current=true, dw_created_at=now())

4. INSERT new versions for changed rows
   (Iceberg MERGE INTO cannot UPDATE + INSERT in the same MATCHED clause,
   so changed rows are inserted as a separate step after the expire UPDATE)
```

### How Each Dimension Calls It

```python
# silver/dims.py

SCD2_CONFIG = {
    "dim_patients": {
        "natural_key": "patient_id",
        "tracked_columns": [
            "address", "city", "state", "zip", "phone",
            "gender", "race", "ethnicity", "deceased_flag", "deathdate"
        ],
    },
    "dim_providers": {
        "natural_key": "provider_id",
        "tracked_columns": ["specialty", "address", "city", "state", "org_id"],
    },
    "dim_organizations": {
        "natural_key": "org_id",
        "tracked_columns": ["org_name", "address", "city", "state", "zip", "phone"],
    },
    "dim_payers": {
        "natural_key": "payer_id",
        "tracked_columns": ["payer_name", "member_months", "amount_covered"],
    },
}

# One call per dimension — no repeated logic
for dim_name, config in SCD2_CONFIG.items():
    apply_scd2(
        spark=spark,
        source_df=source_dfs[dim_name],
        target_table=f"silver.{dim_name}",
        natural_key=config["natural_key"],
        tracked_columns=config["tracked_columns"],
        ds=ds,
    )
```

### SCD Type 2 Test Cases (test_scd2.py)

| Test | Scenario | Expected |
|---|---|---|
| `test_new_row_insert` | Natural key not in target | Row inserted, `is_current=True`, `expiry_date=None` |
| `test_changed_row_expires_old` | Tracked column changed | Old row: `is_current=False`, `expiry_date=ds-1` |
| `test_changed_row_inserts_new` | Tracked column changed | New row: `is_current=True`, new `surrogate_key`, `effective_date=ds` |
| `test_unchanged_row_no_op` | No tracked column changed | Row count unchanged, no updates |
| `test_non_tracked_column_no_op` | Non-tracked column changed | No new version created |
| `test_multiple_dims` | Run config loop for all 4 dims | All dims processed correctly |

---

## Confirmed Decisions

| # | Question | Decision |
|---|---|---|
| 1 | Storage format | **Apache Iceberg** |
| 2 | `ds` partition format | String `YYYY-MM-DD` |
| 3 | Gold layer | **Multiple tables** — dims (current state) + facts (full history) + patient_summary |
| 4 | Spark Expectations library | **Nike `spark-expectations`** (open source) |
| 5 | Run target | Local Spark for dev/book; production callout boxes for Databricks/cloud |
