"""Workflow controller for OpenHands-based PWI.

This module provides the main orchestration layer that:
- Manages sequential agent execution using SDK Conversation
- Handles review gates via EventStream
- Integrates with session persistence
- Exports artifacts to output directory

Supports both SDK runtime (recommended) and legacy runtime modes.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from dataclasses import dataclass, field

from pwi.openhands.agents import (
    AGENT_SEQUENCE,
    # SDK Factory Functions
    create_pwi_agent,
    create_pwi_conversation,
    create_llm,
    load_microagent_prompt,
    # Auto-discovery
    discover_microagents,
)


# =============================================================================
# Simple dataclasses for workflow state (replaces legacy BasePWIAgent types)
# =============================================================================


@dataclass
class PWIAgentConfig:
    """Configuration for a PWI agent."""

    name: str
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class PWIAgentState:
    """Execution state for a PWI agent."""

    agent_name: str
    status: str = "pending"
    tool_calls: list[dict] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)
    error: str | None = None


@dataclass
class PWIAgentResult:
    """Result from a PWI agent execution."""

    agent_name: str
    artifact_type: str
    artifact_content: str
    artifact_format: str = "markdown"
    success: bool = True
    error: str | None = None
    error_message: str | None = None
    tool_calls_count: int = 0
    duration_seconds: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tool_calls: list[dict] = field(default_factory=list)


def get_agent_info(agent_name: str) -> dict[str, str]:
    """Get information about an agent from microagent files.

    Args:
        agent_name: Name of the agent.

    Returns:
        Dictionary with agent information.

    Raises:
        ValueError: If agent name is not recognized.
    """
    # Use auto-discovery instead of static map
    microagents = discover_microagents()
    if agent_name not in microagents:
        raise ValueError(f"Unknown agent: {agent_name}")

    # Map agent names to artifact info
    artifact_info = {
        "data_analyst": ("drd", "markdown"),
        "data_architect": ("pad", "markdown"),
        "mapping_engineer": ("dmd", "csv"),
        "dq_engineer": ("dqs", "yaml"),
        "story_writer": ("stories", "markdown"),
        "sync_agent": ("package", "markdown"),
        "validator_agent": ("validation", "markdown"),
    }

    artifact_type, artifact_format = artifact_info.get(
        agent_name, ("unknown", "text")
    )

    return {
        "name": agent_name,
        "artifact_type": artifact_type,
        "artifact_format": artifact_format,
        "version": "2.0.0",
    }
from pwi.openhands.workflow.events import (
    AgentFailedEvent,
    AgentStartedEvent,
    AgentToolCallEvent,
    AgentToolResultEvent,
    EventStream,
    WorkflowCompletedEvent,
    WorkflowFailedEvent,
    WorkflowResumedEvent,
    WorkflowStartedEvent,
)
from pwi.openhands.workflow.review_handler import (
    BaseReviewHandler,
    get_review_handler,
)
from pwi.openhands.tools.artifact_tool import (
    ValidateArtifactExecutor,
    ValidateArtifactAction,
)
from pwi.openhands.workflow.session_adapter import SessionEventAdapter
from pwi.utils.logging import get_logger

if TYPE_CHECKING:
    from openhands.sdk import Agent, Conversation, Event
    from pwi.config.schema import PWIConfig
    from pwi.llm.client import LLMClient
    from pwi.workflow.session import Session, SessionManager

logger = get_logger("openhands.workflow.controller")
console = Console()


class PWIWorkflowController:
    """OpenHands-based workflow controller for PWI.

    This controller manages the execution of PWI agents using the
    OpenHands SDK patterns with event-sourced state management.

    Supports two execution modes:
    - SDK mode (runtime_mode="sdk"): Uses SDK Agent and Conversation
    - Legacy mode (runtime_mode="legacy"): Uses custom BasePWIAgent
    """

    def __init__(
        self,
        session: Session,
        session_manager: SessionManager,
        config: PWIConfig,
        llm_client: LLMClient,
        auto_approve: bool = False,
        skip_review: bool = False,
        review_mode: str = "cli",
        runtime_mode: Literal["sdk", "legacy"] = "sdk",
        workspace_path: Path | None = None,
        on_agent_complete: Callable[[str, PWIAgentResult], None] | None = None,
        strict_validation: bool = False,
    ) -> None:
        """Initialize the workflow controller.

        Args:
            session: Current workflow session.
            session_manager: Session persistence manager.
            config: PWI configuration.
            llm_client: LLM client for agent calls (used in legacy mode).
            auto_approve: Auto-approve all review gates.
            skip_review: Skip all review gates entirely.
            review_mode: Review mode ('cli', 'file', 'auto', 'skip').
            runtime_mode: Execution mode - 'sdk' (recommended) or 'legacy'.
            workspace_path: Workspace directory for SDK conversations.
            on_agent_complete: Optional callback when agent completes.
            strict_validation: If True, block workflow on validation failures.
        """
        self.session = session
        self.session_manager = session_manager
        self.config = config
        self.llm_client = llm_client
        self.auto_approve = auto_approve
        self.skip_review = skip_review
        self.review_mode = review_mode
        self.runtime_mode = runtime_mode
        self.workspace_path = workspace_path or config.project.output_dir
        self.on_agent_complete = on_agent_complete
        self.strict_validation = strict_validation

        # Initialize event stream and session adapter
        self.event_stream = EventStream(session.session_id)
        self.session_adapter = SessionEventAdapter(
            session=session,
            session_manager=session_manager,
            event_stream=self.event_stream,
        )

        # Initialize review handler
        self._init_review_handler()

        # Get prompts directory
        self.prompts_dir = Path(__file__).parent.parent.parent / "agents" / "prompts"

        # Tracking state
        self._current_agent: str | None = None
        self._is_running: bool = False
        self._sdk_llm = None  # Cached SDK LLM instance

        logger.info(
            f"Workflow controller initialized in {runtime_mode} mode",
            extra={"session_id": session.session_id, "runtime_mode": runtime_mode},
        )

    def _init_review_handler(self) -> None:
        """Initialize the review handler based on configuration."""
        if self.skip_review:
            mode = "skip"
        elif self.auto_approve:
            mode = "auto"
        else:
            mode = self.review_mode

        self.review_handler = get_review_handler(
            mode=mode,
            event_stream=self.event_stream,
            review_dir=self.config.project.output_dir / "review",
            timeout_minutes=self.config.review.timeout_minutes,
        )

    def _create_agent_config(self, agent_name: str) -> PWIAgentConfig:
        """Create configuration for an agent.

        Args:
            agent_name: Name of the agent.

        Returns:
            Agent configuration.
        """
        agent_config = self.config.get_agent_config(agent_name)
        resolved_model = self.config.get_resolved_model(agent_name)

        return PWIAgentConfig(
            name=agent_name,
            model=resolved_model,
            temperature=agent_config.temperature,
            max_tokens=agent_config.max_tokens,
            prompts_dir=self.prompts_dir,
        )

    def _create_agent_state(self, agent_name: str) -> PWIAgentState:
        """Create initial state for an agent.

        Args:
            agent_name: Name of the agent.

        Returns:
            Initial agent state.
        """
        # Build artifacts dict with file-based content support
        artifacts = {}
        for atype, artifact in self.session.artifacts.items():
            content = self.session.read_artifact_content(
                self.session_manager.session_dir, atype
            )
            if content:
                artifacts[atype] = content
            elif artifact.content:
                artifacts[atype] = artifact.content

        return PWIAgentState(
            session_id=self.session.session_id,
            business_request=self.session.request_content,
            artifacts=artifacts,
        )

    async def _execute_agent(
        self, agent_name: str, validation_feedback: str | None = None
    ) -> PWIAgentResult:
        """Execute a single agent.

        Dispatches to SDK or legacy execution based on runtime_mode.

        Args:
            agent_name: Name of the agent to execute.
            validation_feedback: Optional feedback from previous validation failure.

        Returns:
            Agent execution result.
        """
        self._current_agent = agent_name

        if self.runtime_mode == "sdk":
            result = await self._execute_agent_sdk(agent_name, validation_feedback)
        else:
            result = await self._execute_agent_legacy(agent_name)

        self._current_agent = None
        return result

    async def _execute_agent_sdk(
        self, agent_name: str, validation_feedback: str | None = None
    ) -> PWIAgentResult:
        """Execute agent using OpenHands SDK Conversation.

        Args:
            agent_name: Name of the agent to execute.
            validation_feedback: Optional feedback from previous validation failure.

        Returns:
            Agent execution result.
        """
        from openhands.sdk import Event

        # Get LLM config from PWI config
        agent_config = self.config.get_agent_config(agent_name)
        resolved_model = self.config.get_resolved_model(agent_name)

        llm_config = {
            "model": resolved_model,
            "temperature": agent_config.temperature,
            "max_tokens": agent_config.max_tokens,
        }

        # Emit start event
        start_event = AgentStartedEvent(
            session_id=self.session.session_id,
            agent_name=agent_name,
            model=resolved_model,
            tool_count=0,  # Updated after agent creation
        )
        self.event_stream.append(start_event)

        logger.info(f"Starting SDK agent {agent_name} with model {resolved_model}")

        try:
            # Create SDK agent and conversation
            agent = create_pwi_agent(agent_name, llm_config=llm_config)

            # Event callback to capture tool calls
            def sdk_event_callback(event: Event) -> None:
                event_type = type(event).__name__
                if "ToolCall" in event_type or "Action" in event_type:
                    tool_event = AgentToolCallEvent(
                        session_id=self.session.session_id,
                        agent_name=agent_name,
                        tool_name=getattr(event, "tool", "unknown"),
                        arguments=getattr(event, "arguments", {}),
                    )
                    self.event_stream.append(tool_event)

            conversation = create_pwi_conversation(
                agent=agent,
                workspace=self.workspace_path,
                callbacks=[sdk_event_callback],
            )

            # Build message with context (read from files for file-based artifacts)
            context = {}
            for atype, artifact in self.session.artifacts.items():
                # Read content from file if file-based, otherwise use inline
                content = self.session.read_artifact_content(
                    self.session_manager.session_dir, atype
                )
                if content:
                    context[atype] = content
                elif artifact.content:  # Fallback to inline content
                    context[atype] = artifact.content
            message = self._build_agent_message(agent_name, context)

            # Add validation feedback if this is a retry
            if validation_feedback:
                message += f"""

