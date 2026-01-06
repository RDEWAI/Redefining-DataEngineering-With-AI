"""Story Writer Agent for Planning with Intent.

This agent analyzes all previous artifacts and produces
Epics and User Stories for implementation.
"""

from __future__ import annotations

from pwi.agents.base import BaseAgent


class StoryWriterAgent(BaseAgent):
    """Story Writer Agent that produces implementation stories.

    The Story Writer receives all previous artifacts (DRD, PAD, DMD, DQS)
    and creates actionable epics and user stories for implementation.
    """

    AGENT_NAME = "story_writer"
    ARTIFACT_TYPE = "stories"
    ARTIFACT_FORMAT = "markdown"
    VERSION = "1.0"

    def get_required_inputs(self) -> list[str]:
        """Return list of required artifact types from previous agents.

        The Story Writer requires all previous artifacts.
        """
        return ["drd", "pad", "dmd", "dqs"]

    def _get_default_prompt(self) -> str:
        """Get the default system prompt for the Story Writer.

        This is used as a fallback if no prompt file is found.
        """
        return """You are a Senior Technical Product Manager specializing in translating
data engineering requirements into actionable user stories and epics. Your role is
to analyze all previous artifacts (DRD, PAD, DMD, DQS) and produce comprehensive
Epics and User Stories for implementation.

Create implementation stories including:
1. Epics grouped by functional area (Ingestion, Transformation, Quality, Operations)
2. User stories with clear acceptance criteria
3. Technical implementation notes
4. Story point estimates (Fibonacci: 1, 2, 3, 5, 8, 13)
5. Dependencies between stories
6. Implementation phases

Output format (Markdown):
- Project Overview with stats
- Epics with descriptions and metadata
- Stories with:
  - User story format (As a... I want... So that...)
  - Acceptance criteria (checkboxes)
  - Technical notes and code snippets
  - Dependencies
  - Story point estimates
- Story point summary by epic
- Implementation phases/roadmap"""

    def _build_user_message(self, context: str) -> str:
        """Build the user message for the Story Writer.

        The Story Writer receives all artifacts as context.
        """
        return f"""Please analyze all the following artifacts and create comprehensive
implementation stories (Epics and User Stories).

{context}

Generate a complete set of implementation stories. Include:
- Epics for each major functional area
- Detailed user stories with acceptance criteria
- Technical implementation notes with code examples
- Story point estimates for each story
- Clear dependencies between stories
- Phased implementation roadmap

Stories should be independently deliverable and testable.
Use Fibonacci story points (1, 2, 3, 5, 8, 13)."""
