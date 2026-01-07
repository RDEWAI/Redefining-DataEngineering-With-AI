---
name: duckdb
triggers:
  - duckdb
  - duck db
  - sql query
  - database
  - query
---

# DuckDB Knowledge

## Database Location

- **Path**: `data/duckdb/raw.db` (or `../data/duckdb/raw.db` from chapter-4)
- **Schema**: `synthea`

## Query Patterns

- Tables are accessed as `synthea.<table_name>` (e.g., `synthea.patients`)
- Always use `LIMIT` clause for data exploration (e.g., `LIMIT 5` or `LIMIT 10`)
- Use `duckdb_tables` tool first to list available tables
- Use `duckdb_schema` tool to inspect table structure before querying

## Available Tables (Synthea Healthcare Data)

| Table | Description |
|-------|-------------|
| `synthea.patients` | Patient demographics (Id, BIRTHDATE, GENDER, etc.) |
| `synthea.encounters` | Healthcare encounters/visits |
| `synthea.conditions` | Diagnoses and conditions |
| `synthea.medications` | Prescribed medications |
| `synthea.procedures` | Medical procedures |
| `synthea.observations` | Clinical observations (vital signs, lab results) |
| `synthea.immunizations` | Vaccination records |
| `synthea.allergies` | Patient allergies |
| `synthea.careplans` | Care plan information |
| `synthea.providers` | Healthcare provider information |
| `synthea.organizations` | Healthcare organizations |
| `synthea.payers` | Insurance/payer information |
| `synthea.payer_transitions` | Insurance coverage changes |
| `synthea.claims` | Healthcare claims |
| `synthea.claims_transactions` | Claim line items |
| `synthea.devices` | Medical devices |
| `synthea.supplies` | Medical supplies |
| `synthea.imaging_studies` | Imaging study records |

## Common Query Examples

```sql
-- List all tables
SHOW TABLES;

-- Get table schema
DESCRIBE synthea.patients;

-- Sample patient data
SELECT * FROM synthea.patients LIMIT 5;

-- Count records
SELECT COUNT(*) FROM synthea.encounters;

-- Join example
SELECT p.Id, p.FIRST, p.LAST, e.DESCRIPTION
FROM synthea.patients p
JOIN synthea.encounters e ON p.Id = e.PATIENT
LIMIT 10;
```

## Performance Tips

- DuckDB handles CSV files natively via `read_csv_auto()`
- Use columnar operations for large datasets
- Avoid `SELECT *` on large tables - specify columns needed
- Use `EXPLAIN` to analyze query plans

## Tool Usage Limits

- Call `duckdb_tables` ONCE to see all tables
- Call `duckdb_schema` for 2-3 relevant tables only
- Call `duckdb_query` sparingly with `LIMIT` clauses
- After 3-5 tool calls, generate the artifact
