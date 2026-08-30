# Transformation Standards — Patient 360 Pipeline

| Field | Value |
|-------|-------|
| Version | 1.0 |
| Last Updated | 2026-03-16 |
| Scope | All Medallion layer transformations |
| Applies To | STM (Source-to-Target Mapping) |

## 1. Idempotency Rules

All transformations MUST be idempotent — re-running on the same source data
produces identical results.

| Rule | Standard | Example |
|------|----------|---------|
| ID-1 | Use MERGE (upsert) for all silver/gold loads | `MERGE INTO slv_patients USING brz_patients ON patient_id` |
| ID-2 | Bronze loads use INSERT with dedup | `INSERT INTO brz_patients SELECT DISTINCT * FROM source` |
| ID-3 | Include batch_id in all bronze records | `batch_id = '{run_date}_{source_file}'` |
| ID-4 | Gold aggregations use full refresh or incremental with watermark | `WHERE updated_at > last_watermark` |

## 2. Type Casting Standards

| Source Type | Target Type | Cast Expression | Notes |
|-------------|-------------|-----------------|-------|
| VARCHAR date strings | DATE | `CAST(col AS DATE)` | Reject if unparseable |
| VARCHAR timestamps | TIMESTAMP | `STRPTIME(col, '%Y-%m-%dT%H:%M:%SZ')` | DuckDB strptime syntax |
| VARCHAR numeric | DECIMAL(p,s) | `TRY_CAST(col AS DECIMAL(18,2))` | NULL on failure |
| VARCHAR boolean | BOOLEAN | `CASE WHEN col IN ('true','1','yes') THEN TRUE ...` | Case-insensitive |
| INTEGER IDs | BIGINT | `CAST(col AS BIGINT)` | Widen for surrogate keys |

## 3. Null Handling Conventions

| Criticality | Action | When to Apply |
|-------------|--------|---------------|
| HIGH | REJECT record | Primary keys, business-critical identifiers |
| MEDIUM | DEFAULT value | Descriptive fields (address, phone) |
| LOW | PASS NULL | Optional/derived fields (death_date, middle_name) |

Default values by type:

| Type | Default | Example |
|------|---------|---------|
| VARCHAR | 'UNKNOWN' | `city = COALESCE(city, 'UNKNOWN')` |
| DATE | '1900-01-01' | Only for non-nullable date fields |
| NUMERIC | 0 | `cost = COALESCE(cost, 0)` |
| BOOLEAN | FALSE | `is_active = COALESCE(is_active, FALSE)` |

## 4. Deduplication Rules

| Rule | Standard | Layer |
|------|----------|-------|
| DD-1 | `ROW_NUMBER() OVER (PARTITION BY pk ORDER BY updated_at DESC) = 1` | Bronze → Silver |
| DD-2 | Source-level dedup before bronze load | Source → Bronze |
| DD-3 | Gold dimensions: SCD merge handles dedup inherently | Silver → Gold |

## 5. String Standardization

| Rule | Standard | Example |
|------|----------|---------|
| SS-1 | TRIM all VARCHAR fields | `TRIM(first_name)` |
| SS-2 | UPPER for code fields | `UPPER(gender)` |
| SS-3 | INITCAP for name fields | `INITCAP(TRIM(first_name))` |
| SS-4 | Remove non-printable characters | `REGEXP_REPLACE(col, '[^\x20-\x7E]', '')` |

## 6. Date/Time Standards

| Rule | Standard |
|------|----------|
| DT-1 | All timestamps stored as UTC |
| DT-2 | Date format: YYYY-MM-DD |
| DT-3 | Timestamp format: YYYY-MM-DD HH:MM:SS.ffffff |
| DT-4 | ingestion_timestamp = CURRENT_TIMESTAMP at load time |
| DT-5 | effective_from/effective_to for SCD Type 2 |

## 7. Surrogate Key Generation

| Rule | Standard | Example |
|------|----------|---------|
| SK-1 | Use BIGINT sequence for dimension surrogate keys | `patient_sk BIGINT GENERATED ALWAYS AS IDENTITY` |
| SK-2 | Hash-based keys for large dimensions | `MD5(CONCAT(col1, '\|', col2))` |
| SK-3 | -1 for unknown/missing dimension members | `DEFAULT -1 for FK columns` |

## 8. SCD Merge Patterns

### Type 1 (Overwrite)
```sql
MERGE INTO dim_table t
USING staging s ON t.natural_key = s.natural_key
WHEN MATCHED THEN UPDATE SET t.col = s.col, t.updated_at = CURRENT_TIMESTAMP
WHEN NOT MATCHED THEN INSERT (...)
```

### Type 2 (History)
```sql
-- Step 1: Expire changed records
UPDATE dim_table SET effective_to = CURRENT_DATE - 1, is_current = FALSE
WHERE natural_key IN (SELECT natural_key FROM staging WHERE has_changes)
  AND is_current = TRUE;

-- Step 2: Insert new versions
INSERT INTO dim_table (natural_key, ..., effective_from, effective_to, is_current)
SELECT natural_key, ..., CURRENT_DATE, '9999-12-31', TRUE FROM staging WHERE has_changes;
```
