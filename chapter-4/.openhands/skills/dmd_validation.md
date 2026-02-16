---
name: dmd_validation
triggers:
  - data mapping
  - dmd
  - mapping document
  - validate dmd
  - column mapping
---

# DMD (Data Mapping Document) Validation

## Format Requirements

- **Format**: CSV (raw, no code fences)
- **Exactly 13 columns** in THIS order:
  1. source_system
  2. source_table
  3. source_column
  4. source_type
  5. target_table
  6. target_column
  7. target_type
  8. transformation
  9. business_rule
  10. nullable
  11. default_value
  12. notes
  13. layer

## Layer Values (Column 13)

- **bronze**: Raw source data, minimal transformation
- **silver**: Cleaned, standardized, type-converted
- **gold**: Aggregated, business-ready, dimensional

## Validation Checklist

Format checks:
- [ ] First line is header with exactly 13 columns
- [ ] Header starts with `source_system` (NOT `target_table`)
- [ ] Header ends with `layer`
- [ ] No code fences (```csv) around content
- [ ] No preamble text before CSV
- [ ] No markdown headers or prose

Content checks:
- [ ] All rows have exactly 13 columns
- [ ] Layer values are ONLY: bronze, silver, or gold
- [ ] All source tables from DRD are mapped
- [ ] Transformations are valid SQL/DuckDB expressions
- [ ] Business rules reference BR codes from DRD

## Common Issues

### 1. Wrong column order (target before source)
**BAD:**
```
target_table,target_column,source_system...
```
**GOOD:**
```
source_system,source_table,source_column...
```

### 2. Missing layer column (only 12 columns)
**BAD:** 12 columns without layer
**GOOD:** 13 columns with layer as last

### 3. Invalid layer values
**BAD:** `layer: raw`, `layer: clean`, `layer: business`
**GOOD:** `layer: bronze`, `layer: silver`, `layer: gold`

### 4. Wrapped in code fences
**BAD:**
```
```csv
source_system,source_table...
```
```
**GOOD:**
```
source_system,source_table...
```

### 5. Markdown prose instead of CSV
**BAD:** Starting with `# Data Mapping Document`
**GOOD:** Starting directly with CSV header

## Example Valid DMD

```
source_system,source_table,source_column,source_type,target_table,target_column,target_type,transformation,business_rule,nullable,default_value,notes,layer
<source>,<table>,<id_col>,VARCHAR,bronze.<table>,<id_col>,VARCHAR,<id_col>,BR001,No,,Raw copy from source,bronze
<source>,<table>,<id_col>,VARCHAR,silver.<table>,<id_col>_id,VARCHAR,TRIM(<id_col>),BR001,No,,Primary key cleaned,silver
<source>,<table>,<date_col>,DATE,bronze.<table>,<date_col>,DATE,<date_col>,BR002,No,,Raw date,bronze
<source>,<table>,<date_col>,DATE,silver.<table>,<date_col>,DATE,CAST(<date_col> AS DATE),BR002,No,,Date conversion,silver
```

## Cross-Reference Validation

When validating DMD against DRD:
- All source tables mentioned in DRD should appear in DMD
- All source columns from DRD entity definitions should be mapped
- Business rules (BR codes) should match those defined in DRD
