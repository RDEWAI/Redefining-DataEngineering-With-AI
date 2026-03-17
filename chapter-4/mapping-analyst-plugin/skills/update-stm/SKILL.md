# Update STM

Update an existing Source-to-Target Mapping (STM) Excel workbook with new information.

## Role Context

You are the Mapping Analyst in the artifact chain: DRD → HLD → DMS → **STM** → DQS → LLD → Stories.
You produce STM documents as Excel workbooks (.xlsx) with 8 sheets covering all Medallion layer
transformations. The output format is .xlsx (not markdown), generated using openpyxl.

## Pitfall Prevention

1. **Mapping from memory instead of metadata** — MUST query DESCRIBE and SELECT LIMIT 10
   on actual source tables before adding or modifying mappings.
2. **Ignoring null rates** — Check actual null rates for any new columns being mapped.
3. **Under-specifying transformation logic** — Every transformation must be an explicit SQL
   expression, not English prose like "clean the address".

## Steps

1. **Load the existing STM workbook.**
   ```bash
   ls -d outputs/stm/v* | sort -V | tail -1
   ```
   Load the xlsx file with openpyxl:
   ```python
   import openpyxl
   wb = openpyxl.load_workbook("path/to/existing.xlsx")
   ```

2. **Identify what changed.**
   - New DMS version? Read the updated DMS and diff against existing mappings.
   - New source tables? Verify via DESCRIBE before adding mappings.
   - Revised transformations? Confirm the specific changes needed.

3. **Ask the user to confirm scope of changes** using `AskUserQuestion`:
   ```json
   {
     "questions": [
       {
         "question": "What type of STM update is needed?",
         "header": "Update Type",
         "multiSelect": true,
         "options": [
           { "label": "New tables", "description": "Add mappings for new source tables" },
           { "label": "Transform fix", "description": "Fix existing transformation logic" },
           { "label": "SCD change", "description": "Change SCD type for a dimension" },
           { "label": "Schema update", "description": "Source schema changed, update mappings" }
         ]
       }
     ]
   }
   ```

4. **Modify affected sheets** while preserving unchanged content:
   - Add new rows for new mappings
   - Update existing cells for revised transformations
   - Update Summary sheet metadata (version, date, change description)
   - Maintain formatting (bold headers, color fills, auto-filter)

5. **Save and validate:**
   ```python
   wb.save("outputs/stm/v{N}/STM-{YYYY-MM-DD}-{pipeline-name}.xlsx")
   ```
   ```bash
   uv run python mapping-analyst-plugin/skills/validate-stm/scripts/validate_stm.py <file>
   ```

6. **Write session memory** to `mapping-analyst-plugin/memory/`:
   - What was changed and why
   - DMS sections affected
   - Any open items for next session

## Reference: Four Responsibilities

1. **Source-to-Bronze Mappings** — Column pass-through with metadata injection
2. **Bronze-to-Silver Transformations** — Type conversions, null handling, dedup, business rules
3. **Silver-to-Gold Mappings** — Surrogate keys, SCD merge, joins, aggregations
4. **Edge Case & Lineage Documentation** — Schema evolution, FK failures, full column-level lineage
