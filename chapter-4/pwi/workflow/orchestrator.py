"""Workflow orchestrator for Planning with Intent.

This module coordinates the execution of agents in sequence,
manages state transitions, and handles review gates.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from pwi.agents import (
    AgentConfig,
    DataAnalystAgent,
    DataArchitectAgent,
    DQEngineerAgent,
    MappingEngineerAgent,
    StoryWriterAgent,
    SyncAgent,
)
from pwi.agents.base import AgentResult, BaseAgent
from pwi.utils.logging import (
    get_logger,
    log_agent_complete,
    log_agent_error,
    log_agent_start,
    log_workflow_event,
)
from pwi.workflow.session import Session, SessionManager
from pwi.workflow.state_machine import PWIWorkflow
from pwi.workflow.states import AGENT_ORDER

if TYPE_CHECKING:
    from pwi.config.schema import PWIConfig
    from pwi.llm.client import LLMClient

logger = get_logger("orchestrator")
console = Console()


# Mapping from agent name to agent class
AGENT_CLASSES: dict[str, type[BaseAgent]] = {
    "data_analyst": DataAnalystAgent,
    "data_architect": DataArchitectAgent,
    "mapping_engineer": MappingEngineerAgent,
    "dq_engineer": DQEngineerAgent,
    "story_writer": StoryWriterAgent,
    "sync_agent": SyncAgent,
}

# Mapping from agent name to state machine trigger for completion
AGENT_COMPLETE_TRIGGERS: dict[str, str] = {
    "data_analyst": "analyst_complete",
    "data_architect": "architect_complete",
    "mapping_engineer": "mapping_complete",
    "dq_engineer": "dq_complete",
    "story_writer": "stories_complete",
    "sync_agent": "sync_complete",
}

# Mapping from agent name to state machine trigger for approval
AGENT_APPROVED_TRIGGERS: dict[str, str] = {
    "data_analyst": "analyst_approved",
    "data_architect": "architect_approved",
    "mapping_engineer": "mapping_approved",
    "dq_engineer": "dq_approved",
    "story_writer": "stories_approved",
    "sync_agent": "complete",  # Final completion
}


class WorkflowOrchestrator:
    """Orchestrates the PWI workflow execution.

    Coordinates agent execution, state transitions, and review gates.
    """

    def __init__(
        self,
        session: Session,
        session_manager: SessionManager,
        config: PWIConfig,
        llm_client: LLMClient,
        auto_approve: bool = False,
        skip_review: bool = False,
        on_agent_complete: Callable[[str, AgentResult], None] | None = None,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            session: Current workflow session.
            session_manager: Session persistence manager.
            config: PWI configuration.
            llm_client: LLM client for agent calls.
            auto_approve: Auto-approve all review gates.
            skip_review: Skip all review gates entirely.
            on_agent_complete: Optional callback when agent completes.
        """
        self.session = session
        self.session_manager = session_manager
        self.config = config
        self.llm_client = llm_client
        self.auto_approve = auto_approve
        self.skip_review = skip_review
        self.on_agent_complete = on_agent_complete

        # Initialize state machine
        self.workflow = PWIWorkflow(session, session_manager)

        # Get prompts directory
        self.prompts_dir = Path(__file__).parent.parent / "agents" / "prompts"

    def _create_agent(self, agent_name: str) -> BaseAgent:
        """Create an agent instance for the given agent name.

        Args:
            agent_name: Name of the agent to create.

        Returns:
            Configured agent instance.
        """
        agent_class = AGENT_CLASSES[agent_name]
        agent_config = self.config.get_agent_config(agent_name)

        # Resolve the model alias to actual model name
        resolved_model = self.config.get_resolved_model(agent_name)

        config = AgentConfig(
            name=agent_name,
            model=resolved_model,
            temperature=agent_config.temperature,
            max_tokens=agent_config.max_tokens,
        )

        return agent_class(
            config=config,
            llm_client=self.llm_client,
            prompts_dir=self.prompts_dir,
        )

    async def _execute_agent(self, agent_name: str) -> AgentResult:
        """Execute a single agent.

        Args:
            agent_name: Name of the agent to execute.

        Returns:
            Result from agent execution.
        """
        agent = self._create_agent(agent_name)
        result = await agent.execute(self.session)
        return result

    def _save_artifact(self, agent_name: str, result: AgentResult) -> None:
        """Save agent result as an artifact.

        Args:
            agent_name: Name of the agent that produced the artifact.
            result: Agent execution result.
        """
        if not result.success or not result.artifact_content:
            return

        self.session.add_artifact(
            artifact_type=result.artifact_type or agent_name,
            content=result.artifact_content,
            format=result.artifact_format,
            agent=agent_name,
        )
        self.session_manager.save(self.session)

    def _record_token_usage(self, agent_name: str, result: AgentResult) -> None:
        """Record token usage from agent execution.

        Args:
            agent_name: Name of the agent.
            result: Agent execution result.
        """
        if result.total_tokens > 0:
            self.session.add_token_usage(
                agent=agent_name,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                model=result.model,
            )
            self.session_manager.save(self.session)

    async def _handle_review_gate(self, agent_name: str) -> bool:
        """Handle the review gate after an agent completes.

        Args:
            agent_name: Name of the agent whose output needs review.

        Returns:
            True if approved, False if rejected.
        """
        if self.skip_review:
            return True

        if self.auto_approve:
            console.print(f"  [dim]Auto-approving {agent_name} output[/dim]")
            return True

        # Get review gate configuration
        review_config = self.config.review.get_gate_config(agent_name)
        if not review_config.enabled:
            return True

        # Get the artifact to review
        artifact_type = (
            AGENT_CLASSES[agent_name].ARTIFACT_TYPE
            if agent_name in AGENT_CLASSES
            else agent_name
        )
        artifact = self.session.get_artifact(artifact_type)

        if not artifact:
            logger.warning(f"No artifact found for {agent_name}, auto-approving")
            return True

        # Create appropriate review handler based on mode
        from pwi.review import BaseReviewHandler, CLIReviewHandler, FileReviewHandler

        handler: BaseReviewHandler
        if review_config.mode == "file":
            handler = FileReviewHandler(
                review_dir=self.config.project.output_dir / "review",
                timeout_minutes=self.config.review.timeout_minutes,
            )
        else:
            # Default to CLI mode
            handler = CLIReviewHandler(show_full_content=False)

        # Perform the review
        result = await handler.review(self.session, agent_name, artifact)

        # Record the review decision
        self.session.add_review(
            agent=agent_name,
            approved=result.approved,
            feedback=result.feedback,
        )
        self.session_manager.save(self.session)

        # Handle edited content (for file-based review)
        if result.approved and result.edited_content:
            self.session.add_artifact(
                artifact_type=artifact_type,
                content=result.edited_content,
                format=artifact.format,
                agent=agent_name,
            )
            self.session_manager.save(self.session)

        return result.approved

    async def run(self, resume_from: str | None = None) -> bool:
        """Run the full workflow.

        Executes all agents in sequence with review gates.

        Args:
            resume_from: Optional agent name to resume from.

        Returns:
            True if workflow completed successfully.
        """
        # Start the workflow if not resuming
        if resume_from is None:
            self.workflow.start()
            log_workflow_event(
                logger, self.session.session_id, "workflow_started",
                {"state": self.workflow.state}
            )
            console.print(f"[dim]Workflow started in state: {self.workflow.state}[/dim]\n")
        else:
            log_workflow_event(
                logger, self.session.session_id, "workflow_resumed",
                {"resume_from": resume_from}
            )
            console.print(f"[dim]Resuming workflow from: {resume_from}[/dim]\n")

        # Determine which agents to run
        if resume_from:
            start_idx = AGENT_ORDER.index(resume_from)
            agents_to_run = AGENT_ORDER[start_idx:]
        else:
            agents_to_run = AGENT_ORDER

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            for agent_name in agents_to_run:
                # Update progress
                task = progress.add_task(
                    f"Running {agent_name.replace('_', ' ').title()}...",
                    total=None,
                )

                try:
                    # Log agent start
                    log_agent_start(logger, agent_name, self.session.session_id)

                    # Execute agent
                    result = await self._execute_agent(agent_name)

                    # Record token usage
                    self._record_token_usage(agent_name, result)

                    if not result.success:
                        log_agent_error(
                            logger, agent_name, self.session.session_id,
                            result.error_message or "Unknown error"
                        )
                        progress.update(
                            task,
                            description=f"[red]✗ {agent_name} failed: {result.error_message}[/red]",
                        )
                        self.workflow.fail()
                        self.session.error_message = result.error_message
                        self.session_manager.save(self.session)
                        return False

                    # Save artifact
                    self._save_artifact(agent_name, result)

                    # Log agent completion
                    log_agent_complete(
                        logger, agent_name, self.session.session_id,
                        result.total_tokens,
                        getattr(result, "cost_usd", None)
                    )

                    # Trigger completion state
                    complete_trigger = AGENT_COMPLETE_TRIGGERS.get(agent_name)
                    if complete_trigger:
                        trigger_method = getattr(self.workflow, complete_trigger, None)
                        if trigger_method:
                            trigger_method()

                    progress.update(
                        task,
                        description=f"[green]✓ {agent_name.replace('_', ' ').title()} complete[/green]",
                    )

                    # Callback if provided
                    if self.on_agent_complete:
                        self.on_agent_complete(agent_name, result)

                except Exception as e:
                    log_agent_error(logger, agent_name, self.session.session_id, str(e))
                    logger.exception(f"Error executing {agent_name}")
                    progress.update(
                        task,
                        description=f"[red]✗ {agent_name} error: {e}[/red]",
                    )
                    self.workflow.fail()
                    self.session.error_message = str(e)
                    self.session_manager.save(self.session)
                    return False

                # Handle review gate
                progress.remove_task(task)
                approved = await self._handle_review_gate(agent_name)

                if not approved:
                    log_workflow_event(
                        logger, self.session.session_id, "review_rejected",
                        {"agent": agent_name}
                    )
                    console.print(f"[yellow]Review rejected for {agent_name}[/yellow]")
                    self.workflow.pause()
                    return False

                log_workflow_event(
                    logger, self.session.session_id, "review_approved",
                    {"agent": agent_name}
                )

                # Trigger approval state
                approved_trigger = AGENT_APPROVED_TRIGGERS.get(agent_name)
                if approved_trigger and approved_trigger != "complete":
                    trigger_method = getattr(self.workflow, approved_trigger, None)
                    if trigger_method:
                        trigger_method()

        # Workflow completed - sync_complete already transitions to COMPLETED state
        log_workflow_event(
            logger, self.session.session_id, "workflow_completed",
            {
                "total_tokens": self.session.get_total_tokens(),
                "total_cost": self.session.get_formatted_cost(),
                "artifact_count": len(self.session.artifacts),
            }
        )
        # Export artifacts to output directory
        self._export_artifacts()
        return True

    def _export_artifacts(self) -> None:
        """Export all artifacts to the output directory."""
        # Create session-specific output directory
        output_dir = self.config.project.output_dir / self.session.session_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Mapping from artifact type to file extension
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
            logger.info(f"Exported artifact: {filename}")

        console.print(f"\n[dim]Artifacts exported to: {output_dir}[/dim]")

    def get_current_state(self) -> str:
        """Get the current workflow state.

        Returns:
            Current state name.
        """
        return self.workflow.state
