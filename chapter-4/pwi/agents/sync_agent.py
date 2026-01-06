"""Sync Agent for Planning with Intent.

This agent reviews all artifacts and produces
a final consolidated package summary.
"""

from __future__ import annotations

from pwi.agents.base import BaseAgent


class SyncAgent(BaseAgent):
    """Sync Agent that produces the final package.

    The Sync Agent receives all previous artifacts and validates
    consistency, identifies gaps, and produces a consolidated summary.
    """

    AGENT_NAME = "sync_agent"
    ARTIFACT_TYPE = "package"
    ARTIFACT_FORMAT = "markdown"
    VERSION = "1.0"

    def get_required_inputs(self) -> list[str]:
        """Return list of required artifact types from previous agents.

        The Sync Agent requires all previous artifacts.
        """
        return ["drd", "pad", "dmd", "dqs", "stories"]

    def _get_default_prompt(self) -> str:
        """Get the default system prompt for the Sync Agent.

        This is used as a fallback if no prompt file is found.
        """
        return """You are a Senior Data Engineering Lead responsible for reviewing and
packaging all artifacts produced by the planning workflow. Your role is to ensure
consistency across all documents and produce a final consolidated package.

Your responsibilities:
1. Validate consistency across all artifacts
2. Identify gaps or misalignments
3. Create traceability matrices
4. Produce executive summary
5. Generate implementation checklist
6. Assess risks and open questions

Output format (Markdown):
- Executive Summary with key metrics
- Data Flow Overview (ASCII diagram)
- Traceability Matrix (requirements to implementation)
- Entity Coverage Matrix
- Quality Rule Coverage
- Implementation Roadmap
- Risk Assessment
- Consistency Check Results
- Artifact Locations
- Next Steps
- Appendix (glossary, version history)"""

    def _build_user_message(self, context: str) -> str:
        """Build the user message for the Sync Agent.

        The Sync Agent receives all artifacts as context.
        """
        return f"""Please review all the following artifacts and produce a comprehensive
final package summary.

{context}

Generate a complete package summary that:
- Validates consistency across all documents
- Identifies any gaps or misalignments
- Creates traceability from requirements to implementation
- Provides executive summary with key metrics
- Includes implementation roadmap
- Assesses risks and documents open questions
- Lists specific consistency check results (passed/warnings/failed)

The package should serve as the single source of truth for the project."""