## VALIDATION FEEDBACK - PLEASE FIX THE FOLLOWING ISSUES

Your previous output failed validation. Please regenerate the artifact addressing these issues:

{validation_feedback}

IMPORTANT: Generate the complete artifact again with these issues fixed. Do NOT just describe what you would change - output the full corrected artifact.
"""

            # Run conversation
            logger.info(f"Starting conversation.run() with max_iterations={conversation.max_iteration_per_run}")
            conversation.send_message(message)
            conversation.run()
            logger.info(f"conversation.run() completed")

            # Extract result from conversation
            artifact_content = self._extract_artifact_from_conversation(
                agent_name, conversation
            )

            # Get agent info for artifact type
            agent_info = get_agent_info(agent_name)

            result = PWIAgentResult(
                agent_name=agent_name,
                artifact_type=agent_info["artifact_type"],
                artifact_content=artifact_content,
                artifact_format=agent_info["artifact_format"],
                success=True,
                prompt_tokens=0,  # SDK tracks internally
                completion_tokens=0,
                tool_calls=[],
            )

            # Emit completion
            self.session_adapter.emit_agent_completed(
                agent_name=agent_name,
                artifact_type=result.artifact_type or "",
                artifact_format=result.artifact_format,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                tool_calls_count=0,
                model=resolved_model,
            )

            # Cleanup
            conversation.close()

            return result

        except Exception as e:
            logger.exception(f"SDK agent {agent_name} failed")
            fail_event = AgentFailedEvent(
                session_id=self.session.session_id,
                agent_name=agent_name,
                error_message=str(e),
            )
            self.event_stream.append(fail_event)

            return PWIAgentResult(
                agent_name=agent_name,
                artifact_type="error",
                artifact_content="",
                artifact_format="text",
                success=False,
                error_message=str(e),
            )

    def _build_agent_message(
        self, agent_name: str, context: dict[str, str]
    ) -> str:
        """Build the message to send to the SDK agent.

        Args:
            agent_name: Name of the agent.
            context: Context from previous agents (artifacts).

        Returns:
            Formatted message for the agent.
        """
        # Artifact type mapping
        artifact_types = {
            "data_analyst": ("DRD", "Data Requirements Document"),
            "data_architect": ("PAD", "Pipeline Architecture Document"),
            "mapping_engineer": ("DMD", "Data Mapping Document"),
            "dq_engineer": ("DQS", "Data Quality Specification"),
            "story_writer": ("Stories", "User Stories"),
            "sync_agent": ("Package", "Data Engineering Delivery Package"),
        }

        artifact_code, artifact_name = artifact_types.get(
            agent_name, ("Artifact", "Artifact")
        )

        # Get business request
        message = f"## Business Request\n\n{self.session.request_content}\n"

        # Add context from previous artifacts
        if context:
            message += "\n## Context from Previous Agents\n\n"
            for artifact_type, content in context.items():
                message += f"### {artifact_type.upper()}\n\n{content}\n\n"

        # Add critical instructions for artifact generation
        message += f"""
