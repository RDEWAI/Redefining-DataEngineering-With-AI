"""Plan command for Planning with Intent.

This module provides the `pwi plan` command for running
planning workflows on business requests.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pwi.config.loader import load_config
from pwi.openhands.agents import AGENT_SEQUENCE
from pwi.workflow.session import Session, SessionManager
from pwi.workflow.states import WorkflowState

if TYPE_CHECKING:
    from pwi.config.schema import PWIConfig

app = typer.Typer(help="Run planning workflow on a request")
console = Console()


@app.command("run")
def run_plan(
    request_path: Path = typer.Argument(
        ...,
        help="Path to the business request markdown file",
        exists=True,
        readable=True,
    ),
    config_path: Path = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
    ),
    auto_approve: bool = typer.Option(
        False,
        "--auto-approve",
        "-y",
        help="Automatically approve all review gates",
    ),
    skip_review: bool = typer.Option(
        False,
        "--skip-review",
        help="Skip all review gates (not recommended)",
    ),
) -> None:
    """Run the planning workflow on a business request.

    This executes the full agent pipeline:
    1. Data Analyst → DRD
    2. Data Architect → PAD
    3. Mapping Engineer → DMD
    4. DQ Engineer → DQS
    5. Story Writer → Stories
    6. Sync Agent → Final Package
    """
    # Load configuration
    try:
        config = load_config(config_path)
    except Exception as e:
        console.print(f"[red]Failed to load configuration: {e}[/red]")
        raise typer.Exit(1)

    # Check for API key and base URL
    if not config.llm.api_key:
        console.print(
            "[red]No API key configured![/red]\n"
            "Set LLM_API_KEY environment variable or update pwi.yaml"
        )
        raise typer.Exit(1)

    if not config.llm.base_url:
        console.print(
            "[red]No LLM base URL configured![/red]\n"
            "Set LLM_BASE_URL environment variable or update pwi.yaml"
        )
        raise typer.Exit(1)

    # Read request content
    request_content = request_path.read_text(encoding="utf-8")

    # Create session
    config.ensure_directories()
    session_manager = SessionManager(config.project.session_dir)
    session = session_manager.create(
        project_name=config.project.name,
        request_path=str(request_path),
        request_content=request_content,
    )

    console.print(
        Panel.fit(
            f"[bold blue]Starting PWI Workflow (OpenHands)[/bold blue]\n\n"
            f"[dim]Session ID:[/dim] {session.session_id}\n"
            f"[dim]Request:[/dim] {request_path.name}\n"
            f"[dim]Project:[/dim] {config.project.name}\n"
            f"[dim]Mode:[/dim] [green]OpenHands SDK (with tool-use)[/green]",
            title="PWI Plan",
        )
    )

    # Show agent pipeline with tools info
    table = Table(title="Agent Pipeline (OpenHands)", show_header=True)
    table.add_column("Agent", style="cyan")
    table.add_column("Output", style="green")
    table.add_column("Tools", style="magenta")
    table.add_column("Status", style="yellow")

    agent_outputs = {
        "data_analyst": "DRD (Data Requirements)",
        "data_architect": "PAD (Pipeline Architecture)",
        "mapping_engineer": "DMD (Data Mappings)",
        "dq_engineer": "DQS (Data Quality Spec)",
        "story_writer": "Epics & Stories",
        "sync_agent": "Final Package",
    }

    agent_tools = {
        "data_analyst": "DuckDB, CSV",
        "data_architect": "Schema, Validate",
        "mapping_engineer": "CSV, Metadata",
        "dq_engineer": "DuckDB, Validate",
        "story_writer": "Artifact",
        "sync_agent": "All",
    }

    for agent in AGENT_SEQUENCE:
        table.add_row(
            agent.replace("_", " ").title(),
            agent_outputs[agent],
            agent_tools.get(agent, "-"),
            "Pending",
        )

    console.print(table)
    console.print()

    # Run the workflow
    try:
        asyncio.run(
            _run_workflow(
                session=session,
                session_manager=session_manager,
                config=config,
                auto_approve=auto_approve,
                skip_review=skip_review,
            )
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Workflow interrupted. Session saved.[/yellow]")
        session.set_state(WorkflowState.PAUSED)
        session_manager.save(session)
        console.print(f"Resume with: pwi session resume {session.session_id}")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"\n[red]Workflow failed: {e}[/red]")
        session.set_state(WorkflowState.FAILED)
        session.error_message = str(e)
        session_manager.save(session)
        raise typer.Exit(1)

    # Show completion summary
    if session.is_complete():
        console.print(
            Panel.fit(
                f"[bold green]Workflow Complete![/bold green]\n\n"
                f"[dim]Session:[/dim] {session.session_id}\n"
                f"[dim]Artifacts:[/dim] {len(session.artifacts)}\n"
                f"[dim]Total Tokens:[/dim] {session.get_total_tokens():,}\n"
                f"[dim]Estimated Cost:[/dim] {session.get_formatted_cost()}\n"
                f"[dim]Output:[/dim] {config.project.output_dir}",
                title="Success",
            )
        )


async def _run_workflow(
    session: Session,
    session_manager: SessionManager,
    config: PWIConfig,
    auto_approve: bool,
    skip_review: bool,
) -> None:
    """Run the workflow asynchronously using OpenHands SDK.

    Executes all agents in sequence using the OpenHands workflow controller
    with tool-use capabilities for external system integration.
    """
    from pwi.llm.client import LLMClient
    from pwi.openhands.workflow.controller import PWIWorkflowController

    # Initialize LLM client
    llm_client = LLMClient(
        api_key=config.llm.api_key,
        base_url=config.llm.base_url,
        default_model=config.llm.default_model,
    )

    try:
        # Initialize OpenHands workflow controller
        controller = PWIWorkflowController(
            session=session,
            session_manager=session_manager,
            config=config,
            llm_client=llm_client,
            auto_approve=auto_approve,
            skip_review=skip_review,
            review_mode=config.review.default_mode,
        )

        # Run the workflow
        success = await controller.run()

        if not success:
            console.print("\n[yellow]Workflow did not complete successfully.[/yellow]")
            console.print(
                f"Run 'pwi plan status {session.session_id}' to check session state."
            )

    finally:
        # Always close LLM client
        await llm_client.aclose()


@app.command("status")
def plan_status(
    session_id: str = typer.Argument(..., help="Session ID to check"),
) -> None:
    """Check the status of a planning session."""
    config = load_config()
    session_manager = SessionManager(config.project.session_dir)

    if not session_manager.exists(session_id):
        console.print(f"[red]Session not found: {session_id}[/red]")
        raise typer.Exit(1)

    session = session_manager.load(session_id)

    # Build status display
    state = session.get_state()
    state_color = {
        WorkflowState.COMPLETED: "green",
        WorkflowState.FAILED: "red",
        WorkflowState.CANCELLED: "yellow",
        WorkflowState.PAUSED: "yellow",
    }.get(state, "blue")

    console.print(
        Panel.fit(
            f"[bold]Session Status[/bold]\n\n"
            f"[dim]ID:[/dim] {session.session_id}\n"
            f"[dim]Project:[/dim] {session.project_name}\n"
            f"[dim]State:[/dim] [{state_color}]{state.value}[/{state_color}]\n"
            f"[dim]Created:[/dim] {session.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"[dim]Updated:[/dim] {session.updated_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"[dim]Artifacts:[/dim] {len(session.artifacts)}\n"
            f"[dim]Total Tokens:[/dim] {session.get_total_tokens():,}",
            title=f"Session {session_id}",
        )
    )

    if session.artifacts:
        table = Table(title="Artifacts", show_header=True)
        table.add_column("Type", style="cyan")
        table.add_column("Agent", style="green")
        table.add_column("Version", style="yellow")
        table.add_column("Format")

        for artifact_type, artifact in session.artifacts.items():
            table.add_row(
                artifact_type.upper(),
                artifact.agent,
                str(artifact.version),
                artifact.format,
            )

        console.print(table)

    if session.error_message:
        console.print(f"\n[red]Error: {session.error_message}[/red]")
