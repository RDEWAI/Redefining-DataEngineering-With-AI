---
Version: 1.0
Status: Approved
Topic: Module, table, column, and config-key naming
---

# Naming Conventions

## Purpose

Consistent naming across projects so a reader moving between them can
predict, from a name alone, what kind of object they are looking at
(dimension vs fact, natural vs surrogate key, boolean flag, audit column,
etc.).

## Pattern

### Tables

| Kind | Prefix | Example |
|---|---|---|
| Bronze raw | (none; table = source name) | `bronze.{source_table}` |
| Silver dimension | `dim_` | `silver.dim_{entity}` |
| Silver fact | `fct_` | `silver.fct_{event}` |
| Gold consumer dataset | `{subject}_summary` / `{subject}_metrics` | `gold.{subject}_summary` |

Catalogs: `spark_catalog`. Schemas: `bronze`, `silver`, `gold` (one per
layer, never project-prefixed — the catalog holds the project).

### Columns

| Suffix | Meaning |
|---|---|
| `_nk` | Natural key (source system key) — carried on facts |
| `_sk` | Surrogate key (UUID) — PK of a SCD2 dimension |
| `_flag` | Boolean, always `true`/`false` (never `Y`/`N` or `1`/`0`) |
| `_datetime` | Timestamp column |
| `_date` | Date-only column |
| `_years` / `_minutes` / `_days` | Numeric unit-suffixed derivations |
| `_masked` | PII-masked text (SSN, etc.) |

### SCD2 metadata columns (on every silver dim)

| Column | Type | Meaning |
|---|---|---|
| `surrogate_key` | string (UUID) | Dimension PK |
| `start_ts` | date | Row is valid from this date |
| `end_ts` | date | Row is valid through this date (null for current) |
| `dim_is_current` | boolean | True iff the row is the current version |
| `record_hash` | string | Hash over tracked columns — change-detection key |
| `dw_created_at` / `dw_updated_at` | timestamp | Warehouse audit |

### Audit columns (on every bronze + silver fact)

| Column | Type | Meaning |
|---|---|---|
| `ds` | date (string `YYYY-MM-DD`) | Partition key = logical run date |
| `ingested_at` | timestamp | `current_timestamp()` at write time |

### Files & modules

| Kind | Convention |
|---|---|
| Python module | lowercase snake_case (`ingest.py`, `scd2.py`, `dims.py`) |
| Test module | `test_{module}.py` mirroring `src/{project}/{layer}/{module}.py` |
| Expectation rule file | `{layer}/{table}_expectations.json` |
| Airflow DAG file | `{project}_{schedule}_v{N}.py` (e.g. `patient_360_hourly_v1.py`) |
| Config YAML | `airflow/configs/{table}.yml` — one per table |

### Config keys

All JSON / YAML keys are `snake_case`. Boolean values are lowercase
`true`/`false`. Lists of string enums use lowercase (`fail`, `drop`,
`warn`).

## Illustrative examples

```
# Silver dim
silver.dim_{entity}
  surrogate_key, {entity}_id (natural key), start_ts, end_ts,
  dim_is_current, record_hash, ...tracked columns..., dw_created_at

# Silver fact
silver.fct_{event}
  {event}_id, {parent}_nk, {parent}_sk, start_datetime, duration_minutes,
  {event}_status, ds, ingested_at

# Gold consumer dataset
gold.{subject}_summary
  {subject}_id, {subject}_full_name, total_{metric}, total_{cost}, ds
```

## Common pitfalls

- Using plural dim names (`dim_patients_table`) — stick to singular-plural
  convention matching the source (`dim_patients` because source is
  `patients`). The `dim_` / `fct_` prefix already disambiguates role.
- Letting `dim_is_current` become int (`0`/`1`) — always boolean.
- Naming a natural key without `_nk` on a fact — readers can't tell it
  apart from a surrogate key.
- Omitting `_years` / `_minutes` unit suffixes on derived numeric columns
  — ambiguity on `age` (days? years?).

## References

- `/mvp/src/patient_360/silver/dims.py` (SCD2 config + metadata columns)
- `/mvp/src/patient_360/silver/facts.py` (NK/SK conventions)
- `/mvp/src/patient_360/silver/transformations.py` (unit suffixes)
- `/mvp/src/patient_360/bronze/schemas.py` (bronze column names)
