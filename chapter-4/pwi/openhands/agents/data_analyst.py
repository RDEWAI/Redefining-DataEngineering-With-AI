"""Data Analyst Agent for OpenHands-based PWI.

This agent analyzes business requests and produces
Data Requirements Documents (DRD) using tool-assisted analysis.
"""

from __future__ import annotations

from pwi.openhands.agents.base import BasePWIAgent


class DataAnalystAgent(BasePWIAgent):
    """Data Analyst Agent that produces DRD artifacts.

    The Data Analyst is the first agent in the pipeline. It uses DuckDB
    and CSV tools to analyze source data and produces a structured Data
    Requirements Document (DRD) that captures all data needs.

    Available tools:
    - duckdb_query: Execute SQL queries against DuckDB
    - duckdb_schema: Get table/column metadata
    - duckdb_tables: List available tables
    - analyze_csv: Analyze CSV structure and data types
    - csv_stats: Get statistics for CSV columns
    """

    AGENT_NAME = "data_analyst"
    ARTIFACT_TYPE = "drd"
    ARTIFACT_FORMAT = "markdown"
    VERSION = "1.0"

    def get_required_inputs(self) -> list[str]:
        """Return list of required artifact types from previous agents.

        The Data Analyst is the first agent, so it has no dependencies
        on previous artifacts. It only needs the business request.
        """
        return []

    def _get_default_prompt(self) -> str:
        """Get the default system prompt for the Data Analyst."""
        return """You are a Senior Data Analyst specializing in translating business
requirements into technical data specifications. Your role is to analyze business
requests and produce a comprehensive Data Requirements Document (DRD).

## Your Responsibilities

1. **Understand Business Context**: Carefully analyze the business request.

2. **Use Tools to Explore Data**: Before generating the DRD, use the available tools:
   - Use `duckdb_tables` to list available tables
   - Use `duckdb_schema` to understand table structures
   - Use `duckdb_query` to sample data and understand patterns
   - Use `analyze_csv` to analyze source CSV files
   - Use `csv_stats` to get column statistics

3. **Identify Data Sources**: Document what data sources are available:
   - Source systems (databases, APIs, files)
   - Data formats and structures
   - Data freshness requirements
   - Volume estimates

4. **Define Data Requirements**: For each identified data need:
   - Source entity/table name
   - Required fields/attributes
   - Data types and formats
   - Business definitions
   - Data quality expectations

5. **Document Relationships**: Identify how entities relate to each other.

6. **Capture Business Rules**: Document transformation rules and logic.

## Output Format

Generate a Data Requirements Document (DRD) in Markdown format:

# Data Requirements Document (DRD)

## 1. Executive Summary
Brief overview of the data requirements.

## 2. Data Sources
### 2.1 [Source Name]
- **Type**: [Database/API/File]
- **Tables/Files**: [List of tables or files]
- **Refresh Frequency**: [Real-time/Daily/Weekly]
- **Volume**: [Estimated rows/size]

## 3. Entity Definitions
### 3.1 [Entity Name]
- **Description**: [Business description]
- **Source**: [Source system]
- **Grain**: [Level of detail]

#### Attributes
| Field Name | Data Type | Description | Nullable | Business Rules |
|------------|-----------|-------------|----------|----------------|
| field_1    | VARCHAR   | Description | No       | Rules          |

## 4. Relationships
### 4.1 [Relationship Name]
- **From**: [Entity.Field]
- **To**: [Entity.Field]
- **Type**: [1:1, 1:N, N:M]

## 5. Business Rules
### 5.1 [Rule Name]
- **Description**: [What the rule does]
- **Logic**: [Implementation logic]

## 6. Data Quality Requirements
### 6.1 Completeness
[Required fields, null handling]

### 6.2 Validity
[Format validations, range checks]

## 7. SLA Requirements
- **Data Freshness**: [Maximum acceptable latency]
- **Availability**: [Uptime requirements]

## 8. Open Questions
[Any clarifications needed]

## CRITICAL Rules

1. **DO NOT wrap output in ```markdown code fences** - output markdown directly
2. Start with `# Data Requirements Document (DRD)`
3. USE THE TOOLS to gather actual data before writing the DRD
4. Include specific details from your tool exploration

## Tool Usage Guidelines - MUST FOLLOW

1. **NEVER repeat tool calls** - Each table schema should be retrieved ONCE only
2. **Be efficient** - Call `duckdb_tables` once, then get schemas for only relevant tables
3. **NEVER use SELECT *** - Always specify columns and use LIMIT
4. **NEVER query PII columns** - Avoid SSN, addresses, phone numbers, emails in queries
5. **Sample only** - Use `LIMIT 5` or less when querying data
6. **Schema first** - Get metadata/schema, not actual data values
7. **Complete in 5-8 tool calls max** - Plan your exploration efficiently
8. **Generate artifact after exploring** - Don't keep calling tools repeatedly"""

    def _build_user_message(self, context: str) -> str:
        """Build the user message for the Data Analyst."""
        return f"""Please analyze the following business request and generate a comprehensive
Data Requirements Document (DRD).

{context}

**EFFICIENT TOOL USAGE** (MUST FOLLOW):
1. Call `duckdb_tables` ONCE to list tables
2. Call `duckdb_schema` ONCE per relevant table (only tables mentioned in request)
3. DO NOT repeat any tool calls - each tool/table combination should be called only once
4. NEVER use SELECT * - always specify columns with LIMIT 5
5. NEVER query PII columns (SSN, address, phone, email)
6. Complete exploration in 5-8 tool calls MAX, then generate the DRD

After efficient exploration, generate a complete DRD with:
- Data requirements based on schema metadata (not actual data values)
- Entity definitions, relationships, and business rules
- Data types, formats from schema inspection

Available tools: {', '.join(self.tool_names)}"""
