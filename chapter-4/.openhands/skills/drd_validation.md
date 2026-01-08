---
name: drd_validation
triggers:
  - data requirements
  - drd
  - requirements document
  - validate drd
---

# DRD (Data Requirements Document) Validation

## Format Requirements

- **Format**: Markdown (.md)
- **Header**: Must start with `# Data Requirements Document`
- **No code fences** around the entire document
- **No ASCII art diagrams** - use Mermaid instead

## Required Sections

1. **Overview/Executive Summary** - Project context and objectives
2. **Data Sources** - Source systems with connection details
3. **Entity Definitions** - Tables/entities with attribute definitions
4. **Business Rules** - Data transformation and business logic rules

## Validation Checklist

Format checks:
- [ ] Document starts with `# Data Requirements Document` header
- [ ] No ``` markers wrapping the entire document
- [ ] No ASCII art characters (┌ ─ ┐ │ └ ┘)

Content checks:
- [ ] Overview section present
- [ ] Data sources section with specific system names
- [ ] Entity definitions with attribute tables
- [ ] Business rules section with numbered rules
- [ ] No placeholder text ([TBD], [TODO], etc.)

Quality checks:
- [ ] Minimum 20 non-empty lines
- [ ] Entity tables have: Field, Type, Description columns
- [ ] Specific values, not generic examples

## Common Issues

1. **Missing sections** - Add all required section headers
2. **Incomplete entity definitions** - Include all columns and data types
3. **Vague business rules** - Make rules specific and measurable
4. **Placeholder content** - Replace [TBD] with actual values
5. **ASCII diagrams** - Convert to Mermaid flowcharts

## Example Valid Structure

```markdown
# Data Requirements Document

## 1. Project Overview
Brief description of the data pipeline project...

## 2. Data Sources
### 2.1 Source System: Synthea
- Connection: DuckDB at ../data/duckdb/raw.db
- Schema: synthea
- Tables: patients, encounters, conditions

## 3. Entity Definitions
### 3.1 Patients
| Field | Type | Description | Nullable |
|-------|------|-------------|----------|
| id | VARCHAR | Unique patient identifier | No |
| birthdate | DATE | Patient date of birth | No |

## 4. Business Rules
- BR001: Patient ID must be unique
- BR002: Birthdate must be in the past
```
