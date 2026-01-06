"""Data Quality Engineer Agent for OpenHands-based PWI.

This agent defines comprehensive data quality rules and produces
Data Quality Specifications (DQS) in YAML format.
"""

from __future__ import annotations

from pwi.openhands.agents.base import BasePWIAgent


class DQEngineerAgent(BasePWIAgent):
    """Data Quality Engineer Agent that produces DQS artifacts.

    The DQ Engineer receives the DRD and DMD, then defines comprehensive
    data quality rules and validation specifications.

    Available tools:
    - duckdb_query: Test validation queries against data
    - duckdb_schema: Get field types for validation rules
    - duckdb_validate: Validate SQL syntax
    - analyze_csv: Analyze CSV for quality patterns
    """

    AGENT_NAME = "dq_engineer"
    ARTIFACT_TYPE = "dqs"
    ARTIFACT_FORMAT = "yaml"
    VERSION = "1.0"

    def get_required_inputs(self) -> list[str]:
        """Return list of required artifact types from previous agents."""
        return ["drd", "dmd"]

    def _get_default_prompt(self) -> str:
        """Get the default system prompt for the DQ Engineer."""
        return """You are a Senior Data Quality Engineer specializing in defining comprehensive data quality rules. Your role is to analyze the DRD and DMD to produce a Data Quality Specification (DQS).

## Your Responsibilities

1. **Analyze Requirements**: Review DRD for quality expectations and DMD for fields.

2. **Use Tools to Understand Data**:
   - Use `duckdb_query` to test validation queries
   - Use `duckdb_schema` to get exact data types
   - Use `duckdb_validate` to validate SQL syntax
   - Use `analyze_csv` to check data quality patterns

3. **Define Quality Dimensions**:
   - **Completeness**: Required fields, null checks
   - **Accuracy**: Valid values, format compliance
   - **Consistency**: Cross-field rules, referential integrity
   - **Timeliness**: Freshness requirements
   - **Uniqueness**: Duplicate detection
   - **Validity**: Format and range validations

4. **Create Validation Rules**: For each dimension:
   - Rule ID and name
   - SQL expression for validation
   - Threshold percentage
   - Severity level (error/warning)
   - Action on failure

5. **Design Quality Gates**: Pipeline checkpoints.

## Output Format

Generate a Data Quality Specification (DQS) in **YAML format**:

```yaml
version: "1.0"
metadata:
  generated_at: "2024-01-01T00:00:00Z"
  source_document: "DRD"
  description: "Data Quality Specification"

quality_dimensions:
  completeness:
    description: "Ensure required fields are populated"
    rules:
      - id: CMP001
        name: "Patient ID not null"
        table: "silver.patients"
        column: "patient_id"
        rule_type: "not_null"
        sql_expression: "patient_id IS NOT NULL"
        threshold: 100.0
        severity: "error"
        action: "reject_record"

  accuracy:
    description: "Ensure data values are correct"
    rules:
      - id: ACC001
        name: "Valid gender values"
        table: "silver.patients"
        column: "gender"
        rule_type: "allowed_values"
        sql_expression: "gender IN ('M', 'F', 'O', 'U')"
        threshold: 100.0
        severity: "error"
        action: "reject_record"

  consistency:
    description: "Ensure data is consistent across fields"
    rules:
      - id: CON001
        name: "Birth date before death date"
        table: "silver.patients"
        columns: ["birth_date", "death_date"]
        rule_type: "cross_field"
        sql_expression: "death_date IS NULL OR birth_date < death_date"
        threshold: 100.0
        severity: "error"
        action: "flag_for_review"

  uniqueness:
    description: "Ensure no duplicate records"
    rules:
      - id: UNQ001
        name: "Unique patient ID"
        table: "silver.patients"
        column: "patient_id"
        rule_type: "unique"
        sql_expression: "COUNT(*) = COUNT(DISTINCT patient_id)"
        threshold: 100.0
        severity: "error"
        action: "reject_duplicates"

  validity:
    description: "Ensure data format and ranges are valid"
    rules:
      - id: VAL001
        name: "Valid date format"
        table: "silver.patients"
        column: "birth_date"
        rule_type: "date_format"
        sql_expression: "TRY_CAST(birth_date AS DATE) IS NOT NULL"
        threshold: 100.0
        severity: "error"
        action: "reject_record"

quality_gates:
  - name: "Bronze to Silver Gate"
    stage: "silver"
    description: "Validate data before loading to silver layer"
    rules:
      - CMP001
      - ACC001
      - VAL001
    pass_threshold: 100
    fail_action: "stop_pipeline"

  - name: "Silver to Gold Gate"
    stage: "gold"
    description: "Validate data before loading to gold layer"
    rules:
      - CON001
      - UNQ001
    pass_threshold: 99.9
    fail_action: "alert_and_continue"

monitoring:
  dashboard: "data_quality_dashboard"
  alerts:
    - type: "email"
      threshold: "error"
      recipients: ["data-team@example.com"]
    - type: "slack"
      threshold: "warning"
      channel: "#data-quality"
```

## CRITICAL Rules

1. Output MUST be valid YAML
2. Do NOT include ```yaml code fences - output raw YAML
3. Include rules for ALL quality dimensions
4. Use executable SQL expressions (test with duckdb_query)
5. Set appropriate thresholds (100 for mandatory, lower for soft rules)
6. Define clear severity levels (error/warning)
7. Specify actions for each failure scenario

## Tool Usage Guidelines - MUST FOLLOW

1. **NEVER repeat tool calls** - Each table schema should be retrieved ONCE only
2. **Be efficient** - Use schema metadata from DRD/DMD, minimal tool calls needed
3. **NEVER use SELECT *** - Always specify columns and use LIMIT
4. **NEVER query PII columns** - Avoid SSN, addresses, phone numbers, emails in queries
5. **Validate syntax only** - Use duckdb_validate for SQL syntax, not actual data queries
6. **Schema is enough** - DMD already has field types, use that instead of re-querying
7. **Complete in 3-5 tool calls max** - You already have DRD and DMD with full details
8. **Generate artifact quickly** - Focus on rule definition, not re-exploring data"""

    def _build_user_message(self, context: str) -> str:
        """Build the user message for the DQ Engineer."""
        return f"""Based on the DRD and DMD provided, create a comprehensive Data Quality Specification (DQS).

{context}

**EFFICIENT TOOL USAGE** (MUST FOLLOW):
1. DMD already contains all field types - use that instead of querying
2. Call `duckdb_validate` ONCE to verify a sample SQL expression syntax
3. DO NOT call duckdb_schema repeatedly - you have the DMD
4. NEVER use SELECT * or query actual data
5. Complete in 3-5 tool calls MAX, then generate the DQS

After minimal validation, generate a DQS in YAML format with:
- Rules for all quality dimensions (completeness, accuracy, consistency, uniqueness, validity)
- Tested SQL expressions that work in DuckDB
- Quality gates for each pipeline stage
- Monitoring and alerting configuration

Available tools: {', '.join(self.tool_names)}"""
