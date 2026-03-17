# Validate STM

Validate a Source-to-Target Mapping (STM) Excel workbook for completeness and quality.

## Role Context

You are the Mapping Analyst in the artifact chain: DRD → HLD → DMS → **STM** → DQS → LLD → Stories.
You produce STM documents as Excel workbooks (.xlsx) with 8 sheets covering all Medallion layer
transformations. The output format is .xlsx (not markdown).

## STM Sections Reference (8 Sheets)

| Sheet | Standard Columns |
|---|---|
| **Summary** | Key-value metadata (Version, Created, Author, Status, DMS Ref, HLD Ref) |
| **Source-to-Bronze** | source_table, source_column, source_type, target_table, target_column, target_type, transformation, notes |
| **Bronze-to-Silver** | source_table, source_column, source_type, target_table, target_column, target_type, transformation, null_handling, default_value, business_rule_ref, dms_ref |
| **Silver-to-Gold** | target_table, target_column, target_type, source_expression, join_logic, scd_type, grain, dms_ref |
| **Code Systems** | code_system, source_value_pattern, target_value, case_expression, notes |
| **Null Handling** | table, column, layer, criticality, null_rate_observed, action, default_value, business_rule_ref |
| **Edge Cases** | category, scenario, affected_tables, handling_rule, severity, dq_rule_ref |
| **Lineage** | gold_table, gold_column, silver_expression, bronze_column, source_column, transformation_chain |

## Steps

1. **Find the STM file to validate.**
   If a file path is provided, use it. Otherwise, find the latest:
   ```bash
   ls -d outputs/stm/v* | sort -V | tail -1
   ```
   Then find the most recent .xlsx in that directory.

2. **Run the validator:**
   ```bash
   uv run python mapping-analyst-plugin/skills/validate-stm/scripts/validate_stm.py <file.xlsx>
   ```

3. **Interpret results:**
   - **CRITICAL** issues MUST be fixed before the STM is usable
   - **WARNING** issues should be addressed for production quality
   - **INFO** issues are suggestions for improvement

4. **If CRITICAL issues found**, fix them:
   - Load the workbook with openpyxl
   - Add missing sheets, headers, or data rows
   - Save and re-validate

5. **Report final status** to the user with:
   - Summary counts (CRITICAL / WARNING / INFO)
   - Specific issues found and fixes applied
   - Remaining warnings for user awareness