## YOUR TASK - IMPORTANT

You MUST generate a complete {artifact_name} ({artifact_code}) based on the business request above.

**CRITICAL INSTRUCTIONS:**
1. Use tools to explore the data FIRST (duckdb_tables, duckdb_schema, etc.)
2. Then generate the COMPLETE {artifact_code} document following your system prompt format
3. Your FINAL message must be the FULL {artifact_code} content - NOT a summary or question
4. Do NOT ask for confirmation or next steps - just generate the artifact
5. Do NOT wrap the output in code fences - output the raw content directly
6. The artifact should be comprehensive and follow the exact format in your system prompt

Generate the {artifact_code} now.
"""

        return message

    def _extract_artifact_from_conversation(
        self, agent_name: str, conversation: "Conversation"
    ) -> str:
        """Extract artifact content from SDK conversation.

        Uses the SDK's get_agent_final_response utility to extract
        the agent's final message from the conversation events.
        Also applies post-processing to clean the artifact content.

        If no finish call is found, falls back to searching for substantial
        message content that looks like an artifact.

        Args:
            agent_name: Name of the agent.
            conversation: SDK Conversation instance.

        Returns:
            Extracted and cleaned artifact content.
        """
        from openhands.sdk.conversation import get_agent_final_response

        # Get events from conversation state
        events = list(conversation.state.events)

        # Extract final response using SDK utility
        response = get_agent_final_response(events)

        # FALLBACK: If no finish call found, try to extract from message events
        if not response:
            logger.info(
                f"No finish call found for {agent_name}, trying fallback extraction"
            )
            response = self._extract_last_substantial_message(events, agent_name)

        if not response:
            logger.warning(
                f"No final response found in conversation for {agent_name}"
            )
            return f"[No artifact extracted from {agent_name}]"

        # Get artifact type for format-specific cleaning
        agent_info = get_agent_info(agent_name)
        artifact_type = agent_info.get("artifact_type", "")

        # Clean the response - remove code fence wrapping if present
        cleaned = self._clean_artifact_content(response, artifact_type=artifact_type)

        logger.info(
            f"Extracted artifact from {agent_name}",
            extra={"content_length": len(cleaned), "artifact_type": artifact_type},
        )

        return cleaned

    def _extract_last_substantial_message(
        self, events: list, agent_name: str
    ) -> str | None:
        """Fallback extraction: find the last substantial message from agent.

        Looks for MessageEvent or ActionEvent with long text content that looks
        like an artifact (markdown headers, CSV rows, or YAML structure).

        Args:
            events: List of conversation events.
            agent_name: Name of the agent (for artifact format lookup).

        Returns:
            Extracted content if found, None otherwise.
        """
        from openhands.sdk.event import ActionEvent, MessageEvent
        from openhands.sdk.llm.message import content_to_str

        agent_info = get_agent_info(agent_name)
        artifact_format = agent_info.get("artifact_format", "")

        # Patterns that indicate artifact content by format
        artifact_markers = {
            "markdown": ["# ", "## ", "### ", "**"],
            "csv": ["source_system,", ",source_table,", ",target_table,"],
            "yaml": ["version:", "metadata:", "rules:", "checks:"],
        }
        markers = artifact_markers.get(artifact_format, artifact_markers["markdown"])

        for event in reversed(events):
            content = ""
            if isinstance(event, MessageEvent) and event.source == "agent":
                text_parts = content_to_str(event.llm_message.content)
                content = "".join(text_parts) if text_parts else ""
            elif isinstance(event, ActionEvent) and event.source == "agent":
                # Check if action has thought content (agent's reasoning/output)
                if hasattr(event, "thought") and event.thought:
                    content = event.thought

            # Check if content looks like an artifact (>500 chars with markers)
            if content and len(content) > 500:
                for marker in markers:
                    if marker in content:
                        logger.info(
                            f"Fallback extraction found artifact for {agent_name}",
                            extra={"content_length": len(content), "marker": marker},
                        )
                        return content

        return None

    def _clean_artifact_content(self, content: str, artifact_type: str = "") -> str:
        """Clean artifact content by removing code fence wrappers and preamble text.

        Args:
            content: Raw content from the agent.
            artifact_type: Type of artifact (dmd, dqs, etc.) for format-specific cleaning.

        Returns:
            Cleaned content without code fence wrappers or preamble.
        """
        content = content.strip()

        # Remove code fence wrappers - handle various patterns
        fence_patterns = [
            "```markdown\n",
            "```markdown",
            "```yaml\n",
            "```yaml",
            "```yml\n",
            "```yml",
            "```csv\n",
            "```csv",
            "```\n",
            "```",
        ]

        for pattern in fence_patterns:
            if content.startswith(pattern):
                content = content[len(pattern):]
                break

        # Remove trailing fence
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # Handle leading 'yaml' or 'csv' text artifacts (from partial fence removal)
        if content.lower().startswith("yaml\n"):
            content = content[5:]
        elif content.lower().startswith("csv\n"):
            content = content[4:]

        # For CSV/DMD: Strip preamble text before the actual CSV header
        if artifact_type == "dmd" or (
            "source_system" in content.lower() and "," in content
        ):
            lines = content.split("\n")
            csv_start = 0
            for i, line in enumerate(lines):
                line_lower = line.lower().strip()
                # Look for the CSV header line
                if line_lower.startswith("source_system,") or (
                    "source_system" in line_lower and line.count(",") >= 5
                ):
                    csv_start = i
                    break
            if csv_start > 0:
                content = "\n".join(lines[csv_start:])
                logger.debug(f"Stripped {csv_start} preamble lines from CSV content")

        # For YAML/DQS: Ensure content starts with valid YAML
        if artifact_type == "dqs" or content.strip().startswith("version:"):
            lines = content.split("\n")
            yaml_start = 0
            for i, line in enumerate(lines):
                stripped = line.strip()
                # Look for YAML starting key
                if stripped.startswith("version:") or stripped.startswith("metadata:"):
                    yaml_start = i
                    break
            if yaml_start > 0:
                content = "\n".join(lines[yaml_start:])
                logger.debug(f"Stripped {yaml_start} preamble lines from YAML content")

        return content.strip()

    async def _execute_agent_legacy(self, agent_name: str) -> PWIAgentResult:
        """Execute agent using legacy custom agent system.

        DEPRECATED: Legacy agent system has been removed.
        Use runtime_mode="sdk" instead.

        Args:
            agent_name: Name of the agent to execute.

        Raises:
            NotImplementedError: Legacy mode is no longer supported.
        """
        raise NotImplementedError(
            "Legacy agent execution mode is no longer supported. "
            "The custom BasePWIAgent classes have been removed. "
            "Please use runtime_mode='sdk' instead, which uses the "
            "OpenHands SDK with microagent-based prompts. "
            f"To run agent '{agent_name}' with SDK mode, set "
            "runtime_mode='sdk' in the controller configuration."
        )

    async def _handle_review_gate(self, agent_name: str) -> bool:
        """Handle review gate after agent completes.

        Args:
            agent_name: Name of the agent whose output needs review.

        Returns:
            True if approved, False if rejected.
        """
        # Get the artifact type from agent info (without instantiating)
        agent_info = get_agent_info(agent_name)
        artifact_type = agent_info["artifact_type"]
        artifact = self.session.get_artifact(artifact_type)

        if not artifact:
            logger.warning(f"No artifact found for {agent_name}, auto-approving")
            return True

        # Perform review
        result = await self.review_handler.review(
            session=self.session,
            agent_name=agent_name,
            artifact=artifact,
        )

        # Handle edited content
        if result.approved and result.edited_content:
            self.session.add_artifact(
                artifact_type=artifact_type,
                content=result.edited_content,
                format=artifact.format,
                agent=agent_name,
            )
            self.session_manager.save(self.session)

        return result.approved

    def _save_artifact(self, agent_name: str, result: PWIAgentResult) -> None:
        """Save agent result as an artifact.

        Args:
            agent_name: Name of the agent.
            result: Agent execution result.
        """
        if not result.success or not result.artifact_content:
            return

        self.session_adapter.emit_artifact_generated(
            agent_name=agent_name,
            artifact_type=result.artifact_type or agent_name,
            artifact_format=result.artifact_format,
            content=result.artifact_content,
        )

    async def _validate_artifact(
        self, agent_name: str, result: PWIAgentResult
    ) -> tuple[bool, list[str]]:
        """Validate artifact against template requirements.

        Performs automatic validation after agent execution to catch
        format issues before the next agent runs.

        Args:
            agent_name: Name of the agent.
            result: Agent execution result.

        Returns:
            Tuple of (is_valid, list_of_issues).
        """
        if not result.success or not result.artifact_content:
            return True, []  # Nothing to validate

        if not result.artifact_type:
            return True, []  # No artifact type to validate against

        # Use ValidateArtifactTool executor directly
        executor = ValidateArtifactExecutor()
        action = ValidateArtifactAction(
            artifact_type=result.artifact_type,
            content=result.artifact_content,
        )
        observation = executor(action)

        if not observation.valid:
            logger.warning(
                f"Artifact validation failed for {agent_name}",
                extra={"issues": observation.issues, "artifact_type": result.artifact_type},
            )

        return observation.valid, observation.issues

    async def _run_validator_agent(
        self, agent_name: str, result: PWIAgentResult
    ) -> tuple[str, list[str]]:
        """Run ValidatorAgent to comprehensively validate an artifact.

        Uses LLM reasoning to validate format, content quality, and
        cross-references with previous artifacts.

        Args:
            agent_name: Name of the agent whose output is being validated.
            result: Agent execution result containing the artifact.

        Returns:
            Tuple of (validation_status, list_of_issues) where status is
            'PASS', 'WARN', or 'FAIL'.
        """
        if not result.success or not result.artifact_content:
            return "PASS", []  # Nothing to validate

        if not result.artifact_type:
            return "PASS", []  # No artifact type to validate

        # Get LLM config for validator agent
        agent_config = self.config.get_agent_config("validator_agent")
        resolved_model = self.config.get_resolved_model("validator_agent")

        llm_config = {
            "model": resolved_model,
            "temperature": 0.3,  # Lower temperature for consistent validation
            "max_tokens": agent_config.max_tokens,
        }

        try:
            # Create validator agent
            validator = create_pwi_agent("validator_agent", llm_config=llm_config)

            conversation = create_pwi_conversation(
                agent=validator,
                workspace=self.workspace_path,
            )

            # Build validation message with context (file-based support)
            context = {}
            for atype, artifact in self.session.artifacts.items():
                content = self.session.read_artifact_content(
                    self.session_manager.session_dir, atype
                )
                if content:
                    context[atype] = content
                elif artifact.content:
                    context[atype] = artifact.content

            message = f"""## Validation Task

