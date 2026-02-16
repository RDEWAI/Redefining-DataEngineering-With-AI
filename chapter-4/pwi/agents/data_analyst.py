"""Data Analyst Agent for Planning with Intent.

This agent analyzes business requests and produces
Data Requirements Documents (DRD).
"""

from __future__ import annotations

from pwi.agents.base import BaseAgent


class DataAnalystAgent(BaseAgent):
    """Data Analyst Agent that produces DRD artifacts.

    The Data Analyst is the first agent in the pipeline. It takes
    the raw business request and produces a structured Data Requirements
    Document (DRD) that captures all data needs.
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
        """Get the default system prompt for the Data Analyst.

        This is used as a fallback if no prompt file is found.
        """
        return """You are a Senior Data Analyst specializing in translating business
requirements into technical data specifications. Your role is to analyze business
requests and produce a comprehensive Data Requirements Document (DRD).

Analyze the business request and identify:
1. Data sources and their types
2. Required entities and attributes
3. Relationships between entities
4. Business rules and transformations
5. Data quality requirements
6. SLA requirements

Output a well-structured DRD in Markdown format with sections for:
- Executive Summary
- Data Sources
- Entity Definitions (with attribute tables)
- Relationships
- Business Rules
- Data Quality Requirements
- SLA Requirements
- Open Questions"""

    def _build_user_message(self, context: str) -> str:
        """Build the user message for the Data Analyst.

        The Data Analyst receives only the business request context.
        """
        return f"""Please analyze the following business request and generate a comprehensive
Data Requirements Document (DRD).

{context}

Generate a complete, well-structured DRD that captures all data requirements,
entities, relationships, and business rules. Include specific details about
data types, formats, and quality expectations."""
