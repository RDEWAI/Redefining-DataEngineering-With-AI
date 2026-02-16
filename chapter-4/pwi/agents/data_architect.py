"""Data Architect Agent for Planning with Intent.

This agent analyzes the DRD and produces
Pipeline Architecture Documents (PAD).
"""

from __future__ import annotations

from pwi.agents.base import BaseAgent


class DataArchitectAgent(BaseAgent):
    """Data Architect Agent that produces PAD artifacts.

    The Data Architect receives the DRD from the Data Analyst and
    designs the pipeline architecture, including data layers,
    technology choices, and implementation patterns.
    """

    AGENT_NAME = "data_architect"
    ARTIFACT_TYPE = "pad"
    ARTIFACT_FORMAT = "markdown"
    VERSION = "1.0"

    def get_required_inputs(self) -> list[str]:
        """Return list of required artifact types from previous agents.

        The Data Architect requires the DRD from the Data Analyst.
        """
        return ["drd"]

    def _get_default_prompt(self) -> str:
        """Get the default system prompt for the Data Architect.

        This is used as a fallback if no prompt file is found.
        """
        return """You are a Senior Data Architect specializing in designing scalable
data pipelines and architectures. Your role is to analyze the Data Requirements
Document (DRD) and produce a comprehensive Pipeline Architecture Document (PAD).

Design the pipeline architecture including:
1. High-level architecture diagram (ASCII)
2. Data layers (Bronze/Silver/Gold or equivalent)
3. Technology stack recommendations
4. Pipeline components and their responsibilities
5. Data models (dimensional model for analytics)
6. Error handling and recovery strategies
7. Monitoring and observability approach
8. Security and governance considerations

Output a well-structured PAD in Markdown format with sections for:
- Architecture Overview
- Data Layers
- Pipeline Components
- Data Models
- Technology Stack
- Data Quality Framework
- Error Handling
- Security & Governance
- Performance Considerations
- Implementation Phases"""

    def _build_user_message(self, context: str) -> str:
        """Build the user message for the Data Architect.

        The Data Architect receives the business request and DRD.
        """
        return f"""Please analyze the following requirements and design a comprehensive
Pipeline Architecture Document (PAD).

{context}

Generate a complete, well-structured PAD that includes:
- High-level architecture with data flow
- Technology recommendations appropriate for the scale
- Detailed data model design
- Implementation phases and approach

Consider scalability, reliability, and maintainability in your design."""
