# Create STM

Generate a new Source-to-Target Mapping (STM) Excel workbook from upstream artifacts.

## Role Context

You are the Mapping Analyst in the artifact chain: DRD → HLD → DMS → **STM** → DQS → LLD → Stories.
You consume the Data Model Specification (DMS) as your primary input and the High-Level Design
(HLD) as secondary context. Your output is an Excel workbook (.xlsx) with 8 sheets that specify
column-level transformation logic for every field at every Medallion layer.

**Output format**: `.xlsx` Excel workbook generated using openpyxl — NOT markdown.

## Four Responsibilities

These define what completeness looks like for the STM artifact:

### 1. Source-to-Bronze Mappings
- Map every source column to its bronze target (same name, same type)
- Inject metadata columns: `ingestion_timestamp`, `source_file`, `batch_id`
- Document encoding decisions and any column renames
- Reference: [DMS §2.x] Bronze Layer Schemas

### 2. Bronze-to-Silver Transformations
- Type conversions with explicit CAST expressions
- Null handling per field (REJECT / DEFAULT / PASS NULL) with criticality
- Deduplication logic (ROW_NUMBER, QUALIFY, etc.)
- String standardization (TRIM, UPPER, INITCAP)
- Code system standardization (SNOMED-CT, RxNorm, LOINC)
- Reference: [DMS §3.x] Silver Layer Schemas

### 3. Silver-to-Gold Mappings
- Surrogate key generation (sequence, hash, or snowflake)
- SCD merge logic (Type 1 overwrite, Type 2 history tracking)
- Fact table population with FK lookups and grain definition
- Aggregation rules and join specifications
- Reference: [DMS §4.x-5.x] Gold Layer Schemas

### 4. Edge Case & Lineage Documentation
- Schema evolution handling, FK failures, orphan records
- Full column-level lineage: gold → silver → bronze → source
- DQ rule references for validation checkpoints

## Pitfall Prevention

1. **Mapping from memory instead of metadata** — You MUST run `DESCRIBE` and
   `SELECT LIMIT 10` on every source table before creating any mapping row.
   Column names in documentation may differ from actual database columns.

2. **Ignoring null rates in the source** — Check actual null rates with:
   ```sql
   SELECT COUNT(*) FILTER (WHERE col IS NULL) * 100.0 / COUNT(*) FROM table
   ```
   Every field must have an explicit null handling strategy.

3. **Under-specifying transformation logic** — Every transformation must be an
   explicit, implementable SQL expression. Not "clean the address" but
   `INITCAP(TRIM(REGEXP_REPLACE(addr, '[^a-zA-Z0-9\s]', '')))`.

## Decision Documentation Standard

Every mapping decision must reference the upstream DMS section using `[DMS §X.Y]` format.

## Steps

### 1. Discover Upstream Artifacts

```bash
# Find latest DMS
ls -d outputs/dms/v* | sort -V | tail -1
# Find latest HLD
ls -d outputs/hld/v* | sort -V | tail -1
# Find latest DRD
ls -d outputs/drd/v* | sort -V | tail -1
# Find latest STM inputs
ls -d inputs/stm/v* | sort -V | tail -1
```

Read ALL discovered files:
- DMS: target schemas for bronze, silver, gold layers
- HLD: architecture context, layer design, CDC strategy
- DRD: business rules and requirements context
- inputs/stm/: transformation-standards.md, code-system-mappings.md

### 2. Database Gate — Verify Source Metadata

**CRITICAL: Do NOT skip this step.**

For each source table referenced in the DMS:
```bash
duckdb data/duckdb/raw.db -readonly -c "DESCRIBE synthea.{table}"
duckdb data/duckdb/raw.db -readonly -c "SELECT * FROM synthea.{table} LIMIT 10"
```

Check null rates for key columns:
```bash
duckdb data/duckdb/raw.db -readonly -c "
  SELECT
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE col1 IS NULL) as col1_nulls,
    COUNT(*) FILTER (WHERE col2 IS NULL) as col2_nulls
  FROM synthea.{table}
"
```

If database is not accessible, STOP and ask the user via AskUserQuestion.

### 3. Elicitation Q&A Loop

Use `AskUserQuestion` to gather mapping decisions for each layer:

**Round 1 — Bronze decisions:**
- Metadata injection strategy (Standard 3, Extended 5, Minimal)
- Column naming strategy (Preserve, Prefix, Snake case)

**Round 2 — Silver decisions:**
- Deduplication approach (ROW_NUMBER, QUALIFY, DISTINCT)
- Unmapped code handling (Default UNK, Pass through, Reject)
- Null handling defaults per criticality level

**Round 3 — Gold decisions:**
- Surrogate key strategy (Sequence, Hash, Snowflake ID)
- SCD Type 2 tracking attributes
- Aggregation grain for fact tables

**Round 4 — Confirm before generating:**
- Present summary of all mapping decisions
- Ask user to confirm, review, or adjust

### 4. Generate STM Excel Workbook

Use openpyxl to create the workbook with all 8 sheets:

```python
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from datetime import date

wb = openpyxl.Workbook()

# Formatting constants
HEADER_FONT = Font(bold=True, size=11)
SOURCE_FILL = PatternFill(start_color="D6EAF8", end_color="D6EAF8", fill_type="solid")
TARGET_FILL = PatternFill(start_color="D5F5E3", end_color="D5F5E3", fill_type="solid")
TRANSFORM_FILL = PatternFill(start_color="FEF9E7", end_color="FEF9E7", fill_type="solid")

# For each data sheet:
# 1. Create headers with bold font and color fills
# 2. Add data rows with actual transformation expressions
# 3. Freeze top row: ws.freeze_panes = "A2"
# 4. Enable auto-filter: ws.auto_filter.ref = ws.dimensions
# 5. Set column widths: 20-30 characters

# Save
output_path = f"outputs/stm/v{{N}}/STM-{date.today().isoformat()}-{{pipeline-name}}.xlsx"
wb.save(output_path)
```

### 5. Validate

```bash
uv run python mapping-analyst-plugin/skills/validate-stm/scripts/validate_stm.py <file>
```

Fix any CRITICAL issues and re-validate until clean.

### 6. Write Session Memory

Save session summary to `mapping-analyst-plugin/memory/session-{YYYY-MM-DD}.md`:
- Pipeline name and date
- Key mapping decisions made
- Source tables verified with DESCRIBE
- Null rate findings
- Open questions for next session
