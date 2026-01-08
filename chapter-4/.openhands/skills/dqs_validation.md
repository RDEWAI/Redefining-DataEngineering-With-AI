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
**GOOD:** Specific tables like `silver.patients`

## Example Valid DQS

```yaml
version: "1.0"
metadata:
  name: "Healthcare Analytics DQS"
  description: "Data quality specification for Synthea data pipeline"

quality_dimensions:
  completeness:
    rules:
      - name: patient_id_not_null
        table: silver.patients
        column: patient_id
        check: "patient_id IS NOT NULL"
        severity: critical

  accuracy:
    rules:
      - name: valid_birthdate
        table: silver.patients
        column: birth_date
        check: "birth_date <= CURRENT_DATE"
        severity: high

  consistency:
    rules:
      - name: encounter_patient_exists
        table: silver.encounters
        check: "patient_id IN (SELECT patient_id FROM silver.patients)"
        severity: critical

  uniqueness:
    rules:
      - name: unique_patient_id
        table: silver.patients
        column: patient_id
        check: "COUNT(*) = COUNT(DISTINCT patient_id)"
        severity: critical

  validity:
    rules:
      - name: valid_gender
        table: silver.patients
        column: gender
        check: "gender IN ('M', 'F', 'O')"
        severity: medium

  timeliness:
    rules:
      - name: recent_encounters
        table: gold.fact_encounters
        check: "MAX(encounter_date) >= CURRENT_DATE - INTERVAL '30 days'"
        severity: low

quality_gates:
  - name: "Bronze to Silver Gate"
    threshold: 95
    rules:
      - patient_id_not_null
      - valid_birthdate

  - name: "Silver to Gold Gate"
    threshold: 99
    rules:
      - unique_patient_id
      - encounter_patient_exists
```
