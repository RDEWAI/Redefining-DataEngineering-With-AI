# Quickstart: DuckDB CSV Data Loader

**Feature**: 002-duckdb-csv-loader
**Date**: 2025-12-01
**Audience**: Data analysts, data engineers, developers

## Overview

This guide walks you through loading Synthea healthcare CSV data into DuckDB so you can query it through Apache Superset dashboards.

**Time to complete**: ~15 minutes (including data extraction and loading)

**What you'll accomplish**:
- Extract raw Synthea CSV files (18 files, ~4.3GB)
- Load CSV data into DuckDB tables
- Verify data is queryable through Superset

---

## Prerequisites

Before starting, ensure you have:

1. **System Requirements**:
   - macOS or Linux
   - At least 10GB free disk space
   - Docker installed and running (for data extraction)
   - UV package manager installed

2. **Project Setup Completed**:
   - Development environment set up (`make dev-setup`)
   - Superset initialized (`make superset-init`)

If you haven't completed these, see the main project README.

---

## Step 1: Extract Raw Data (2 minutes)

Extract Synthea CSV files from the Docker image:

```bash
make raw-data-copy
```

**Expected output**:
```text
=== Extracting Synthea CSV data from Docker image ===

[1/6] Checking Docker prerequisites...
✓ Docker found: Docker version 24.0.6
✓ Docker daemon is running

[2/6] Creating data/raw directory...
✓ Directory created

[3/6] Pulling Docker image...
✓ Image pulled

[4/6] Creating temporary container...
✓ Container created: abc123...

[5/6] Copying CSV files from container to data/raw/...
✓ Files copied successfully

[6/6] Cleaning up temporary container...
✓ Container removed

✅ Raw data extraction complete!

CSV files are now available in: data/raw/
Files: 18 CSV files
```

**Verify the extraction**:
```bash
ls -lh data/raw/
```

You should see 18 CSV files including:
- `patients.csv`
- `encounters.csv`
- `observations.csv` (~772MB)
- `claims_transactions.csv` (~2.5GB)
- And 14 more files

---

## Step 2: Load Data into DuckDB (6-10 minutes)

Load all CSV files into DuckDB tables:

```bash
make load-raw-data
```

**Expected output**:
```text
=== Loading CSV data into DuckDB ===

[1/3] Checking prerequisites...
✓ Virtual environment exists
✓ Raw data directory contains 18 CSV files
✓ DuckDB database directory exists

[2/3] Loading CSV files into DuckDB tables...

[1/18] Loading allergies...
  ✓ Loaded 234 rows in 0.2s

[2/18] Loading careplans...
  ✓ Loaded 12,456 rows in 1.1s

[3/18] Loading claims...
  ✓ Loaded 145,678 rows in 12.3s

[4/18] Loading claims_transactions...
  ✓ Loaded 8,234,567 rows in 180.5s

... [progress for remaining 14 files]

[3/3] Validating loaded tables...
✓ All 18 tables created successfully

✅ Data loading complete!

Summary:
  Tables created: 18
  Total rows loaded: 15,234,567
  Total time: 8m 32s

DuckDB tables are now available in: data/duckdb/raw.db (synthea schema)
```

**What's happening**:
- Each CSV file is loaded into a corresponding DuckDB table
- DuckDB automatically infers column types from CSV content
- Large files (like `claims_transactions.csv`) take longer to load
- Progress is shown for each file

**If the command fails**, see the Troubleshooting section below.

---

## Step 3: Verify Data Loading

Check that all tables exist and contain data:

```bash
# Activate virtual environment
source .venv/bin/activate

# Open DuckDB CLI
python -c "import duckdb; conn = duckdb.connect('data/duckdb/raw.db'); conn.execute('SHOW ALL TABLES').df()"
```

**Expected output**: List of 18 tables:
```
┌───────────────────────┐
│      table_name       │
├───────────────────────┤
│ allergies             │
│ careplans             │
│ claims                │
│ claims_transactions   │
│ conditions            │
│ devices               │
│ encounters            │
│ imaging_studies       │
│ immunizations         │
│ medications           │
│ observations          │
│ organizations         │
│ patients              │
│ payer_transitions     │
│ payers                │
│ procedures            │
│ providers             │
│ supplies              │
└───────────────────────┘
```

**Query sample data**:
```bash
python -c "import duckdb; conn = duckdb.connect('data/duckdb/raw.db'); print(conn.execute('SELECT COUNT(*) AS patient_count FROM synthea.patients').df())"
```

**Expected output**:
```
   patient_count
0         124000
```

---

## Step 4: Query Data in Superset

1. **Start Superset** (if not already running):
   ```bash
   make superset-run
   ```

2. **Access Superset**:
   - Open http://localhost:8088 in your browser
   - Login with username: `admin`, password: `admin`

3. **Open SQL Lab**:
   - Click **SQL** → **SQL Lab** in the top menu

4. **Select DuckDB Analytics database**:
   - In the SQL Lab, select **DuckDB Analytics** from the database dropdown
   - Select **raw.synthea** from the schema dropdown

   > **Note**: In Superset, the schema appears as `raw.synthea` where `raw` is the database filename and `synthea` is the schema name.