Validate the following {result.artifact_type.upper()} artifact produced by {agent_name}:

### Artifact to Validate ({result.artifact_type.upper()})
{result.artifact_content}

### Previous Artifacts (for cross-reference)
"""
            for atype, content in context.items():
                if atype != result.artifact_type:
                    # Include summary of previous artifacts, not full content
                    preview = content[:500] + "..." if len(content) > 500 else content
                    message += f"\n#### {atype.upper()} (preview)\n{preview}\n"

            message += """

Perform comprehensive validation and output a validation report.
"""

            # Run validation
            conversation.send_message(message)
            conversation.run()

            # Extract validation result
            from openhands.sdk.conversation import get_agent_final_response

            events = list(conversation.state.events)
            response = get_agent_final_response(events) or ""

            # Parse validation result
            status = "PASS"
            issues = []

            if "VALIDATION_RESULT: FAIL" in response:
                status = "FAIL"
            elif "VALIDATION_RESULT: WARN" in response:
                status = "WARN"

            # Extract issues from the response
            for line in response.split("\n"):
                line = line.strip()
                if line.startswith("- ") and any(
                    word in line.lower()
                    for word in ["issue", "missing", "error", "fail", "warn", "invalid"]
                ):
                    issues.append(line[2:])  # Remove "- " prefix

            # Cleanup
            conversation.close()

            logger.info(
                f"ValidatorAgent completed for {agent_name}",
                extra={"status": status, "issue_count": len(issues)},
            )

            return status, issues

        except Exception as e:
            logger.exception(f"ValidatorAgent failed for {agent_name}")
            # Fall back to basic validation on error
            is_valid, basic_issues = await self._validate_artifact(agent_name, result)
            return "PASS" if is_valid else "WARN", basic_issues

    def _export_artifacts(self) -> None:
        """Export all artifacts to the output directory."""
        output_dir = self.config.project.output_dir / self.session.session_id
        output_dir.mkdir(parents=True, exist_ok=True)

        artifact_extensions = {
            "drd": "md",
            "pad": "md",
            "dmd": "csv",
            "dqs": "yaml",
            "stories": "md",
            "package": "md",
        }

        for artifact_type, artifact in self.session.artifacts.items():
            # Read content from file if file-based, otherwise use inline
            content = self.session.read_artifact_content(
                self.session_manager.session_dir, artifact_type
            )
            if not content:
                content = artifact.content  # Fallback to inline

            if not content:
                logger.warning(f"No content found for artifact: {artifact_type}")
                continue

            ext = artifact_extensions.get(artifact_type, "txt")
            filename = output_dir / f"{artifact_type}.{ext}"
            filename.write_text(content, encoding="utf-8")

            self.session_adapter.emit_artifact_saved(
                artifact_type=artifact_type,
                file_path=str(filename),
            )

            logger.info(f"Exported artifact: {filename}")

        console.print(f"\n[dim]Artifacts exported to: {output_dir}[/dim]")

    async def run(self, resume_from: str | None = None) -> bool:
        """Run the full workflow.

        Executes all agents in sequence with review gates.

        Args:
            resume_from: Optional agent name to resume from.

        Returns:
            True if workflow completed successfully.
        """
        self._is_running = True

        # Emit start or resume event
        if resume_from is None:
            self.session_adapter.emit_workflow_started()
            console.print(f"[dim]Workflow started for session: {self.session.session_id}[/dim]\n")
        else:
            resume_event = WorkflowResumedEvent(
                session_id=self.session.session_id,
                resumed_from=resume_from,
            )
            self.event_stream.append(resume_event)
            console.print(f"[dim]Resuming workflow from: {resume_from}[/dim]\n")

        # Determine which agents to run
        if resume_from:
            try:
                start_idx = AGENT_SEQUENCE.index(resume_from)
                agents_to_run = AGENT_SEQUENCE[start_idx:]
            except ValueError:
                logger.error(f"Unknown agent: {resume_from}")
                self._is_running = False
                return False
        else:
            agents_to_run = AGENT_SEQUENCE

        # Execute agents with progress display
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            for agent_name in agents_to_run:
                task = progress.add_task(
                    f"Running {agent_name.replace('_', ' ').title()}...",
                    total=None,
                )

                try:
                    # Retry loop with validation feedback
                    max_retries = 2  # Number of retries after initial attempt
                    retry_count = 0
                    validation_feedback: str | None = None

                    while True:
                        # Execute agent (with feedback on retry)
                        if retry_count > 0:
                            progress.update(
                                task,
                                description=f"Retrying {agent_name.replace('_', ' ').title()} ({retry_count}/{max_retries})...",
                            )
                        result = await self._execute_agent(agent_name, validation_feedback)

                        if not result.success:
                            progress.update(
                                task,
                                description=f"[red]✗ {agent_name} failed: {result.error_message}[/red]",
                            )
                            self.session_adapter.emit_workflow_failed(
                                error_message=result.error_message or "Unknown error",
                                failed_at_agent=agent_name,
                            )
                            self._is_running = False
                            return False

                        # Run ValidatorAgent for comprehensive validation
                        progress.update(
                            task,
                            description=f"Validating {agent_name.replace('_', ' ').title()}...",
                        )
                        validation_status, validation_issues = await self._run_validator_agent(
                            agent_name, result
                        )

                        # If validation passed or we've exhausted retries, break
                        if validation_status == "PASS":
                            break
                        if retry_count >= max_retries:
                            break

                        # Validation failed - prepare feedback for retry
                        console.print(
                            f"\n[yellow]⚠ Validation issues for {agent_name} (retry {retry_count + 1}/{max_retries}):[/yellow]"
                        )
                        for issue in validation_issues:
                            console.print(f"  [dim]- {issue}[/dim]")
                        console.print()

                        # Build feedback message for retry
                        validation_feedback = f"""Validation Status: {validation_status}

