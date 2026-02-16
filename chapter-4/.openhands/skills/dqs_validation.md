---
name: dqs_validation
triggers:
  - data quality
  - dqs
  - quality specification
  - validate dqs
  - quality rules
---

# DQS (Data Quality Specification) Validation

## Format Requirements

- **Format**: YAML (.yaml)
- **First line MUST be**: `version: "1.0"`
- **No code fences** around content
- **Valid YAML syntax**

## Required Structure

```yaml
version: "1.0"
metadata:
  name: "Project Name DQS"
  description: "Data quality specification for..."

quality_dimensions:
  completeness:
    rules: [...]
  accuracy:
    rules: [...]
  consistency:
    rules: [...]
  uniqueness:
    rules: [...]
  validity:
    rules: [...]
  timeliness:
    rules: [...]

quality_gates:
  - name: "Bronze to Silver Gate"
    rules: [...]
  - name: "Silver to Gold Gate"
    rules: [...]
```

## Required Quality Dimensions

All 6 must be present:
1. **completeness** - Data is not missing
2. **accuracy** - Data values are correct
3. **consistency** - Data is uniform across sources
4. **uniqueness** - No duplicates where expected
5. **validity** - Data conforms to formats/rules
6. **timeliness** - Data is current and up-to-date

## Validation Checklist

Format checks:
- [ ] First line is `version: "1.0"`
- [ ] No code fences (```yaml)
- [ ] Valid YAML syntax (parseable)
- [ ] Root is a YAML object/dictionary

Content checks:
- [ ] `quality_dimensions` section present
- [ ] All 6 quality dimensions defined
- [ ] Each dimension has `rules` array
- [ ] `quality_gates` section present (recommended)
- [ ] Rules reference actual table names from DMD
- [ ] No placeholder text

## Common Issues

### 1. First line is code fence, not version
**BAD:**
```
```yaml
version: "1.0"
```
**GOOD:**
```
version: "1.0"
```

### 2. Missing quality dimensions
**BAD:** Only 3 dimensions
**GOOD:** All 6 dimensions present

### 3. Invalid YAML syntax
**BAD:** Incorrect indentation, missing quotes
**GOOD:** Properly indented, valid YAML

### 4. Rules don't reference actual tables
**BAD:** Generic `table_name` placeholders
**GOOD:** Specific tables like `silver.<table>` (based on your DMD)

## Example Valid DQS

```yaml
version: "1.0"
metadata:
  name: "<Project Name> DQS"
  description: "Data quality specification for <project> data pipeline"

quality_dimensions:
  completeness:
    rules:
      - name: <primary_key>_not_null
        table: silver.<table>
        column: <primary_key>
        check: "<primary_key> IS NOT NULL"
        severity: critical

  accuracy:
    rules:
      - name: valid_<date_field>
        table: silver.<table>
        column: <date_field>
        check: "<date_field> <= CURRENT_DATE"
        severity: high

  consistency:
    rules:
      - name: <child_table>_<parent>_exists
        table: silver.<child_table>
        check: "<foreign_key> IN (SELECT <primary_key> FROM silver.<parent_table>)"
        severity: critical

  uniqueness:
    rules:
      - name: unique_<primary_key>
        table: silver.<table>
        column: <primary_key>
        check: "COUNT(*) = COUNT(DISTINCT <primary_key>)"
        severity: critical

  validity:
    rules:
      - name: valid_<column>
        table: silver.<table>
        column: <column>
        check: "<column> IN ('<valid_value_1>', '<valid_value_2>')"
        severity: medium

  timeliness:
    rules:
      - name: recent_<table>
        table: gold.fact_<table>
        check: "MAX(<date_column>) >= CURRENT_DATE - INTERVAL '30 days'"
        severity: low

quality_gates:
  - name: "Bronze to Silver Gate"
    threshold: 95
    rules:
      - <primary_key>_not_null
      - valid_<date_field>

  - name: "Silver to Gold Gate"
    threshold: 99
    rules:
      - unique_<primary_key>
      - <child_table>_<parent>_exists
```