5. **Run a test query**:
   ```sql
   SELECT
       COUNT(*) AS total_patients,
       COUNT(DISTINCT GENDER) AS gender_categories
   FROM raw.synthea.patients;
   ```

   > **Tip**: When using SQL Lab, use `raw.synthea.tablename` for full paths, or just `tablename` if you've selected the `raw.synthea` schema in the dropdown.

   **Expected result**:
   ```
   total_patients  gender_categories
   124000         2
   ```

6. **Try more queries**:

   **Top 10 most common conditions**:
   ```sql
   SELECT
       DESCRIPTION AS condition,
       COUNT(*) AS occurrence_count
   FROM raw.synthea.conditions
   GROUP BY DESCRIPTION
   ORDER BY occurrence_count DESC
   LIMIT 10;
   ```

   **Patient encounter summary**:
   ```sql
   SELECT
       p.FIRST || ' ' || p.LAST AS patient_name,
       COUNT(e.Id) AS encounter_count,
       MIN(e.START) AS first_visit,
       MAX(e.START) AS last_visit
   FROM raw.synthea.patients p
   JOIN raw.synthea.encounters e ON p.Id = e.PATIENT
   GROUP BY p.Id, p.FIRST, p.LAST
   LIMIT 10;
   ```

---

## Common Tasks

### Re-load Data (Idempotent)

If CSV files are updated or you want to refresh the data:

```bash
make load-raw-data
```

This is safe to run multiple times. Existing tables are replaced with fresh data.

### Check Database Size

```bash
du -sh data/duckdb/raw.db
```

**Typical size**: 2-3GB (compressed from 4.3GB CSV)

### List All Tables

```bash
python -c "import duckdb; duckdb.connect('data/duckdb/raw.db').execute('SHOW ALL TABLES').show()"
```

### Get Row Count for All Tables

```bash
python << 'EOF'
import duckdb

conn = duckdb.connect('data/duckdb/raw.db')
tables = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'synthea'").fetchall()

print("Table Row Counts:")
print("-" * 40)
for (table_name,) in tables:
    count = conn.execute(f"SELECT COUNT(*) FROM synthea.{table_name}").fetchone()[0]
    print(f"{table_name:25} {count:>12,}")

EOF
```

### Clear All Data

To remove loaded data and start fresh:

```bash
rm data/duckdb/raw.db
make load-raw-data
```

---

## Troubleshooting

### Error: "data/raw/ directory not found"

**Cause**: Raw CSV files not extracted yet

**Solution**:
```bash
make raw-data-copy
```

### Error: "Virtual environment not activated"

**Cause**: Development environment not set up

**Solution**:
```bash
make dev-setup
source .venv/bin/activate
```

### Error: "No space left on device"

**Cause**: Insufficient disk space (need ~10GB)

**Solution**: Free up disk space and try again:
```bash
# Check disk usage
df -h

# Clean up old Docker images (if using Docker for other projects)
docker system prune -a
```

### Loading Takes Too Long (>15 minutes)

**Cause**: System resource constraints or large dataset

**Check progress**: The loading command shows which file is being processed. The largest file (`claims_transactions.csv`) takes 3-5 minutes alone.

**Solution**: Be patient - the process is working. If it hangs on one file for >10 minutes:
1. Press `Ctrl+C` to cancel
2. Check `data/raw/claims_transactions.csv` file integrity
3. Try running `make load-raw-data` again (it's idempotent)

### Error: "Permission denied writing to data/duckdb/"

**Cause**: File permissions issue

**Solution**:
```bash
chmod -R u+w data/duckdb/
make load-raw-data
```

### Superset Shows "No tables found"

**Cause**: Tables loaded but Superset cache is stale

**Solution**:
1. In Superset, go to **Data** → **Databases**
2. Click **DuckDB Analytics** database
3. Click **Edit** button
4. Go to **Advanced** tab
5. Click **Sync columns from source** (may need to refresh schema)

### Tables Load But Queries Are Slow

**Cause**: DuckDB query execution is working, but Superset may need tuning

**Solution**: This is expected for first-time queries. Subsequent queries should be faster due to DuckDB's caching. For complex queries on large tables (observations, claims_transactions), expect 2-5 second response times.

---

## Next Steps

Now that your data is loaded:

1. **Create Dashboards**: Use Superset to build interactive dashboards
2. **Explore Data**: Run SQL queries to understand the Synthea dataset
3. **Build Reports**: Create charts and visualizations for healthcare insights

**Useful SQL queries to explore**:
- Patient demographics distribution
- Most common diagnoses and procedures
- Healthcare utilization patterns
- Cost analysis from claims data
- Provider and organization statistics

**Documentation**:
- Synthea Data Dictionary: https://github.com/synthetichealth/synthea/wiki/CSV-File-Data-Dictionary
- DuckDB SQL Reference: https://duckdb.org/docs/sql/introduction
- Superset Documentation: https://superset.apache.org/docs/intro

---

## Summary

✅ You've successfully:
- Extracted 18 Synthea CSV files (~4.3GB)
- Loaded all data into DuckDB (18 tables, ~15M rows)
- Verified data is queryable through Superset

**Total time**: ~15 minutes

**Key commands**:
- Extract data: `make raw-data-copy`
- Load data: `make load-raw-data`
- Start Superset: `make superset-run`

**Questions or issues?** Check the Troubleshooting section above or see the main project README.
