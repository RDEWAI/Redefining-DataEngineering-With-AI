"""Data Quality Engineer Agent for Planning with Intent.

This agent analyzes the DRD and DMD to produce
Data Quality Specifications (DQS) in YAML format.
"""

from __future__ import annotations

from pwi.agents.base import BaseAgent


class DQEngineerAgent(BaseAgent):
    """Data Quality Engineer Agent that produces DQS artifacts.

    The DQ Engineer receives the DRD and DMD, then creates
    comprehensive data quality rules and specifications.
    """

    AGENT_NAME = "dq_engineer"
    ARTIFACT_TYPE = "dqs"
    ARTIFACT_FORMAT = "yaml"
    VERSION = "1.0"

    def get_required_inputs(self) -> list[str]:
        """Return list of required artifact types from previous agents.

        The DQ Engineer requires DRD and DMD.
        """
        return ["drd", "dmd"]

    def _get_default_prompt(self) -> str:
        """Get the default system prompt for the DQ Engineer.

        This is used as a fallback if no prompt file is found.
        """
        return """You are a Senior Data Quality Engineer specializing in designing
comprehensive data quality frameworks. Your role is to analyze the Data Requirements
Document (DRD) and Data Mapping Document (DMD) to produce a Data Quality
Specification (DQS) in YAML format.

Design quality checks for:
1. Completeness - Required fields, null handling
2. Validity - Format validation, range checks, domain values
3. Accuracy - Business rule validation
4. Consistency - Cross-field validation, referential integrity
5. Timeliness - Freshness checks, processing SLAs
6. Uniqueness - Duplicate detection, key validation

Output valid YAML with sections for:
- Metadata (version, project, owner)
- Config (default severity, thresholds, channels)
- Sources (data source definitions)
- Rules (organized by quality dimension)
- Metrics (quality scoring)
- Alerts (notification configuration)
- Schedule (execution timing)
- Remediation (procedures for failures)"""

    def _build_user_message(self, context: str) -> str:
        """Build the user message for the DQ Engineer.

        The DQ Engineer receives the business request, DRD, and DMD.
        """
        return f"""Please analyze the following requirements and create a comprehensive
Data Quality Specification (DQS) in YAML format.

{context}

Generate valid YAML with all quality rules. Include:
- Rules for every critical field identified in the DRD
- Coverage of all quality dimensions (completeness, validity, accuracy, consistency, uniqueness, timeliness)
- Appropriate severity levels (critical, high, medium, low)
- Alert configuration for critical failures
- Scheduled execution for different rule types
- Remediation procedures for common failures

The YAML must be valid and parseable."""

    def _process_response(self, content: str) -> str:
        """Process the LLM response to extract clean YAML content.

        Removes any markdown code fences if present.
        """
        content = content.strip()

        # Remove markdown code fences if present
        if content.startswith("```yaml"):
            content = content[7:]
        elif content.startswith("```yml"):
            content = content[6:]
        elif content.startswith("```"):
            content = content[3:]

        if content.endswith("```"):
            content = content[:-3]

        return content.strip()
