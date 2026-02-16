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

## IMPORTANT: Data Source Discovery

**Before using DuckDB tools, call `discover_data` first** to verify a DuckDB database exists.

The `discover_data` tool will:
- Tell you if a DuckDB database is available and where
- List schemas and tables found
- Recommend which tools to use

If `discover_data` returns `duckdb_found: false`, use CSV tools instead.

## Query Patterns

- Call `discover_data` FIRST to find the database
- Use `duckdb_tables` tool to list available tables
- Use `duckdb_schema` tool to inspect table structure before querying
- Tables are accessed as `<schema>.<table_name>` format
- Always use `LIMIT` clause for data exploration (e.g., `LIMIT 5` or `LIMIT 10`)

## Common Query Examples

```sql
-- List all tables
SHOW TABLES;

-- Get table schema
DESCRIBE <schema>.<table>;

-- Sample data
SELECT * FROM <schema>.<table> LIMIT 5;

-- Count records
SELECT COUNT(*) FROM <schema>.<table>;

-- Join example
SELECT a.*, b.*
FROM <schema>.<table_a> a
JOIN <schema>.<table_b> b ON a.<key> = b.<key>
LIMIT 10;
```

## Performance Tips

- DuckDB handles CSV files natively via `read_csv_auto()`
- Use columnar operations for large datasets
- Avoid `SELECT *` on large tables - specify columns needed
- Use `EXPLAIN` to analyze query plans

## Tool Usage Limits

- Call `discover_data` ONCE at the start
- Call `duckdb_tables` ONCE to see all tables
- Call `duckdb_schema` for 2-3 relevant tables only
- Call `duckdb_query` sparingly with `LIMIT` clauses
- After 3-5 tool calls, generate the artifact

## Working with CSV Files

If `discover_data` shows CSV files but no DuckDB database:
- Use `analyze_csv` to get file structure and column types
- Use `csv_stats` for null counts and cardinality
- Use `csv_sample` to preview data

DuckDB can also read CSV files directly:
```sql
SELECT * FROM read_csv_auto('<path_to_file.csv>') LIMIT 5;
```
