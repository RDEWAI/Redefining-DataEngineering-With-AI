"""Workflow controller for OpenHands-based PWI.

This module provides the main orchestration layer that:
- Manages sequential agent execution
- Handles review gates via EventStream
- Integrates with session persistence
- Exports artifacts to output directory
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from pwi.openhands.agents import (
    AGENT_SEQUENCE,
    PWIAgentConfig,
    PWIAgentResult,
    PWIAgentState,
    get_agent,
    get_agent_info,
)
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
from pwi.openhands.workflow.session_adapter import SessionEventAdapter
from pwi.utils.logging import get_logger

if TYPE_CHECKING:
    from pwi.config.schema import PWIConfig
    from pwi.llm.client import LLMClient
    from pwi.workflow.session import Session, SessionManager

logger = get_logger("openhands.workflow.controller")
console = Console()


class PWIWorkflowController:
    """OpenHands-based workflow controller for PWI.

    This controller manages the execution of PWI agents using the
    OpenHands SDK patterns with event-sourced state management.
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
        on_agent_complete: Callable[[str, PWIAgentResult], None] | None = None,
    ) -> None:
        """Initialize the workflow controller.

        Args:
            session: Current workflow session.
            session_manager: Session persistence manager.
            config: PWI configuration.
            llm_client: LLM client for agent calls.
            auto_approve: Auto-approve all review gates.
            skip_review: Skip all review gates entirely.
            review_mode: Review mode ('cli', 'file', 'auto', 'skip').
            on_agent_complete: Optional callback when agent completes.
        """
        self.session = session
        self.session_manager = session_manager
        self.config = config
        self.llm_client = llm_client
        self.auto_approve = auto_approve
        self.skip_review = skip_review
        self.review_mode = review_mode
        self.on_agent_complete = on_agent_complete

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
        return PWIAgentState(
            session_id=self.session.session_id,
            business_request=self.session.request_content,
            artifacts={
                atype: artifact.content
                for atype, artifact in self.session.artifacts.items()
            },
        )

    async def _execute_agent(self, agent_name: str) -> PWIAgentResult:
        """Execute a single agent.

        Args:
            agent_name: Name of the agent to execute.

        Returns:
            Agent execution result.
        """
        self._current_agent = agent_name

        # Emit start event
        config = self._create_agent_config(agent_name)
        agent = get_agent(agent_name, config, self.llm_client)

        start_event = AgentStartedEvent(
            session_id=self.session.session_id,
            agent_name=agent_name,
            model=config.model,
            tool_count=len(agent.tools),
        )
        self.event_stream.append(start_event)

        logger.info(f"Starting agent {agent_name} with model {config.model}")

        # Create initial state
        state = self._create_agent_state(agent_name)

        # Subscribe to tool calls for event emission
        original_execute_tool = agent.execute_tool

        def tracked_execute_tool(tool_name: str, arguments: dict) -> dict:
            # Emit tool call event
            call_event = AgentToolCallEvent(
                session_id=self.session.session_id,
                agent_name=agent_name,
                tool_name=tool_name,
                arguments=arguments,
            )
            self.event_stream.append(call_event)

            # Execute tool
            result = original_execute_tool(tool_name, arguments)

            # Emit tool result event
            result_event = AgentToolResultEvent(
                session_id=self.session.session_id,
                agent_name=agent_name,
                tool_name=tool_name,
                success=result.get("success", False),
                result=result,
            )
            self.event_stream.append(result_event)

            return result

        agent.execute_tool = tracked_execute_tool

        # Run agent to completion
        result = await agent.run(state)

        # Emit completion or failure event
        if result.success:
            self.session_adapter.emit_agent_completed(
                agent_name=agent_name,
                artifact_type=result.artifact_type or "",
                artifact_format=result.artifact_format,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                tool_calls_count=len(result.tool_calls),
                model=config.model,
            )
        else:
            fail_event = AgentFailedEvent(
                session_id=self.session.session_id,
                agent_name=agent_name,
                error_message=result.error_message or "Unknown error",
            )
            self.event_stream.append(fail_event)

        self._current_agent = None
        return result

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
            ext = artifact_extensions.get(artifact_type, "txt")
            filename = output_dir / f"{artifact_type}.{ext}"
            filename.write_text(artifact.content, encoding="utf-8")

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
                    # Execute agent
                    result = await self._execute_agent(agent_name)

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

                    # Save artifact
                    self._save_artifact(agent_name, result)

                    progress.update(
                        task,
                        description=f"[green]✓ {agent_name.replace('_', ' ').title()} complete[/green]",
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
