"""Base agent class for Planning with Intent.

This module defines the abstract base class that all PWI agents
must inherit from.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from pwi.llm.client import CompletionResponse, LLMClient
from pwi.utils.logging import get_logger
from pwi.utils.markdown import MarkdownValidator, ValidationResult
from pwi.workflow.session import Session

logger = get_logger("agents.base")


class AgentConfig(BaseModel):
    """Configuration for an agent."""

    name: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    system_prompt_path: Path | None = None
    system_prompt: str | None = None


class AgentResult(BaseModel):
    """Result from agent execution."""

    success: bool
    artifact_type: str | None = None
    artifact_content: str | None = None
    artifact_format: str = "markdown"
    error_message: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    validation_issues: list[str] = Field(default_factory=list)
    was_auto_fixed: bool = False

    @classmethod
    def success_result(
        cls,
        artifact_type: str,
        artifact_content: str,
        artifact_format: str,
        response: CompletionResponse,
        metadata: dict[str, Any] | None = None,
        validation_issues: list[str] | None = None,
        was_auto_fixed: bool = False,
    ) -> AgentResult:
        """Create a successful result."""
        return cls(
            success=True,
            artifact_type=artifact_type,
            artifact_content=artifact_content,
            artifact_format=artifact_format,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            total_tokens=response.total_tokens,
            model=response.model,
            metadata=metadata or {},
            validation_issues=validation_issues or [],
            was_auto_fixed=was_auto_fixed,
        )

    @classmethod
    def failure_result(cls, error_message: str) -> AgentResult:
        """Create a failure result."""
        return cls(
            success=False,
            error_message=error_message,
        )


class BaseAgent(ABC):
    """Abstract base class for all PWI agents.

    Agents are responsible for processing business requests and
    generating specific artifacts in the data engineering workflow.
    """

    # Class attributes to be defined by subclasses
    AGENT_NAME: str = "base"
    ARTIFACT_TYPE: str = "artifact"
    ARTIFACT_FORMAT: str = "markdown"
    VERSION: str = "1.0"

    def __init__(
        self,
        config: AgentConfig,
        llm_client: LLMClient,
        prompts_dir: Path | None = None,
    ) -> None:
        """Initialize the agent.

        Args:
            config: Agent configuration.
            llm_client: LLM client for making completion requests.
            prompts_dir: Directory containing prompt templates.
        """
        self.config = config
        self.llm = llm_client
        self.prompts_dir = prompts_dir
        self._system_prompt: str | None = None

    def _load_system_prompt(self) -> str:
        """Load the system prompt for this agent.

        Returns:
            The system prompt string.

        Raises:
            FileNotFoundError: If prompt file doesn't exist.
        """
        # Use provided prompt if available
        if self.config.system_prompt:
            return self.config.system_prompt

        # Try to load from file
        if self.config.system_prompt_path and self.config.system_prompt_path.exists():
            return self.config.system_prompt_path.read_text(encoding="utf-8")

        # Try default location in prompts directory
        if self.prompts_dir:
            prompt_file = self.prompts_dir / f"{self.AGENT_NAME}.md"
            if prompt_file.exists():
                return prompt_file.read_text(encoding="utf-8")

        # Return default prompt
        return self._get_default_prompt()

    @abstractmethod
    def _get_default_prompt(self) -> str:
        """Get the default system prompt for this agent.

        Subclasses must implement this to provide a fallback prompt
        when no prompt file is available.
        """
        pass

    @property
    def system_prompt(self) -> str:
        """Get the system prompt, loading from file if needed."""
        if self._system_prompt is None:
            self._system_prompt = self._load_system_prompt()
        return self._system_prompt

    def _build_context(
        self,
        session: Session,
    ) -> str:
        """Build the context string from session data.

        This includes the business request and any artifacts from
        previous agents.

        Args:
            session: Current session with request and artifacts.

        Returns:
            Context string to include in the prompt.
        """
        parts = []

        # Add the business request
        parts.append("## Business Request\n")
        parts.append(session.request_content)
        parts.append("\n")

        # Add artifacts from previous agents
        required_inputs = self.get_required_inputs()
        for artifact_type in required_inputs:
            artifact = session.get_artifact(artifact_type)
            if artifact:
                parts.append(f"\n## {artifact_type.upper()} (from {artifact.agent})\n")
                parts.append(artifact.content)
                parts.append("\n")

        return "\n".join(parts)

    @abstractmethod
    def get_required_inputs(self) -> list[str]:
        """Return list of required artifact types from previous agents.

        For example, the Data Architect agent requires the DRD from
        the Data Analyst.

        Returns:
            List of artifact type strings (e.g., ['drd']).
        """
        pass

    def validate_inputs(self, session: Session) -> tuple[bool, str | None]:
        """Validate that all required inputs are present.

        Args:
            session: Current session to validate.

        Returns:
            Tuple of (is_valid, error_message).
        """
        required = self.get_required_inputs()
        missing = []

        for artifact_type in required:
            if artifact_type not in session.artifacts:
                missing.append(artifact_type)

        if missing:
            return False, f"Missing required artifacts: {', '.join(missing)}"

        return True, None

    async def execute(self, session: Session) -> AgentResult:
        """Execute the agent's task.

        This is the main entry point for running an agent. It:
        1. Validates required inputs
        2. Builds the context from session
        3. Calls the LLM
        4. Processes the response
        5. Validates and fixes markdown (for markdown artifacts)
        6. Returns the result

        Args:
            session: Current session with request and context.

        Returns:
            AgentResult with success status and generated artifact.
        """
        # Validate inputs
        is_valid, error = self.validate_inputs(session)
        if not is_valid:
            return AgentResult.failure_result(error or "Validation failed")

        # Build context
        context = self._build_context(session)

        # Build the user message
        user_message = self._build_user_message(context)

        try:
            # Call the LLM
            logger.info(f"Agent {self.AGENT_NAME} calling LLM model {self.config.model}")
            response = await self.llm.acomplete_with_retry(
                user_message=user_message,
                system_prompt=self.system_prompt,
                model=self.config.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

            # Process the response
            artifact_content = self._process_response(response.content)

            # Validate and fix markdown for markdown artifacts
            validation_issues: list[str] = []
            was_auto_fixed = False

            if self.ARTIFACT_FORMAT == "markdown":
                validation_result = self._validate_markdown(artifact_content)
                validation_issues = [str(issue) for issue in validation_result.issues]

                if validation_issues:
                    logger.warning(
                        f"Agent {self.AGENT_NAME} generated markdown with "
                        f"{len(validation_issues)} validation issues"
                    )

                # Use auto-fixed content if available
                if validation_result.formatted_content:
                    if validation_result.formatted_content != artifact_content:
                        was_auto_fixed = True
                        artifact_content = validation_result.formatted_content
                        logger.info(
                            f"Agent {self.AGENT_NAME} markdown was auto-fixed"
                        )

            return AgentResult.success_result(
                artifact_type=self.ARTIFACT_TYPE,
                artifact_content=artifact_content,
                artifact_format=self.ARTIFACT_FORMAT,
                response=response,
                validation_issues=validation_issues,
                was_auto_fixed=was_auto_fixed,
            )

        except Exception as e:
            logger.error(f"Agent {self.AGENT_NAME} failed: {e}")
            return AgentResult.failure_result(str(e))

    def _validate_markdown(self, content: str) -> ValidationResult:
        """Validate markdown content and attempt to fix issues.

        Args:
            content: Markdown content to validate.

        Returns:
            ValidationResult with issues found and fixed content.
        """
        validator = MarkdownValidator(
            max_line_length=120,
            strict_mermaid=True,
            fix_formatting=True,
        )
        return validator.validate(content)

    def _build_user_message(self, context: str) -> str:
        """Build the user message from context.

        Subclasses can override this to customize the message format.

        Args:
            context: Context string with request and previous artifacts.

        Returns:
            User message to send to the LLM.
        """
        return f"""Please analyze the following and generate the {self.ARTIFACT_TYPE.upper()}.

{context}

Generate a complete, well-structured {self.ARTIFACT_TYPE.upper()} based on the above information."""

    def _process_response(self, content: str) -> str:
        """Process the LLM response content.

        Subclasses can override this to extract specific parts or
        transform the content.

        Args:
            content: Raw response content from the LLM.

        Returns:
            Processed artifact content.
        """
        return content.strip()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.AGENT_NAME}, model={self.config.model})"
