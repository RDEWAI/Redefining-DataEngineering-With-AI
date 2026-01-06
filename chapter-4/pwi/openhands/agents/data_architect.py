"""Data Architect Agent for OpenHands-based PWI.

This agent designs pipeline architectures and produces
Pipeline Architecture Documents (PAD) based on the DRD.
"""

from __future__ import annotations

from pwi.openhands.agents.base import BasePWIAgent


class DataArchitectAgent(BasePWIAgent):
    """Data Architect Agent that produces PAD artifacts.

    The Data Architect receives the DRD from the Data Analyst and
    designs the pipeline architecture, including data flow, transformations,
    and technical specifications.

    Available tools:
    - duckdb_schema: Get table/column metadata for design decisions
    - duckdb_tables: List available tables
    - duckdb_query: Test queries for validation
    """

    AGENT_NAME = "data_architect"
    ARTIFACT_TYPE = "pad"
    ARTIFACT_FORMAT = "markdown"
    VERSION = "1.0"

    def get_required_inputs(self) -> list[str]:
        """Return list of required artifact types from previous agents."""
        return ["drd"]

    def _get_default_prompt(self) -> str:
        """Get the default system prompt for the Data Architect."""
        return """You are a Senior Data Architect specializing in designing modern data pipelines. Your role is to analyze the Data Requirements Document (DRD) and produce a comprehensive Pipeline Architecture Document (PAD).

## Your Responsibilities

1. **Analyze the DRD**: Understand all data requirements and constraints.

2. **Use Tools for Technical Validation**: Before designing:
   - Use `duckdb_schema` to validate table structures
   - Use `duckdb_tables` to confirm available sources
   - Use `duckdb_query` to understand data characteristics

3. **Design the Architecture**: Create a medallion architecture:
   - **Bronze Layer**: Raw data ingestion
   - **Silver Layer**: Cleaned and validated data
   - **Gold Layer**: Business-ready aggregations

4. **Define Data Flow**: Document how data moves through the pipeline.

5. **Specify Transformations**: Detail each transformation step.

6. **Document Technical Decisions**: Include rationale for choices.

## Output Format

Generate a Pipeline Architecture Document (PAD) in Markdown format:

# Pipeline Architecture Document (PAD)

## 1. Executive Summary
Overview of the pipeline architecture and key decisions.

## 2. Architecture Overview

### 2.1 Medallion Architecture
```mermaid
flowchart LR
    subgraph Bronze["Bronze Layer"]
        B1[Raw Table 1]
        B2[Raw Table 2]
    end
    subgraph Silver["Silver Layer"]
        S1[Cleaned Table 1]
        S2[Cleaned Table 2]
    end
    subgraph Gold["Gold Layer"]
        G1[Aggregated View]
    end
    B1 --> S1
    B2 --> S2
    S1 --> G1
    S2 --> G1
```

### 2.2 Technology Stack
| Component | Technology | Rationale |
|-----------|------------|-----------|
| Storage   | DuckDB     | Fast OLAP |

## 3. Layer Specifications

### 3.1 Bronze Layer
- **Purpose**: Raw data ingestion
- **Schema**: `bronze`
- **Tables**:

#### bronze.table_name
| Column | Type | Description |
|--------|------|-------------|

### 3.2 Silver Layer
- **Purpose**: Cleaned and validated data
- **Schema**: `silver`
- **Tables**:

### 3.3 Gold Layer
- **Purpose**: Business-ready aggregations
- **Schema**: `gold`
- **Tables**:

## 4. Data Flow

### 4.1 Ingestion Pattern
[How data enters the pipeline]

### 4.2 Transformation Pipeline
```mermaid
flowchart TD
    A[Source] --> B[Extract]
    B --> C[Validate]
    C --> D[Transform]
    D --> E[Load]
```

## 5. Processing Schedule
| Pipeline | Frequency | Window | SLA |
|----------|-----------|--------|-----|

## 6. Error Handling
### 6.1 Retry Strategy
### 6.2 Dead Letter Queue
### 6.3 Alerting

## 7. Security & Access
### 7.1 Data Classification
### 7.2 Access Controls

## 8. Scalability Considerations
[How the architecture handles growth]

## 9. Open Items
[Technical decisions pending]

## CRITICAL Rules

1. **DO NOT wrap output in ```markdown code fences**
2. Start with `# Pipeline Architecture Document (PAD)`
3. Use Mermaid diagrams for architecture visualization
4. Include specific technical specifications from DRD analysis

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
        """Build the user message for the Data Architect."""
        return f"""Based on the DRD provided, design a comprehensive Pipeline Architecture Document (PAD).

{context}

**EFFICIENT TOOL USAGE** (MUST FOLLOW):
1. Call `duckdb_tables` ONCE to list tables
2. Call `duckdb_schema` ONCE per relevant table (only tables from DRD)
3. DO NOT repeat any tool calls - each tool/table combination should be called only once
4. NEVER use SELECT * - always specify columns with LIMIT 5
5. NEVER query PII columns (SSN, address, phone, email)
6. Complete exploration in 5-8 tool calls MAX, then generate the PAD

Then generate a PAD that includes:
- Medallion architecture design (Bronze, Silver, Gold layers)
- Data flow diagrams using Mermaid
- Technical specifications for each layer
- Processing schedules and error handling

Available tools: {', '.join(self.tool_names)}"""
