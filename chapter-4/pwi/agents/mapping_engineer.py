"""Mapping Engineer Agent for Planning with Intent.

This agent analyzes the DRD and PAD to produce
Data Mapping Documents (DMD) in CSV format.
"""

from __future__ import annotations

from pwi.agents.base import BaseAgent


class MappingEngineerAgent(BaseAgent):
    """Mapping Engineer Agent that produces DMD artifacts.

    The Mapping Engineer receives the DRD and PAD, then creates
    detailed source-to-target field mappings with transformation rules.
    """

    AGENT_NAME = "mapping_engineer"
    ARTIFACT_TYPE = "dmd"
    ARTIFACT_FORMAT = "csv"
    VERSION = "1.0"

    def get_required_inputs(self) -> list[str]:
        """Return list of required artifact types from previous agents.

        The Mapping Engineer requires both DRD and PAD.
        """
        return ["drd", "pad"]

    def _get_default_prompt(self) -> str:
        """Get the default system prompt for the Mapping Engineer.

        This is used as a fallback if no prompt file is found.
        """
        return """You are a Senior Data Mapping Engineer specializing in source-to-target
data mappings. Your role is to analyze the Data Requirements Document (DRD) and
Pipeline Architecture Document (PAD) to produce a comprehensive Data Mapping
Document (DMD) in CSV format.

Create detailed field-level mappings including:
1. Target table and column
2. Source system, table, and column
3. Data types (source and target)
4. Transformation rules
5. Default values
6. Null handling
7. Business rule references

Use semicolons instead of commas within transformation rules to avoid CSV parsing issues.

Output format (CSV with header):
target_table,target_column,target_data_type,source_system,source_table,source_column,source_data_type,transformation_rule,default_value,nullable,business_rule,notes

Include mappings for:
- All dimension tables
- All fact tables
- Surrogate key generation
- SCD Type 2 columns (effective dates, is_current flag)
- Audit columns (load_timestamp, source_file)"""

    def _build_user_message(self, context: str) -> str:
        """Build the user message for the Mapping Engineer.

        The Mapping Engineer receives the business request, DRD, and PAD.
        """
        return f"""Please analyze the following requirements and create a comprehensive
Data Mapping Document (DMD) in CSV format.

{context}

Generate a complete CSV with all field mappings. Include:
- Header row with all columns
- Mappings for every target field
- Transformation rules using semicolons (not commas) for nested logic
- Default values and null handling
- SCD Type 2 metadata columns where applicable
- Audit columns for each table

The CSV must be valid and parseable. Use double quotes for values containing
special characters."""

    def _process_response(self, content: str) -> str:
        """Process the LLM response to extract clean CSV content.

        Removes any markdown code fences if present.
        """
        content = content.strip()

        # Remove markdown code fences if present
        if content.startswith("```csv"):
            content = content[6:]
        elif content.startswith("```"):
            content = content[3:]

        if content.endswith("```"):
            content = content[:-3]

        return content.strip()