Issues found:
"""
                        for issue in validation_issues:
                            validation_feedback += f"- {issue}\n"

                        retry_count += 1

                    # Display final validation results
                    if validation_status == "FAIL":
                        console.print(
                            f"\n[red]✗ Validation FAILED for {agent_name} after {retry_count} retries:[/red]"
                        )
                        for issue in validation_issues:
                            console.print(f"  [red]- {issue}[/red]")
                        console.print()

                        # In strict mode, stop workflow on FAIL
                        if self.strict_validation:
                            self.session_adapter.emit_workflow_failed(
                                error_message=f"Validation failed for {agent_name}",
                                failed_at_agent=agent_name,
                            )
                            self._is_running = False
                            return False

                    elif validation_status == "WARN":
                        if retry_count > 0:
                            console.print(
                                f"\n[yellow]⚠ Validation warnings remain for {agent_name} after {retry_count} retries:[/yellow]"
                            )
                        else:
                            console.print(
                                f"\n[yellow]⚠ Validation warnings for {agent_name}:[/yellow]"
                            )
                        for issue in validation_issues:
                            console.print(f"  [dim]- {issue}[/dim]")
                        console.print()
                    elif retry_count > 0:
                        # PASS after retries
                        console.print(
                            f"\n[green]✓ Validation passed for {agent_name} after {retry_count} retry(ies)[/green]\n"
                        )

                    # Save artifact (even with validation warnings)
                    self._save_artifact(agent_name, result)

                    # Update progress with validation status
                    if validation_status == "PASS":
                        progress.update(
                            task,
                            description=f"[green]✓ {agent_name.replace('_', ' ').title()} complete[/green]",
                        )
                    elif validation_status == "WARN":
                        progress.update(
                            task,
                            description=f"[yellow]✓ {agent_name.replace('_', ' ').title()} complete (with warnings)[/yellow]",
                        )
                    else:  # FAIL but not strict mode
                        progress.update(
                            task,
                            description=f"[red]✓ {agent_name.replace('_', ' ').title()} complete (validation failed)[/red]",
                        )

                    # Callback if provided
                    if self.on_agent_complete:
                        self.on_agent_complete(agent_name, result)

                except Exception as e:
                    logger.exception(f"Error executing {agent_name}")
                    progress.update(
                        task,
                        description=f"[red]✗ {agent_name} error: {e}[/red]",
                    )
                    self.session_adapter.emit_workflow_failed(
                        error_message=str(e),
                        failed_at_agent=agent_name,
                    )
                    self._is_running = False
                    return False

                # Handle review gate
                progress.remove_task(task)
                approved = await self._handle_review_gate(agent_name)

                if not approved:
                    console.print(f"[yellow]Review rejected for {agent_name}[/yellow]")
                    self.session_adapter.emit_workflow_paused(
                        pause_reason="review_rejected",
                        resume_from=agent_name,
                    )
                    self._is_running = False
                    return False

        # Workflow completed
        self.session_adapter.emit_workflow_completed(
            total_tokens=self.session.get_total_tokens(),
            total_cost_usd=float(self.session.get_total_cost() or 0),
        )

        # Export artifacts
        self._export_artifacts()

        self._is_running = False
        return True

    def get_current_state(self) -> dict[str, Any]:
        """Get the current workflow state.

        Returns:
            Dictionary with current state information.
        """
        completed = self.session_adapter.get_completed_agents()
        pending_review = self.session_adapter.get_pending_review_agent()

        return {
            "session_id": self.session.session_id,
            "status": self.session.current_state,
            "is_running": self._is_running,
            "current_agent": self._current_agent,
            "completed_agents": completed,
            "pending_review_agent": pending_review,
            "artifact_count": len(self.session.artifacts),
            "event_count": len(self.event_stream),
        }

    def get_event_history(self) -> list[dict[str, Any]]:
        """Get the event history for this workflow.

        Returns:
            List of event dictionaries.
        """
        return self.session_adapter.get_event_history()
